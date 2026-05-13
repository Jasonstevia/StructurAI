from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import hypot

from backend.core.structura_model import Point2D, StructuraProject


@dataclass
class ValidationIssue:
    code: str
    severity: str
    message: str
    entity_id: str | None = None


@dataclass
class ValidationReport:
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "issues": [issue.__dict__ for issue in self.issues],
        }


def _distance(a: Point2D, b: Point2D) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def _point_in_rect(point: Point2D, center: Point2D, width: float, length: float, tolerance: float = 1.0) -> bool:
    return (
        abs(point.x - center.x) <= width / 2 + tolerance
        and abs(point.y - center.y) <= length / 2 + tolerance
    )


def _polygon_area(points: list[Point2D]) -> float:
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point.x * nxt.y - nxt.x * point.y
    return abs(total) / 2


def _has_column_at(project: StructuraProject, point: Point2D, tolerance: float = 150.0) -> bool:
    return any(_distance(column.center, point) <= tolerance for column in project.columns)


def _has_footing_at(project: StructuraProject, point: Point2D, tolerance: float = 1.0) -> bool:
    return any(_point_in_rect(point, footing.center, footing.width_mm, footing.length_mm, tolerance) for footing in project.footings)


def _grid_positions(project: StructuraProject, axis: str) -> list[float]:
    return sorted({round(grid.offset_mm, 3) for grid in project.grid_lines if grid.axis == axis})


def _segment_length(start: Point2D, end: Point2D) -> float:
    return _distance(start, end)


def _same_segment(a_start: Point2D, a_end: Point2D, b_start: Point2D, b_end: Point2D, tolerance: float = 250.0) -> bool:
    same = _distance(a_start, b_start) <= tolerance and _distance(a_end, b_end) <= tolerance
    reverse = _distance(a_start, b_end) <= tolerance and _distance(a_end, b_start) <= tolerance
    return same or reverse


def _wall_has_strip_footing(project: StructuraProject, wall_id: str) -> bool:
    wall = next((item for item in project.walls if item.id == wall_id), None)
    if not wall:
        return False
    return any(_same_segment(wall.start, wall.end, footing.start, footing.end) for footing in project.strip_footings)


