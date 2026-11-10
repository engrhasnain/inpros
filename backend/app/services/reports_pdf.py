"""Generated PDF reports (Spanish, as INPROS issues them). Header data always comes from the project record."""

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK = colors.HexColor("#1e293b")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#cbd5e1")
HEAD = colors.HexColor("#f1f5f9")
RED = colors.HexColor("#fbebeb")
AMBER = colors.HexColor("#f9eeda")
GREEN = colors.HexColor("#e5f4e4")
BLUE = colors.HexColor("#e7f1fb")

_ss = getSampleStyleSheet()
T = ParagraphStyle("t", parent=_ss["Title"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK, alignment=TA_LEFT, spaceAfter=2)
SUB = ParagraphStyle("s", parent=_ss["Normal"], fontName="Helvetica", fontSize=9, textColor=MUTED, leading=12)
H = ParagraphStyle("h", parent=_ss["Heading3"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=INK, spaceBefore=9, spaceAfter=4)
B = ParagraphStyle("b", parent=_ss["Normal"], fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK, spaceAfter=3)
C = ParagraphStyle("c", parent=B, fontSize=8, leading=10, spaceAfter=0)
CB = ParagraphStyle("cb", parent=C, fontName="Helvetica-Bold")
CR = ParagraphStyle("cr", parent=C, alignment=2)
SEV = {"error": RED, "warning": AMBER, "ok": GREEN, "info": BLUE}


def _esc(s) -> str:
    return (str(s if s is not None else "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def money(n) -> str:
    if n is None:
        return "—"
    return f"-${-n:,.2f}" if n < 0 else f"${n:,.2f}"


def num(n) -> str:
    return "—" if n is None else f"{n:,.2f}".rstrip("0").rstrip(".")


def _table(rows, widths, header=True, styles=()):
    data = []
    for i, r in enumerate(rows):
        data.append([c if not isinstance(c, str) else Paragraph(c, CB if (header and i == 0) else C) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), HEAD))
    st.extend(styles)
    t.setStyle(TableStyle(st))
    return t


def _r(v) -> Paragraph:
    return Paragraph(v, CR)


def _header_block(h: dict, width: float, extra: list[tuple[str, str]] = ()) -> Table:
    rows = [
        ("Proyecto", h["project"]), ("Cliente", h["client"]), ("Contrato No.", h["contract_number"]),
        ("Contratista", h["contractor"]), ("Ubicación", h["location"] or "—"), *extra,
    ]
    half = (len(rows) + 1) // 2
    left, right = rows[:half], rows[half:]
    data = []
    for i in range(half):
        a = left[i]
        b = right[i] if i < len(right) else ("", "")
        data.append([Paragraph(f"<b>{_esc(a[0])}</b>", C), Paragraph(_esc(a[1]), C),
                     Paragraph(f"<b>{_esc(b[0])}</b>", C), Paragraph(_esc(b[1]), C)])
    t = Table(data, colWidths=[width * 0.14, width * 0.36, width * 0.14, width * 0.36])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, -1), HEAD),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    return t


def _signatures(h: dict, width: float) -> KeepTogether:
    data = [
        [Paragraph("Elaboró", C), Paragraph("Aprobó", C)],
        [Spacer(1, 16), Spacer(1, 16)],
        [Paragraph("_______________________________", C), Paragraph("_______________________________", C)],
        [Paragraph(f"<b>{_esc(h['supervisor_name'])}</b><br/>{_esc(h['supervisor_title'])}", C),
         Paragraph(f"<b>{_esc(h['approver_name'])}</b><br/>{_esc(h['approver_title'])}", C)],
    ]
    t = Table(data, colWidths=[width / 2, width / 2])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return KeepTogether([Spacer(1, 10), t])


def _build(story, title: str, h: dict, pagesize=LETTER) -> bytes:
    buf = io.BytesIO()

    def footer(c, doc):
        c.saveState()
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUTED)
        c.drawString(15 * mm, 9 * mm, f"{title} · Contrato {h['contract_number']} · generado {date.today().isoformat()}")
        c.drawRightString(doc.pagesize[0] - 15 * mm, 9 * mm, f"Página {doc.page}")
        c.restoreState()

    SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                      bottomMargin=16 * mm, title=title, author=h["supervisor_name"]).build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# --------------------------------------------------------------------------- dictamen de estimación
RESULT_ES = {"OK": "Procede", "Not verified": "No verificable en planos", "Review": "Revisar", "Adjusted": "Ajustado"}


