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


def validate_project(project: StructuraProject) -> ValidationReport:
    issues: list[ValidationIssue] = []

    counts = Counter(project.all_ids())
    for entity_id, count in counts.items():
        if count > 1:
            issues.append(ValidationIssue("DUPLICATE_ID", "error", f"Duplicate id '{entity_id}' appears {count} times.", entity_id))

    if not project.columns:
        issues.append(ValidationIssue("NO_COLUMNS", "error", "At least one column is required for an RC structural package."))

    if not project.footings:
        issues.append(ValidationIssue("NO_FOOTINGS", "error", "At least one footing is required."))

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

    for beam in project.beams:
        supports = [column for column in project.columns if _distance(beam.start, column.center) <= 150 or _distance(beam.end, column.center) <= 150]
        if len(supports) < 2:
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
    for required_schedule in {"bar_bending", "footing", "column", "beam", "material_takeoff"}:
        if required_schedule not in schedule_types:
            issues.append(ValidationIssue("SCHEDULES_MISSING", "error", f"Required schedule missing: {required_schedule}."))

    if not project.drawing_package.sheets:
        issues.append(ValidationIssue("SHEETS_MISSING", "error", "At least one sheet definition is required."))

    if not project.drawing_package.general_notes:
        issues.append(ValidationIssue("NOTES_MISSING", "warning", "General structural notes are missing."))

    passed = not any(issue.severity == "error" for issue in issues)
    return ValidationReport(passed=passed, issues=issues)
