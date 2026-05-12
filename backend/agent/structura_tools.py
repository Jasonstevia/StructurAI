from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.core.structura_model import (
    Beam,
    DetailCallout,
    Dimension,
    DrawingView,
    Footing,
    GridLine,
    Level,
    Point2D,
    RebarSpec,
    ScheduleDefinition,
    SectionMarker,
    SheetDefinition,
    Slab,
    StructuraProject,
    Column,
)


@dataclass
class StructuraTools:
    project: StructuraProject

    def _replace_or_add(self, collection: list, item) -> None:
        for index, existing in enumerate(collection):
            if existing.id == item.id:
                collection[index] = item
                self.project.change_log.append(f"Updated {item.__class__.__name__} {item.id}.")
                return
        collection.append(item)
        self.project.change_log.append(f"Added {item.__class__.__name__} {item.id}.")

    def add_level(self, level_id: str, elevation_mm: float, name: str) -> None:
        self._replace_or_add(self.project.levels, Level(id=level_id, elevation_mm=elevation_mm, name=name))

    def add_grid_line(self, grid_id: str, axis: str, offset_mm: float, label: str) -> None:
        self._replace_or_add(self.project.grid_lines, GridLine(id=grid_id, axis=axis, offset_mm=offset_mm, label=label))

    def add_footing(
        self,
        footing_id: str,
        center_x: float,
        center_y: float,
        width_mm: float,
        length_mm: float,
        depth_mm: float,
        top_elevation_mm: float,
        rebar: Iterable[RebarSpec] | None = None,
    ) -> None:
        self._replace_or_add(
            self.project.footings,
            Footing(
                id=footing_id,
                center=Point2D(x=center_x, y=center_y),
                width_mm=width_mm,
                length_mm=length_mm,
                depth_mm=depth_mm,
                top_elevation_mm=top_elevation_mm,
                rebar=list(rebar or []),
            ),
        )

    def add_column(
        self,
        column_id: str,
        center_x: float,
        center_y: float,
        width_mm: float,
        depth_mm: float,
        base_elevation_mm: float,
        top_elevation_mm: float,
        rebar: Iterable[RebarSpec] | None = None,
    ) -> None:
        self._replace_or_add(
            self.project.columns,
            Column(
                id=column_id,
                center=Point2D(x=center_x, y=center_y),
                width_mm=width_mm,
                depth_mm=depth_mm,
                base_elevation_mm=base_elevation_mm,
                top_elevation_mm=top_elevation_mm,
                rebar=list(rebar or []),
            ),
        )

    def add_beam(
        self,
        beam_id: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width_mm: float,
        depth_mm: float,
        elevation_mm: float,
        rebar: Iterable[RebarSpec] | None = None,
    ) -> None:
        self._replace_or_add(
            self.project.beams,
            Beam(
                id=beam_id,
                start=Point2D(x=start_x, y=start_y),
                end=Point2D(x=end_x, y=end_y),
                width_mm=width_mm,
                depth_mm=depth_mm,
                elevation_mm=elevation_mm,
                rebar=list(rebar or []),
            ),
        )

    def add_slab(self, slab_id: str, boundary: list[Point2D], thickness_mm: float, elevation_mm: float, rebar: Iterable[RebarSpec] | None = None) -> None:
        self._replace_or_add(
            self.project.slabs,
            Slab(id=slab_id, boundary=boundary, thickness_mm=thickness_mm, elevation_mm=elevation_mm, rebar=list(rebar or [])),
        )

    def add_dimension(self, dimension_id: str, start: Point2D, end: Point2D, offset_mm: float, label: str | None = None) -> None:
        self._replace_or_add(
            self.project.drawing_package.dimensions,
            Dimension(id=dimension_id, start=start, end=end, offset_mm=offset_mm, label=label),
        )

    def add_section(self, section_id: str, label: str, start: Point2D, end: Point2D) -> None:
        self._replace_or_add(
            self.project.drawing_package.sections,
            SectionMarker(id=section_id, label=label, start=start, end=end),
        )

    def ensure_standard_views(self) -> None:
        views = [
            DrawingView(id="V-FOUNDATION", view_type="foundation_plan", title="Foundation Plan"),
            DrawingView(id="V-ROOF", view_type="roof_framing_plan", title="Roof Framing Plan"),
            DrawingView(id="V-SECTION-A", view_type="section", title="Section A-A"),
            DrawingView(id="V-SECTION-B", view_type="section", title="Section B-B"),
            DrawingView(id="V-FOOTING-DETAIL", view_type="detail", title="Isolated Footing Details", scale="1:25"),
            DrawingView(id="V-COLUMN-DETAIL", view_type="detail", title="Column Reinforcement Details", scale="1:25"),
            DrawingView(id="V-ROOF-DETAIL", view_type="detail", title="Roof Slab Reinforcement Details", scale="1:25"),
            DrawingView(id="V-BBS", view_type="schedule", title="Bar Bending Schedule"),
        ]
        for view in views:
            self._replace_or_add(self.project.drawing_package.views, view)

    def ensure_schedules(self) -> None:
        schedules = [
            ScheduleDefinition(id="SCH-BBS", schedule_type="bar_bending", title="Bar Bending Schedule"),
            ScheduleDefinition(id="SCH-FOOTING", schedule_type="footing", title="Footing Schedule"),
            ScheduleDefinition(id="SCH-COLUMN", schedule_type="column", title="Column Schedule"),
            ScheduleDefinition(id="SCH-BEAM", schedule_type="beam", title="Beam Schedule"),
            ScheduleDefinition(id="SCH-MATERIAL", schedule_type="material_takeoff", title="Concrete and Rebar Takeoff"),
        ]
        for schedule in schedules:
            self._replace_or_add(self.project.drawing_package.schedules, schedule)

    def ensure_detail_callouts(self) -> None:
        first_footing = self.project.footings[0].id if self.project.footings else None
        first_column = self.project.columns[0].id if self.project.columns else None
        first_slab = self.project.slabs[0].id if self.project.slabs else None
        details = [
            DetailCallout(
                id="DET-FOOTING-PLAN-SECTION",
                detail_type="isolated_footing",
                title="Typical Isolated Footing Plan and Section",
                source_entity_id=first_footing,
                parameters={"show_rebar": True, "show_cover": True, "show_subgrade": True},
            ),
            DetailCallout(
                id="DET-COLUMN-STARTER",
                detail_type="column_reinforcement",
                title="Typical Column Starter Bars and Ties",
                source_entity_id=first_column,
                parameters={"lap_length_mm": 650, "starter_projection_mm": 600},
            ),
            DetailCallout(
                id="DET-ROOF-SLAB",
                detail_type="roof_slab_reinforcement",
                title="Typical Roof Slab Reinforcement",
                source_entity_id=first_slab,
                parameters={"top_cover_mm": 30, "bottom_cover_mm": 30},
            ),
        ]
        for detail in details:
            self._replace_or_add(self.project.drawing_package.details, detail)

    def ensure_sheet_set(self) -> None:
        sheets = [
            SheetDefinition(
                id="SHT-S-001",
                number="S-001",
                title="General Structural Arrangement",
                view_ids=["V-FOUNDATION", "V-ROOF", "V-SECTION-A", "V-SECTION-B"],
            ),
            SheetDefinition(
                id="SHT-S-002",
                number="S-002",
                title="Reinforcement Details and Schedules",
                view_ids=["V-FOOTING-DETAIL", "V-COLUMN-DETAIL", "V-ROOF-DETAIL", "V-BBS"],
            ),
        ]
        for sheet in sheets:
            self._replace_or_add(self.project.drawing_package.sheets, sheet)

    def ensure_professional_drawing_package(self) -> None:
        self.ensure_reinforcement_defaults()
        self.ensure_standard_views()
        self.ensure_plan_annotations()
        self.ensure_detail_callouts()
        self.ensure_schedules()
        self.ensure_sheet_set()
        self.add_standard_notes()

    def ensure_reinforcement_defaults(self) -> None:
        for footing in self.project.footings:
            if not footing.rebar:
                footing.rebar.extend(
                    [
                        RebarSpec(mark=f"{footing.id}-BOT-X", diameter_mm=16, spacing_mm=150, direction="x", cover_mm=75),
                        RebarSpec(mark=f"{footing.id}-BOT-Y", diameter_mm=16, spacing_mm=150, direction="y", cover_mm=75),
                    ]
                )
                self.project.change_log.append(f"Added default footing reinforcement to {footing.id}.")
        for column in self.project.columns:
            if not column.rebar:
                column.rebar.extend(
                    [
                        RebarSpec(mark=f"{column.id}-VERT", diameter_mm=16, quantity=8, direction="longitudinal", cover_mm=40),
                        RebarSpec(mark=f"{column.id}-TIES", diameter_mm=8, spacing_mm=150, direction="transverse", cover_mm=40),
                    ]
                )
                self.project.change_log.append(f"Added default column reinforcement to {column.id}.")
        for beam in self.project.beams:
            if not beam.rebar:
                beam.rebar.extend(
                    [
                        RebarSpec(mark=f"{beam.id}-TOP", diameter_mm=16, quantity=2, direction="longitudinal", cover_mm=40),
                        RebarSpec(mark=f"{beam.id}-BOT", diameter_mm=16, quantity=2, direction="longitudinal", cover_mm=40),
                        RebarSpec(mark=f"{beam.id}-STIR", diameter_mm=8, spacing_mm=150, direction="transverse", cover_mm=40),
                    ]
                )
                self.project.change_log.append(f"Added default beam reinforcement to {beam.id}.")
        for slab in self.project.slabs:
            if not slab.rebar:
                slab.rebar.extend(
                    [
                        RebarSpec(mark=f"{slab.id}-X", diameter_mm=12, spacing_mm=150, direction="x", cover_mm=30),
                        RebarSpec(mark=f"{slab.id}-Y", diameter_mm=12, spacing_mm=150, direction="y", cover_mm=30),
                    ]
                )
                self.project.change_log.append(f"Added default slab reinforcement to {slab.id}.")

    def add_standard_notes(self) -> None:
        notes = [
            "All dimensions are in millimeters unless noted otherwise.",
            "Concrete grade C30 assumed for MVP drafting package; engineer to verify.",
            "Reinforcement cover: 75mm for footings, 40mm for columns/beams/slabs unless noted.",
            "This package is generated for engineer review and coordination, not final sealed design.",
        ]
        for note in notes:
            if note not in self.project.drawing_package.general_notes:
                self.project.drawing_package.general_notes.append(note)

    def ensure_plan_annotations(self) -> None:
        points: list[Point2D] = []
        for slab in self.project.slabs:
            points.extend(slab.boundary)
        if not points:
            points.extend(column.center for column in self.project.columns)
        if not points:
            return
        min_x = min(point.x for point in points)
        max_x = max(point.x for point in points)
        min_y = min(point.y for point in points)
        max_y = max(point.y for point in points)
        if not self.project.drawing_package.dimensions:
            self.add_dimension("D-WIDTH", Point2D(x=min_x, y=min_y), Point2D(x=max_x, y=min_y), -700, f"{max_x - min_x:.0f}")
            self.add_dimension("D-LENGTH", Point2D(x=max_x, y=min_y), Point2D(x=max_x, y=max_y), 700, f"{max_y - min_y:.0f}")
        if not self.project.drawing_package.sections:
            self.add_section("SEC-A", "A-A", Point2D(x=min_x - 500, y=(min_y + max_y) / 2), Point2D(x=max_x + 500, y=(min_y + max_y) / 2))
            self.add_section("SEC-B", "B-B", Point2D(x=(min_x + max_x) / 2, y=min_y - 500), Point2D(x=(min_x + max_x) / 2, y=max_y + 500))

    def create_small_rc_room(self, width_mm: float, length_mm: float, title: str = "RC Pump Room") -> StructuraProject:
        self.project.title = title
        self.project.description = f"AI-generated reinforced concrete small-room structural drafting package, {width_mm:.0f}x{length_mm:.0f}mm."
        self.project.assumptions.extend(
            [
                "Rectangular reinforced-concrete room footprint inferred from prompt.",
                "Support grid selected parametrically from room span, with intermediate supports when bay lengths exceed commercial drafting thresholds.",
                "Roof slab assumed at +3000mm with perimeter beams.",
            ]
        )
        self.add_level("L-FOUNDATION", -500, "Foundation Top")
        self.add_level("L-GROUND", 0, "Ground Floor")
        self.add_level("L-ROOF", 3000, "Roof")
        x_positions = _support_positions(width_mm, max_bay_mm=7500)
        y_positions = _support_positions(length_mm, max_bay_mm=4500)
        for index, x in enumerate(x_positions, start=1):
            self.add_grid_line(f"GX-{index}", "x", x, str(index))
        for index, y in enumerate(y_positions):
            self.add_grid_line(f"GY-{chr(65 + index)}", "y", y, chr(65 + index))

        footing_rebar = [RebarSpec(mark="F-BOT-X", diameter_mm=16, spacing_mm=150, direction="x", cover_mm=75), RebarSpec(mark="F-BOT-Y", diameter_mm=16, spacing_mm=150, direction="y", cover_mm=75)]
        column_rebar = [RebarSpec(mark="C-VERT", diameter_mm=16, quantity=8, direction="longitudinal", cover_mm=40), RebarSpec(mark="C-TIES", diameter_mm=8, spacing_mm=150, direction="transverse", cover_mm=40)]
        beam_rebar = [RebarSpec(mark="B-TOP", diameter_mm=16, quantity=2, direction="longitudinal"), RebarSpec(mark="B-BOT", diameter_mm=16, quantity=2, direction="longitudinal"), RebarSpec(mark="B-STIR", diameter_mm=8, spacing_mm=150, direction="transverse")]
        slab_rebar = [RebarSpec(mark="S-X", diameter_mm=12, spacing_mm=150, direction="x", cover_mm=30), RebarSpec(mark="S-Y", diameter_mm=12, spacing_mm=150, direction="y", cover_mm=30)]

        support_points = [(x, y) for y in y_positions for x in x_positions]
        footing_size = 1500 if max(width_mm, length_mm) >= 5000 else 1400
        for index, (x, y) in enumerate(support_points, start=1):
            self.add_footing(f"F{index}", x, y, footing_size, footing_size, 500, -500, footing_rebar)
            self.add_column(f"C{index}", x, y, 300, 300, -500, 3000, column_rebar)

        beam_index = 1
        for y in y_positions:
            for start_x, end_x in zip(x_positions, x_positions[1:]):
                self.add_beam(f"B{beam_index}", start_x, y, end_x, y, 250, 450, 3000, beam_rebar)
                beam_index += 1
        for x in x_positions:
            for start_y, end_y in zip(y_positions, y_positions[1:]):
                self.add_beam(f"B{beam_index}", x, start_y, x, end_y, 250, 450, 3000, beam_rebar)
                beam_index += 1

        self.add_slab(
            "S1",
            [Point2D(x=0, y=0), Point2D(x=width_mm, y=0), Point2D(x=width_mm, y=length_mm), Point2D(x=0, y=length_mm)],
            150,
            3000,
            slab_rebar,
        )
        self.add_dimension("D-WIDTH-TOTAL", Point2D(x=0, y=0), Point2D(x=width_mm, y=0), -1100, f"{width_mm:.0f}")
        self.add_dimension("D-LENGTH-TOTAL", Point2D(x=width_mm, y=0), Point2D(x=width_mm, y=length_mm), 1100, f"{length_mm:.0f}")
        for index, (start_x, end_x) in enumerate(zip(x_positions, x_positions[1:]), start=1):
            self.add_dimension(f"D-X-BAY-{index}", Point2D(x=start_x, y=0), Point2D(x=end_x, y=0), -700, f"{end_x - start_x:.0f}")
        for index, (start_y, end_y) in enumerate(zip(y_positions, y_positions[1:]), start=1):
            self.add_dimension(f"D-Y-BAY-{index}", Point2D(x=width_mm, y=start_y), Point2D(x=width_mm, y=end_y), 700, f"{end_y - start_y:.0f}")
        self.add_section("SEC-A", "A-A", Point2D(x=-500, y=length_mm / 2), Point2D(x=width_mm + 500, y=length_mm / 2))
        self.add_section("SEC-B", "B-B", Point2D(x=width_mm / 2, y=-500), Point2D(x=width_mm / 2, y=length_mm + 500))
        self.ensure_professional_drawing_package()
        return self.project


def _support_positions(span_mm: float, max_bay_mm: float = 4500) -> list[float]:
    if span_mm <= max_bay_mm:
        return [0.0, span_mm]
    bay_count = max(2, round(span_mm / max_bay_mm + 0.49))
    bay = span_mm / bay_count
    return [round(index * bay, 3) for index in range(bay_count + 1)]
