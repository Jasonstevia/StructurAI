from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

from backend.core.structura_model import Beam, Column, Footing, Opening, Point2D, RebarSpec, Slab, SteelMember, StripFooting, StructuraProject, Wall


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> Point2D:
        return Point2D(x=(self.min_x + self.max_x) / 2, y=(self.min_y + self.max_y) / 2)

    def shift(self, point: Point2D, origin: Point2D) -> Point2D:
        return Point2D(x=origin.x + point.x - self.min_x, y=origin.y + point.y - self.min_y)


@dataclass(frozen=True)
class BarScheduleRow:
    mark: str
    element: str
    bar: str
    spacing_or_qty: str
    length_mm: float
    count: int
    total_weight_kg: float
    shape: str


def export_dxf(project: StructuraProject, path: Path) -> Path:
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/structurai-cache")
    try:
        import ezdxf
    except ImportError as exc:
        raise RuntimeError("DXF export requires ezdxf.") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    _setup_layers(doc)
    _setup_styles(doc)

    msp = doc.modelspace()
    bounds = _project_bounds(project)
    framing_levels = _framing_elevations(project)
    plan_gap = max(9000.0, bounds.width + 5500.0)
    framing_stack_height = max(1, len(framing_levels)) * (bounds.height + 3000.0)
    row_gap = max(9500.0, bounds.height + 7000.0, framing_stack_height + 4500.0)

    foundation_origin = Point2D(x=0, y=0)
    roof_origin = Point2D(x=plan_gap, y=0)
    section_a_origin = Point2D(x=0, y=-row_gap)
    section_b_origin = Point2D(x=plan_gap, y=-row_gap)
    details_origin = Point2D(x=0, y=-2 * row_gap)
    schedules_origin = Point2D(x=plan_gap, y=-2 * row_gap)

    _draw_package_title(msp, project, Point2D(x=0, y=bounds.height + 3600), plan_gap + bounds.width + 3500)
    _draw_foundation_plan(msp, project, bounds, foundation_origin)
    _draw_roof_plan(msp, project, bounds, roof_origin)
    _draw_section(msp, project, bounds, section_a_origin, "A-A", along="x")
    _draw_section(msp, project, bounds, section_b_origin, "B-B", along="y")
    _draw_detail_sheet(msp, project, details_origin)
    _draw_schedule_sheet(msp, project, schedules_origin)
    if project.steel_members:
        _draw_steel_repair_sheet(msp, project, Point2D(x=0, y=-3 * row_gap))
    _draw_title_block(msp, project, Point2D(x=plan_gap + bounds.width + 2200, y=-2 * row_gap), height=12000)

    doc.saveas(path)
    return path


def _setup_layers(doc) -> None:
    layers = {
        "SAI-A-BORDER": (7, 25),
        "SAI-A-TEXT": (4, 13),
        "SAI-A-TITLE": (6, 30),
        "SAI-A-DIMS": (6, 13),
        "SAI-A-GRID": (1, 13),
        "SAI-A-SECTION": (1, 25),
        "SAI-S-CONCRETE": (30, 35),
        "SAI-S-CONCRETE-CUT": (1, 40),
        "SAI-S-FOOTING": (2, 35),
        "SAI-S-COLUMN": (5, 35),
        "SAI-S-BEAM": (30, 35),
        "SAI-S-SLAB": (4, 25),
        "SAI-S-WALL": (5, 45),
        "SAI-S-STEEL": (5, 35),
        "SAI-S-BRACE": (1, 35),
        "SAI-S-OPENING": (1, 25),
        "SAI-S-REBAR": (1, 25),
        "SAI-S-TIES": (3, 20),
        "SAI-H-CONCRETE": (8, 13),
        "SAI-H-SOIL": (8, 13),
        "SAI-H-GREEN": (3, 13),
        "SAI-H-PAVING": (2, 13),
        "SAI-X-REFERENCE": (9, 13),
        "SAI-SCHEDULE": (4, 13),
    }
    for name, (color, weight) in layers.items():
        if name in doc.layers:
            layer = doc.layers.get(name)
        else:
            layer = doc.layers.add(name, color=color)
        layer.dxf.color = color
        layer.dxf.lineweight = weight


def _setup_styles(doc) -> None:
    if "SAI-STANDARD" not in doc.styles:
        doc.styles.add("SAI-STANDARD", font="txt.shx")


def _project_bounds(project: StructuraProject) -> Bounds:
    xs: list[float] = []
    ys: list[float] = []
    for footing in project.footings:
        xs.extend([footing.center.x - footing.width_mm / 2, footing.center.x + footing.width_mm / 2])
        ys.extend([footing.center.y - footing.length_mm / 2, footing.center.y + footing.length_mm / 2])
    for strip in project.strip_footings:
        xs.extend([strip.start.x, strip.end.x])
        ys.extend([strip.start.y, strip.end.y])
    for column in project.columns:
        xs.extend([column.center.x - column.width_mm / 2, column.center.x + column.width_mm / 2])
        ys.extend([column.center.y - column.depth_mm / 2, column.center.y + column.depth_mm / 2])
    for wall in project.walls:
        xs.extend([wall.start.x, wall.end.x])
        ys.extend([wall.start.y, wall.end.y])
    for member in project.steel_members:
        xs.extend([member.start.x, member.end.x])
        ys.extend([member.start.z, member.end.z])
    for slab in project.slabs:
        xs.extend(point.x for point in slab.boundary)
        ys.extend(point.y for point in slab.boundary)
    for beam in project.beams:
        xs.extend([beam.start.x, beam.end.x])
        ys.extend([beam.start.y, beam.end.y])
    if not xs or not ys:
        return Bounds(0, 0, 5000, 5000)
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def _rect_points(center: Point2D, width: float, height: float) -> list[tuple[float, float]]:
    x0 = center.x - width / 2
    y0 = center.y - height / 2
    return [(x0, y0), (x0 + width, y0), (x0 + width, y0 + height), (x0, y0 + height)]


def _add_text(msp, text: str, x: float, y: float, height: float = 150, layer: str = "SAI-A-TEXT", rotation: float = 0) -> None:
    msp.add_text(
        text,
        dxfattribs={"height": height, "layer": layer, "style": "SAI-STANDARD", "rotation": rotation},
    ).set_placement((x, y))


def _add_multiline(msp, text: str, x: float, y: float, height: float = 140, layer: str = "SAI-A-TEXT", line_gap: float = 1.45) -> None:
    for index, line in enumerate(text.splitlines()):
        _add_text(msp, line, x, y - index * height * line_gap, height, layer)


def _add_polyline(msp, points: list[tuple[float, float]], layer: str, closed: bool = True, width: float = 0) -> None:
    pts = points + [points[0]] if closed and points[0] != points[-1] else points
    msp.add_lwpolyline(pts, dxfattribs={"layer": layer, "const_width": width})


def _add_hatch(msp, points: list[tuple[float, float]], layer: str, pattern: str = "ANSI31", scale: float = 120, angle: float = 45, color: int = 8) -> None:
    hatch = msp.add_hatch(color=color, dxfattribs={"layer": layer})
    hatch.set_pattern_fill(pattern, scale=scale, angle=angle)
    hatch.paths.add_polyline_path(points, is_closed=True)


def _add_solid_hatch(msp, points: list[tuple[float, float]], layer: str, color: int) -> None:
    hatch = msp.add_hatch(color=color, dxfattribs={"layer": layer})
    hatch.set_solid_fill(color=color)
    hatch.paths.add_polyline_path(points, is_closed=True)


