from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UnitSystem(str, Enum):
    MILLIMETERS = "mm"


class Point2D(BaseModel):
    x: float
    y: float


class Point3D(Point2D):
    z: float = 0.0


class RebarSpec(BaseModel):
    mark: str
    diameter_mm: int = Field(gt=0)
    spacing_mm: int | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, gt=0)
    direction: Literal["x", "y", "longitudinal", "transverse", "both"] = "both"
    cover_mm: int = Field(default=50, ge=25)
    note: str = ""

    def label(self) -> str:
        if self.spacing_mm:
            return f"T{self.diameter_mm} @{self.spacing_mm} {self.direction}"
        if self.quantity:
            return f"{self.quantity}T{self.diameter_mm} {self.direction}"
        return f"T{self.diameter_mm} {self.direction}"


class GridLine(BaseModel):
    id: str
    axis: Literal["x", "y"]
    offset_mm: float
    label: str


class Level(BaseModel):
    id: str
    elevation_mm: float
    name: str


class Footing(BaseModel):
    id: str
    center: Point2D
    width_mm: float = Field(gt=0)
    length_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)
    top_elevation_mm: float
    concrete_grade: str = "C30"
    rebar: list[RebarSpec] = Field(default_factory=list)

    @property
    def bottom_elevation_mm(self) -> float:
        return self.top_elevation_mm - self.depth_mm


class StripFooting(BaseModel):
    id: str
    start: Point2D
    end: Point2D
    width_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)
    top_elevation_mm: float
    concrete_grade: str = "C30"
    rebar: list[RebarSpec] = Field(default_factory=list)

    @property
    def bottom_elevation_mm(self) -> float:
        return self.top_elevation_mm - self.depth_mm

    @model_validator(mode="after")
    def check_length(self) -> "StripFooting":
        if self.start.x == self.end.x and self.start.y == self.end.y:
            raise ValueError("strip footing start and end cannot be equal")
        return self


