"""End-to-end check of steps 1-7 against a running backend (use a scratch database!).

    uv run python scripts/e2e_check.py http://localhost:8010 "../Data and Meeting Summary" ../data/samples
"""

import json
import sys
import urllib.request
from pathlib import Path
from uuid import uuid4

BASE, DWG_DIR, SAMPLES = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
failures: list[str] = []


def call(method: str, path: str, body=None, files=None, fields=None, raw=False):
    data, headers = None, {}
    if files:
        boundary = uuid4().hex
        parts = []
        for k, v in (fields or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for k, p in files.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{p.name}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n".encode() + p.read_bytes() + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        data = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            content = r.read()
            return content if raw else (json.loads(content) if content else None)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} -> {e.code}: {e.read().decode()[:400]}") from e


def expect(cond: bool, msg: str) -> None:
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


print("1-3  project + drawings")
import os  # noqa: E402

p = call("POST", "/projects", {"name": os.environ.get("E2E_PROJECT", "E2E Ejército Nacional 3er nivel"), "client": "INPROS"})
pid = p["id"]
for f in sorted(DWG_DIR.glob("*.dwg")):
    r = call("POST", f"/projects/{pid}/drawings", files={"file": f})
    expect(r["version"]["status"] == "ready", f"{f.name} ready")

print("4    quantities")
items = call("GET", f"/projects/{pid}/takeoff")
lam_a = [i for i in items if i["drawing_name"] == "3erNLUMI" and i.get("symbol") == "LAM-A"]
expect(len(lam_a) == 1 and lam_a[0]["quantity"] == 321, f"LAM-A on lighting plan = 321 (got {[i['quantity'] for i in lam_a]})")
tub = [i for i in items if i["drawing_name"] == "3erNTUBN-R" and i["layer"] == "TUBERIA"]
expect(sorted(i["sheet"] for i in tub) == ["A", "B"], "conduit drawing measured per sheet A and B")

print("5    catalog + links")
cat = call("POST", f"/projects/{pid}/catalog", files={"file": SAMPLES / "DEMO_catalogo_conceptos.xlsx"})
expect(cat["totals"]["items"] == 12, f"12 catalog items imported (got {cat['totals']['items']})")
by_clave = {r["clave"]: r for r in cat["items"]}
s1 = by_clave["IE-001"]["link"]
expect(bool(s1) and s1["drawing_name"] == "3erNLUMI" and "LAM-A" in s1["takeoff_key"], f"IE-001 suggested -> LAM-A on 3erNLUMI (got {s1})")
print("     suggestions:")
for r in cat["items"]:
    lk = r["link"]
    print(f"       {r['clave']} {r['descripcion'][:45]:45} -> {lk['drawing_name'] + ' ' + lk['sheet'] + ' ' + lk['takeoff_key'] if lk else '—'}")

# the engineer confirms / corrects links (what a person does in the UI)
wanted = {
    "IE-001": ("3erNLUMI", "A", "count|LUMINARIOS|LAM-A"),
    "IE-002": ("3erNLUMI", "A", "count|LUMINARIOS|LAM-B"),
    "IE-003": ("3erNLUMI", "A", "count|LUMINARIOS|LAM-C"),
    "IE-010": ("ALIMPPAL", "A", "count|IETU1150|CA"),
    "IE-020": ("3erNTUBN-R", "A", "length|TUBERIA"),
    "IE-021": ("3erNTUBN-R", "A", "length|TUBERIA ELEVADA"),
    "IE-022": ("3erNTUBVD", "A", "length|TUBERÍAS"),
    "IE-030": ("CHAR-DERIV", "A", "length|charola"),
    "IE-040": ("DIAGUNIF", "A", "count|IESI1420|TAB-E"),
    "IE-050": ("MOTORESKW (1)", "A", "length|MOTORES"),
}
for clave, (dn, sh, key) in wanted.items():
    cat = call("PUT", f"/catalog-items/{by_clave[clave]['id']}/link", {"drawing_name": dn, "sheet": sh, "takeoff_key": key})