def _draw_rect(msp, center: Point2D, width: float, height: float, layer: str, hatch_layer: str | None = None, hatch_pattern: str = "ANSI31") -> None:
    points = _rect_points(center, width, height)
    if hatch_layer:
        _add_hatch(msp, points, hatch_layer, pattern=hatch_pattern)
    _add_polyline(msp, points, layer)


def _draw_package_title(msp, project: StructuraProject, origin: Point2D, width: float) -> None:
    _add_text(msp, project.title.upper(), origin.x, origin.y, 360, "SAI-A-TITLE")
    _add_text(msp, "STRUCTURAL CAD PACKAGE - GENERATED FROM VALIDATED STRUCTURAI JSON MODEL", origin.x, origin.y - 420, 180, "SAI-A-TEXT")
    msp.add_line((origin.x, origin.y - 620), (origin.x + width, origin.y - 620), dxfattribs={"layer": "SAI-A-BORDER"})


def _draw_view_title(msp, title: str, scale: str, origin: Point2D, width: float = 4500) -> None:
    _add_text(msp, title.upper(), origin.x, origin.y, 220, "SAI-A-TITLE")
    msp.add_line((origin.x, origin.y - 80), (origin.x + width, origin.y - 80), dxfattribs={"layer": "SAI-A-TITLE"})
    _add_text(msp, f"SCALE {scale}", origin.x, origin.y - 300, 130, "SAI-A-TEXT")


def _draw_grid_bubble(msp, x: float, y: float, label: str, radius: float = 150) -> None:
    msp.add_circle((x, y), radius, dxfattribs={"layer": "SAI-A-GRID"})
    _add_text(msp, label, x - radius / 3, y - radius / 3, radius * 1.15, "SAI-A-GRID")


def _draw_grid(msp, project: StructuraProject, bounds: Bounds, origin: Point2D) -> None:
    ext = 850
    xs = [grid for grid in project.grid_lines if grid.axis == "x"]
    ys = [grid for grid in project.grid_lines if grid.axis == "y"]
    for grid in xs:
        x = origin.x + grid.offset_mm - bounds.min_x
        y0 = origin.y - ext
        y1 = origin.y + bounds.height + ext
        msp.add_line((x, y0), (x, y1), dxfattribs={"layer": "SAI-A-GRID"})
        _draw_grid_bubble(msp, x, y1 + 230, grid.label)
    for grid in ys:
        y = origin.y + grid.offset_mm - bounds.min_y
        x0 = origin.x - ext
        x1 = origin.x + bounds.width + ext
        msp.add_line((x0, y), (x1, y), dxfattribs={"layer": "SAI-A-GRID"})
        _draw_grid_bubble(msp, x0 - 230, y, grid.label)


def _draw_dimension(msp, start: Point2D, end: Point2D, offset: float, label: str | None = None, layer: str = "SAI-A-DIMS") -> None:
    dx = end.x - start.x
    dy = end.y - start.y
    horizontal = abs(dx) >= abs(dy)
    text = label or f"{math.hypot(dx, dy):.0f}"
    tick = 80
    if horizontal:
        y = start.y + offset
        msp.add_line((start.x, y), (end.x, y), dxfattribs={"layer": layer})
        msp.add_line((start.x, start.y), (start.x, y + math.copysign(120, offset)), dxfattribs={"layer": layer})
        msp.add_line((end.x, end.y), (end.x, y + math.copysign(120, offset)), dxfattribs={"layer": layer})
        for x in (start.x, end.x):
            msp.add_line((x - tick, y - tick), (x + tick, y + tick), dxfattribs={"layer": layer})
        _add_text(msp, text, (start.x + end.x) / 2 - len(text) * 28, y + math.copysign(120, offset), 120, layer)
    else:
        x = start.x + offset
        msp.add_line((x, start.y), (x, end.y), dxfattribs={"layer": layer})
        msp.add_line((start.x, start.y), (x + math.copysign(120, offset), start.y), dxfattribs={"layer": layer})
        msp.add_line((end.x, end.y), (x + math.copysign(120, offset), end.y), dxfattribs={"layer": layer})
        for y in (start.y, end.y):
            msp.add_line((x - tick, y + tick), (x + tick, y - tick), dxfattribs={"layer": layer})
        _add_text(msp, text, x + math.copysign(120, offset), (start.y + end.y) / 2 - len(text) * 28, 120, layer, rotation=90)


def _draw_beam_plan(msp, beam: Beam, bounds: Bounds, origin: Point2D, label_offset: float = 170) -> None:
    start = bounds.shift(beam.start, origin)
    end = bounds.shift(beam.end, origin)
    dx = end.x - start.x
    dy = end.y - start.y
    length = math.hypot(dx, dy) or 1.0
    nx = -dy / length
    ny = dx / length
    half = beam.width_mm / 2
    p1 = (start.x + nx * half, start.y + ny * half)
    p2 = (end.x + nx * half, end.y + ny * half)
    p3 = (end.x - nx * half, end.y - ny * half)
    p4 = (start.x - nx * half, start.y - ny * half)
    _add_polyline(msp, [p1, p2, p3, p4], "SAI-S-BEAM")
    msp.add_line((start.x, start.y), (end.x, end.y), dxfattribs={"layer": "SAI-X-REFERENCE"})
    _add_text(msp, beam.id, (start.x + end.x) / 2 + nx * label_offset, (start.y + end.y) / 2 + ny * label_offset, 120, "SAI-A-TEXT", rotation=math.degrees(math.atan2(dy, dx)))


def _segment_rect_points(start: Point2D, end: Point2D, width: float) -> list[tuple[float, float]]:
    dx = end.x - start.x
    dy = end.y - start.y
    length = math.hypot(dx, dy) or 1.0
    nx = -dy / length
    ny = dx / length
    half = width / 2
    return [
        (start.x + nx * half, start.y + ny * half),
        (end.x + nx * half, end.y + ny * half),
        (end.x - nx * half, end.y - ny * half),
        (start.x - nx * half, start.y - ny * half),
    ]


def _draw_strip_footing_plan(msp, strip: StripFooting, bounds: Bounds, origin: Point2D) -> None:
    start = bounds.shift(strip.start, origin)
    end = bounds.shift(strip.end, origin)
    points = _segment_rect_points(start, end, strip.width_mm)
    _add_hatch(msp, points, "SAI-H-CONCRETE", "ANSI31", scale=120, color=8)
    _add_polyline(msp, points, "SAI-S-FOOTING")
    mid_x = (start.x + end.x) / 2
    mid_y = (start.y + end.y) / 2
    _add_text(msp, f"{strip.id} {strip.width_mm:.0f}x{strip.depth_mm:.0f}", mid_x + 120, mid_y + 120, 105, "SAI-A-TEXT")


def _draw_wall_plan(msp, wall: Wall, bounds: Bounds, origin: Point2D) -> None:
    start = bounds.shift(wall.start, origin)
    end = bounds.shift(wall.end, origin)
    points = _segment_rect_points(start, end, wall.thickness_mm)
    _add_solid_hatch(msp, points, "SAI-S-WALL", 5)
    _add_polyline(msp, points, "SAI-S-WALL")
    mid_x = (start.x + end.x) / 2
    mid_y = (start.y + end.y) / 2
    _add_text(msp, wall.id, mid_x + 100, mid_y + 100, 105, "SAI-A-TEXT", rotation=math.degrees(math.atan2(end.y - start.y, end.x - start.x)))


