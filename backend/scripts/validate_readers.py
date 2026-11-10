"""Validate the DWG reader (ezdwg) against ODA-converted reference data.

Usage:  uv run python scripts/validate_readers.py "../Data and Meeting Summary" ../data/dxf ../data/inventory
Reference inventories come from scripts/inventory.py run on ODA-converted DXFs.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.drawing import read_drawing  # noqa: E402
from app.drawing.analysis import _clean, analyse  # noqa: E402
from app.drawing.svg import render_svg  # noqa: E402


def compare(name: str, a: dict, ref: dict) -> list[str]:
    problems = []
    if a["totals"]["objects"] != ref["modelspace_entities"]:
        problems.append(f"objects {a['totals']['objects']} vs {ref['modelspace_entities']}")
    mine = {s["name"]: s["count"] for s in a["symbols"] if not s["name"].startswith("*")}
    theirs = {k: v for k, v in ref["blocks"].items() if not k.startswith("*")}
    diff = {k: (mine.get(k, 0), v) for k, v in theirs.items() if mine.get(k, 0) != v}
    if diff:
        problems.append(f"symbol counts differ: {dict(list(diff.items())[:5])}")
    anon_mine = sum(s["count"] for s in a["symbols"] if s["name"].startswith("*"))
    anon_ref = sum(v for k, v in ref["blocks"].items() if k.startswith("*"))
    if anon_mine != anon_ref:
        problems.append(f"anonymous symbol total {anon_mine} vs {anon_ref}")
    lens = {r["name"]: r["length"] for r in a["layers"]}
    bad_len = {
        k: (lens.get(k, 0.0), v["length"])
        for k, v in ref["layers"].items()
        if abs(lens.get(k, 0.0) - v["length"]) > max(0.05, 0.005 * v["length"])
    }
    if bad_len:
        problems.append(f"layer lengths differ (mine, ref): {dict(list(bad_len.items())[:5])}")
    ref_labels = {_clean(t) for t in ref["texts"]}
    my_labels = {r["text"] for r in a["labels"]}
    missing = ref_labels - my_labels
    if missing:
        problems.append(f"{len(missing)}/{len(ref_labels)} labels differ, e.g. {sorted(missing)[:3]}")
    return problems


def main() -> None:
    dwg_dir, dxf_dir, inv_dir = (Path(p) for p in sys.argv[1:4])
    for dwg in sorted(dwg_dir.glob("*.dwg")):
        ref = json.loads((inv_dir / f"{dwg.stem}.json").read_text(encoding="utf-8"))
        t0 = time.time()
        drawing = read_drawing(dwg)
        t1 = time.time()
        a = analyse(drawing)
        svg = render_svg(drawing)
        t2 = time.time()
        problems = compare(dwg.name, a, ref)
        status = "OK " if not problems else "DIFF"
        print(
            f"[{status}] DWG {dwg.name:40} read {t1 - t0:4.1f}s  analyse+svg {t2 - t1:4.1f}s  "
            f"svg {len(svg) / 1e6:4.1f} MB  objects={a['totals']['objects']}"
        )
        for p in problems:
            print("        -", p)

        dxf = dxf_dir / f"{dwg.stem}.dxf"
        if dxf.exists():
            b = analyse(read_drawing(dxf))
            problems = compare(dxf.name, b, ref)
            print(f"[{'OK ' if not problems else 'DIFF'}] DXF {dxf.name:40}")
            for p in problems:
                print("        -", p)


if __name__ == "__main__":
    main()