def validate_project(project: StructuraProject) -> ValidationReport:
    issues: list[ValidationIssue] = []

    counts = Counter(project.all_ids())
    for entity_id, count in counts.items():
        if count > 1:
            issues.append(ValidationIssue("DUPLICATE_ID", "error", f"Duplicate id '{entity_id}' appears {count} times.", entity_id))

    steel_package = bool(project.steel_members)

    if not project.columns and not steel_package:
        issues.append(ValidationIssue("NO_COLUMNS", "error", "At least one column is required for an RC structural package."))

    if not project.footings and not steel_package:
        issues.append(ValidationIssue("NO_FOOTINGS", "error", "At least one footing is required."))

    x_grids = _grid_positions(project, "x")
    y_grids = _grid_positions(project, "y")
    if not steel_package and len(x_grids) >= 2 and len(y_grids) >= 2:
        intersections = [Point2D(x=x, y=y) for y in y_grids for x in x_grids]
        missing_columns = [point for point in intersections if not _has_column_at(project, point)]
        missing_footings = [point for point in intersections if not _has_footing_at(project, point)]
        if missing_columns:
            issues.append(
                ValidationIssue(
                    "GRID_COLUMNS_MISSING",
                    "error",
                    f"Grid has {len(intersections)} intersections but {len(missing_columns)} have no column.",
                )
            )
        if missing_footings:
            issues.append(
                ValidationIssue(
                    "GRID_FOOTINGS_MISSING",
                    "error",
                    f"Grid has {len(intersections)} intersections but {len(missing_footings)} have no footing.",
                )
            )

    for column in project.columns:
        supporting = [
            footing
            for footing in project.footings
            if _point_in_rect(column.center, footing.center, footing.width_mm, footing.length_mm)
        ]
        if not supporting:
            issues.append(
                ValidationIssue(
                    "COLUMN_UNSUPPORTED",
                    "error",
                    f"Column {column.id} is not supported by any footing.",
                    column.id,
                )
            )
        for footing in supporting:
            if abs(column.base_elevation_mm - footing.top_elevation_mm) > 1.0:
                issues.append(
                    ValidationIssue(
                        "COLUMN_BASE_MISMATCH",
                        "error",
                        f"Column {column.id} base elevation does not match footing {footing.id} top elevation.",
                        column.id,
                    )
                )
        if column.width_mm < 200 or column.depth_mm < 200:
            issues.append(ValidationIssue("COLUMN_TOO_SMALL", "error", f"Column {column.id} is below 200mm minimum size.", column.id))
        if not column.rebar:
            issues.append(ValidationIssue("COLUMN_REBAR_MISSING", "error", f"Column {column.id} has no reinforcement specified.", column.id))

    for footing in project.footings:
        if footing.depth_mm < 300:
            issues.append(ValidationIssue("FOOTING_TOO_SHALLOW", "error", f"Footing {footing.id} depth is below 300mm.", footing.id))
        if min(footing.width_mm, footing.length_mm) < 800:
            issues.append(ValidationIssue("FOOTING_TOO_SMALL", "error", f"Footing {footing.id} plan size is below 800mm.", footing.id))
        if not footing.rebar:
            issues.append(ValidationIssue("FOOTING_REBAR_MISSING", "error", f"Footing {footing.id} has no reinforcement specified.", footing.id))

    for strip in project.strip_footings:
        if _segment_length(strip.start, strip.end) < 500:
            issues.append(ValidationIssue("STRIP_FOOTING_TOO_SHORT", "error", f"Strip footing {strip.id} is too short.", strip.id))
        if strip.depth_mm < 300:
            issues.append(ValidationIssue("STRIP_FOOTING_TOO_SHALLOW", "error", f"Strip footing {strip.id} depth is below 300mm.", strip.id))
        if strip.width_mm < 500:
            issues.append(ValidationIssue("STRIP_FOOTING_TOO_NARROW", "error", f"Strip footing {strip.id} width is below 500mm.", strip.id))
        if not strip.rebar:
            issues.append(ValidationIssue("STRIP_FOOTING_REBAR_MISSING", "error", f"Strip footing {strip.id} has no reinforcement specified.", strip.id))

    for beam in project.beams:
        start_supported = _has_column_at(project, beam.start)
        end_supported = _has_column_at(project, beam.end)
        if not start_supported or not end_supported:
            issues.append(ValidationIssue("BEAM_SUPPORTS_MISSING", "warning", f"Beam {beam.id} should connect to two column supports.", beam.id))
        if beam.depth_mm < 250:
            issues.append(ValidationIssue("BEAM_TOO_SHALLOW", "error", f"Beam {beam.id} depth is below 250mm.", beam.id))
        if not beam.rebar:
            issues.append(ValidationIssue("BEAM_REBAR_MISSING", "error", f"Beam {beam.id} has no reinforcement specified.", beam.id))

    for slab in project.slabs:
        area = _polygon_area(slab.boundary)
        if area <= 0:
            issues.append(ValidationIssue("SLAB_AREA_INVALID", "error", f"Slab {slab.id} has invalid closed boundary area.", slab.id))
        if slab.thickness_mm < 100:
            issues.append(ValidationIssue("SLAB_TOO_THIN", "error", f"Slab {slab.id} thickness is below 100mm.", slab.id))
        if not slab.rebar:
            issues.append(ValidationIssue("SLAB_REBAR_MISSING", "error", f"Slab {slab.id} has no reinforcement specified.", slab.id))

    top_elevation = max((level.elevation_mm for level in project.levels), default=0.0)
    if not steel_package and top_elevation >= 6000 and not project.walls:
        issues.append(ValidationIssue("LATERAL_SYSTEM_MISSING", "error", "Multi-story buildings require a wall/core lateral system in the native model."))

    for wall in project.walls:
        if _segment_length(wall.start, wall.end) < 500:
            issues.append(ValidationIssue("WALL_TOO_SHORT", "error", f"Wall {wall.id} is too short.", wall.id))
        if wall.thickness_mm < 150 and wall.wall_type != "masonry_infill":
            issues.append(ValidationIssue("WALL_TOO_THIN", "error", f"Wall {wall.id} thickness is below 150mm.", wall.id))
        if not wall.rebar and wall.wall_type.startswith("rc_"):
            issues.append(ValidationIssue("WALL_REBAR_MISSING", "error", f"Wall {wall.id} has no reinforcement specified.", wall.id))
        if wall.wall_type.startswith("rc_") and not _wall_has_strip_footing(project, wall.id):
            issues.append(ValidationIssue("WALL_FOOTING_MISSING", "error", f"Wall {wall.id} is missing a matching strip footing.", wall.id))

    wall_ids = {wall.id for wall in project.walls}
    for opening in project.openings:
        if opening.host_id not in wall_ids:
            issues.append(ValidationIssue("OPENING_HOST_MISSING", "error", f"Opening {opening.id} host wall is missing.", opening.id))
            continue
        host = next(wall for wall in project.walls if wall.id == opening.host_id)
        if opening.width_mm >= _segment_length(host.start, host.end):
            issues.append(ValidationIssue("OPENING_TOO_WIDE", "error", f"Opening {opening.id} is wider than host wall {host.id}.", opening.id))
        if opening.sill_elevation_mm + opening.height_mm > host.top_elevation_mm + 1:
            issues.append(ValidationIssue("OPENING_TOO_TALL", "error", f"Opening {opening.id} extends above host wall {host.id}.", opening.id))

    steel_types = {member.member_type for member in project.steel_members}
    if steel_package:
        pipe_support_package = "pipe_support" in steel_types
        if not pipe_support_package and "brace" not in steel_types:
            issues.append(ValidationIssue("STEEL_BRACING_MISSING", "error", "Steel comment-resolution package requires at least one brace member."))
        if "column" not in steel_types:
            issues.append(ValidationIssue("STEEL_COLUMNS_MISSING", "error", "Steel package requires support columns."))
        if pipe_support_package and "pipe_support" not in steel_types:
            issues.append(ValidationIssue("PIPE_SUPPORT_MISSING", "error", "Pipe-support package requires pipe/support centerline members."))
        for member in project.steel_members:
            if _distance(Point2D(x=member.start.x, y=member.start.z), Point2D(x=member.end.x, y=member.end.z)) < 100:
                issues.append(ValidationIssue("STEEL_MEMBER_TOO_SHORT", "error", f"Steel member {member.id} is too short.", member.id))

    view_types = {view.view_type for view in project.drawing_package.views}
    for required in {"foundation_plan", "roof_framing_plan", "section", "detail", "schedule"}:
        if required not in view_types:
            issues.append(ValidationIssue("VIEW_MISSING", "error", f"Required drawing view missing: {required}."))

    if len(project.drawing_package.sections) < 2:
        issues.append(ValidationIssue("SECTION_MISSING", "error", "At least two section markers are required for a reviewable package."))

    if not project.drawing_package.dimensions:
        issues.append(ValidationIssue("DIMENSIONS_MISSING", "error", "Plan dimensions are required."))

    if len(project.drawing_package.details) < 2:
        issues.append(ValidationIssue("DETAILS_MISSING", "error", "Footing, column, and slab detail callouts are required."))

    schedule_types = {schedule.schedule_type for schedule in project.drawing_package.schedules}
    required_schedules = {"steel_member", "material_takeoff"} if steel_package else {"bar_bending", "footing", "column", "beam", "material_takeoff"}
    for required_schedule in required_schedules:
        if required_schedule not in schedule_types:
            issues.append(ValidationIssue("SCHEDULES_MISSING", "error", f"Required schedule missing: {required_schedule}."))
    if project.walls and "wall" not in schedule_types:
        issues.append(ValidationIssue("SCHEDULES_MISSING", "error", "Required schedule missing: wall."))
    if project.steel_members and "steel_member" not in schedule_types:
        issues.append(ValidationIssue("SCHEDULES_MISSING", "error", "Required schedule missing: steel_member."))

    if not project.drawing_package.sheets:
        issues.append(ValidationIssue("SHEETS_MISSING", "error", "At least one sheet definition is required."))

    if not project.drawing_package.general_notes:
        issues.append(ValidationIssue("NOTES_MISSING", "warning", "General structural notes are missing."))

    passed = not any(issue.severity == "error" for issue in issues)
    return ValidationReport(passed=passed, issues=issues)