def _draw_opening_plan(msp, opening: Opening, walls: list[Wall], bounds: Bounds, origin: Point2D) -> None:
    host = next((wall for wall in walls if wall.id == opening.host_id), None)
    if not host:
        return
    center = bounds.shift(opening.center, origin)
    angle = math.atan2(host.end.y - host.start.y, host.end.x - host.start.x)
    ux = math.cos(angle)
    uy = math.sin(angle)
    half = opening.width_mm / 2
    p0 = (center.x - ux * half, center.y - uy * half)
    p1 = (center.x + ux * half, center.y + uy * half)
    msp.add_line(p0, p1, dxfattribs={"layer": "SAI-S-OPENING"})
    _add_text(msp, opening.id, center.x + 120, center.y - 220, 90, "SAI-S-OPENING", rotation=math.degrees(angle))


def _draw_steel_member_elevation(msp, member: SteelMember, origin: Point2D) -> None:
    layer = "SAI-S-BRACE" if member.member_type == "brace" else "SAI-S-STEEL"
    start = (origin.x + member.start.x, origin.y + member.start.z)
    end = (origin.x + member.end.x, origin.y + member.end.z)
    lineweight_width = 60 if member.member_type in {"column", "beam"} else 35
    msp.add_lwpolyline([start, end], dxfattribs={"layer": layer, "const_width": lineweight_width})
    if member.member_type in {"brace", "platform"}:
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        _add_text(msp, member.section, mid_x + 80, mid_y + 80, 90, "SAI-A-TEXT", rotation=math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])))


def _draw_steel_repair_sheet(msp, project: StructuraProject, origin: Point2D) -> None:
    pipe_support = any(member.member_type == "pipe_support" for member in project.steel_members)
    title = "Fire-Fighting Pipe Support Coordination" if pipe_support else "Steel Bracing Comment Resolution"
    _draw_view_title(msp, title, "1:50", Point2D(x=origin.x, y=origin.y + 6200), width=8400)
    note = (
        "PIPE SUPPORT COORDINATION:\nNPS FIRE-FIGHTING LINES MODELLED AS SUPPORT CENTERLINES.\nUPN 160 SUPPORTS ADDED AT PRODUCTION SHED COLUMNS FOR ENGINEER REVIEW."
        if pipe_support
        else "RESPONSE TO RED-PEN COMMENT:\nELEMENT WITHOUT SUPPORT - ADD ADEQUATE BRACING.\nADDED DIAGONAL L50x6 BRACES AND GUSSET PLATE NOTES AT UNSUPPORTED SPANS."
    )
    _add_multiline(msp, note, origin.x, origin.y + 5700, 130, "SAI-A-TEXT")
    ground_y = origin.y + 800
    msp.add_line((origin.x - 500, ground_y), (origin.x + 19500, ground_y), dxfattribs={"layer": "SAI-A-TEXT"})
    sheet_title = "ELEVATION - PIPE SUPPORT COORDINATION" if pipe_support else "FRONT ELEVATION - PROPOSED BRACING OVERLAY"
    _add_text(msp, sheet_title, origin.x, origin.y + 5100, 160, "SAI-A-TITLE")
    for member in project.steel_members:
        _draw_steel_member_elevation(msp, member, Point2D(x=origin.x, y=ground_y))
    _draw_dimension(msp, Point2D(x=origin.x, y=ground_y), Point2D(x=origin.x + 18500, y=ground_y), -650, "18500")
    _draw_dimension(msp, Point2D(x=origin.x - 450, y=ground_y), Point2D(x=origin.x - 450, y=ground_y + 4300), 0, "4300")
    _add_multiline(
        msp,
        (
            "CONNECTION NOTES:\n1. VERIFY CLAMP/WELD LOCATIONS AGAINST EXISTING SHED COLUMNS.\n2. COORDINATE PIPE ELEVATIONS WITH FIRE-FIGHTING ENGINEER.\n3. CHECK UPN 160 SUPPORT CAPACITY BEFORE FABRICATION."
            if pipe_support
            else "CONNECTION NOTES:\n1. ADD 8mm GUSSET PLATES AT BRACE ENDS.\n2. SITE VERIFY EXISTING MEMBER SIZES BEFORE FABRICATION.\n3. WELDS/BOLTS TO BE CHECKED BY STRUCTURAL ENGINEER."
        ),
        origin.x + 12100,
        origin.y + 4200,
        115,
        "SAI-A-TEXT",
    )
    _draw_steel_member_schedule(msp, project, Point2D(x=origin.x, y=origin.y - 800))


def _draw_rebar_grid(msp, center: Point2D, width: float, height: float, bars: list[RebarSpec], layer: str = "SAI-S-REBAR") -> None:
    cover = min((bar.cover_mm for bar in bars), default=75)
    x0 = center.x - width / 2 + cover
    x1 = center.x + width / 2 - cover
    y0 = center.y - height / 2 + cover
    y1 = center.y + height / 2 - cover
    for bar in bars:
        spacing = bar.spacing_mm or 200
        if bar.direction in {"x", "both"}:
            y = y0
            while y <= y1 + 1:
                msp.add_line((x0, y), (x1, y), dxfattribs={"layer": layer})
                y += spacing
        if bar.direction in {"y", "both"}:
            x = x0
            while x <= x1 + 1:
                msp.add_line((x, y0), (x, y1), dxfattribs={"layer": layer})
                x += spacing


def _draw_section_marker(msp, section, bounds: Bounds, origin: Point2D) -> None:
    start = bounds.shift(section.start, origin)
    end = bounds.shift(section.end, origin)
    msp.add_line((start.x, start.y), (end.x, end.y), dxfattribs={"layer": "SAI-A-SECTION"})
    _draw_grid_bubble(msp, start.x, start.y, section.label.split("-")[0], radius=120)
    _draw_grid_bubble(msp, end.x, end.y, section.label.split("-")[-1], radius=120)


def _first_rebar_label(bars: list[RebarSpec], fallback: str) -> str:
    if not bars:
        return fallback
    return " / ".join(bar.label() for bar in bars[:2])


def _draw_foundation_plan(msp, project: StructuraProject, bounds: Bounds, origin: Point2D) -> None:
    _draw_view_title(msp, "Foundation Plan", "1:50", Point2D(x=origin.x, y=origin.y + bounds.height + 1850))
    _draw_grid(msp, project, bounds, origin)
    for strip in project.strip_footings:
        _draw_strip_footing_plan(msp, strip, bounds, origin)
    for beam in project.beams:
        _draw_beam_plan(msp, beam, bounds, origin)
    for footing in project.footings:
        center = bounds.shift(footing.center, origin)
        _draw_rect(msp, center, footing.width_mm, footing.length_mm, "SAI-S-FOOTING", "SAI-H-CONCRETE", "ANSI31")
        inner = min(footing.width_mm, footing.length_mm) * 0.62
        _draw_rect(msp, center, inner, inner, "SAI-S-CONCRETE")
        _draw_rebar_grid(msp, center, footing.width_mm, footing.length_mm, footing.rebar)
        _add_multiline(
            msp,
            f"{footing.id}\n{footing.width_mm:.0f}x{footing.length_mm:.0f}x{footing.depth_mm:.0f}\n{_first_rebar_label(footing.rebar, 'REBAR BY ENGINEER')}",
            center.x + footing.width_mm / 2 + 170,
            center.y + footing.length_mm / 2 - 80,
            100,
            "SAI-A-TEXT",
        )
        _draw_dimension(msp, Point2D(x=center.x - footing.width_mm / 2, y=center.y - footing.length_mm / 2), Point2D(x=center.x + footing.width_mm / 2, y=center.y - footing.length_mm / 2), -260, f"{footing.width_mm:.0f}")
    for column in project.columns:
        center = bounds.shift(column.center, origin)
        _draw_rect(msp, center, column.width_mm, column.depth_mm, "SAI-S-COLUMN")
        _add_solid_hatch(msp, _rect_points(center, column.width_mm, column.depth_mm), "SAI-S-COLUMN", 5)
        _add_text(msp, column.id, center.x + 130, center.y + 130, 115, "SAI-A-TEXT")
    for wall in project.walls:
        _draw_wall_plan(msp, wall, bounds, origin)
    for opening in project.openings:
        _draw_opening_plan(msp, opening, project.walls, bounds, origin)
    for dimension in project.drawing_package.dimensions:
        start = bounds.shift(dimension.start, origin)
        end = bounds.shift(dimension.end, origin)
        _draw_dimension(msp, start, end, dimension.offset_mm, dimension.label)
    for section in project.drawing_package.sections:
        _draw_section_marker(msp, section, bounds, origin)


