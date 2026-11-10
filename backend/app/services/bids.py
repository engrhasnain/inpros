"""Bid evaluation: price every bidder against the contract catalog quantities and flag outliers."""

from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bid, CatalogItem

OUTLIER = 0.25  # a unit price more than 25 % away from the median of all bidders is flagged


def evaluate_bids(db: Session, project_id: int) -> dict:
    catalog = list(db.scalars(select(CatalogItem).where(CatalogItem.project_id == project_id).order_by(CatalogItem.row)))
    bids = list(db.scalars(select(Bid).where(Bid.project_id == project_id).order_by(Bid.bidder)))
    prices = {b.id: {ln.clave: ln.precio_unitario for ln in b.lines} for b in bids}
    cat_claves = {c.clave for c in catalog}

    items = []
    for c in catalog:
        row = {"clave": c.clave, "descripcion": c.descripcion, "unidad": c.unidad, "cantidad": c.cantidad,
               "budget_unit_price": c.precio_unitario, "bidders": {}}
        quoted = [prices[b.id][c.clave] for b in bids if c.clave in prices[b.id]]
        med = median(quoted) if quoted else None
        row["median_unit_price"] = med
        for b in bids:
            pu = prices[b.id].get(c.clave)
            flag = None
            if pu is None:
                flag = "missing"
            elif med and len(quoted) >= 3 and abs(pu - med) / med > OUTLIER:
                flag = "high" if pu > med else "low"
            row["bidders"][b.bidder] = {"unit_price": pu, "amount": round(pu * c.cantidad, 2) if pu is not None else None, "flag": flag}
        items.append(row)

    summary = []
    budget = round(sum(c.cantidad * c.precio_unitario for c in catalog), 2)
    for b in bids:
        total = round(sum(c.cantidad * prices[b.id][c.clave] for c in catalog if c.clave in prices[b.id]), 2)
        missing = [c.clave for c in catalog if c.clave not in prices[b.id]]
        extra = sorted(set(prices[b.id]) - cat_claves)
        flags = [it["clave"] for it in items if it["bidders"][b.bidder]["flag"] in ("high", "low")]
        summary.append({
            "bidder": b.bidder, "bid_id": b.id, "source_filename": b.source_filename,
            "total": total, "vs_budget": round(total - budget, 2),
            "vs_budget_pct": round((total - budget) / budget * 100, 1) if budget else None,
            "missing_items": missing, "extra_items": extra, "price_outliers": flags,
            "complete": not missing,
        })
    # rank complete bids by total; incomplete ones go last (they cannot be compared fairly)
    summary.sort(key=lambda s: (not s["complete"], s["total"]))
    for i, s in enumerate(summary, start=1):
        s["rank"] = i
    rec = next((s for s in summary if s["complete"]), None)
    return {
        "budget_total": budget,
        "bidders": summary,
        "items": items,
        "recommended": rec["bidder"] if rec else None,
        "recommendation_note": (
            f"{rec['bidder']} is the lowest complete bid"
            + (f", with {len(rec['price_outliers'])} unit price(s) to clarify before award." if rec["price_outliers"] else ".")
        ) if rec else "No complete bid yet: every bid misses at least one catalog item.",
    }
