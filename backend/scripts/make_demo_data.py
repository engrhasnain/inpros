"""Create DEMO input files for steps 5-7 until INPROS sends real ones.

    uv run python scripts/make_demo_data.py ../data/dxf/3erNLUMI.dxf ../data/samples

Writes:
  DEMO_catalogo_conceptos.xlsx   contract catalog (12 items, illustrative MXN prices)
  DEMO_estimacion_01.xlsx        contractor estimación 1 with typical errors
  DEMO_estimacion_02.xlsx        contractor estimación 2 (cumulative / previous-paid errors)
  3erNLUMI.dxf                   revision B of the lighting plan (+12 LAM-A, -3 LAM-C, ~40 m conduit removed)

All values are invented for demonstration. Quantities are set near the real drawing takeoff on
purpose (some equal, some different) so the comparison has something to show.
"""

import sys
from pathlib import Path

import ezdxf
from openpyxl import Workbook
from openpyxl.styles import Font

CATALOG = [
    # clave, descripción, unidad, cantidad, P.U. (MXN), partida
    ("IE-001", "Suministro e instalación de luminario tipo A 2x32 W empotrado", "pza", 300, 1850.00, "Alumbrado"),
    ("IE-002", "Suministro e instalación de luminario tipo B 2x17 W", "pza", 7, 2100.00, "Alumbrado"),
    ("IE-003", "Suministro e instalación de luminario tipo C downlight", "pza", 12, 1650.00, "Alumbrado"),
    ("IE-004", "Suministro e instalación de luminario tipo 02 arbotante", "pza", 2, 980.00, "Alumbrado"),
    ("IE-010", "Caja de registro galvanizada 100x100 mm", "pza", 245, 85.00, "Canalizaciones"),
    ("IE-020", "Tubería conduit galvanizada pared delgada 25 mm, contactos normal y regulado", "m", 400, 95.00, "Canalizaciones"),
    ("IE-021", "Tubería conduit elevada galvanizada 25 mm", "m", 300, 110.00, "Canalizaciones"),
    ("IE-022", "Tubería conduit para voz y datos 25 mm", "m", 470, 90.00, "Canalizaciones"),
    ("IE-030", "Charola tipo malla de 12 in, incluye soportería", "m", 400, 640.00, "Canalizaciones"),
    ("IE-040", "Tablero de distribución trifásico con interruptores", "pza", 12, 18500.00, "Tableros"),
    ("IE-050", "Alimentador a motores, cable y canalización", "m", 170, 210.00, "Fuerza"),
    ("IE-090", "Pruebas y puesta en marcha de la instalación eléctrica", "lote", 1, 45000.00, "Pruebas"),
]
PRICE = {c[0]: c[4] for c in CATALOG}
DESC = {c[0]: (c[1], c[2]) for c in CATALOG}

# (clave, cantidad esta estimación, cantidad anterior declarada, P.U. usado)
EST_01 = [
    ("IE-001", 120, 0, PRICE["IE-001"]),        # OK
    ("IE-002", 9, 0, PRICE["IE-002"]),          # exceeds contract (7)
    ("IE-010", 100, 0, 92.00),                  # unit price differs from contract (85.00)
    ("IE-020", 430, 0, PRICE["IE-020"]),        # exceeds contract (400) and drawing
    ("IE-030", 150, 0, PRICE["IE-030"]),        # OK
    ("IE-040", 4, 0, PRICE["IE-040"]),          # OK
    ("IE-099", 1500, 0, 18.00),                 # not in the contract
    ("IE-001", 10, 0, PRICE["IE-001"]),         # same code twice
    ("IE-090", 0.5, 0, PRICE["IE-090"]),        # not measurable from drawings
]
EST_02 = [
    ("IE-001", 200, 120, PRICE["IE-001"]),      # cumulative 320 > contract 300
    ("IE-020", 10, 430, PRICE["IE-020"]),       # contractor's 'previous' (430) != approved (400); nothing remains
    ("IE-022", 200, 0, PRICE["IE-022"]),        # OK
    ("IE-030", 120, 150, PRICE["IE-030"]),      # OK
]
EXTRA_DESC = {"IE-099": ("Cable THW-LS calibre 12 AWG", "m")}

# Bids: unit-price factor vs. budget per bidder; None = item not quoted
BIDS = {
    "Constructora Alfa": {c[0]: 1.06 for c in CATALOG},                       # complete, a bit above budget
    "Instalaciones Beta": {**{c[0]: 0.93 for c in CATALOG}, "IE-090": None},   # cheapest, but misses an item
    "Electro Gama": {**{c[0]: 0.99 for c in CATALOG}, "IE-030": 0.58, "IE-040": 1.45},  # lowest complete; 2 odd prices
}

# Site progress reported by the resident engineer (fecha, clave, cantidad, zona, nota)
FIELD = [
    ("2026-10-03", "IE-001", 40, "Eje 1-6", "Luminarios tipo A instalados en plafón"),
    ("2026-10-08", "IE-001", 45, "Eje 6-12", ""),
    ("2026-10-14", "IE-001", 25, "Eje 12-16", "Faltan 10 por falta de material"),
    ("2026-10-06", "IE-002", 7, "Sanitarios", ""),
    ("2026-10-09", "IE-010", 100, "Todo el nivel", ""),
    ("2026-10-10", "IE-020", 220, "Eje 1-8", "Tubería por piso"),
    ("2026-10-15", "IE-020", 160, "Eje 8-16", ""),
    ("2026-10-12", "IE-030", 150, "Pasillo central", "Charola con soportería"),
    ("2026-10-13", "IE-040", 4, "Cuarto eléctrico", "Tableros AN, AR, BN, BR"),
]