def _draw_roof_plan(msp, project: StructuraProject, bounds: Bounds, origin: Point2D) -> None:
    elevations = _framing_elevations(project)
    vertical_gap = bounds.height + 3000.0
    for index, elevation in enumerate(elevations):
        level_origin = Point2D(x=origin.x, y=origin.y - index * vertical_gap)
        is_roof = index == len(elevations) - 1
        title = "Roof Framing and Reinforcement Plan" if is_roof else f"Level {index + 1} Framing and Reinforcement Plan"
        _draw_framing_plan(msp, project, bounds, level_origin, elevation, title)


def _draw_framing_plan(msp, project: StructuraProject, bounds: Bounds, origin: Point2D, elevation: float, title: str) -> None:
    _draw_view_title(msp, title, "1:50", Point2D(x=origin.x, y=origin.y + bounds.height + 1850), width=7200)
    _draw_grid(msp, project, bounds, origin)
    for slab in _slabs_at_elevation(project, elevation):
        shifted = [bounds.shift(point, origin) for point in slab.boundary]
        points = [(point.x, point.y) for point in shifted]
        _add_polyline(msp, points, "SAI-S-SLAB")
        _add_hatch(msp, points, "SAI-H-CONCRETE", "ANSI37", scale=220, angle=0, color=8)
        _draw_roof_rebar(msp, points, slab)
        center_x = sum(point.x for point in shifted) / len(shifted)
        center_y = sum(point.y for point in shifted) / len(shifted)
        slab_label = "ROOF SLAB" if "Roof" in title else "FLOOR SLAB"
        _add_multiline(msp, f"{slab.id} {slab_label}\nTHK={slab.thickness_mm:.0f}mm\n{_first_rebar_label(slab.rebar, 'SLAB REBAR BY ENGINEER')}", center_x - 600, center_y + 250, 120, "SAI-A-TEXT")
    for beam in _beams_at_elevation(project, elevation):
        _draw_beam_plan(msp, beam, bounds, origin)
    for wall in project.walls:
        if wall.base_elevation_mm <= elevation <= wall.top_elevation_mm + 1:
            _draw_wall_plan(msp, wall, bounds, origin)
    for opening in project.openings:
        if opening.sill_elevation_mm <= elevation <= opening.sill_elevation_mm + 3500:
            _draw_opening_plan(msp, opening, project.walls, bounds, origin)
    _draw_roof_arrows(msp, bounds, origin)
    for dimension in project.drawing_package.dimensions:
        start = bounds.shift(dimension.start, origin)
        end = bounds.shift(dimension.end, origin)
        _draw_dimension(msp, start, end, dimension.offset_mm, dimension.label)


def _draw_roof_rebar(msp, points: list[tuple[float, float]], slab: Slab) -> None:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    for bar in slab.rebar:
        spacing = bar.spacing_mm or 200
        if bar.direction in {"x", "both"}:
            y = min_y + spacing
            while y < max_y:
                msp.add_line((min_x + 250, y), (max_x - 250, y), dxfattribs={"layer": "SAI-S-REBAR"})
                y += spacing * 2
        if bar.direction in {"y", "both"}:
            x = min_x + spacing
            while x < max_x:
                msp.add_line((x, min_y + 250), (x, max_y - 250), dxfattribs={"layer": "SAI-S-TIES"})
                x += spacing * 2


def _draw_roof_arrows(msp, bounds: Bounds, origin: Point2D) -> None:
    p1 = Point2D(x=origin.x + 250, y=origin.y + 250)
    p2 = Point2D(x=origin.x + bounds.width - 250, y=origin.y + bounds.height - 250)
    p3 = Point2D(x=origin.x + bounds.width - 250, y=origin.y + 250)
    p4 = Point2D(x=origin.x + 250, y=origin.y + bounds.height - 250)
    for start, end in ((p1, p2), (p3, p4)):
        msp.add_line((start.x, start.y), (end.x, end.y), dxfattribs={"layer": "SAI-S-TIES"})
    _add_text(msp, "HIGH POINT", origin.x + bounds.width - 900, origin.y + bounds.height - 60, 110, "SAI-A-SECTION")
    _add_text(msp, "LOW POINT", origin.x - 200, origin.y + bounds.height + 220, 110, "SAI-A-SECTION")


def _draw_section(msp, project: StructuraProject, bounds: Bounds, origin: Point2D, title: str, along: str) -> None:
    levels = _framing_elevations(project)
    ground_y = origin.y + 900
    foundation_top = _level(project, "L-FOUNDATION", -500)
    top_elevation = max(levels or [_level(project, "L-ROOF", 3000)])
    roof_y = ground_y + (top_elevation - foundation_top)
    _draw_view_title(msp, f"Section {title}", "1:50", Point2D(x=origin.x, y=roof_y + 900))
    section_width = bounds.width if along == "x" else bounds.height
    section_width = max(section_width, 4200)
    soil = [(origin.x - 700, origin.y), (origin.x + section_width + 900, origin.y), (origin.x + section_width + 900, ground_y), (origin.x - 700, ground_y)]
    _add_hatch(msp, soil, "SAI-H-SOIL", "ANSI32", scale=150, angle=35, color=8)
    _add_polyline(msp, soil, "SAI-X-REFERENCE")
    msp.add_line((origin.x - 700, ground_y), (origin.x + section_width + 900, ground_y), dxfattribs={"layer": "SAI-A-TEXT"})
    _add_text(msp, "+0.000 GL", origin.x + section_width / 2, ground_y + 120, 130, "SAI-A-TEXT")

    columns = sorted(project.columns, key=lambda column: column.center.x if along == "x" else column.center.y)
    if not columns:
        return
    first = columns[0]
    last = columns[-1]
    section_columns = [first] if first.id == last.id else [first, last]
    for column in section_columns:
        pos = _section_position(column.center, bounds, section_width, along)
        x = origin.x + pos
        col_height = column.top_elevation_mm - column.base_elevation_mm
        col_center = Point2D(x=x, y=ground_y + col_height / 2)
        _draw_rect(msp, col_center, column.width_mm, col_height, "SAI-S-CONCRETE-CUT", "SAI-H-CONCRETE", "ANSI31")
        _draw_column_rebar_symbol(msp, col_center, column.width_mm, col_height)
        footing = _supporting_footing(column, project.footings)
        if footing:
            foot_center = Point2D(x=x, y=ground_y - footing.depth_mm / 2)
            _draw_rect(msp, foot_center, footing.width_mm, footing.depth_mm, "SAI-S-FOOTING", "SAI-H-CONCRETE", "ANSI31")
            _draw_rebar_grid(msp, foot_center, footing.width_mm, footing.depth_mm, footing.rebar)
            _draw_dimension(msp, Point2D(x=x - footing.width_mm / 2, y=ground_y - footing.depth_mm - 180), Point2D(x=x + footing.width_mm / 2, y=ground_y - footing.depth_mm - 180), 0, f"{footing.width_mm:.0f}")
        _draw_grid_bubble(msp, x, roof_y + 700, _nearest_grid_label(project, column.center, along))

    for index, elevation in enumerate(levels, start=1):
        y = ground_y + (elevation - foundation_top)
        is_roof = index == len(levels)
        _draw_rect(msp, Point2D(x=origin.x + section_width / 2, y=y), section_width, 170, "SAI-S-SLAB", "SAI-H-CONCRETE", "ANSI31")
        label = "ROOF SLAB / BEAM" if is_roof else f"LEVEL {index} SLAB / BEAM"
        _add_text(msp, label, origin.x + section_width / 2 - 450, y + 220, 120, "SAI-A-TEXT")
        _draw_level_marker(msp, origin.x + section_width / 2 + 600, y, _level_label(elevation, "ROOF" if is_roof else f"L{index}"))
    _add_multiline(msp, "POLYETHYLENE SHEET\nCOMPACTED SUBGRADE TO 95%\nCONCRETE INTERLOCK PAVING", origin.x + section_width / 2 - 200, ground_y - 300, 120, "SAI-A-TEXT")
    _draw_level_marker(msp, origin.x + section_width / 2 + 600, ground_y, "+0.000 GL")
    _draw_dimension(msp, Point2D(x=origin.x - 450, y=ground_y), Point2D(x=origin.x - 450, y=roof_y), 0, f"{roof_y - ground_y:.0f}")


