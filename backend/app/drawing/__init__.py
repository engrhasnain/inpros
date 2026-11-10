"""Drawing reading, analysis and preview.

Readers (DWG via ezdwg, DXF via ezdxf) produce the same small in-memory model,
so analysis and rendering do not depend on the file format.
"""

from app.drawing.model import Drawing, Entity
from app.drawing.reader import read_drawing

__all__ = ["Drawing", "Entity", "read_drawing"]