def dictamen_estimacion(h: dict, est: dict) -> bytes:
    pagesize = landscape(LETTER)
    W = pagesize[0] - 30 * mm
    t = est["totals"]
    diff = t["claimed_amount"] - t["approvable_amount"]
    status = "APROBADA" if est["status"] == "approved" else "REVISADA (pendiente de aprobación)"
    story = [
        Paragraph(f"Dictamen técnico de la Estimación No. {est['numero']}", T),
        Paragraph(f"Periodo: {_esc(est.get('periodo') or '—')} · Estado: {status} · Archivo: {_esc(est['source_filename'])}", SUB),
        Spacer(1, 6),
        _header_block(h, W),
        Paragraph("Alcance", H),
        Paragraph(_esc(h["scope"]), B),
        Paragraph("Resultado", H),
        Paragraph(
            f"El contratista presenta un importe de <b>{money(t['claimed_amount'])}</b>. Tras revisar cada concepto contra el "
            f"catálogo del contrato, las estimaciones aprobadas anteriormente, las cantidades medidas en planos y el avance "
            f"reportado en obra, el importe procedente es <b>{money(t['approvable_amount'])}</b>, con una diferencia de "
            f"<b>{money(diff)}</b>. De {t['lines']} conceptos: {t['ok']} proceden, {t['errors']} se ajustan, "
            f"{t['warnings']} requieren revisión y {t['not_verified']} no son verificables en planos.", B),
        Paragraph("Detalle por concepto", H),
    ]
    rows = [["Clave", "Concepto", "Unidad", "Reclamado", "Aprob. anterior", "Contrato", "Planos", "Obra", "Procedente",
             "Importe reclamado", "Importe procedente", "Resultado"]]
    sev_styles = []
    for i, ln in enumerate(est["lines"], start=1):
        rows.append([
            _esc(ln["clave"]), _esc(ln["descripcion"]), _esc(ln["unidad"]), _r(num(ln["claimed"])), _r(num(ln["previous_approved"])),
            _r(num(ln["contract_quantity"])), _r(num(ln["drawing_quantity"])), _r(num(ln.get("field_quantity"))),
            _r(f"<b>{num(ln['approvable'])}</b>"), _r(money(ln["claimed_amount"])), _r(money(ln["approvable_amount"])),
            RESULT_ES.get(ln["result"], ln["result"]),
        ])
        sev_styles.append(("BACKGROUND", (11, i), (11, i), SEV.get(ln["severity"], BLUE)))
    rows.append(["", "<b>Total</b>", "", "", "", "", "", "", "", _r(f"<b>{money(t['claimed_amount'])}</b>"),
                 _r(f"<b>{money(t['approvable_amount'])}</b>"), ""])
    widths = [0.06, 0.25, 0.05, 0.065, 0.07, 0.06, 0.06, 0.055, 0.07, 0.09, 0.09, 0.07]
    story.append(_table(rows, [w * W for w in widths], styles=sev_styles))

    obs = [(ln["clave"], f) for ln in est["lines"] for f in ln["findings"]]
    if obs:
        obs_table = _table([["Clave", "Tipo", "Observación"]] + [
            [_esc(c), {"error": "Ajuste", "warning": "Revisar", "info": "Nota"}[f["severity"]], _esc(f["message"])] for c, f in obs
        ], [0.08 * W, 0.08 * W, 0.84 * W])
        story.append(KeepTogether([Paragraph("Observaciones", H), obs_table]))
    story.append(Paragraph(
        "Las cantidades en planos provienen de la cuantificación automática de la última versión de cada plano, "
        "vinculada a cada concepto por el área técnica. Los importes procedentes usan los precios unitarios del contrato.", SUB))
    story.append(_signatures(h, W))
    return _build(story, f"Dictamen Estimación {est['numero']}", h, pagesize)


# --------------------------------------------------------------------------- evaluación de propuestas
FLAG_ES = {"high": "Alto", "low": "Bajo", "missing": "Falta"}


