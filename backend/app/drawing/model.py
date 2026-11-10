from dataclasses import dataclass, field
from typing import Any

Point = tuple[float, float]


@dataclass(slots=True)
class Entity:
    """One drawing object, format-independent.

    ``type`` uses DXF names (LINE, ARC, CIRCLE, LWPOLYLINE, TEXT, MTEXT, INSERT, ...).
    ``data`` holds the geometry, with these keys per type:
      LINE        start, end
      ARC         center, radius, start_angle, end_angle   (degrees, counter-clockwise)
      CIRCLE      center, radius
      ELLIPSE     center, major_axis, axis_ratio, start_param, end_param
      LWPOLYLINE  points, bulges, closed       (old-style POLYLINE is normalised to this)
      SOLID       points
      HATCH       paths [list of point lists], solid
      TEXT/MTEXT/ATTRIB  text, insert, height, rotation
      INSERT      name, insert, xscale, yscale, rotation, attribs {tag: value}
      DIMENSION   points
    """

    type: str
    layer: str
    color: int  # AutoCAD color index; 0 = BYBLOCK, 256 = BYLAYER (already resolved when possible)
    data: dict[str, Any]
    handle: int = 0


@dataclass(slots=True)
class Drawing:
    source_format: str  # "dwg" | "dxf"
    version: str  # e.g. "AC1015"
    reader: str  # library + version that read the file
    modelspace: list[Entity]
    blocks: dict[str, list[Entity]]
    layers: dict[str, int]  # layer name -> color index
    insunits: int | None = None
    notes: list[str] = field(default_factory=list)  # anything the reader could not handle