for r in cat["items"]:  # confirm the remaining suggestions as an engineer would
    if r["link"] and not r["link"]["confirmed"]:
        cat = call("POST", f"/catalog-items/{r['id']}/confirm")
by_clave = {r["clave"]: r for r in cat["items"]}
expect(cat["totals"]["confirmed"] == cat["totals"]["linked"], "all links confirmed")
expect(by_clave["IE-001"]["drawing_quantity"] == 321 and by_clave["IE-001"]["difference"] == 21,
       "IE-001: drawing 321 vs contract 300 -> +21 flagged")
expect(by_clave["IE-090"]["status"] == "not_linked", "IE-090 (tests, lote) stays without a drawing link")

print("6    estimaciones")
e1 = call("POST", f"/projects/{pid}/estimaciones", files={"file": SAMPLES / "DEMO_estimacion_01.xlsx"}, fields={"numero": 1, "periodo": "01-15 oct 2026"})
codes = {(ln["clave"], f["code"]) for ln in e1["lines"] for f in ln["findings"]}
for code in [("IE-002", "EXCEEDS_CONTRACT"), ("IE-010", "PRICE_MISMATCH"), ("IE-020", "EXCEEDS_CONTRACT"),
             ("IE-020", "EXCEEDS_DRAWING"), ("IE-099", "NOT_IN_CONTRACT"), ("IE-001", "DUPLICATE_LINE"),
             ("IE-090", "NO_DRAWING_LINK")]:
    expect(code in codes, f"estimación 1 flags {code[1]} on {code[0]}")
ok_lines = [ln["clave"] for ln in e1["lines"] if ln["severity"] == "ok"]
expect(set(ok_lines) == {"IE-030", "IE-040"} | ({"IE-001"} if "IE-001" in ok_lines else set()), f"clean lines pass (ok: {ok_lines})")
t = e1["totals"]
print(f"     claimed {t['claimed_amount']:,.2f}  approvable {t['approvable_amount']:,.2f}")
expect(t["approvable_amount"] < t["claimed_amount"], "approvable amount below claimed amount")
xlsx = call("GET", f"/estimaciones/{e1['id']}/export.xlsx", raw=True)
expect(xlsx[:2] == b"PK", "validated estimación exports as .xlsx")
call("POST", f"/estimaciones/{e1['id']}/approve")
e2 = call("POST", f"/projects/{pid}/estimaciones", files={"file": SAMPLES / "DEMO_estimacion_02.xlsx"}, fields={"numero": 2, "periodo": "16-31 oct 2026"})
l2 = {ln["clave"]: ln for ln in e2["lines"]}
expect(l2["IE-001"]["previous_approved"] == 120 and l2["IE-001"]["approvable"] == 180,
       f"est. 2: IE-001 previous 120, approvable capped at 180 (got {l2['IE-001']['previous_approved']}, {l2['IE-001']['approvable']})")
expect(any(f["code"] == "PREVIOUS_MISMATCH" for f in l2["IE-020"]["findings"]), "est. 2: IE-020 contractor's 'previous' differs from approved")
expect(l2["IE-020"]["approvable"] == 0, "est. 2: IE-020 nothing left to pay")

print("7    revision changes")
r = call("POST", f"/projects/{pid}/drawings", files={"file": SAMPLES / "3erNLUMI.dxf"})
expect(r["version"]["version"] == 2 and r["version"]["status"] == "ready", "revision B uploaded as version 2")
drawings = call("GET", f"/projects/{pid}/drawings")
did = next(d["id"] for d in drawings if d["name"] == "3erNLUMI")
cmp = call("GET", f"/drawings/{did}/compare?old=1&new=2")
ch = {c["key"]: c for c in cmp["quantity_changes"]}
print("     changes:", [(c["description"], c["old"], c["new"], c["delta"], c["cost_impact"]) for c in cmp["quantity_changes"]])
expect(ch.get("count|LUMINARIOS|LAM-A", {}).get("delta") == 12, "rev B: +12 luminaire type A")
expect(ch.get("count|LUMINARIOS|LAM-A", {}).get("cost_impact") == 12 * 1850.0, "rev B: +12 x 1,850 = 22,200 cost impact")
expect(ch.get("count|LUMINARIOS|LAM-C", {}).get("delta") in (-3, -2), "rev B: luminaire type C reduced")
iet = ch.get("length|IETU1150", {}).get("delta")
expect(iet is not None and -43 < iet < -41, f"rev B: about -42 m conduit on IETU1150 (got {iet})")
print(f"     cost impact total: {cmp['cost_impact_total']:,.2f}")

