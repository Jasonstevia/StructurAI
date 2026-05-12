from __future__ import annotations

import json
import math
import os
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

    score = _check_minimums(entity_counts, layer_count, issues, score)
    missing_layers = sorted(REQUIRED_LAYERS - layers)
    if missing_layers:
        score -= min(20, len(missing_layers) * 3)
        issues.append(DrawingReviewIssue("LAYERS_MISSING", "error", f"Missing required drafting layers: {', '.join(missing_layers)}."))

    all_text = "\n".join(text_values)
    missing_text = sorted(required for required in REQUIRED_TEXT if required not in all_text)
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


def _check_minimums(entity_counts: dict[str, int], layer_count: int, issues: list[DrawingReviewIssue], score: int) -> int:
    minimums = {
        "TEXT": 400,
        "LINE": 400,
        "LWPOLYLINE": 95,
        "HATCH": 30,
        "CIRCLE": 24,
    }
    for dxftype, minimum in minimums.items():
        actual = entity_counts.get(dxftype, 0)
        if actual < minimum:
            score -= 10
            issues.append(DrawingReviewIssue("ENTITY_DENSITY_LOW", "error", f"Expected at least {minimum} {dxftype} entities, found {actual}."))
    if layer_count < 16:
        score -= 10
        issues.append(DrawingReviewIssue("LAYER_DENSITY_LOW", "error", f"Expected at least 16 active layers, found {layer_count}."))
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
        return DrawingReviewIssue("PREVIEW_RENDER_FAILED", "warning", f"Could not render DXF preview: {exc}")


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
