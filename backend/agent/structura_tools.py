from __future__ import annotations

import math
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
    Point3D,
    RebarSpec,
    ScheduleDefinition,
    SectionMarker,
    SheetDefinition,
    Slab,
    SteelMember,
    StripFooting,
    StructuraProject,
    Column,
    Opening,
    Wall,
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

    def add_strip_footing(
        self,
        footing_id: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width_mm: float,
        depth_mm: float,
        top_elevation_mm: float,
        rebar: Iterable[RebarSpec] | None = None,
    ) -> None:
        self._replace_or_add(
            self.project.strip_footings,
            StripFooting(
                id=footing_id,
                start=Point2D(x=start_x, y=start_y),
                end=Point2D(x=end_x, y=end_y),
                width_mm=width_mm,
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

    def add_wall(
        self,
        wall_id: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        thickness_mm: float,
        base_elevation_mm: float,
        top_elevation_mm: float,
        wall_type: str = "rc_shear_wall",
        rebar: Iterable[RebarSpec] | None = None,
    ) -> None:
        self._replace_or_add(
            self.project.walls,
            Wall(
                id=wall_id,
                start=Point2D(x=start_x, y=start_y),
                end=Point2D(x=end_x, y=end_y),
                thickness_mm=thickness_mm,
                base_elevation_mm=base_elevation_mm,
                top_elevation_mm=top_elevation_mm,
                wall_type=wall_type,  # type: ignore[arg-type]
                rebar=list(rebar or []),
            ),
        )

    def add_opening(
        self,
        opening_id: str,
        host_id: str,
        center_x: float,
        center_y: float,
        width_mm: float,
        height_mm: float,
        sill_elevation_mm: float,
        opening_type: str = "door",
    ) -> None:
        self._replace_or_add(
            self.project.openings,
            Opening(
                id=opening_id,
                host_id=host_id,
                center=Point2D(x=center_x, y=center_y),
                width_mm=width_mm,
                height_mm=height_mm,
                sill_elevation_mm=sill_elevation_mm,
                opening_type=opening_type,  # type: ignore[arg-type]
            ),
        )

    def add_steel_member(
        self,
        member_id: str,
        member_type: str,
        start_x: float,
        start_y: float,
        start_z: float,
        end_x: float,
        end_y: float,
        end_z: float,
        section: str,
        material_grade: str = "S275",
        connection_note: str = "",
    ) -> None:
        self._replace_or_add(
            self.project.steel_members,
            SteelMember(
                id=member_id,
                member_type=member_type,  # type: ignore[arg-type]
                start=Point3D(x=start_x, y=start_y, z=start_z),
                end=Point3D(x=end_x, y=end_y, z=end_z),
                section=section,
                material_grade=material_grade,
                connection_note=connection_note,
            ),
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
        elevated_slabs = sorted({round(slab.elevation_mm, 3) for slab in self.project.slabs if slab.elevation_mm > 0})
        views: list[DrawingView] = [
            DrawingView(id="V-FOUNDATION", view_type="foundation_plan", title="Foundation Plan"),
        ]
        if len(elevated_slabs) > 1:
            for index, elevation in enumerate(elevated_slabs, start=1):
                is_roof = index == len(elevated_slabs)
                views.append(
                    DrawingView(
                        id="V-ROOF" if is_roof else f"V-FLOOR-{index}",
                        view_type="roof_framing_plan" if is_roof else "floor_framing_plan",
                        title="Roof Framing Plan" if is_roof else f"Level {index} Framing Plan",
                    )
                )
        else:
            views.append(DrawingView(id="V-ROOF", view_type="roof_framing_plan", title="Roof Framing Plan"))
        views.extend(
            [
                DrawingView(id="V-SECTION-A", view_type="section", title="Section A-A"),
                DrawingView(id="V-SECTION-B", view_type="section", title="Section B-B"),
                DrawingView(id="V-FOOTING-DETAIL", view_type="detail", title="Isolated Footing Details", scale="1:25"),
                DrawingView(id="V-COLUMN-DETAIL", view_type="detail", title="Column Reinforcement Details", scale="1:25"),
                DrawingView(id="V-ROOF-DETAIL", view_type="detail", title="Roof Slab Reinforcement Details", scale="1:25"),
                DrawingView(id="V-WALL-DETAIL", view_type="detail", title="Core Wall and Opening Details", scale="1:25"),
                DrawingView(id="V-BBS", view_type="schedule", title="Bar Bending Schedule"),
            ]
        )
        for view in views:
            self._replace_or_add(self.project.drawing_package.views, view)

    def ensure_schedules(self) -> None:
        schedules = [
            ScheduleDefinition(id="SCH-BBS", schedule_type="bar_bending", title="Bar Bending Schedule"),
            ScheduleDefinition(id="SCH-FOOTING", schedule_type="footing", title="Footing Schedule"),
            ScheduleDefinition(id="SCH-STRIP-FOOTING", schedule_type="strip_footing", title="Strip Footing Schedule"),
            ScheduleDefinition(id="SCH-COLUMN", schedule_type="column", title="Column Schedule"),
            ScheduleDefinition(id="SCH-BEAM", schedule_type="beam", title="Beam Schedule"),
            ScheduleDefinition(id="SCH-WALL", schedule_type="wall", title="Wall and Core Schedule"),
            ScheduleDefinition(id="SCH-OPENING", schedule_type="opening", title="Opening Schedule"),
            ScheduleDefinition(id="SCH-STEEL", schedule_type="steel_member", title="Structural Steel Member Schedule"),
            ScheduleDefinition(id="SCH-MATERIAL", schedule_type="material_takeoff", title="Concrete and Rebar Takeoff"),
        ]
        for schedule in schedules:
            if schedule.schedule_type == "strip_footing" and not self.project.strip_footings:
                continue
            if schedule.schedule_type in {"wall", "opening"} and not (self.project.walls or self.project.openings):
                continue
            if schedule.schedule_type == "steel_member" and not self.project.steel_members:
                continue
            self._replace_or_add(self.project.drawing_package.schedules, schedule)

    def ensure_detail_callouts(self) -> None:
        first_footing = self.project.footings[0].id if self.project.footings else None
        first_column = self.project.columns[0].id if self.project.columns else None
        first_slab = self.project.slabs[0].id if self.project.slabs else None
        first_wall = self.project.walls[0].id if self.project.walls else None
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
        if first_wall:
            details.extend(
                [
                    DetailCallout(
                        id="DET-CORE-WALL",
                        detail_type="wall_reinforcement",
                        title="Typical RC Core Wall Reinforcement",
                        source_entity_id=first_wall,
                        parameters={"boundary_bars": "T16", "web_rebar": "T12 @200 each face"},
                    ),
                    DetailCallout(
                        id="DET-WALL-OPENING",
                        detail_type="core_wall_opening",
                        title="Typical Wall Opening Trimmer Bars",
                        source_entity_id=first_wall,
                        parameters={"trimmer_bars": "2T16 each side", "diagonal_bars": "2T12"},
                    ),
                ]
            )
        for detail in details:
            self._replace_or_add(self.project.drawing_package.details, detail)

    def ensure_sheet_set(self) -> None:
        arrangement_views = ["V-FOUNDATION"]
        arrangement_views.extend(
            view.id
            for view in self.project.drawing_package.views
            if view.view_type in {"floor_framing_plan", "roof_framing_plan"}
        )
        arrangement_views.extend(["V-SECTION-A", "V-SECTION-B"])
        sheets = [
            SheetDefinition(
                id="SHT-S-001",
                number="S-001",
                title="General Structural Arrangement",
                view_ids=list(dict.fromkeys(arrangement_views)),
            ),
            SheetDefinition(
                id="SHT-S-002",
                number="S-002",
                title="Reinforcement Details and Schedules",
                view_ids=["V-FOOTING-DETAIL", "V-COLUMN-DETAIL", "V-ROOF-DETAIL", "V-WALL-DETAIL", "V-BBS"],
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

    def create_steel_bracing_comment_resolution(self, title: str = "Steel Bracing Comment Resolution") -> StructuraProject:
        self.project.title = title
        self.project.description = "AI-generated structural steel comment-resolution package for unsupported conveyor/platform members."
        _append_unique(self.project.assumptions, "Supervisor/red-pen comment requires additional bracing for an unsupported steel member.")
        _append_unique(self.project.assumptions, "Steel repair geometry inferred from extracted PDF dimensions and visible framing layout.")
        self.add_level("L-FLOOR", 0, "Finished Floor")
        self.add_level("L-STEEL", 4300, "Steel Support Level")
        spans = [0.0, 4000.0, 8000.0, 12000.0, 15500.0, 18500.0]
        for index, x in enumerate(spans, start=1):
            self.add_grid_line(f"GX-ST-{index}", "x", x, str(index))
            self.add_steel_member(f"ST-C{index}", "column", x, 0, 0, x, 0, 4300, "SHS 100x4", connection_note="Base plate and anchor bolts by engineer.")
        for index, (start_x, end_x) in enumerate(zip(spans, spans[1:]), start=1):
            self.add_steel_member(f"ST-B{index}", "beam", start_x, 0, 4300, end_x, 0, 4300, "SHS 100x4", connection_note="Weld/bolt to column cap plate.")
        brace_pairs = [(4000.0, 8000.0), (8000.0, 12000.0), (12000.0, 15500.0)]
        for index, (start_x, end_x) in enumerate(brace_pairs, start=1):
            mid_x = (start_x + end_x) / 2
            self.add_steel_member(f"ST-BR{index}A", "brace", start_x, 0, 4300, mid_x, 0, 3100, "L50x6", connection_note="Add gusset plate both ends.")
            self.add_steel_member(f"ST-BR{index}B", "brace", end_x, 0, 4300, mid_x, 0, 3100, "L50x6", connection_note="Add gusset plate both ends.")
        self.add_steel_member("ST-UNSUPPORTED-REF", "platform", 6500, 0, 4300, 13750, 0, 4300, "Existing conveyor/platform edge", connection_note="Reference member flagged by comment.")
        self.add_dimension("D-STEEL-LENGTH", Point2D(x=0, y=0), Point2D(x=18500, y=0), -900, "18500")
        self.add_section("SEC-STEEL-A", "A-A", Point2D(x=0, y=-500), Point2D(x=18500, y=-500))
        self.add_section("SEC-STEEL-B", "B-B", Point2D(x=9250, y=-500), Point2D(x=9250, y=500))
        self.ensure_professional_drawing_package()
        return self.project

    def create_pipe_support_coordination_package(self, title: str = "Fire-Fighting Pipe Support Coordination Package") -> StructuraProject:
        self.project.title = title
        self.project.description = "AI-generated coordination package for fire-fighting pipe supports inside an industrial production shed."
        _append_unique(self.project.assumptions, "Existing production shed columns and UPN 160 supports inferred from PDF drawing context.")
        _append_unique(self.project.assumptions, "Pipe routes are represented as support-centerline members for coordination and engineer review.")
        self.add_level("L-FLOOR", 0, "Finished Floor")
        self.add_level("L-PIPE-SUPPORT", 2000, "Fire-Fighting Pipe Support Level")
        positions = [round(index * 7700.0, 3) for index in range(11)]
        for index, x in enumerate(positions, start=1):
            self.add_grid_line(f"GX-PL-{index}", "x", x, str(12 - index))
            self.add_steel_member(f"PS-C{index}", "column", x, 0, 0, x, 0, 2000, "UPN 160", connection_note="Clamp/weld support to existing shed column after site verification.")
        for index, (start_x, end_x) in enumerate(zip(positions, positions[1:]), start=1):
            self.add_steel_member(f"PS-RAIL{index}", "beam", start_x, 0, 2000, end_x, 0, 2000, "UPN 160", connection_note="Continuous pipe support rail.")
        pipe_specs = [("NPS 6 CS SCH40", 2100.0), ("NPS 4 CS SCH40", 2250.0), ("NPS 2 1/2 CS SCH40", 2400.0)]
        for index, (section, z) in enumerate(pipe_specs, start=1):
            self.add_steel_member(f"FF-PIPE-{index}", "pipe_support", positions[0], 0, z, positions[-1], 0, z, section, "CS", "Coordinate pipe clearances and hanger spacing with firefighting engineer.")
        for index, x in enumerate((positions[0], positions[5], positions[9]), start=1):
            self.add_steel_member(f"FHC-REF-{index}", "misc", x + 1200, 0, 0, x + 1200, 0, 1600, "Fire hose cabinet reference", connection_note="Reference only; verify final cabinet location.")
        self.add_dimension("D-PIPELINE-LENGTH", Point2D(x=0, y=0), Point2D(x=positions[-1], y=0), -900, f"{positions[-1]:.0f}")
        self.add_section("SEC-PIPE-A", "A-A", Point2D(x=0, y=-500), Point2D(x=positions[-1], y=-500))
        self.add_section("SEC-PIPE-B", "B-B", Point2D(x=positions[5], y=-500), Point2D(x=positions[5], y=500))
        self.ensure_professional_drawing_package()
        return self.project

    def ensure_building_frame(self, width_mm: float, length_mm: float, story_count: int = 1, title: str | None = None) -> StructuraProject:
        """Complete a rectangular RC frame from explicit design-scope intent."""
        width_mm = max(float(width_mm), 1000.0)
        length_mm = max(float(length_mm), 1000.0)
        story_count = max(1, int(story_count))
        if title and self.project.title in {"StructurAI Project", "StructurAI Drafting Package", "RC Structural Room"}:
            self.project.title = title
        elif title and not self.project.title.strip():
            self.project.title = title
        self.project.description = self.project.description or (
            f"AI-generated reinforced concrete structural drafting package, {width_mm:.0f}x{length_mm:.0f}mm, "
            f"{story_count} {'story' if story_count == 1 else 'stories'}."
        )
        _append_unique(self.project.assumptions, "Rectangular reinforced-concrete frame inferred from prompt/design brief.")
        _append_unique(self.project.assumptions, "Support grid completed parametrically so beams and slabs have explicit supports.")

        foundation_top = -500.0
        self.add_level("L-FOUNDATION", foundation_top, "Foundation Top")
        self.add_level("L-GROUND", 0, "Ground Floor")
        elevated_levels = self._ensure_story_levels(story_count)
        self._dedupe_levels_by_elevation()
        roof_elevation = elevated_levels[-1]

        x_positions = _support_positions(width_mm, max_bay_mm=7500)
        y_positions = _support_positions(length_mm, max_bay_mm=4500)
        self._ensure_grid_positions("x", x_positions, [str(index) for index in range(1, len(x_positions) + 1)])
        self._ensure_grid_positions("y", y_positions, [chr(65 + index) for index in range(len(y_positions))])
        self._prune_supports_to_grid(x_positions, y_positions)

        footing_size = _round_to_nearest(max(1400.0, min(2600.0, 1250.0 + story_count * 180.0 + max(width_mm, length_mm) / 30.0)), 50)
        footing_depth = _round_to_nearest(max(500.0, min(900.0, 420.0 + story_count * 70.0)), 50)
        column_size = _round_to_nearest(max(300.0, min(550.0, 280.0 + story_count * 45.0)), 50)
        slab_thickness = _round_to_nearest(max(150.0, min(250.0, 135.0 + story_count * 15.0)), 10)

        support_points = [(x, y) for y in y_positions for x in x_positions]
        for index, (x, y) in enumerate(support_points, start=1):
            footing = self._find_footing_at(x, y)
            footing_id = footing.id if footing else f"F{index}"
            self.add_footing(
                footing_id,
                x,
                y,
                footing_size,
                footing_size,
                footing_depth,
                foundation_top,
                [
                    RebarSpec(mark=f"{footing_id}-BOT-X", diameter_mm=16, spacing_mm=150, direction="x", cover_mm=75),
                    RebarSpec(mark=f"{footing_id}-BOT-Y", diameter_mm=16, spacing_mm=150, direction="y", cover_mm=75),
                ],
            )
            column = self._find_column_at(x, y)
            column_id = column.id if column else f"C{index}"
            self.add_column(
                column_id,
                x,
                y,
                column_size,
                column_size,
                foundation_top,
                roof_elevation,
                [
                    RebarSpec(mark=f"{column_id}-VERT", diameter_mm=16 if story_count <= 2 else 20, quantity=8, direction="longitudinal", cover_mm=40),
                    RebarSpec(mark=f"{column_id}-TIES", diameter_mm=8, spacing_mm=150, direction="transverse", cover_mm=40),
                ],
            )

        self._prune_unsupported_beams()
        for level_index, elevation in enumerate(elevated_levels, start=1):
            for row_index, y in enumerate(y_positions):
                for bay_index, (start_x, end_x) in enumerate(zip(x_positions, x_positions[1:]), start=1):
                    existing_beam = self._find_beam(start_x, y, end_x, y, elevation)
                    beam_id = existing_beam.id if existing_beam else f"B-L{level_index}-Y{row_index + 1}-X{bay_index}"
                    span = end_x - start_x
                    self.add_beam(
                        beam_id,
                        start_x,
                        y,
                        end_x,
                        y,
                        300 if story_count > 1 else 250,
                        _beam_depth(span),
                        elevation,
                        _beam_rebar(beam_id, story_count),
                    )
            for col_index, x in enumerate(x_positions, start=1):
                for bay_index, (start_y, end_y) in enumerate(zip(y_positions, y_positions[1:]), start=1):
                    existing_beam = self._find_beam(x, start_y, x, end_y, elevation)
                    beam_id = existing_beam.id if existing_beam else f"B-L{level_index}-X{col_index}-Y{bay_index}"
                    span = end_y - start_y
                    self.add_beam(
                        beam_id,
                        x,
                        start_y,
                        x,
                        end_y,
                        300 if story_count > 1 else 250,
                        _beam_depth(span),
                        elevation,
                        _beam_rebar(beam_id, story_count),
                    )
            existing_slab = self._find_slab_at_elevation(elevation)
            slab_id = existing_slab.id if existing_slab else ("S1" if story_count == 1 else ("S-ROOF" if level_index == len(elevated_levels) else f"S-L{level_index}"))
            self.add_slab(
                slab_id,
                [Point2D(x=0, y=0), Point2D(x=width_mm, y=0), Point2D(x=width_mm, y=length_mm), Point2D(x=0, y=length_mm)],
                slab_thickness,
                elevation,
                [
                    RebarSpec(mark=f"{slab_id}-X", diameter_mm=12 if story_count <= 2 else 14, spacing_mm=150, direction="x", cover_mm=30),
                    RebarSpec(mark=f"{slab_id}-Y", diameter_mm=12 if story_count <= 2 else 14, spacing_mm=150, direction="y", cover_mm=30),
                ],
            )

        self._dedupe_beams_by_geometry()
        self._dedupe_slabs_by_elevation()
        self._ensure_lateral_core(width_mm, length_mm, foundation_top, roof_elevation, story_count, elevated_levels)
        self._ensure_scope_dimensions(width_mm, length_mm, x_positions, y_positions)
        self.add_section("SEC-A", "A-A", Point2D(x=-500, y=length_mm / 2), Point2D(x=width_mm + 500, y=length_mm / 2))
        self.add_section("SEC-B", "B-B", Point2D(x=width_mm / 2, y=-500), Point2D(x=width_mm / 2, y=length_mm + 500))
        self.ensure_professional_drawing_package()
        return self.project

    def _ensure_story_levels(self, story_count: int) -> list[float]:
        positive = sorted({level.elevation_mm for level in self.project.levels if level.elevation_mm > 0})
        if len(positive) >= story_count:
            return positive[:story_count]
        floor_to_floor = 3000.0 if story_count == 1 else 3500.0
        for index in range(len(positive) + 1, story_count + 1):
            elevation = floor_to_floor * index
            level_id = "L-ROOF" if index == story_count else f"L-FLOOR-{index}"
            name = "Roof" if index == story_count else f"Level {index}"
            self.add_level(level_id, elevation, name)
            positive.append(elevation)
        return positive[:story_count]

    def _ensure_grid_positions(self, axis: str, positions: list[float], labels: list[str]) -> None:
        self.project.grid_lines = [
            grid
            for grid in self.project.grid_lines
            if grid.axis != axis or any(abs(grid.offset_mm - position) <= 1.0 for position in positions)
        ]
        existing = [grid for grid in self.project.grid_lines if grid.axis == axis]
        for index, (position, label) in enumerate(zip(positions, labels), start=1):
            matching = next((grid for grid in existing if abs(grid.offset_mm - position) <= 1.0), None)
            if matching:
                if matching.label != label:
                    matching.label = label
                    self.project.change_log.append(f"Updated grid {matching.id} label to {label}.")
                continue
            prefix = "GX" if axis == "x" else "GY"
            self.add_grid_line(f"{prefix}-{index}", axis, position, label)

    def _find_footing_at(self, x: float, y: float):
        return _find_by_center(self.project.footings, x, y)

    def _find_column_at(self, x: float, y: float):
        return _find_by_center(self.project.columns, x, y)

    def _find_slab_at_elevation(self, elevation: float):
        for slab in self.project.slabs:
            if abs(slab.elevation_mm - elevation) <= 1.0:
                return slab
        return None

    def _find_beam(self, start_x: float, start_y: float, end_x: float, end_y: float, elevation: float):
        for beam in self.project.beams:
            if abs(beam.elevation_mm - elevation) > 1.0:
                continue
            same_direction = (
                _points_close(beam.start, start_x, start_y)
                and _points_close(beam.end, end_x, end_y)
            )
            reverse_direction = (
                _points_close(beam.start, end_x, end_y)
                and _points_close(beam.end, start_x, start_y)
            )
            if same_direction or reverse_direction:
                return beam
        return None

    def _dedupe_levels_by_elevation(self) -> None:
        unique = {}
        for level in sorted(self.project.levels, key=lambda item: (item.elevation_mm, 0 if item.id.startswith("L-") else 1)):
            key = round(level.elevation_mm, 3)
            unique.setdefault(key, level)
        if len(unique) != len(self.project.levels):
            self.project.levels = list(unique.values())
            self.project.change_log.append("Removed duplicate level elevations during compiler normalization.")

    def _dedupe_slabs_by_elevation(self) -> None:
        unique = {}
        for slab in self.project.slabs:
            unique.setdefault(round(slab.elevation_mm, 3), slab)
        if len(unique) != len(self.project.slabs):
            self.project.slabs = list(unique.values())
            self.project.change_log.append("Removed duplicate slab elevations during compiler normalization.")

    def _dedupe_beams_by_geometry(self) -> None:
        unique = {}
        for beam in self.project.beams:
            start = (round(beam.start.x, 3), round(beam.start.y, 3))
            end = (round(beam.end.x, 3), round(beam.end.y, 3))
            ordered = tuple(sorted([start, end]))
            key = (round(beam.elevation_mm, 3), ordered)
            unique.setdefault(key, beam)
        if len(unique) != len(self.project.beams):
            self.project.beams = list(unique.values())
            self.project.change_log.append("Removed duplicate beams during compiler normalization.")

    def _ensure_lateral_core(self, width_mm: float, length_mm: float, base_elevation: float, roof_elevation: float, story_count: int, elevated_levels: list[float]) -> None:
        if story_count < 2 or min(width_mm, length_mm) < 7000:
            return
        _append_unique(self.project.assumptions, "Multi-story frame includes an RC core/shear-wall lateral system generated by the StructurAI engine.")
        core_width = min(max(width_mm * 0.18, 2400.0), max(2400.0, width_mm - 2400.0), 4200.0)
        core_length = min(max(length_mm * 0.22, 3000.0), max(2400.0, length_mm - 2400.0), 5000.0)
        x0 = round(width_mm / 2 - core_width / 2, 3)
        x1 = round(width_mm / 2 + core_width / 2, 3)
        y0 = round(length_mm / 2 - core_length / 2, 3)
        y1 = round(length_mm / 2 + core_length / 2, 3)
        thickness = 250.0 if story_count <= 3 else 300.0
        strip_width = thickness + 800.0
        strip_depth = 550.0 if story_count <= 3 else 700.0
        wall_rebar = [
            RebarSpec(mark="CORE-VERT", diameter_mm=16, spacing_mm=200, direction="longitudinal", cover_mm=40),
            RebarSpec(mark="CORE-HORZ", diameter_mm=12, spacing_mm=200, direction="transverse", cover_mm=40),
        ]
        strip_rebar = [
            RebarSpec(mark="SF-CORE-BOT-LONG", diameter_mm=16, spacing_mm=150, direction="longitudinal", cover_mm=75),
            RebarSpec(mark="SF-CORE-BOT-TRANS", diameter_mm=12, spacing_mm=150, direction="transverse", cover_mm=75),
        ]
        walls = [
            ("CORE-W-N", x0, y1, x1, y1),
            ("CORE-W-E", x1, y0, x1, y1),
            ("CORE-W-S", x0, y0, x1, y0),
            ("CORE-W-W", x0, y0, x0, y1),
        ]
        for wall_id, sx, sy, ex, ey in walls:
            self.add_wall(wall_id, sx, sy, ex, ey, thickness, base_elevation, roof_elevation, "rc_core_wall", wall_rebar)
            self.add_strip_footing(f"SF-{wall_id}", sx, sy, ex, ey, strip_width, strip_depth, base_elevation, strip_rebar)

        floor_bases = [0.0] + elevated_levels[:-1]
        for index, sill in enumerate(floor_bases, start=1):
            self.add_opening(
                f"OP-CORE-S-{index}",
                "CORE-W-S",
                width_mm / 2,
                y0,
                1000.0,
                2100.0,
                sill,
                "door",
            )

    def _prune_unsupported_beams(self) -> None:
        if not self.project.beams or not self.project.columns:
            return
        kept: list[Beam] = []
        removed: list[str] = []
        for beam in self.project.beams:
            if _has_column_at(self.project.columns, beam.start) and _has_column_at(self.project.columns, beam.end):
                kept.append(beam)
            else:
                removed.append(beam.id)
        if removed:
            self.project.beams = kept
            self.project.change_log.append(f"Removed unsupported AI beam(s): {', '.join(removed[:8])}.")

    def _prune_supports_to_grid(self, x_positions: list[float], y_positions: list[float]) -> None:
        def on_grid(x: float, y: float) -> bool:
            return any(abs(x - gx) <= 1.0 for gx in x_positions) and any(abs(y - gy) <= 1.0 for gy in y_positions)

        before_columns = len(self.project.columns)
        before_footings = len(self.project.footings)
        self.project.columns = [column for column in self.project.columns if on_grid(column.center.x, column.center.y)]
        self.project.footings = [footing for footing in self.project.footings if on_grid(footing.center.x, footing.center.y)]
        removed = (before_columns - len(self.project.columns)) + (before_footings - len(self.project.footings))
        if removed:
            self.project.change_log.append(f"Removed {removed} off-grid AI support element(s) outside the completed structural grid.")

    def _ensure_scope_dimensions(self, width_mm: float, length_mm: float, x_positions: list[float], y_positions: list[float]) -> None:
        self.add_dimension("D-WIDTH-TOTAL", Point2D(x=0, y=0), Point2D(x=width_mm, y=0), -1100, f"{width_mm:.0f}")
        self.add_dimension("D-LENGTH-TOTAL", Point2D(x=width_mm, y=0), Point2D(x=width_mm, y=length_mm), 1100, f"{length_mm:.0f}")
        for index, (start_x, end_x) in enumerate(zip(x_positions, x_positions[1:]), start=1):
            self.add_dimension(f"D-X-BAY-{index}", Point2D(x=start_x, y=0), Point2D(x=end_x, y=0), -700, f"{end_x - start_x:.0f}")
        for index, (start_y, end_y) in enumerate(zip(y_positions, y_positions[1:]), start=1):
            self.add_dimension(f"D-Y-BAY-{index}", Point2D(x=width_mm, y=start_y), Point2D(x=width_mm, y=end_y), 700, f"{end_y - start_y:.0f}")

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
        for strip in self.project.strip_footings:
            if not strip.rebar:
                strip.rebar.extend(
                    [
                        RebarSpec(mark=f"{strip.id}-LONG", diameter_mm=16, spacing_mm=150, direction="longitudinal", cover_mm=75),
                        RebarSpec(mark=f"{strip.id}-TRANS", diameter_mm=12, spacing_mm=150, direction="transverse", cover_mm=75),
                    ]
                )
                self.project.change_log.append(f"Added default strip footing reinforcement to {strip.id}.")
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
        for wall in self.project.walls:
            if not wall.rebar:
                wall.rebar.extend(
                    [
                        RebarSpec(mark=f"{wall.id}-VERT", diameter_mm=16, spacing_mm=200, direction="longitudinal", cover_mm=40),
                        RebarSpec(mark=f"{wall.id}-HORZ", diameter_mm=12, spacing_mm=200, direction="transverse", cover_mm=40),
                    ]
                )
                self.project.change_log.append(f"Added default wall reinforcement to {wall.id}.")

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
        return self.ensure_building_frame(width_mm, length_mm, story_count=1, title=title)


def _support_positions(span_mm: float, max_bay_mm: float = 4500) -> list[float]:
    if span_mm <= max_bay_mm:
        return [0.0, span_mm]
    bay_count = max(2, round(span_mm / max_bay_mm + 0.49))
    bay = span_mm / bay_count
    return [round(index * bay, 3) for index in range(bay_count + 1)]


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _round_to_nearest(value: float, increment: float) -> float:
    return round(value / increment) * increment


def _beam_depth(span_mm: float) -> float:
    return _round_to_nearest(max(450.0, min(800.0, span_mm / 12.0)), 50)


def _beam_rebar(beam_id: str, story_count: int) -> list[RebarSpec]:
    diameter = 16 if story_count <= 2 else 20
    return [
        RebarSpec(mark=f"{beam_id}-TOP", diameter_mm=diameter, quantity=2, direction="longitudinal", cover_mm=40),
        RebarSpec(mark=f"{beam_id}-BOT", diameter_mm=diameter, quantity=2, direction="longitudinal", cover_mm=40),
        RebarSpec(mark=f"{beam_id}-STIR", diameter_mm=8, spacing_mm=150, direction="transverse", cover_mm=40),
    ]


def _find_by_center(collection, x: float, y: float, tolerance: float = 1.0):
    for item in collection:
        if abs(item.center.x - x) <= tolerance and abs(item.center.y - y) <= tolerance:
            return item
    return None


def _points_close(point: Point2D, x: float, y: float, tolerance: float = 1.0) -> bool:
    return abs(point.x - x) <= tolerance and abs(point.y - y) <= tolerance


def _has_column_at(columns: list[Column], point: Point2D, tolerance: float = 150.0) -> bool:
    return any(math.hypot(column.center.x - point.x, column.center.y - point.y) <= tolerance for column in columns)