def evaluacion_propuestas(h: dict, ev: dict) -> bytes:
    pagesize = landscape(LETTER)
    W = pagesize[0] - 30 * mm
    story = [
        Paragraph("Evaluación económica de propuestas", T),
        Paragraph(f"{len(ev['bidders'])} propuestas evaluadas contra el catálogo de conceptos del contrato", SUB),
        Spacer(1, 6),
        _header_block(h, W, [("Presupuesto base", money(ev["budget_total"]))]),
        Paragraph("Alcance", H),
        Paragraph(_esc(h["scope"]), B),
        Paragraph("Resumen", H),
    ]
    rows = [["Lugar", "Licitante", "Importe total", "vs. presupuesto", "Conceptos faltantes", "Precios fuera de rango (±25 %)"]]
    for s in ev["bidders"]:
        rows.append([
            str(s["rank"]), f"<b>{_esc(s['bidder'])}</b>", _r(money(s["total"])),
            _r(f"{money(s['vs_budget'])} ({s['vs_budget_pct']:+.1f} %)" if s["vs_budget_pct"] is not None else money(s["vs_budget"])),
            ", ".join(s["missing_items"]) or "Ninguno", ", ".join(s["price_outliers"]) or "Ninguno",
        ])
    story.append(_table(rows, [0.06 * W, 0.2 * W, 0.14 * W, 0.18 * W, 0.18 * W, 0.24 * W]))
    story.append(Paragraph("Recomendación", H))
    rec = ev["recommendation_note"]
    rec_es = rec
    if ev["recommended"]:
        best = next(s for s in ev["bidders"] if s["bidder"] == ev["recommended"])
        rec_es = (f"La propuesta solvente más baja es la de <b>{_esc(ev['recommended'])}</b> por {money(best['total'])}"
                  + (f"; antes de adjudicar se deben aclarar {len(best['price_outliers'])} precio(s) unitario(s) fuera de rango."
                     if best["price_outliers"] else "."))
    else:
        rec_es = "Ninguna propuesta está completa: todas omiten al menos un concepto del catálogo."
    story.append(Paragraph(rec_es, B))

    story.append(Paragraph("Comparativo por concepto (precio unitario)", H))
    names = [s["bidder"] for s in sorted(ev["bidders"], key=lambda s: s["bidder"])]
    head = ["Clave", "Concepto", "Unidad", "Cantidad", "P.U. presupuesto", "Mediana"] + names
    rows = [head]
    styles = []
    for i, it in enumerate(ev["items"], start=1):
        r = [_esc(it["clave"]), _esc(it["descripcion"]), _esc(it["unidad"]), _r(num(it["cantidad"])),
             _r(money(it["budget_unit_price"])), _r(money(it["median_unit_price"]))]
        for j, n in enumerate(names):
            cell = it["bidders"][n]
            label = money(cell["unit_price"]) if cell["unit_price"] is not None else "—"
            if cell["flag"]:
                label += f" ({FLAG_ES[cell['flag']]})"
                styles.append(("BACKGROUND", (6 + j, i), (6 + j, i), RED if cell["flag"] in ("missing", "high") else AMBER))
            r.append(_r(label))
        rows.append(r)
    fixed = [0.06, 0.26, 0.05, 0.07, 0.09, 0.09]
    rest = (1 - sum(fixed)) / max(1, len(names))
    story.append(_table(rows, [w * W for w in fixed] + [rest * W] * len(names), styles=styles))
    story.append(_signatures(h, W))
    return _build(story, "Evaluación de propuestas", h, pagesize)


# --------------------------------------------------------------------------- reporte de avance
def reporte_avance(h: dict, catalog: list, entries: list) -> bytes:
    pagesize = LETTER
    W = pagesize[0] - 30 * mm
    by_clave: dict[str, float] = {}
    last: dict[str, str] = {}
    for e in entries:
        by_clave[e.clave] = by_clave.get(e.clave, 0.0) + e.cantidad
        last[e.clave] = max(last.get(e.clave, ""), e.fecha)
    total_contract = sum(c.cantidad * c.precio_unitario for c in catalog) or 0.0
    total_done = sum(min(by_clave.get(c.clave, 0.0), c.cantidad) * c.precio_unitario for c in catalog)
    pct = (total_done / total_contract * 100) if total_contract else 0.0
    period = f"{min(e.fecha for e in entries)} a {max(e.fecha for e in entries)}" if entries else "sin registros"
    story = [
        Paragraph("Reporte de avance de obra", T),
        Paragraph(f"Registros de campo del {period} · {len(entries)} registros", SUB),
        Spacer(1, 6),
        _header_block(h, W, [("Avance financiero", f"{pct:.1f} %")]),
        Paragraph("Resumen", H),
        Paragraph(f"Con base en el avance reportado en obra, el importe ejecutado es <b>{money(total_done)}</b> de "
                  f"<b>{money(total_contract)}</b> contratados (<b>{pct:.1f} %</b>).", B),
        Paragraph("Avance por concepto", H),
    ]
    rows = [["Clave", "Concepto", "Unidad", "Contrato", "Ejecutado", "Avance", "Último registro"]]
    styles = []
    for i, c in enumerate(catalog, start=1):
        done = by_clave.get(c.clave, 0.0)
        p = (done / c.cantidad * 100) if c.cantidad else 0.0
        rows.append([_esc(c.clave), _esc(c.descripcion), _esc(c.unidad), _r(num(c.cantidad)), _r(num(done)),
                     _r(f"{p:.0f} %"), last.get(c.clave, "—")])
        if p > 100.0001:
            styles.append(("BACKGROUND", (5, i), (5, i), RED))
        elif p >= 99.999:
            styles.append(("BACKGROUND", (5, i), (5, i), GREEN))
    story.append(_table(rows, [0.08 * W, 0.42 * W, 0.07 * W, 0.1 * W, 0.1 * W, 0.09 * W, 0.14 * W], styles=styles))
    if entries:
        story.append(Paragraph("Registros de campo", H))
        rows = [["Fecha", "Clave", "Cantidad", "Zona / frente", "Reportó", "Nota"]]
        for e in sorted(entries, key=lambda e: (e.fecha, e.clave)):
            rows.append([e.fecha, _esc(e.clave), _r(num(e.cantidad)), _esc(e.zona or "—"), _esc(e.reportado_por or "—"), _esc(e.nota or "")])
        story.append(_table(rows, [0.11 * W, 0.09 * W, 0.1 * W, 0.2 * W, 0.17 * W, 0.33 * W]))
    story.append(_signatures(h, W))
    return _build(story, "Reporte de avance", h, pagesize)