print("8    reports, bids, field progress")
# reports refuse until project details are complete
req = urllib.request.Request(f"{BASE}/estimaciones/{e1['id']}/dictamen.pdf")
try:
    urllib.request.urlopen(req, timeout=60)
    expect(False, "dictamen refused while project details are incomplete")
except urllib.error.HTTPError as err:
    expect(err.code == 409, f"dictamen refused while project details are incomplete ({err.code})")
call("PUT", f"/projects/{pid}", {
    "client": "INPROS", "contract_number": "INP-2026-014", "contractor": "Instalaciones Eléctricas del Centro, S.A. de C.V.",
    "location": "Av. Ejército Nacional 769-A, CDMX",
    "scope": "Supervisión de la instalación eléctrica del 3er nivel: alumbrado, canalizaciones, tableros y fuerza.",
    "supervisor_name": "Ing. Carlos Aranda", "supervisor_title": "Supervisor de obra",
    "approver_name": "Lic. Enrique Tort Schietekat", "approver_title": "Director de Administración",
})
expect(call("GET", f"/projects/{pid}/report-readiness")["ready"], "project details complete -> reports ready")
pdf = call("GET", f"/estimaciones/{e1['id']}/dictamen.pdf", raw=True)
expect(pdf[:4] == b"%PDF" and len(pdf) > 3000, "dictamen técnico PDF generated")

f = call("POST", f"/projects/{pid}/field/upload", files={"file": SAMPLES / "DEMO_avance_obra.xlsx"})
ie001 = next(p for p in f["progress"] if p["clave"] == "IE-001")
expect(len(f["entries"]) == 9 and ie001["installed"] == 110, f"field progress imported (IE-001 installed {ie001['installed']})")
e1b = call("GET", f"/estimaciones/{e1['id']}")
l1 = next(ln for ln in e1b["lines"] if ln["clave"] == "IE-020")
expect(any(fd["code"] == "EXCEEDS_FIELD" for fd in l1["findings"]), "estimación flags claims above site-reported progress")
pdf = call("GET", f"/projects/{pid}/field/report.pdf", raw=True)
expect(pdf[:4] == b"%PDF", "progress report PDF generated")

for path in sorted(SAMPLES.glob("DEMO_propuesta_*.xlsx")):
    bidder = {"alfa": "Constructora Alfa", "beta": "Instalaciones Beta", "gama": "Electro Gama"}[path.stem.split("_")[-1]]
    ev = call("POST", f"/projects/{pid}/bids", files={"file": path}, fields={"bidder": bidder})
ranks = {b["bidder"]: b for b in ev["bidders"]}
expect(ev["recommended"] == "Electro Gama", f"lowest complete bid recommended (got {ev['recommended']})")
expect(ranks["Instalaciones Beta"]["missing_items"] == ["IE-090"], "incomplete bid detected (Beta misses IE-090)")
expect(set(ranks["Electro Gama"]["price_outliers"]) == {"IE-030", "IE-040"}, f"price outliers flagged {ranks['Electro Gama']['price_outliers']}")
pdf = call("GET", f"/projects/{pid}/bids/report.pdf", raw=True)
expect(pdf[:4] == b"%PDF", "bid evaluation PDF generated")
for name, rel in [("dictamen", f"/estimaciones/{e1['id']}/dictamen.pdf"), ("avance", f"/projects/{pid}/field/report.pdf"),
                  ("propuestas", f"/projects/{pid}/bids/report.pdf")]:
    out = Path(os.environ.get("E2E_PDF_DIR", "")) if os.environ.get("E2E_PDF_DIR") else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{name}.pdf").write_bytes(call("GET", rel, raw=True))

print("\nRESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
