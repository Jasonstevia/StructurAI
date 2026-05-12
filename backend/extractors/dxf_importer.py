from __future__ import annotations

from pathlib import Path
import os

from backend.core.structura_model import ExtractedContext


def extract_dxf_context(path: Path) -> ExtractedContext:
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/structurai-cache")
    try:
        import ezdxf
    except ImportError as exc:
        raise RuntimeError("DXF extraction requires ezdxf.") from exc

    doc = ezdxf.readfile(path)
    modelspace = doc.modelspace()
    layers: dict[str, int] = {}
    lines: list[dict[str, object]] = []
    for entity in modelspace:
        layer = entity.dxf.layer
        layers[layer] = layers.get(layer, 0) + 1
        if entity.dxftype() == "LINE":
            lines.append(
                {
                    "layer": layer,
                    "start": [float(entity.dxf.start.x), float(entity.dxf.start.y), float(entity.dxf.start.z)],
                    "end": [float(entity.dxf.end.x), float(entity.dxf.end.y), float(entity.dxf.end.z)],
                }
            )
        elif entity.dxftype() in {"LWPOLYLINE", "POLYLINE"}:
            points = [[float(point[0]), float(point[1])] for point in entity.get_points()]
            lines.append({"layer": layer, "polyline": points})
    return ExtractedContext(source_path=str(path), file_type="dxf", layers=layers, lines=lines, notes=[f"Extracted {len(lines)} lightweight line/polyline entities."])
