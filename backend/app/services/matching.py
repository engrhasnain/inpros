"""Suggest which drawing quantity measures each catalog item.

Rule-based and transparent: unit must be compatible (count vs. length), then text similarity
between the catalog description and the drawing item (symbol, layer, description), helped by a
small Spanish/English construction vocabulary. A person confirms every link.
"""

import re
import unicodedata
from difflib import SequenceMatcher

COUNT_UNITS = {"pza", "pz", "pieza", "piezas", "pzas", "salida", "sal", "lote", "jgo", "juego", "eq", "equipo", "u", "un", "unidad"}
LENGTH_UNITS = {"m", "ml", "mts", "metro", "metros", "m lineal", "metro lineal"}

# words that mean the same thing in catalogs (Spanish) and drawings (layer/block names, English)
VOCAB = {
    "luminario": ["lam", "luminaire", "luminarios", "lumin"],
    "lampara": ["lam", "luminaire"],
    "tubo": ["tuberia", "tub", "conduit", "tubo"],
    "tuberia": ["tuberia", "tub", "conduit"],
    "conduit": ["tuberia", "conduit"],
    "charola": ["charola", "char", "tray"],
    "caja": ["ca", "caja", "junction box"],
    "registro": ["ca", "caja"],
    "tablero": ["tab", "tablero", "panel"],
    "motor": ["motor", "motores"],
    "alimentador": ["alim", "feeder", "motores"],
    "contacto": ["cont", "outlet", "contn"],
    "elevada": ["elevada", "elevated"],
    "voz": ["vd"],
    "datos": ["vd"],
    "normal": ["tubn", "normal"],
    "regulado": ["tubn", "regulated"],
}


def _token_hit(syn: str, tokens: list[str]) -> bool:
    """A synonym matches a whole word, the start of a word, or the end of a drawing code
    (e.g. 'vd' in '3erntubvd', 'tubn' in '3erntubn'), never a random middle substring."""
    if " " in syn:
        return syn in " ".join(tokens)
    return any(t == syn or t.startswith(syn) or (len(syn) >= 2 and t.endswith(syn) and any(c.isdigit() for c in t)) for t in tokens)


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def unit_kind(unidad: str) -> str | None:
    u = _norm(unidad)
    if u in COUNT_UNITS:
        return "count"
    if u in LENGTH_UNITS:
        return "length"
    return None


def _item_text(item: dict) -> str:
    parts = [item.get("description", ""), item.get("symbol") or "", item["layer"], item["drawing_name"]]
    return _norm(" ".join(parts))


def _type_token(text: str) -> str | None:
    """'tipo A' / 'type A' / 'LAM-A' -> 'a' (distinguishes luminaire types)."""
    m = re.search(r"\b(?:tipo|type)\s+([a-z0-9]{1,3})\b", text)
    if m:
        return m.group(1)
    m = re.search(r"\blam\s*([a-z0-9]{1,3})\b", text)
    return m.group(1) if m else None


def score(catalog_desc: str, catalog_unit: str, item: dict) -> float:
    kind = unit_kind(catalog_unit)
    if kind and kind != item["kind"]:
        return 0.0
    cat = _norm(catalog_desc)
    txt = _item_text(item)
    s = SequenceMatcher(None, cat, txt).ratio() * 0.4
    cat_words = set(cat.split())
    tokens = txt.split()
    hits = sum(
        1 for word, synonyms in VOCAB.items()
        if word in cat_words and any(_token_hit(syn, tokens) for syn in synonyms)
    )
    s += min(0.25 * hits, 0.6) + (0.2 if hits else 0.0)
    ct, it = _type_token(cat), _type_token(txt)
    if ct and it:
        s += 0.3 if ct == it else -0.4
    # a qualifier on the drawing item that the catalog line does not mention points to a different item
    # (each group lists the same qualifier in Spanish and English)
    for group in ({"elevada", "elevado", "elevated"},):
        if group & set(tokens) and not group & cat_words:
            s -= 0.25
    if item.get("symbol", "") and item["symbol"].startswith("A$C"):
        s -= 0.1  # unnamed copies are rarely what a catalog line means
    return max(0.0, min(s, 1.0))


def suggest(catalog_desc: str, catalog_unit: str, items: list[dict]) -> tuple[dict | None, float]:
    best, best_score = None, 0.0
    for it in items:
        sc = score(catalog_desc, catalog_unit, it)
        # prefer larger quantities when equal (main run over a stray fragment)
        if sc > best_score + 1e-9 or (abs(sc - best_score) < 1e-9 and best and it["quantity"] > best["quantity"]):
            best, best_score = it, sc
    return (best, best_score) if best_score >= 0.45 else (None, best_score)