def _level(project: StructuraProject, level_id: str, fallback: float) -> float:
    for level in project.levels:
        if level.id == level_id:
            return level.elevation_mm
    return fallback


def _framing_elevations(project: StructuraProject) -> list[float]:
    elevations = {round(slab.elevation_mm, 3) for slab in project.slabs if slab.elevation_mm > 0}
    elevations.update(round(beam.elevation_mm, 3) for beam in project.beams if beam.elevation_mm > 0)
    if not elevations:
        elevations.add(round(_level(project, "L-ROOF", 3000), 3))
    return sorted(elevations)


def _slabs_at_elevation(project: StructuraProject, elevation: float) -> list[Slab]:
    return [slab for slab in project.slabs if abs(slab.elevation_mm - elevation) <= 1.0]


def _beams_at_elevation(project: StructuraProject, elevation: float) -> list[Beam]:
    return [beam for beam in project.beams if abs(beam.elevation_mm - elevation) <= 1.0]


def _level_label(elevation: float, suffix: str) -> str:
    sign = "+" if elevation >= 0 else "-"
    return f"{sign}{abs(elevation) / 1000:.3f} {suffix}"


def _section_position(point: Point2D, bounds: Bounds, width: float, along: str) -> float:
    if along == "x":
        base = bounds.width or 1
        return (point.x - bounds.min_x) / base * width
    base = bounds.height or 1
    return (point.y - bounds.min_y) / base * width


def _nearest_grid_label(project: StructuraProject, point: Point2D, along: str) -> str:
    axis = "x" if along == "x" else "y"
    value = point.x if along == "x" else point.y
    candidates = [grid for grid in project.grid_lines if grid.axis == axis]
    if not candidates:
        return "?"
    return min(candidates, key=lambda grid: abs(grid.offset_mm - value)).label


def _supporting_footing(column: Column, footings: list[Footing]) -> Footing | None:
    return min(footings, key=lambda footing: math.hypot(footing.center.x - column.center.x, footing.center.y - column.center.y), default=None)


def _draw_column_rebar_symbol(msp, center: Point2D, width: float, height: float) -> None:
    x0 = center.x - width / 2 + 45
    x1 = center.x + width / 2 - 45
    y0 = center.y - height / 2 + 120
    y1 = center.y + height / 2 - 120
    for x in (x0, x1):
        msp.add_line((x, y0), (x, y1), dxfattribs={"layer": "SAI-S-REBAR"})
    y = y0 + 180
    while y < y1:
        msp.add_lwpolyline([(x0, y), (x1, y), (x1, y + 45), (x0, y + 45), (x0, y)], dxfattribs={"layer": "SAI-S-TIES"})
        y += 300


def _draw_level_marker(msp, x: float, y: float, label: str) -> None:
    msp.add_line((x - 420, y), (x, y), dxfattribs={"layer": "SAI-A-TEXT"})
    _add_solid_hatch(msp, [(x, y), (x + 90, y + 130), (x - 90, y + 130)], "SAI-A-TEXT", 4)
    _add_text(msp, label, x - 400, y + 170, 120, "SAI-A-TEXT")


def _draw_detail_sheet(msp, project: StructuraProject, origin: Point2D) -> None:
    _draw_view_title(msp, "Reinforcement Details", "1:25", Point2D(x=origin.x, y=origin.y + 5000), width=5200)
    footing = project.footings[0] if project.footings else None
    column = project.columns[0] if project.columns else None
    slab = project.slabs[0] if project.slabs else None
    wall = project.walls[0] if project.walls else None
    if footing:
        _draw_footing_detail(msp, footing, Point2D(x=origin.x, y=origin.y + 2800))
    if column:
        _draw_column_detail(msp, column, Point2D(x=origin.x + 5200, y=origin.y + 2800))
    if slab:
        _draw_slab_detail(msp, slab, Point2D(x=origin.x, y=origin.y - 1700))
    if wall:
        _draw_wall_detail(msp, wall, Point2D(x=origin.x + 6500, y=origin.y - 1700))


def _draw_footing_detail(msp, footing: Footing, origin: Point2D) -> None:
    _add_text(msp, "TYPICAL ISOLATED FOOTING", origin.x, origin.y + 1500, 180, "SAI-A-TITLE")
    plan_center = Point2D(x=origin.x + 900, y=origin.y + 650)
    _draw_rect(msp, plan_center, footing.width_mm, footing.length_mm, "SAI-S-FOOTING", "SAI-H-CONCRETE", "ANSI31")
    _draw_rebar_grid(msp, plan_center, footing.width_mm, footing.length_mm, footing.rebar)
    _add_text(msp, f"PLAN {footing.id}", plan_center.x - 280, plan_center.y - footing.length_mm / 2 - 260, 120, "SAI-A-TEXT")
    section_center = Point2D(x=origin.x + 3300, y=origin.y + 650)
    _draw_rect(msp, section_center, footing.width_mm, footing.depth_mm, "SAI-S-FOOTING", "SAI-H-CONCRETE", "ANSI31")
    _draw_rebar_grid(msp, section_center, footing.width_mm, footing.depth_mm, footing.rebar)
    _add_text(msp, "SECTION 1-1", section_center.x - 340, section_center.y - footing.depth_mm / 2 - 260, 120, "SAI-A-TEXT")
    _draw_dimension(msp, Point2D(x=section_center.x - footing.width_mm / 2, y=section_center.y - footing.depth_mm / 2 - 180), Point2D(x=section_center.x + footing.width_mm / 2, y=section_center.y - footing.depth_mm / 2 - 180), 0, f"{footing.width_mm:.0f}")
    _draw_dimension(msp, Point2D(x=section_center.x + footing.width_mm / 2 + 220, y=section_center.y - footing.depth_mm / 2), Point2D(x=section_center.x + footing.width_mm / 2 + 220, y=section_center.y + footing.depth_mm / 2), 0, f"{footing.depth_mm:.0f}")
    _add_multiline(msp, f"BOT: {_first_rebar_label(footing.rebar, 'REBAR BY ENGINEER')}\nCOVER: {min((bar.cover_mm for bar in footing.rebar), default=75)}mm\nCONC: {footing.concrete_grade}", origin.x + 4500, origin.y + 1200, 115, "SAI-A-TEXT")


