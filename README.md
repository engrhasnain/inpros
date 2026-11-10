# INPROS Estimations Pilot

Reads AutoCAD drawings, takes off quantities, links them to the contract catalog and checks
contractor *estimaciones* against contract, earlier approvals and drawings. It also shows what
changed between drawing revisions, with the cost impact.

## Run

```powershell
# backend (FastAPI, port 8000)
cd backend
uv run uvicorn app.main:app --port 8000

# frontend (Next.js, port 3100; port 3000 is used by another project on this machine)
cd frontend
npm run dev
```

Open http://localhost:3100.

- The DWG reader is the vendored, patched `vendor/ezdwg` (MIT). Building it needs Rust: `uv add ../vendor/ezdwg`.
- The ODA File Converter is **not** used by the app. Its free version is for non-commercial use only.
- Data lives in `backend/inpros.db` (SQLite) and `backend/storage/`. Set `DATABASE_URL` / `STORAGE_DIR` in `backend/.env` to change them.

## Deploy on Vercel (one project)

`vercel.json` runs both parts as **one Vercel project** (Vercel Services): the Next.js app on `/`
and the FastAPI backend on `/api/*`.

1. Import this GitHub repo in Vercel. Root directory: the repo root (where `vercel.json` is).
2. Add a Postgres database (Vercel Storage → Neon, or any Postgres) and set the environment variable
   `DATABASE_URL` (e.g. `postgresql://user:pass@host/db?sslmode=require`).
   Without it the app still starts, but data lives in `/tmp` and is lost between requests.
3. Deploy. Open `https://<your-app>.vercel.app` — `/api/health` should show `"database": "postgresql+psycopg"`.

Notes:
- Uploaded drawings and generated files are also stored in the database on Vercel
  (`FILES_IN_DATABASE`, on automatically), because Vercel servers do not keep files between requests.
- The patched DWG reader is shipped prebuilt for Linux in `backend/wheels/` (built from `vendor/ezdwg`
  with `vendor/ezdwg-inpros-fixes.patch`). Rebuild: `maturin build --release --target x86_64-unknown-linux-gnu --zig --compatibility manylinux_2_28`.
- Vercel limits a request body to about 4.5 MB, so a single uploaded drawing must be smaller than that.

## Steps

| # | Page | What it does |
|---|------|--------------|
| 1–3 | Home | Create a project and upload `.dwg` / `.dxf` files. Each upload becomes a version, and an identical re-upload is detected. |
| — | Drawing page | Preview (zoom/pan) plus layers, symbols, labels and this drawing's quantities. |
| 4 | Quantities | Takeoff per sheet: electrical layers only. Objects outside the sheet frames, legend samples and exact duplicates are excluded and counted. |
| 5 | Contract catalog | Upload the *catálogo de conceptos* (.xlsx). Each line gets a suggested drawing item, and an engineer confirms it. Shows contract vs. drawing difference in units and pesos. |
| 6 | Estimación check | Upload the contractor's .xlsx. It flags codes not in the contract, price mismatches, duplicates, over-contract and over-drawing claims, and wrong "previously paid" figures. It computes the approvable amount. Approve, or export the validated Excel. |
| 7 | Revision changes | Upload a new version of a drawing (same file name), open it, and compare versions. You get quantity changes and the cost impact at contract prices. |

## Demo data (until INPROS sends real files)

`data/samples/` holds **invented** files made by `backend/scripts/make_demo_data.py`:

- `DEMO_catalogo_conceptos.xlsx` – 12 catalog lines with illustrative prices
- `DEMO_estimacion_01.xlsx`, `DEMO_estimacion_02.xlsx` – contractor claims with typical errors
- `3erNLUMI.dxf` – revision B of the lighting plan (+12 LAM-A, −3 LAM-C, −42 m conduit)

Demo flow:
1. Upload the 8 DWGs.
2. Upload the catalog and confirm or correct the suggested links.
3. Upload estimación 1 and approve it.
4. Upload estimación 2.
5. Upload `3erNLUMI.dxf` and open 3erNLUMI to see the revision changes.

## Checks

```powershell
cd backend
uv run python scripts/validate_readers.py "../Data and Meeting Summary" ../data/dxf ../data/inventory   # readers vs ODA reference
uv run python scripts/e2e_check.py http://localhost:<port> "../Data and Meeting Summary" ../data/samples # steps 1-7; use a scratch database
```

## Known limits (pilot)

- Takeoff rules are name-based (electrical layer prefixes) and tuned on the sample drawings. Real INPROS drawings may need rule adjustments.
- Tray length is an estimate: half of the two drawn edges.
- Conduit is measured per layer, not per diameter.
- Zone (department) breakdown works only where zones are drawn as area outlines. The sample drawings only have brackets.
- Catalog-link suggestions are rule-based and must be confirmed by a person. No AI service is called.
- Single user, no login. Database tables are created automatically; add Alembic migrations before production.
