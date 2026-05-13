from __future__ import annotations

import json
import math
import os
import struct
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DrawingReviewIssue:
    code: str
    severity: str
    message: str


@dataclass
class DrawingReviewReport:
    passed: bool
    score: int
    issues: list[DrawingReviewIssue] = field(default_factory=list)
    entity_counts: dict[str, int] = field(default_factory=dict)
    layer_count: int = 0
    extents: dict[str, float] = field(default_factory=dict)
    image_metrics: dict[str, Any] = field(default_factory=dict)
    preview_path: str | None = None

    def errors(self) -> list[DrawingReviewIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


REQUIRED_LAYERS = {
    "SAI-A-DIMS",
    "SAI-A-GRID",
    "SAI-A-SECTION",
    "SAI-S-FOOTING",
    "SAI-S-COLUMN",
    "SAI-S-BEAM",
    "SAI-S-SLAB",
    "SAI-S-REBAR",
    "SAI-SCHEDULE",
    "SAI-H-CONCRETE",
    "SAI-H-SOIL",
}

REQUIRED_TEXT = {
    "FOUNDATION PLAN",
    "ROOF FRAMING",
    "SECTION A-A",
    "SECTION B-B",
    "TYPICAL ISOLATED FOOTING",
    "BAR BENDING SCHEDULE",
    "FOOTING SCHEDULE",
    "COLUMN SCHEDULE",
    "BEAM SCHEDULE",
    "MATERIAL TAKEOFF",
    "REINFORCEMENT LEGEND",
}

STEEL_REQUIRED_LAYERS = {
    "SAI-A-DIMS",
    "SAI-A-TEXT",
    "SAI-A-TITLE",
    "SAI-S-STEEL",
    "SAI-S-BRACE",
    "SAI-SCHEDULE",
}

STEEL_REQUIRED_TEXT = {
    "STEEL BRACING COMMENT RESOLUTION",
    "RESPONSE TO RED-PEN COMMENT",
    "CONNECTION NOTES",
    "STEEL MEMBER SCHEDULE",
}

PIPE_SUPPORT_REQUIRED_TEXT = {
    "FIRE-FIGHTING PIPE SUPPORT COORDINATION",
    "PIPE SUPPORT",
    "STEEL MEMBER SCHEDULE",
    "CONNECTION NOTES",
}

PIPE_SUPPORT_REQUIRED_LAYERS = {
    "SAI-A-DIMS",
    "SAI-A-TEXT",
    "SAI-A-TITLE",
    "SAI-S-STEEL",
    "SAI-SCHEDULE",
}


def review_dxf(dxf_path: Path, preview_path: Path | None = None) -> DrawingReviewReport:
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/structurai-cache")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/structurai-mpl")
    try:
        import ezdxf
    except ImportError as exc:
        return DrawingReviewReport(False, 0, [DrawingReviewIssue("DXF_REVIEW_IMPORT", "error", f"ezdxf unavailable: {exc}")])

    issues: list[DrawingReviewIssue] = []
    score = 100
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as exc:
        return DrawingReviewReport(False, 0, [DrawingReviewIssue("DXF_OPEN_FAILED", "error", str(exc))])

    audit = doc.audit()
    if audit.errors:
        score -= 35
        issues.append(DrawingReviewIssue("DXF_AUDIT_ERRORS", "error", f"DXF audit found {len(audit.errors)} error(s)."))

    msp = doc.modelspace()
    entities = list(msp)
    entity_counts: dict[str, int] = {}
    layers: set[str] = set()
    text_values: list[str] = []
    text_boxes: list[tuple[float, float, float, float]] = []
    min_x = min_y = math.inf
    max_x = max_y = -math.inf

    for entity in entities:
        dxftype = entity.dxftype()
        entity_counts[dxftype] = entity_counts.get(dxftype, 0) + 1
        layers.add(entity.dxf.layer)
        if dxftype in {"TEXT", "MTEXT"}:
            text = entity.dxf.text if dxftype == "TEXT" else entity.text
            text_values.append(str(text).upper())
            try:
                insert = entity.dxf.insert
                height = float(entity.dxf.height)
                width = max(height * 1.8, len(str(text)) * height * 0.58)
                text_boxes.append((float(insert.x), float(insert.y), float(insert.x) + width, float(insert.y) + height * 1.3))
            except Exception:
                pass

    try:
        from ezdxf import bbox

        ext = bbox.extents(entities)
        if ext.has_data:
            min_x = float(ext.extmin.x)
            min_y = float(ext.extmin.y)
            max_x = float(ext.extmax.x)
            max_y = float(ext.extmax.y)
    except Exception:
        pass

    layer_count = len(layers)
    extents = {
        "min_x": 0.0 if math.isinf(min_x) else min_x,
        "min_y": 0.0 if math.isinf(min_y) else min_y,
        "max_x": 0.0 if math.isinf(max_x) else max_x,
        "max_y": 0.0 if math.isinf(max_y) else max_y,
    }

    all_text = "\n".join(text_values)
    pipe_support_package = "FIRE-FIGHTING PIPE SUPPORT COORDINATION" in all_text
    steel_package = pipe_support_package or "STEEL BRACING COMMENT RESOLUTION" in all_text or "SAI-S-STEEL" in layers

    score = _check_minimums(entity_counts, layer_count, issues, score, steel_package=steel_package)
    if pipe_support_package:
        required_layers = PIPE_SUPPORT_REQUIRED_LAYERS
    else:
        required_layers = STEEL_REQUIRED_LAYERS if steel_package else REQUIRED_LAYERS
    missing_layers = sorted(required_layers - layers)
    if missing_layers:
        score -= min(20, len(missing_layers) * 3)
        issues.append(DrawingReviewIssue("LAYERS_MISSING", "error", f"Missing required drafting layers: {', '.join(missing_layers)}."))

    if pipe_support_package:
        required_text = PIPE_SUPPORT_REQUIRED_TEXT
    else:
        required_text = STEEL_REQUIRED_TEXT if steel_package else REQUIRED_TEXT
    missing_text = sorted(required for required in required_text if required not in all_text)
    if missing_text:
        score -= min(24, len(missing_text) * 4)
        issues.append(DrawingReviewIssue("DRAWING_LABELS_MISSING", "error", f"Missing required drawing labels: {', '.join(missing_text)}."))

    overlap_count = _count_text_overlaps(text_boxes)
    if overlap_count > 35:
        score -= 8
        issues.append(DrawingReviewIssue("TEXT_OVERLAP_RISK", "warning", f"Approximate text overlap count is high: {overlap_count}."))

    image_metrics: dict[str, Any] = {}
    if preview_path:
        render_issue = _render_preview(doc, preview_path)
        if render_issue:
            score -= 5
            issues.append(render_issue)
        elif preview_path.exists():
            image_metrics = _image_metrics(preview_path)
            if image_metrics.get("non_background_ratio", 0) < 0.015:
                score -= 20
                issues.append(DrawingReviewIssue("PREVIEW_TOO_EMPTY", "error", "Rendered preview is almost blank."))
            if image_metrics.get("occupied_grid_cells", 0) < 4:
                score -= 8
                issues.append(DrawingReviewIssue("PREVIEW_POOR_SPREAD", "warning", "Rendered drawing package occupies too few preview regions."))

    score = max(0, min(100, score))
    passed = score >= 85 and not any(issue.severity == "error" for issue in issues)
    return DrawingReviewReport(
        passed=passed,
        score=score,
        issues=issues,
        entity_counts=entity_counts,
        layer_count=layer_count,
        extents=extents,
        image_metrics=image_metrics,
        preview_path=str(preview_path) if preview_path and preview_path.exists() else None,
    )