def _draw_column_detail(msp, column: Column, origin: Point2D) -> None:
    _add_text(msp, "TYPICAL COLUMN STARTER", origin.x, origin.y + 1500, 180, "SAI-A-TITLE")
    height = 2600
    center = Point2D(x=origin.x + 750, y=origin.y + 500)
    _draw_rect(msp, center, column.width_mm, height, "SAI-S-CONCRETE-CUT", "SAI-H-CONCRETE", "ANSI31")
    _draw_column_rebar_symbol(msp, center, column.width_mm, height)
    base_center = Point2D(x=center.x, y=origin.y - 950)
    _draw_rect(msp, base_center, 1200, 450, "SAI-S-FOOTING", "SAI-H-CONCRETE", "ANSI31")
    for x in (center.x - 90, center.x + 90):
        msp.add_line((x, base_center.y + 200), (x, center.y + height / 2 + 500), dxfattribs={"layer": "SAI-S-REBAR"})
    _add_multiline(msp, f"{column.id} {column.width_mm:.0f}x{column.depth_mm:.0f}\n{_first_rebar_label(column.rebar, 'COLUMN REBAR BY ENGINEER')}\nTIES T8 @150", origin.x + 1250, origin.y + 1150, 115, "SAI-A-TEXT")
    _draw_dimension(msp, Point2D(x=center.x + 420, y=base_center.y + 225), Point2D(x=center.x + 420, y=center.y + height / 2), 0, "STARTERS")


def _draw_slab_detail(msp, slab: Slab, origin: Point2D) -> None:
    _add_text(msp, "ROOF SLAB REINFORCEMENT STRIP", origin.x, origin.y + 1100, 180, "SAI-A-TITLE")
    strip = [(origin.x, origin.y), (origin.x + 5600, origin.y), (origin.x + 5600, origin.y + slab.thickness_mm), (origin.x, origin.y + slab.thickness_mm)]
    _add_hatch(msp, strip, "SAI-H-CONCRETE", "ANSI31", scale=90, color=8)
    _add_polyline(msp, strip, "SAI-S-SLAB")
    cover = min((bar.cover_mm for bar in slab.rebar), default=30)
    for y in (origin.y + cover, origin.y + slab.thickness_mm - cover):
        msp.add_line((origin.x + 180, y), (origin.x + 5420, y), dxfattribs={"layer": "SAI-S-REBAR"})
    _add_multiline(msp, f"TOP/BOT: {_first_rebar_label(slab.rebar, 'SLAB REBAR BY ENGINEER')}\nCOVER {cover}mm\nCHAIRS/STOOLS BY CONTRACTOR", origin.x + 250, origin.y - 300, 115, "SAI-A-TEXT")
    _draw_dimension(msp, Point2D(x=origin.x + 5800, y=origin.y), Point2D(x=origin.x + 5800, y=origin.y + slab.thickness_mm), 0, f"{slab.thickness_mm:.0f}")


def _draw_wall_detail(msp, wall: Wall, origin: Point2D) -> None:
    _add_text(msp, "RC CORE WALL REINFORCEMENT", origin.x, origin.y + 1100, 180, "SAI-A-TITLE")
    height = 1800
    length = 2600
    panel = [(origin.x, origin.y), (origin.x + length, origin.y), (origin.x + length, origin.y + height), (origin.x, origin.y + height)]
    _add_hatch(msp, panel, "SAI-H-CONCRETE", "ANSI31", scale=120, color=8)
    _add_polyline(msp, panel, "SAI-S-WALL")
    x = origin.x + 180
    while x < origin.x + length:
        msp.add_line((x, origin.y + 120), (x, origin.y + height - 120), dxfattribs={"layer": "SAI-S-REBAR"})
        x += 200
    y = origin.y + 220
    while y < origin.y + height:
        msp.add_line((origin.x + 120, y), (origin.x + length - 120, y), dxfattribs={"layer": "SAI-S-TIES"})
        y += 200
    _add_multiline(
        msp,
        f"{wall.id} {wall.thickness_mm:.0f}mm THK\nVERT: T16 @200 EF\nHORZ: T12 @200 EF\nOPENINGS: 2T16 TRIMMERS",
        origin.x,
        origin.y - 320,
        115,
        "SAI-A-TEXT",
    )


def _draw_schedule_sheet(msp, project: StructuraProject, origin: Point2D) -> None:
    _draw_view_title(msp, "Schedules and Takeoff", "NTS", Point2D(x=origin.x, y=origin.y + 5000), width=5200)
    rows = _bar_schedule_rows(project)
    _draw_bbs_table(msp, rows, Point2D(x=origin.x, y=origin.y + 4350))
    lower_y = origin.y - 1900
    _draw_footing_schedule(msp, project, Point2D(x=origin.x, y=lower_y))
    _draw_column_schedule(msp, project, Point2D(x=origin.x + 3900, y=lower_y))
    _draw_beam_schedule(msp, project, Point2D(x=origin.x + 7800, y=lower_y))
    if project.walls or project.strip_footings:
        _draw_wall_schedule(msp, project, Point2D(x=origin.x + 11700, y=lower_y))
        _draw_strip_footing_schedule(msp, project, Point2D(x=origin.x, y=lower_y - 2700))
        _draw_opening_schedule(msp, project, Point2D(x=origin.x + 3900, y=lower_y - 2700))
        takeoff_y = lower_y - 5400
    elif project.steel_members:
        _draw_steel_member_schedule(msp, project, Point2D(x=origin.x, y=lower_y - 2700))
        takeoff_y = lower_y - 5400
    else:
        takeoff_y = lower_y - 2700
    _draw_material_takeoff(msp, project, rows, Point2D(x=origin.x, y=takeoff_y))
    _draw_reinforcement_legend(msp, Point2D(x=origin.x + 5200, y=takeoff_y))


def _draw_table(msp, origin: Point2D, title: str, headers: list[str], rows: list[list[str]], widths: list[float], row_height: float = 260) -> None:
    total_width = sum(widths)
    _add_text(msp, title, origin.x, origin.y, 180, "SAI-A-TITLE")
    y = origin.y - 320
    _add_polyline(msp, [(origin.x, y), (origin.x + total_width, y), (origin.x + total_width, y - row_height), (origin.x, y - row_height)], "SAI-SCHEDULE")
    x = origin.x
    for header, width in zip(headers, widths):
        _add_text(msp, header, x + 50, y - 180, 105, "SAI-SCHEDULE")
        x += width
        msp.add_line((x, y), (x, y - row_height * (len(rows) + 1)), dxfattribs={"layer": "SAI-SCHEDULE"})
    for idx, row in enumerate(rows):
        ry = y - row_height * (idx + 1)
        msp.add_line((origin.x, ry), (origin.x + total_width, ry), dxfattribs={"layer": "SAI-SCHEDULE"})
        x = origin.x
        for value, width in zip(row, widths):
            _add_text(msp, value, x + 50, ry - 180, 95, "SAI-SCHEDULE")
            x += width
    bottom = y - row_height * (len(rows) + 1)
    msp.add_line((origin.x, bottom), (origin.x + total_width, bottom), dxfattribs={"layer": "SAI-SCHEDULE"})
    msp.add_line((origin.x, y), (origin.x, bottom), dxfattribs={"layer": "SAI-SCHEDULE"})


