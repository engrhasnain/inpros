"""Render a drawing's model space to SVG (white background, AutoCAD colors adapted for paper)."""

from html import escape

from app.drawing.geometry import apply, iter_expanded, matrix_rotation_deg, matrix_scale_y, outline_points
from app.drawing.model import Drawing

# AutoCAD color index -> colors readable on white. 7 (white/black) is drawn black.
ACI = {
    1: "#d62728", 2: "#b8a000", 3: "#2ca02c", 4: "#0e9aa7", 5: "#1f4fd6",
    6: "#b5179e", 7: "#222222", 8: "#7f7f7f", 9: "#a8a8a8",
}
DEFAULT_COLOR = "#555555"
TEXT_TYPES = {"TEXT", "MTEXT", "ATTRIB"}


def _color(index: int, layer_color: int) -> str:
    c = layer_color if index in (256, None) else index
    return ACI.get(abs(c), DEFAULT_COLOR)


def _bounds(xs: list[float], ys: list[float]) -> tuple[float, float, float, float]:
    """Full extent of everything drawn. Nothing is trimmed: objects parked outside
    the plan are real content and would otherwise be counted without being seen."""
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pad = max(x1 - x0, y1 - y0) * 0.02 or 1.0
    return x0 - pad, y0 - pad, x1 + pad, y1 + pad


def render_svg(drawing: Drawing, focus: list[list[float]] | None = None) -> str:
    """``focus``: sheet boxes [x0, y0, x1, y1] to frame by default (objects outside are still drawn)."""
    paths: dict[str, list[str]] = {}
    fills: list[tuple[str, str]] = []
    texts: list[str] = []
    xs: list[float] = []
    ys: list[float] = []

    for ent, m, color_index in iter_expanded(drawing.modelspace, drawing.blocks):
        color = _color(color_index, drawing.layers.get(ent.layer, 7))
        if ent.type in TEXT_TYPES:
            text = ent.data.get("text", "").strip()
            if not text:
                continue
            x, y = apply(m, ent.data["insert"])
            h = ent.data["height"] * matrix_scale_y(m)
            rot = ent.data["rotation"] + matrix_rotation_deg(m)
            lines = text.splitlines() or [text]
            spans = "".join(
                f'<tspan x="0" dy="{(h * 1.3 if i else 0):.3f}">{escape(line)}</tspan>' for i, line in enumerate(lines)
            )
            texts.append(
                f'<text transform="translate({x:.3f},{-y:.3f}) rotate({-rot:.2f})" '
                f'font-size="{h:.3f}" fill="{color}">{spans}</text>'
            )
            xs.append(x)
            ys.append(-y)
            continue
        if ent.type == "HATCH":
            for path in ent.data["paths"]:
                pts = [apply(m, p) for p in path]
                d = "M" + " L".join(f"{x:.3f},{-y:.3f}" for x, y in pts) + " Z"
                if ent.data.get("solid"):
                    fills.append((color, d))
                else:
                    paths.setdefault(color, []).append(d)
            continue
        pts = outline_points(ent)
        if not pts or len(pts) < 2:
            continue
        world = [apply(m, p) for p in pts]
        d = "M" + " L".join(f"{x:.3f},{-y:.3f}" for x, y in world)
        if ent.type == "SOLID":
            fills.append((color, d + " Z"))
        else:
            paths.setdefault(color, []).append(d)
        for x, y in world:
            xs.append(x)
            ys.append(-y)

    if not xs:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><text x="10" y="25">Empty drawing</text></svg>'

    if focus:
        # frame the sheets; SVG y is flipped, so sheet y-ranges become negative
        fx0 = min(b[0] for b in focus)
        fx1 = max(b[2] for b in focus)
        fy0 = min(-b[3] for b in focus)
        fy1 = max(-b[1] for b in focus)
        pad = max(fx1 - fx0, fy1 - fy0) * 0.02
        x0, y0, x1, y1 = fx0 - pad, fy0 - pad, fx1 + pad, fy1 + pad
    else:
        x0, y0, x1, y1 = _bounds(xs, ys)
    w, h = x1 - x0, y1 - y0
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.3f} {y0:.3f} {w:.3f} {h:.3f}" '
        f'preserveAspectRatio="xMidYMid meet" font-family="Arial, sans-serif">',
        f'<rect x="{x0:.3f}" y="{y0:.3f}" width="{w:.3f}" height="{h:.3f}" fill="#ffffff"/>',
    ]
    for color, d in fills:
        out.append(f'<path d="{d}" fill="{color}" fill-opacity="0.35" stroke="none"/>')
    for color, ds in paths.items():
        out.append(
            f'<path d="{" ".join(ds)}" fill="none" stroke="{color}" stroke-width="1" '
            f'vector-effect="non-scaling-stroke" stroke-linecap="round"/>'
        )
    out.append('<g stroke="none">')
    out.extend(texts)
    out.append("</g></svg>")
    return "\n".join(out)
