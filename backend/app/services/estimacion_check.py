"""Validate a contractor's estimación against the contract catalog, earlier approvals and the drawings."""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogItem, Estimacion, EstimacionStatus, FieldEntry
from app.services.project_data import item_index, project_takeoff

TOL = 1e-6


def _f(msg: str, severity: str, code: str) -> dict:
    return {"code": code, "severity": severity, "message": msg}


def check_estimacion(db: Session, est: Estimacion) -> dict:
    catalog = {c.clave: c for c in db.scalars(select(CatalogItem).where(CatalogItem.project_id == est.project_id))}
    takeoff = item_index(project_takeoff(db, est.project_id))

    # quantities approved in earlier estimaciones of this project
    previous: Counter[str] = Counter()
    earlier = db.scalars(
        select(Estimacion).where(
            Estimacion.project_id == est.project_id,
            Estimacion.numero < est.numero,
            Estimacion.status == EstimacionStatus.approved,
        )
    )
    for e in earlier:
        for ln in e.lines:
            previous[ln.clave] += ln.approved_quantity or 0.0

    # progress reported from site, per item (all dates)
    field: Counter[str] = Counter()
    for fe in db.scalars(select(FieldEntry).where(FieldEntry.project_id == est.project_id)):
        field[fe.clave] += fe.cantidad

    seen: Counter[str] = Counter()
    lines = []
    for ln in est.lines:
        findings: list[dict] = []
        seen[ln.clave] += 1
        cat: CatalogItem | None = catalog.get(ln.clave)
        prev = previous[ln.clave]
        cumulative = prev + ln.cantidad
        drawing_qty = None
        approvable = 0.0
        pu = cat.precio_unitario if cat else (ln.precio_unitario or 0.0)

        if cat is None:
            findings.append(_f("Line item code not in the contract catalog — cannot be paid without a change order.", "error", "NOT_IN_CONTRACT"))
        else:
            if ln.precio_unitario is not None and abs(ln.precio_unitario - cat.precio_unitario) > 0.005:
                findings.append(_f(
                    f"Unit price {ln.precio_unitario:,.2f} differs from contract {cat.precio_unitario:,.2f}; contract price used.",
                    "error", "PRICE_MISMATCH"))
            if ln.unidad and cat.unidad and ln.unidad.strip().lower() != cat.unidad.strip().lower():
                findings.append(_f(f"Unit '{ln.unidad}' differs from contract unit '{cat.unidad}'.", "warning", "UNIT_MISMATCH"))
            if ln.cantidad_anterior is not None and abs(ln.cantidad_anterior - prev) > TOL:
                findings.append(_f(
                    f"Contractor states {ln.cantidad_anterior:g} previously paid; approved records show {prev:g}.",
                    "warning", "PREVIOUS_MISMATCH"))

            remaining = max(0.0, cat.cantidad - prev)
            approvable = min(ln.cantidad, remaining)
            if cumulative > cat.cantidad + TOL:
                findings.append(_f(
                    f"Cumulative {cumulative:g} {cat.unidad} exceeds contracted {cat.cantidad:g}; only {remaining:g} remain.",
                    "error", "EXCEEDS_CONTRACT"))

            m = cat.mapping
            if m is None:
                findings.append(_f("No drawing quantity linked to this item — not verified against drawings.", "info", "NO_DRAWING_LINK"))
            else:
                item = takeoff.get((m.drawing_name, m.sheet, m.takeoff_key))
                if item is None:
                    findings.append(_f("Linked drawing item no longer exists in the latest drawing version.", "warning", "LINK_MISSING"))
                else:
                    drawing_qty = item["quantity"]
                    label = "confirmed" if m.confirmed else "suggested, not yet confirmed"
                    if cumulative > drawing_qty + TOL:
                        findings.append(_f(
                            f"Cumulative {cumulative:g} exceeds the {drawing_qty:g} measured on the drawings "
                            f"({m.drawing_name}, sheet {m.sheet}; link {label}).",
                            "warning", "EXCEEDS_DRAWING"))

        field_qty = field.get(ln.clave)
        if cat is not None and field_qty is not None and cumulative > field_qty + TOL:
            findings.append(_f(
                f"Cumulative {cumulative:g} is more than the {field_qty:g} reported installed on site.",
                "warning", "EXCEEDS_FIELD"))

        if seen[ln.clave] > 1:
            findings.append(_f("Same item code appears again in this estimación — counted once.", "error", "DUPLICATE_LINE"))
            approvable = 0.0
        else:
            # later duplicates take nothing; the first occurrence keeps its approvable amount
            pass

        if est.status == EstimacionStatus.approved and ln.approved_quantity is not None:
            approvable = ln.approved_quantity

        worst = "ok"
        for sev in ("info", "warning", "error"):
            if any(f["severity"] == sev for f in findings):
                worst = sev
        result = {"ok": "OK", "info": "Not verified", "warning": "Review", "error": "Adjusted"}[worst]
        claimed_pu = ln.precio_unitario if ln.precio_unitario is not None else pu
        lines.append({
            "id": ln.id,
            "row": ln.row,
            "clave": ln.clave,
            "descripcion": (cat.descripcion if cat else ln.descripcion) or "",
            "unidad": (cat.unidad if cat else ln.unidad) or "",
            "contract_unit_price": cat.precio_unitario if cat else None,
            "claimed_unit_price": claimed_pu,
            "claimed": ln.cantidad,
            "previous_approved": prev,
            "cumulative": cumulative,
            "contract_quantity": cat.cantidad if cat else None,
            "drawing_quantity": drawing_qty,
            "field_quantity": field_qty,
            "approvable": round(approvable, 4),
            "claimed_amount": round(ln.cantidad * (claimed_pu or 0.0), 2),
            "approvable_amount": round(approvable * (cat.precio_unitario if cat else 0.0), 2),
            "severity": worst,
            "result": result,
            "findings": findings,
        })

    totals = {
        "lines": len(lines),
        "claimed_amount": round(sum(x["claimed_amount"] for x in lines), 2),
        "approvable_amount": round(sum(x["approvable_amount"] for x in lines), 2),
        "errors": sum(1 for x in lines if x["severity"] == "error"),
        "warnings": sum(1 for x in lines if x["severity"] == "warning"),
        "not_verified": sum(1 for x in lines if x["severity"] == "info"),
        "ok": sum(1 for x in lines if x["severity"] == "ok"),
    }
    return {
        "id": est.id,
        "numero": est.numero,
        "periodo": est.periodo,
        "source_filename": est.source_filename,
        "status": est.status,
        "uploaded_at": est.uploaded_at.isoformat(),
        "approved_at": est.approved_at.isoformat() if est.approved_at else None,
        "totals": totals,
        "lines": lines,
    }