def _draw_bbs_table(msp, rows: list[BarScheduleRow], origin: Point2D) -> None:
    table_rows = [
        [row.mark, row.element, row.bar, row.spacing_or_qty, f"{row.length_mm:.0f}", str(row.count), f"{row.total_weight_kg:.1f}", row.shape]
        for row in rows[:22]
    ]
    _draw_table(
        msp,
        origin,
        "BAR BENDING SCHEDULE",
        ["MARK", "ELEMENT", "BAR", "SP/QTY", "L(mm)", "NO.", "KG", "SHAPE"],
        table_rows,
        [800, 1050, 650, 850, 760, 560, 620, 900],
        row_height=230,
    )


def _draw_footing_schedule(msp, project: StructuraProject, origin: Point2D) -> None:
    rows = [[footing.id, f"{footing.width_mm:.0f}", f"{footing.length_mm:.0f}", f"{footing.depth_mm:.0f}", footing.concrete_grade] for footing in project.footings]
    _draw_table(msp, origin, "FOOTING SCHEDULE", ["ID", "B", "L", "D", "CONC"], rows, [650, 650, 650, 650, 900], row_height=230)


def _draw_column_schedule(msp, project: StructuraProject, origin: Point2D) -> None:
    rows = [
        [column.id, f"{column.width_mm:.0f}", f"{column.depth_mm:.0f}", f"{column.top_elevation_mm - column.base_elevation_mm:.0f}", _first_rebar_label(column.rebar, "-")]
        for column in project.columns
    ]
    _draw_table(msp, origin, "COLUMN SCHEDULE", ["ID", "B", "D", "H", "REINF."], rows, [620, 560, 560, 650, 1400], row_height=230)


def _draw_beam_schedule(msp, project: StructuraProject, origin: Point2D) -> None:
    rows = [
        [beam.id, f"{math.hypot(beam.end.x - beam.start.x, beam.end.y - beam.start.y):.0f}", f"{beam.width_mm:.0f}", f"{beam.depth_mm:.0f}", _first_rebar_label(beam.rebar, "-")]
        for beam in project.beams
    ]
    _draw_table(msp, origin, "BEAM SCHEDULE", ["ID", "L", "B", "D", "REINF."], rows[:12], [620, 700, 560, 560, 1350], row_height=230)


def _draw_strip_footing_schedule(msp, project: StructuraProject, origin: Point2D) -> None:
    rows = [
        [strip.id, f"{math.hypot(strip.end.x - strip.start.x, strip.end.y - strip.start.y):.0f}", f"{strip.width_mm:.0f}", f"{strip.depth_mm:.0f}", _first_rebar_label(strip.rebar, "-")]
        for strip in project.strip_footings
    ]
    _draw_table(msp, origin, "STRIP FOOTING SCHEDULE", ["ID", "L", "B", "D", "REINF."], rows[:8], [900, 650, 560, 560, 1350], row_height=230)


def _draw_wall_schedule(msp, project: StructuraProject, origin: Point2D) -> None:
    rows = [
        [
            wall.id,
            f"{math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y):.0f}",
            f"{wall.thickness_mm:.0f}",
            f"{wall.top_elevation_mm - wall.base_elevation_mm:.0f}",
            wall.wall_type.upper().replace("_", " "),
        ]
        for wall in project.walls
    ]
    _draw_table(msp, origin, "WALL / CORE SCHEDULE", ["ID", "L", "T", "H", "TYPE"], rows[:8], [900, 650, 560, 650, 1500], row_height=230)


def _draw_opening_schedule(msp, project: StructuraProject, origin: Point2D) -> None:
    rows = [
        [opening.id, opening.host_id, f"{opening.width_mm:.0f}", f"{opening.height_mm:.0f}", f"{opening.sill_elevation_mm:.0f}"]
        for opening in project.openings
    ]
    _draw_table(msp, origin, "OPENING SCHEDULE", ["ID", "HOST", "W", "H", "SILL"], rows[:8], [850, 950, 560, 560, 650], row_height=230)


def _draw_steel_member_schedule(msp, project: StructuraProject, origin: Point2D) -> None:
    rows = [
        [
            member.id,
            member.member_type.upper(),
            member.section,
            f"{_steel_length(member):.0f}",
            member.connection_note[:24] or "-",
        ]
        for member in project.steel_members
    ]
    _draw_table(msp, origin, "STEEL MEMBER SCHEDULE", ["ID", "TYPE", "SECTION", "L", "CONNECTION"], rows[:20], [900, 900, 1300, 650, 1800], row_height=230)


def _draw_material_takeoff(msp, project: StructuraProject, rows: list[BarScheduleRow], origin: Point2D) -> None:
    concrete_m3 = _concrete_volume_m3(project)
    rebar_kg = sum(row.total_weight_kg for row in rows)
    steel_m = sum(_steel_length(member) for member in project.steel_members) / 1000
    takeoff_rows = [
        ["CONCRETE", f"{concrete_m3:.2f}", "m3"],
        ["REBAR", f"{rebar_kg:.1f}", "kg"],
    ]
    if project.steel_members:
        takeoff_rows.append(["STRUCTURAL STEEL", f"{steel_m:.1f}", "m"])
    takeoff_rows.append(["FORMWORK REVIEW", "BY ENGINEER", "-"])
    _draw_table(msp, origin, "MATERIAL TAKEOFF", ["ITEM", "QTY", "UNIT"], takeoff_rows, [1700, 1100, 850], row_height=250)
    _add_multiline(msp, "NOTE:\nQuantities are generated from the internal model.\nEngineer must verify loads, soil, and code design.", origin.x, origin.y - 1900, 115, "SAI-A-TEXT")


def _draw_reinforcement_legend(msp, origin: Point2D) -> None:
    _add_text(msp, "REINFORCEMENT LEGEND", origin.x, origin.y, 180, "SAI-A-TITLE")
    samples = [
        ("MAIN BAR", "SAI-S-REBAR"),
        ("TIES / STIRRUPS", "SAI-S-TIES"),
        ("CONCRETE CUT", "SAI-H-CONCRETE"),
        ("COMPACTED SOIL", "SAI-H-SOIL"),
    ]
    y = origin.y - 450
    for label, layer in samples:
        if "CONCRETE" in label:
            points = [(origin.x, y - 80), (origin.x + 700, y - 80), (origin.x + 700, y + 80), (origin.x, y + 80)]
            _add_hatch(msp, points, layer, "ANSI31", scale=80, color=8)
            _add_polyline(msp, points, "SAI-A-BORDER")
        elif "SOIL" in label:
            points = [(origin.x, y - 80), (origin.x + 700, y - 80), (origin.x + 700, y + 80), (origin.x, y + 80)]
            _add_hatch(msp, points, layer, "ANSI32", scale=90, color=8)
            _add_polyline(msp, points, "SAI-A-BORDER")
        else:
            msp.add_line((origin.x, y), (origin.x + 700, y), dxfattribs={"layer": layer})
            for x in range(0, 701, 140):
                msp.add_circle((origin.x + x, y), 18, dxfattribs={"layer": layer})
        _add_text(msp, label, origin.x + 900, y - 55, 115, "SAI-A-TEXT")
        y -= 330