def write_catalog(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Catálogo"
    ws["A1"] = "DEMO — Catálogo de conceptos (datos de ejemplo, no son del contrato real)"
    ws["A1"].font = Font(bold=True)
    ws["A2"] = "Obra: Oficinas Corporativas Ejército Nacional — Instalación eléctrica 3er nivel"
    ws.append([])
    ws.append(["Clave", "Descripción", "Unidad", "Cantidad", "P.U.", "Importe", "Partida"])
    for c in ws[4]:
        c.font = Font(bold=True)
    for clave, desc, unit, qty, pu, partida in CATALOG:
        ws.append([clave, desc, unit, qty, pu, qty * pu, partida])
    for col, w in zip("ABCDEFG", (10, 70, 8, 10, 12, 14, 16)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def write_estimacion(path: Path, numero: int, periodo: str, lines) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = f"Estimación {numero}"
    ws["A1"] = f"DEMO — Estimación No. {numero} (datos de ejemplo)"
    ws["A1"].font = Font(bold=True)
    ws["A2"] = f"Periodo: {periodo}"
    ws.append([])
    ws.append(["Clave", "Concepto", "Unidad", "Cantidad anterior", "Cantidad esta estimación", "P.U.", "Importe"])
    for c in ws[4]:
        c.font = Font(bold=True)
    for clave, qty, prev, pu in lines:
        desc, unit = DESC.get(clave) or EXTRA_DESC[clave]
        ws.append([clave, desc, unit, prev, qty, pu, qty * pu])
    for col, w in zip("ABCDEFG", (10, 70, 8, 16, 22, 12, 14)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def write_bid(path: Path, bidder: str, factors: dict) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Propuesta"
    ws["A1"] = f"DEMO — Propuesta económica de {bidder} (datos de ejemplo)"
    ws["A1"].font = Font(bold=True)
    ws.append([])
    ws.append(["Clave", "Descripción", "Unidad", "Cantidad", "P.U.", "Importe"])
    for c in ws[3]:
        c.font = Font(bold=True)
    for clave, desc, unit, qty, pu, _ in CATALOG:
        f = factors.get(clave)
        if f is None:
            continue
        price = round(pu * f, 2)
        ws.append([clave, desc, unit, qty, price, round(qty * price, 2)])
    for col, w in zip("ABCDEF", (10, 70, 8, 10, 12, 14)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def write_field(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Avance"
    ws["A1"] = "DEMO — Reporte de avance de obra (datos de ejemplo)"
    ws["A1"].font = Font(bold=True)
    ws.append([])
    ws.append(["Fecha", "Clave", "Cantidad instalada", "Zona", "Nota", "Reportado por"])
    for c in ws[3]:
        c.font = Font(bold=True)
    for fecha, clave, qty, zona, nota in FIELD:
        ws.append([fecha, clave, qty, zona, nota, "Ing. residente de obra"])
    for col, w in zip("ABCDEF", (12, 10, 18, 18, 40, 24)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def write_revision(src_dxf: Path, out: Path) -> dict:
    doc = ezdxf.readfile(src_dxf)
    msp = doc.modelspace()
    # keep changes inside the sheet frame (x 1.3..121.3, y 60.5..108.2 on this drawing)
    lam_a = [e for e in msp.query('INSERT[name=="LAM-A"]') if 10 < e.dxf.insert.x < 110 and 65 < e.dxf.insert.y < 104]
    added = 0
    for e in lam_a[:12]:
        copy = e.copy()
        copy.dxf.insert = (e.dxf.insert.x + 1.2, e.dxf.insert.y + 0.6, 0)
        msp.add_entity(copy)
        added += 1
    removed_c = 0
    for e in list(msp.query('INSERT[name=="LAM-C"]'))[:3]:
        msp.delete_entity(e)
        removed_c += 1
    removed_len = 0.0
    lines = sorted(msp.query('LINE[layer=="IETU1150"]'), key=lambda e: -e.dxf.start.distance(e.dxf.end))
    for e in lines:
        if removed_len >= 40:
            break
        removed_len += e.dxf.start.distance(e.dxf.end)
        msp.delete_entity(e)
    doc.saveas(out)
    return {"added_LAM-A": added, "removed_LAM-C": removed_c, "removed_IETU1150_m": round(removed_len, 2)}


def main() -> None:
    src_dxf, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    write_catalog(out_dir / "DEMO_catalogo_conceptos.xlsx")
    write_estimacion(out_dir / "DEMO_estimacion_01.xlsx", 1, "01–15 octubre 2026", EST_01)
    write_estimacion(out_dir / "DEMO_estimacion_02.xlsx", 2, "16–31 octubre 2026", EST_02)
    for i, (bidder, factors) in enumerate(BIDS.items(), start=1):
        write_bid(out_dir / f"DEMO_propuesta_{i}_{bidder.split()[-1].lower()}.xlsx", bidder, factors)
    write_field(out_dir / "DEMO_avance_obra.xlsx")
    changes = write_revision(src_dxf, out_dir / "3erNLUMI.dxf")
    print("wrote demo files to", out_dir.resolve())
    print("revision B changes:", changes)


if __name__ == "__main__":
    main()