def _check_minimums(entity_counts: dict[str, int], layer_count: int, issues: list[DrawingReviewIssue], score: int, steel_package: bool = False) -> int:
    if steel_package:
        minimums = {
            "TEXT": 120,
            "LINE": 100,
            "LWPOLYLINE": 25,
        }
        layer_minimum = 8
    else:
        minimums = {
            "TEXT": 400,
            "LINE": 400,
            "LWPOLYLINE": 95,
            "HATCH": 30,
            "CIRCLE": 24,
        }
        layer_minimum = 16
    for dxftype, minimum in minimums.items():
        actual = entity_counts.get(dxftype, 0)
        if actual < minimum:
            score -= 10
            issues.append(DrawingReviewIssue("ENTITY_DENSITY_LOW", "error", f"Expected at least {minimum} {dxftype} entities, found {actual}."))
    if layer_count < layer_minimum:
        score -= 10
        issues.append(DrawingReviewIssue("LAYER_DENSITY_LOW", "error", f"Expected at least {layer_minimum} active layers, found {layer_count}."))
    return score


def _count_text_overlaps(boxes: list[tuple[float, float, float, float]]) -> int:
    count = 0
    for index, a in enumerate(boxes):
        for b in boxes[index + 1 :]:
            if a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]:
                count += 1
                if count > 100:
                    return count
    return count


