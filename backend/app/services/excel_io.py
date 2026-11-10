"""Read contract catalogs and estimaciones from Excel, write the validated estimación.

Real spreadsheets differ in layout, so columns are found by header name (Spanish or English)
within the first 25 rows, not by position.
"""

import io
import re
import unicodedata
from dataclasses import dataclass

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


class ExcelFormatError(ValueError):
    pass


def _norm(text) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _number(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d.,\-]", "", str(value))
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(",", "")  # 1,250.00
    elif s.count(",") == 1 and len(s.split(",")[1]) != 3:
        s = s.replace(",", ".")  # 1250,5
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# column -> header phrases (normalised); first match wins, longer phrases are tried first
CATALOG_COLUMNS = {
    "clave": ["clave", "codigo", "code", "concepto clave", "no concepto"],
    "descripcion": ["descripcion", "concepto", "description", "descripcion del concepto"],
    "unidad": ["unidad", "unit", "u m", "um", "u"],
    "cantidad": ["cantidad contratada", "cantidad", "cant", "qty", "quantity"],
    "precio_unitario": ["precio unitario", "p u", "pu", "precio", "unit price"],
    "partida": ["partida", "capitulo", "seccion", "section"],
}
ESTIMACION_COLUMNS = {
    "clave": CATALOG_COLUMNS["clave"],
    "descripcion": CATALOG_COLUMNS["descripcion"],
    "unidad": CATALOG_COLUMNS["unidad"],
    "cantidad": [
        "cantidad esta estimacion", "esta estimacion", "cantidad estimada", "cantidad del periodo",
        "cantidad periodo", "cantidad", "qty this period", "qty",
    ],
    "cantidad_anterior": ["cantidad anterior", "estimado anterior", "acumulado anterior", "anterior"],
    "precio_unitario": CATALOG_COLUMNS["precio_unitario"],
}
BID_COLUMNS = {
    "clave": CATALOG_COLUMNS["clave"],
    "precio_unitario": CATALOG_COLUMNS["precio_unitario"],
}
FIELD_COLUMNS = {
    "fecha": ["fecha", "date", "dia"],
    "clave": CATALOG_COLUMNS["clave"],
    "cantidad": ["cantidad instalada", "cantidad ejecutada", "avance", "cantidad", "qty", "quantity"],
    "zona": ["zona", "frente", "area", "zone", "eje"],
    "nota": ["nota", "observaciones", "comentario", "note", "notes"],
    "reportado_por": ["reportado por", "residente", "supervisor", "reported by"],
}
REQUIRED = {"catalog": ["clave", "descripcion", "unidad", "cantidad", "precio_unitario"],
            "estimacion": ["clave", "cantidad"],
            "bid": ["clave", "precio_unitario"],
            "field": ["fecha", "clave", "cantidad"]}
COLUMNS = {"catalog": CATALOG_COLUMNS, "estimacion": ESTIMACION_COLUMNS, "bid": BID_COLUMNS, "field": FIELD_COLUMNS}
QTY_FIELD = {"catalog": "cantidad", "estimacion": "cantidad", "bid": "precio_unitario", "field": "cantidad"}


def _find_header(ws, columns: dict[str, list[str]], required: list[str]) -> tuple[int, dict[str, int]]:
    for r, row in enumerate(ws.iter_rows(min_row=1, max_row=25, values_only=True), start=1):
        cells = [_norm(c) for c in row]
        found: dict[str, int] = {}
        for field, phrases in columns.items():
            for phrase in sorted(phrases, key=len, reverse=True):
                for idx, cell in enumerate(cells):
                    if idx in found.values():
                        continue
                    if cell == phrase or (len(phrase) > 3 and cell.startswith(phrase)):
                        found[field] = idx
                        break
                if field in found:
                    break
        if all(f in found for f in required):
            return r, found
    raise ExcelFormatError(
        "Could not find the header row. Expected columns: " + ", ".join(required) + " (Spanish or English names)."
    )


@dataclass
class Row:
    row: int
    values: dict


def _read(content: bytes, kind: str) -> list[Row]:
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:  # openpyxl raises several types
        raise ExcelFormatError(f"Not a readable .xlsx file: {exc}") from exc
    columns = COLUMNS[kind]
    last_error: Exception | None = None
    for ws in wb.worksheets:
        try:
            header_row, cols = _find_header(ws, columns, REQUIRED[kind])
        except ExcelFormatError as exc:
            last_error = exc
            continue
        rows = []
        for r, raw in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
            vals = {f: (raw[i] if i < len(raw) else None) for f, i in cols.items()}
            clave = str(vals.get("clave") or "").strip()
            if not clave or _number(vals.get(QTY_FIELD[kind])) is None:
                continue  # blank, subtotal or section rows
            rows.append(Row(row=r, values=vals))
        if rows:
            return rows
    raise last_error or ExcelFormatError("No data rows found.")


