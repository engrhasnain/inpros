from pathlib import Path

from app.drawing.model import Drawing

SUPPORTED_SUFFIXES = {".dwg", ".dxf"}


class DrawingReadError(RuntimeError):
    pass


def read_drawing(path: Path) -> Drawing:
    suffix = path.suffix.lower()
    try:
        if suffix == ".dwg":
            from app.drawing.dwg_reader import read_dwg

            return read_dwg(path)
        if suffix == ".dxf":
            from app.drawing.dxf_reader import read_dxf

            return read_dxf(path)
    except Exception as exc:  # readers raise many different error types
        raise DrawingReadError(f"Could not read {path.name}: {exc}") from exc
    raise DrawingReadError(f"Unsupported file type: {suffix}")