def _bar_schedule_rows(project: StructuraProject) -> list[BarScheduleRow]:
    rows: list[BarScheduleRow] = []
    for footing in project.footings:
        for bar in footing.rebar:
            spacing = bar.spacing_mm or 200
            if bar.direction == "x":
                count = max(2, math.floor((footing.length_mm - 2 * bar.cover_mm) / spacing) + 1)
                length = footing.width_mm - 2 * bar.cover_mm + 2 * 150
            elif bar.direction == "y":
                count = max(2, math.floor((footing.width_mm - 2 * bar.cover_mm) / spacing) + 1)
                length = footing.length_mm - 2 * bar.cover_mm + 2 * 150
            else:
                count = max(2, math.floor((min(footing.width_mm, footing.length_mm) - 2 * bar.cover_mm) / spacing) + 1)
                length = max(footing.width_mm, footing.length_mm) - 2 * bar.cover_mm
            rows.append(_row(bar, footing.id, length, count, "A"))
    for strip in project.strip_footings:
        span = math.hypot(strip.end.x - strip.start.x, strip.end.y - strip.start.y)
        for bar in strip.rebar:
            if bar.direction == "longitudinal":
                count = max(2, math.floor((strip.width_mm - 2 * bar.cover_mm) / (bar.spacing_mm or 150)) + 1)
                length = span + 2 * 300
                shape = "STRAIGHT"
            else:
                count = max(2, math.floor(span / (bar.spacing_mm or 150)) + 1)
                length = strip.width_mm - 2 * bar.cover_mm + 2 * 150
                shape = "U"
            rows.append(_row(bar, strip.id, length, count, shape))
    for column in project.columns:
        height = column.top_elevation_mm - column.base_elevation_mm
        for bar in column.rebar:
            if bar.direction == "longitudinal":
                count = bar.quantity or 4
                length = height + 650
                shape = "LAP"
            else:
                count = max(2, math.floor(height / (bar.spacing_mm or 150)) + 1)
                length = 2 * (column.width_mm + column.depth_mm) - 8 * bar.cover_mm + 2 * 80
                shape = "TIE"
            rows.append(_row(bar, column.id, length, count, shape))
    for beam in project.beams:
        span = math.hypot(beam.end.x - beam.start.x, beam.end.y - beam.start.y)
        for bar in beam.rebar:
            if bar.direction == "longitudinal":
                count = bar.quantity or 2
                length = span + 2 * 350
                shape = "STRAIGHT"
            else:
                count = max(2, math.floor(span / (bar.spacing_mm or 150)) + 1)
                length = 2 * (beam.width_mm + beam.depth_mm) + 2 * 80
                shape = "STIR"
            rows.append(_row(bar, beam.id, length, count, shape))
    for slab in project.slabs:
        xs = [point.x for point in slab.boundary]
        ys = [point.y for point in slab.boundary]
        width = max(xs) - min(xs)
        length = max(ys) - min(ys)
        for bar in slab.rebar:
            spacing = bar.spacing_mm or 150
            if bar.direction == "x":
                count = max(2, math.floor(length / spacing) + 1)
                bar_length = width - 2 * bar.cover_mm
            else:
                count = max(2, math.floor(width / spacing) + 1)
                bar_length = length - 2 * bar.cover_mm
            rows.append(_row(bar, slab.id, bar_length, count, "STRAIGHT"))
    for wall in project.walls:
        height = wall.top_elevation_mm - wall.base_elevation_mm
        length = math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
        for bar in wall.rebar:
            if bar.direction == "longitudinal":
                count = max(2, math.floor(length / (bar.spacing_mm or 200)) + 1)
                bar_length = height + 650
                shape = "VERT"
            else:
                count = max(2, math.floor(height / (bar.spacing_mm or 200)) + 1)
                bar_length = length - 2 * bar.cover_mm
                shape = "HORZ"
            rows.append(_row(bar, wall.id, bar_length, count, shape))
    return rows


def _row(bar: RebarSpec, element_id: str, length_mm: float, count: int, shape: str) -> BarScheduleRow:
    unit_weight_kg_per_m = (bar.diameter_mm * bar.diameter_mm) / 162
    total_weight = max(length_mm, 0) / 1000 * count * unit_weight_kg_per_m
    spacing_or_qty = f"@{bar.spacing_mm}" if bar.spacing_mm else f"{bar.quantity or count}"
    return BarScheduleRow(
        mark=bar.mark,
        element=element_id,
        bar=f"T{bar.diameter_mm}",
        spacing_or_qty=spacing_or_qty,
        length_mm=max(length_mm, 0),
        count=count,
        total_weight_kg=total_weight,
        shape=shape,
    )


def _steel_length(member: SteelMember) -> float:
    return math.sqrt(
        (member.end.x - member.start.x) ** 2
        + (member.end.y - member.start.y) ** 2
        + (member.end.z - member.start.z) ** 2
    )


def _concrete_volume_m3(project: StructuraProject) -> float:
    total_mm3 = 0.0
    for footing in project.footings:
        total_mm3 += footing.width_mm * footing.length_mm * footing.depth_mm
    for strip in project.strip_footings:
        length = math.hypot(strip.end.x - strip.start.x, strip.end.y - strip.start.y)
        total_mm3 += strip.width_mm * strip.depth_mm * length
    for column in project.columns:
        total_mm3 += column.width_mm * column.depth_mm * (column.top_elevation_mm - column.base_elevation_mm)
    for beam in project.beams:
        length = math.hypot(beam.end.x - beam.start.x, beam.end.y - beam.start.y)
        total_mm3 += beam.width_mm * beam.depth_mm * length
    for slab in project.slabs:
        total_mm3 += _polygon_area(slab.boundary) * slab.thickness_mm
    for wall in project.walls:
        length = math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
        opening_area = sum(
            opening.width_mm * opening.height_mm
            for opening in project.openings
            if opening.host_id == wall.id
        )
        gross_area = length * (wall.top_elevation_mm - wall.base_elevation_mm)
        total_mm3 += wall.thickness_mm * max(gross_area - opening_area, 0)
    return total_mm3 / 1_000_000_000


def _polygon_area(points: list[Point2D]) -> float:
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point.x * nxt.y - nxt.x * point.y
    return abs(total) / 2


def _draw_title_block(msp, project: StructuraProject, origin: Point2D, height: float) -> None:
    width = 4300
    _add_polyline(msp, [(origin.x, origin.y), (origin.x + width, origin.y), (origin.x + width, origin.y + height), (origin.x, origin.y + height)], "SAI-A-BORDER")
    _add_text(msp, "STRUCTURAI", origin.x + 180, origin.y + height - 520, 300, "SAI-A-TITLE")
    _add_multiline(msp, project.title.upper(), origin.x + 180, origin.y + height - 1100, 160, "SAI-A-TEXT")
    sheet_rows = [[sheet.number, sheet.title, sheet.scale] for sheet in project.drawing_package.sheets]
    _draw_table(msp, Point2D(x=origin.x + 180, y=origin.y + height - 1900), "SHEET INDEX", ["NO", "TITLE", "SCALE"], sheet_rows, [650, 2100, 850], row_height=240)
    note_text = "\n".join(project.drawing_package.general_notes[:8])
    _add_multiline(msp, f"GENERAL NOTES:\n{note_text}", origin.x + 180, origin.y + height - 4800, 115, "SAI-A-TEXT")
    _add_multiline(msp, "ISSUE: 00\nSTATUS: FOR ENGINEER REVIEW\nDRAWN BY: STRUCTURAI\nCHECK: HUMAN ENGINEER", origin.x + 180, origin.y + 1150, 120, "SAI-A-TEXT")
