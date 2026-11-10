"""Turn an uploaded drawing file into stored analysis, takeoff and preview."""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app import files
from app.drawing import read_drawing
from app.drawing.analysis import analyse
from app.drawing.svg import render_svg
from app.takeoff import compute_takeoff

ANALYSIS_FILE = "analysis.json"
TAKEOFF_FILE = "takeoff.json"
PREVIEW_FILE = "preview.svg"


def process_drawing(source: Path, db: Session | None = None) -> dict:
    """Read, analyse, take off and render a drawing; files are written next to the source.
    ``db``: the caller's session when called inside a request transaction."""
    files.ensure(source)
    drawing = read_drawing(source)
    analysis = analyse(drawing)
    takeoff = compute_takeoff(drawing)
    focus = [s["box"] for s in takeoff["sheets"] if s["box"]]
    files.write_text(source.parent / ANALYSIS_FILE, json.dumps(analysis, ensure_ascii=False), db)
    files.write_text(source.parent / TAKEOFF_FILE, json.dumps(takeoff, ensure_ascii=False), db)
    files.write_text(source.parent / PREVIEW_FILE, render_svg(drawing, focus=focus), db)
    return analysis


def load_takeoff(source: Path) -> dict:
    """Takeoff for a stored drawing; computed on demand for files processed before it existed."""
    path = source.parent / TAKEOFF_FILE
    if not files.ensure(path):
        process_drawing(source)
    return json.loads(path.read_text(encoding="utf-8"))


def load_analysis(source: Path) -> dict:
    path = analysis_path(source)
    if not files.ensure(path):
        process_drawing(source)
    return json.loads(path.read_text(encoding="utf-8"))


def analysis_path(source: Path) -> Path:
    return source.parent / ANALYSIS_FILE


def preview_path(source: Path) -> Path:
    return source.parent / PREVIEW_FILE