def read_catalog(content: bytes) -> list[dict]:
    out = []
    for r in _read(content, "catalog"):
        v = r.values
        pu = _number(v.get("precio_unitario"))
        out.append({
            "row": r.row,
            "clave": str(v["clave"]).strip(),
            "descripcion": " ".join(str(v.get("descripcion") or "").split()),
            "unidad": str(v.get("unidad") or "").strip(),
            "cantidad": _number(v["cantidad"]) or 0.0,
            "precio_unitario": pu or 0.0,
            "partida": (str(v["partida"]).strip() if v.get("partida") else None),
        })
    return out


def read_estimacion(content: bytes) -> list[dict]:
    out = []
    for r in _read(content, "estimacion"):
        v = r.values
        out.append({
            "row": r.row,
            "clave": str(v["clave"]).strip(),
            "descripcion": " ".join(str(v.get("descripcion") or "").split()) or None,
            "unidad": (str(v["unidad"]).strip() if v.get("unidad") else None),
            "cantidad": _number(v["cantidad"]) or 0.0,
            "cantidad_anterior": _number(v.get("cantidad_anterior")),
            "precio_unitario": _number(v.get("precio_unitario")),
        })
    return out


def read_bid(content: bytes) -> list[dict]:
    out = []
    for r in _read(content, "bid"):
        out.append({"clave": str(r.values["clave"]).strip(), "precio_unitario": _number(r.values["precio_unitario"]) or 0.0})
    return out


def _date(value) -> str | None:
    from datetime import date, datetime

    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value or "").strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)  # dd/mm/yyyy (Mexico)
    if m:
        return f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def read_field(content: bytes) -> list[dict]:
    out = []
    for r in _read(content, "field"):
        v = r.values
        fecha = _date(v.get("fecha"))
        if not fecha:
            raise ExcelFormatError(f"Row {r.row}: date '{v.get('fecha')}' not understood (use YYYY-MM-DD or DD/MM/YYYY).")
        out.append({
            "fecha": fecha,
            "clave": str(v["clave"]).strip(),
            "cantidad": _number(v["cantidad"]) or 0.0,
            "zona": (str(v["zona"]).strip() if v.get("zona") else None),
            "nota": (str(v["nota"]).strip() if v.get("nota") else None),
            "reportado_por": (str(v["reportado_por"]).strip() if v.get("reportado_por") else None),
        })
    return out


SEVERITY_FILL = {
    "error": PatternFill("solid", fgColor="FBEBEB"),
    "warning": PatternFill("solid", fgColor="F9EEDA"),
    "ok": PatternFill("solid", fgColor="E5F4E4"),
    "info": PatternFill("solid", fgColor="E7F1FB"),
}


def write_validated_estimacion(project_name: str, est: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Estimación validada"
    bold = Font(bold=True)
    ws["A1"] = f"Estimación {est['numero']} — validación"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Proyecto: {project_name}"
    ws["A3"] = f"Periodo: {est.get('periodo') or '—'}    Estado: {est['status']}"
    t = est["totals"]
    ws["A4"] = (
        f"Importe reclamado: {t['claimed_amount']:,.2f}    Importe aprobable: {t['approvable_amount']:,.2f}    "
        f"Diferencia: {t['claimed_amount'] - t['approvable_amount']:,.2f}"
    )
    headers = [
        "Clave", "Descripción", "Unidad", "P.U. contrato", "P.U. reclamado", "Cantidad reclamada",
        "Aprobado anterior", "Acumulado", "Cantidad contrato", "Cantidad en planos", "Cantidad aprobable",
        "Importe reclamado", "Importe aprobable", "Resultado", "Observaciones",
    ]
    hr = 6
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=hr, column=c, value=h)
        cell.font = bold
        cell.fill = PatternFill("solid", fgColor="F1F5F9")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for i, line in enumerate(est["lines"], start=hr + 1):
        vals = [
            line["clave"], line["descripcion"], line["unidad"], line["contract_unit_price"], line["claimed_unit_price"],
            line["claimed"], line["previous_approved"], line["cumulative"], line["contract_quantity"],
            line["drawing_quantity"], line["approvable"], line["claimed_amount"], line["approvable_amount"],
            line["result"], "; ".join(f["message"] for f in line["findings"]),
        ]
        for c, v in enumerate(vals, start=1):
            cell = ws.cell(row=i, column=c, value=v)
            cell.alignment = Alignment(wrap_text=c in (2, 15), vertical="top")
            if isinstance(v, float):
                cell.number_format = "#,##0.00"
        ws.cell(row=i, column=14).fill = SEVERITY_FILL.get(line["severity"], SEVERITY_FILL["info"])
    widths = [10, 42, 8, 12, 12, 12, 12, 12, 12, 12, 12, 14, 14, 12, 60]
    for c, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = ws.cell(row=hr + 1, column=3)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