def _render_preview(doc, preview_path: Path) -> DrawingReviewIssue | None:
    try:
        from ezdxf.addons.drawing import matplotlib as ezplt

        preview_path.parent.mkdir(parents=True, exist_ok=True)
        ezplt.qsave(doc.modelspace(), preview_path, bg="#1f2933")
        return None
    except Exception as exc:
        try:
            _render_lightweight_preview(doc, preview_path)
            return DrawingReviewIssue("PREVIEW_RENDER_FALLBACK", "warning", f"Used lightweight preview renderer because full CAD preview failed: {exc}")
        except Exception as fallback_exc:
            return DrawingReviewIssue("PREVIEW_RENDER_FAILED", "warning", f"Could not render DXF preview: {exc}; fallback failed: {fallback_exc}")


def _render_lightweight_preview(doc, preview_path: Path, width: int = 1400, height: int = 900) -> None:
    entities = list(doc.modelspace())
    min_x, min_y, max_x, max_y = _preview_extents(entities)
    if max_x <= min_x or max_y <= min_y:
        raise ValueError("no drawable extents")

    bg = (31, 41, 51)
    pixels = [bytearray(bg * width) for _ in range(height)]
    margin = 40
    scale = min((width - 2 * margin) / max(max_x - min_x, 1), (height - 2 * margin) / max(max_y - min_y, 1))

    def transform(x: float, y: float) -> tuple[int, int]:
        px = int(margin + (x - min_x) * scale)
        py = int(height - margin - (y - min_y) * scale)
        return px, py

    for entity in entities:
        color = _layer_color(entity.dxf.layer)
        dxftype = entity.dxftype()
        try:
            if dxftype == "LINE":
                _draw_line(pixels, *transform(float(entity.dxf.start.x), float(entity.dxf.start.y)), *transform(float(entity.dxf.end.x), float(entity.dxf.end.y)), color)
            elif dxftype == "LWPOLYLINE":
                points = [(float(point[0]), float(point[1])) for point in entity.get_points()]
                _draw_polyline_preview(pixels, points, transform, color, bool(entity.closed))
            elif dxftype == "POLYLINE":
                points = [(float(vertex.dxf.location.x), float(vertex.dxf.location.y)) for vertex in entity.vertices]
                _draw_polyline_preview(pixels, points, transform, color, bool(entity.is_closed))
            elif dxftype == "CIRCLE":
                center = entity.dxf.center
                radius = float(entity.dxf.radius)
                previous: tuple[float, float] | None = None
                for step in range(37):
                    angle = math.tau * step / 36
                    current = (float(center.x) + math.cos(angle) * radius, float(center.y) + math.sin(angle) * radius)
                    if previous:
                        _draw_line(pixels, *transform(*previous), *transform(*current), color)
                    previous = current
            elif dxftype in {"TEXT", "MTEXT"}:
                insert = entity.dxf.insert
                x, y = transform(float(insert.x), float(insert.y))
                _draw_line(pixels, x, y, x + 14, y, color)
        except Exception:
            continue

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    _write_png(preview_path, width, height, pixels)