class Column(BaseModel):
    id: str
    center: Point2D
    width_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)
    base_elevation_mm: float
    top_elevation_mm: float
    concrete_grade: str = "C30"
    rebar: list[RebarSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_height(self) -> "Column":
        if self.top_elevation_mm <= self.base_elevation_mm:
            raise ValueError("column top_elevation_mm must exceed base_elevation_mm")
        return self


class Beam(BaseModel):
    id: str
    start: Point2D
    end: Point2D
    width_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)
    elevation_mm: float
    concrete_grade: str = "C30"
    rebar: list[RebarSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_length(self) -> "Beam":
        if self.start.x == self.end.x and self.start.y == self.end.y:
            raise ValueError("beam start and end cannot be equal")
        return self


class Slab(BaseModel):
    id: str
    boundary: list[Point2D]
    thickness_mm: float = Field(gt=0)
    elevation_mm: float
    concrete_grade: str = "C30"
    rebar: list[RebarSpec] = Field(default_factory=list)

    @field_validator("boundary")
    @classmethod
    def check_boundary(cls, value: list[Point2D]) -> list[Point2D]:
        if len(value) < 3:
            raise ValueError("slab boundary needs at least 3 points")
        return value


class Wall(BaseModel):
    id: str
    start: Point2D
    end: Point2D
    thickness_mm: float = Field(gt=0)
    base_elevation_mm: float
    top_elevation_mm: float
    wall_type: Literal["rc_shear_wall", "rc_core_wall", "masonry_infill", "retaining_wall"] = "rc_shear_wall"
    concrete_grade: str = "C30"
    rebar: list[RebarSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_geometry(self) -> "Wall":
        if self.start.x == self.end.x and self.start.y == self.end.y:
            raise ValueError("wall start and end cannot be equal")
        if self.top_elevation_mm <= self.base_elevation_mm:
            raise ValueError("wall top_elevation_mm must exceed base_elevation_mm")
        return self


class Opening(BaseModel):
    id: str
    host_id: str
    center: Point2D
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    sill_elevation_mm: float = 0.0
    opening_type: Literal["door", "window", "services", "access_panel"] = "door"


class SteelMember(BaseModel):
    id: str
    member_type: Literal["column", "beam", "brace", "platform", "purlin", "pipe_support", "misc"]
    start: Point3D
    end: Point3D
    section: str
    material_grade: str = "S275"
    connection_note: str = ""

    @model_validator(mode="after")
    def check_length(self) -> "SteelMember":
        if self.start.x == self.end.x and self.start.y == self.end.y and self.start.z == self.end.z:
            raise ValueError("steel member start and end cannot be equal")
        return self


class SectionMarker(BaseModel):
    id: str
    label: str
    start: Point2D
    end: Point2D
    target_view_id: str | None = None


class Dimension(BaseModel):
    id: str
    start: Point2D
    end: Point2D
    offset_mm: float = 500
    label: str | None = None


class DetailCallout(BaseModel):
    id: str
    detail_type: Literal[
        "isolated_footing",
        "column_reinforcement",
        "roof_slab_reinforcement",
        "section_reinforcement",
        "wall_reinforcement",
        "core_wall_opening",
        "material_build_up",
    ]
    title: str
    source_entity_id: str | None = None
    scale: str = "1:25"
    parameters: dict[str, Any] = Field(default_factory=dict)


class ScheduleDefinition(BaseModel):
    id: str
    schedule_type: Literal["bar_bending", "footing", "strip_footing", "column", "beam", "wall", "opening", "steel_member", "material_takeoff"]
    title: str
    source_entity_ids: list[str] = Field(default_factory=list)


class SheetDefinition(BaseModel):
    id: str
    number: str
    title: str
    scale: str = "AS SHOWN"
    view_ids: list[str] = Field(default_factory=list)


class DraftingStandard(BaseModel):
    name: str = "StructurAI Professional RC"
    base_text_height_mm: float = 150
    title_text_height_mm: float = 260
    dimension_text_height_mm: float = 120
    layer_prefix: str = "SAI"
    default_plan_scale: str = "1:50"
    default_detail_scale: str = "1:25"


class DrawingView(BaseModel):
    id: str
    view_type: Literal["foundation_plan", "floor_framing_plan", "roof_framing_plan", "section", "detail", "schedule"]
    title: str
    scale: str = "1:50"
    notes: list[str] = Field(default_factory=list)


class DrawingPackage(BaseModel):
    views: list[DrawingView] = Field(default_factory=list)
    dimensions: list[Dimension] = Field(default_factory=list)
    sections: list[SectionMarker] = Field(default_factory=list)
    details: list[DetailCallout] = Field(default_factory=list)
    schedules: list[ScheduleDefinition] = Field(default_factory=list)
    sheets: list[SheetDefinition] = Field(default_factory=list)
    drafting_standard: DraftingStandard = Field(default_factory=DraftingStandard)
    general_notes: list[str] = Field(default_factory=list)


class ExtractedContext(BaseModel):
    source_path: str | None = None
    file_type: str | None = None
    layers: dict[str, int] = Field(default_factory=dict)
    lines: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StructuraProject(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    project_id: str = "structurai-project"
    title: str = "StructurAI Project"
    units: UnitSystem = UnitSystem.MILLIMETERS
    description: str = ""
    levels: list[Level] = Field(default_factory=list)
    grid_lines: list[GridLine] = Field(default_factory=list)
    footings: list[Footing] = Field(default_factory=list)
    strip_footings: list[StripFooting] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)
    beams: list[Beam] = Field(default_factory=list)
    slabs: list[Slab] = Field(default_factory=list)
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    steel_members: list[SteelMember] = Field(default_factory=list)
    drawing_package: DrawingPackage = Field(default_factory=DrawingPackage)
    extracted_context: ExtractedContext | None = None
    assumptions: list[str] = Field(default_factory=list)
    change_log: list[str] = Field(default_factory=list)

    def all_ids(self) -> list[str]:
        ids: list[str] = []
        for collection in (
            self.levels,
            self.grid_lines,
            self.footings,
            self.strip_footings,
            self.columns,
            self.beams,
            self.slabs,
            self.walls,
            self.openings,
            self.steel_members,
            self.drawing_package.views,
            self.drawing_package.dimensions,
            self.drawing_package.sections,
            self.drawing_package.details,
            self.drawing_package.schedules,
            self.drawing_package.sheets,
        ):
            ids.extend(item.id for item in collection)
        return ids

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> "StructuraProject":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