def _preview_extents(entities) -> tuple[float, float, float, float]:
    try:
        from ezdxf import bbox

        ext = bbox.extents(entities)
        if ext.has_data:
            return float(ext.extmin.x), float(ext.extmin.y), float(ext.extmax.x), float(ext.extmax.y)
    except Exception:
        pass
    xs: list[float] = []
    ys: list[float] = []
    for entity in entities:
        try:
            if entity.dxftype() == "LINE":
                xs.extend([float(entity.dxf.start.x), float(entity.dxf.end.x)])
                ys.extend([float(entity.dxf.start.y), float(entity.dxf.end.y)])
            elif entity.dxftype() == "LWPOLYLINE":
                for point in entity.get_points():
                    xs.append(float(point[0]))
                    ys.append(float(point[1]))
            elif entity.dxftype() == "CIRCLE":
                center = entity.dxf.center
                radius = float(entity.dxf.radius)
                xs.extend([float(center.x) - radius, float(center.x) + radius])
                ys.extend([float(center.y) - radius, float(center.y) + radius])
        except Exception:
            continue
    if not xs or not ys:
        return 0.0, 0.0, 1.0, 1.0
    return min(xs), min(ys), max(xs), max(ys)


def _layer_color(layer: str) -> tuple[int, int, int]:
    palette = [
        (238, 242, 255),
        (125, 211, 252),
        (251, 191, 36),
        (248, 113, 113),
        (134, 239, 172),
        (216, 180, 254),
    ]
    return palette[sum(ord(char) for char in layer) % len(palette)]


def _draw_polyline_preview(pixels: list[bytearray], points: list[tuple[float, float]], transform, color: tuple[int, int, int], closed: bool) -> None:
    if len(points) < 2:
        return
    transformed = [transform(x, y) for x, y in points]
    for start, end in zip(transformed, transformed[1:]):
        _draw_line(pixels, *start, *end, color)
    if closed:
        _draw_line(pixels, *transformed[-1], *transformed[0], color)


def _draw_line(pixels: list[bytearray], x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    width = len(pixels[0]) // 3
    height = len(pixels)
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        for ox, oy in ((0, 0), (1, 0), (0, 1)):
            px, py = x + ox, y + oy
            if 0 <= px < width and 0 <= py < height:
                offset = px * 3
                pixels[py][offset : offset + 3] = bytes(color)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _write_png(path: Path, width: int, height: int, pixels: list[bytearray]) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, level=6))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def _image_metrics(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError:
        return {}

    image = Image.open(path).convert("RGB")
    width, height = image.size
    bg = image.getpixel((0, 0))
    non_bg = 0
    colored = 0
    cells = [[0 for _ in range(3)] for _ in range(3)]
    pixels = image.load()
    stride = max(1, min(width, height) // 900)
    samples = 0
    for y in range(0, height, stride):
        for x in range(0, width, stride):
            samples += 1
            r, g, b = pixels[x, y]
            dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
            if dist > 24:
                non_bg += 1
                cells[min(2, y * 3 // height)][min(2, x * 3 // width)] += 1
                if max(r, g, b) - min(r, g, b) > 35:
                    colored += 1
    occupied = sum(1 for row in cells for value in row if value / max(1, samples / 9) > 0.003)
    return {
        "width_px": width,
        "height_px": height,
        "non_background_ratio": non_bg / max(samples, 1),
        "colored_ratio": colored / max(samples, 1),
        "occupied_grid_cells": occupied,
    }
