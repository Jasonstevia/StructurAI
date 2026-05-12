from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path

from backend.core.structura_model import Beam, Column, Footing, Slab, StructuraProject


@dataclass
class StepBuilder:
    lines: list[str] = field(default_factory=list)
    next_id: int = 1

    def add(self, text: str) -> str:
        ref = f"#{self.next_id}"
        self.next_id += 1
        self.lines.append(f"{ref}={text};")
        return ref


def export_ifc(project: StructuraProject, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_ifc4_geometry(project), encoding="utf-8")
    return path


def _ifc4_geometry(project: StructuraProject) -> str:
    b = StepBuilder()
    person = b.add("IFCPERSON($,$,'StructurAI',$,$,$,$,$)")
    org = b.add("IFCORGANIZATION($,'StructurAI',$,$,$)")
    actor = b.add(f"IFCPERSONANDORGANIZATION({person},{org},$)")
    app = b.add(f"IFCAPPLICATION({org},'0.2.0','StructurAI Backend','STRUCTURAI')")
    owner = b.add(f"IFCOWNERHISTORY({actor},{app},$,.ADDED.,$,{actor},{app},0)")
    length_unit = b.add("IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)")
    area_unit = b.add("IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)")
    volume_unit = b.add("IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.)")
    units = b.add(f"IFCUNITASSIGNMENT(({length_unit},{area_unit},{volume_unit}))")
    origin = b.add("IFCCARTESIANPOINT((0.,0.,0.))")
    z_dir = b.add("IFCDIRECTION((0.,0.,1.))")
    x_dir = b.add("IFCDIRECTION((1.,0.,0.))")
    world_axis = b.add(f"IFCAXIS2PLACEMENT3D({origin},{z_dir},{x_dir})")
    context = b.add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,{world_axis},$)")
    body_context = b.add(f"IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,{context},$,.MODEL_VIEW.,$)")
    project_ref = b.add(f"IFCPROJECT('{_guid(project.project_id)}',{owner},{_s(project.title)},$,$,$,$,({context}),{units})")

    site_placement = _placement(b, None, 0, 0, 0)
    site = b.add(f"IFCSITE('{_guid(project.project_id + '-site')}',{owner},'Default Site',$,$,{site_placement},$,$,.ELEMENT.,$,$,$,$,$)")
    building_placement = _placement(b, site_placement, 0, 0, 0)
    building = b.add(f"IFCBUILDING('{_guid(project.project_id + '-building')}',{owner},'StructurAI Building',$,$,{building_placement},$,$,.ELEMENT.,$,$,$)")
    storey_placement = _placement(b, building_placement, 0, 0, 0)
    storey = b.add(f"IFCBUILDINGSTOREY('{_guid(project.project_id + '-storey')}',{owner},'Structural Storey',$,$,{storey_placement},$,$,.ELEMENT.,0.)")
    b.add(f"IFCRELAGGREGATES('{_guid(project.project_id + '-rel-site')}',{owner},$,$,{project_ref},({site}))")
    b.add(f"IFCRELAGGREGATES('{_guid(project.project_id + '-rel-bldg')}',{owner},$,$,{site},({building}))")
    b.add(f"IFCRELAGGREGATES('{_guid(project.project_id + '-rel-storey')}',{owner},$,$,{building},({storey}))")

    products: list[str] = []
    for footing in project.footings:
        products.append(_footing_entity(b, footing, owner, body_context, storey_placement))
    for column in project.columns:
        products.append(_column_entity(b, column, owner, body_context, storey_placement))
    for beam in project.beams:
        products.append(_beam_entity(b, beam, owner, body_context, storey_placement))
    for slab in project.slabs:
        products.append(_slab_entity(b, slab, owner, body_context, storey_placement))
    if products:
        b.add(f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{_guid(project.project_id + '-contains')}',{owner},$,$,({','.join(products)}),{storey})")

    return "\n".join(
        [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION(('ViewDefinition [CoordinationView_V2.0]'),'2;1');",
            f"FILE_NAME('{_clean(project.project_id)}.ifc','2026-05-12T00:00:00',('StructurAI'),('StructurAI'),'StructurAI','StructurAI','');",
            "FILE_SCHEMA(('IFC4'));",
            "ENDSEC;",
            "DATA;",
            *b.lines,
            "ENDSEC;",
            "END-ISO-10303-21;",
        ]
    ) + "\n"


def _footing_entity(b: StepBuilder, footing: Footing, owner: str, context: str, parent_placement: str) -> str:
    placement = _placement(b, parent_placement, footing.center.x, footing.center.y, footing.bottom_elevation_mm)
    shape = _extruded_box(b, context, footing.width_mm, footing.length_mm, footing.depth_mm)
    product = b.add(f"IFCFOOTING('{_guid(footing.id)}',{owner},{_s(footing.id)},$,$,{placement},{shape},{_s(footing.id)},.PAD_FOOTING.)")
    _property_set(b, owner, product, footing.id, {"ConcreteGrade": footing.concrete_grade, "Depth_mm": footing.depth_mm})
    return product


def _column_entity(b: StepBuilder, column: Column, owner: str, context: str, parent_placement: str) -> str:
    height = column.top_elevation_mm - column.base_elevation_mm
    placement = _placement(b, parent_placement, column.center.x, column.center.y, column.base_elevation_mm)
    shape = _extruded_box(b, context, column.width_mm, column.depth_mm, height)
    product = b.add(f"IFCCOLUMN('{_guid(column.id)}',{owner},{_s(column.id)},$,$,{placement},{shape},{_s(column.id)},.COLUMN.)")
    _property_set(b, owner, product, column.id, {"ConcreteGrade": column.concrete_grade, "Height_mm": height})
    return product


def _beam_entity(b: StepBuilder, beam: Beam, owner: str, context: str, parent_placement: str) -> str:
    dx = beam.end.x - beam.start.x
    dy = beam.end.y - beam.start.y
    span = math.hypot(dx, dy)
    angle = math.atan2(dy, dx)
    mid_x = (beam.start.x + beam.end.x) / 2
    mid_y = (beam.start.y + beam.end.y) / 2
    placement = _placement(b, parent_placement, mid_x, mid_y, beam.elevation_mm - beam.depth_mm, angle)
    shape = _extruded_box(b, context, span, beam.width_mm, beam.depth_mm)
    product = b.add(f"IFCBEAM('{_guid(beam.id)}',{owner},{_s(beam.id)},$,$,{placement},{shape},{_s(beam.id)},.BEAM.)")
    _property_set(b, owner, product, beam.id, {"ConcreteGrade": beam.concrete_grade, "Span_mm": span})
    return product


def _slab_entity(b: StepBuilder, slab: Slab, owner: str, context: str, parent_placement: str) -> str:
    xs = [point.x for point in slab.boundary]
    ys = [point.y for point in slab.boundary]
    width = max(xs) - min(xs)
    length = max(ys) - min(ys)
    placement = _placement(b, parent_placement, min(xs) + width / 2, min(ys) + length / 2, slab.elevation_mm - slab.thickness_mm)
    shape = _extruded_box(b, context, width, length, slab.thickness_mm)
    product = b.add(f"IFCSLAB('{_guid(slab.id)}',{owner},{_s(slab.id)},$,$,{placement},{shape},{_s(slab.id)},.ROOF.)")
    _property_set(b, owner, product, slab.id, {"ConcreteGrade": slab.concrete_grade, "Thickness_mm": slab.thickness_mm})
    return product


def _placement(b: StepBuilder, parent: str | None, x: float, y: float, z: float, angle_rad: float = 0.0) -> str:
    point = b.add(f"IFCCARTESIANPOINT(({_n(x)},{_n(y)},{_n(z)}))")
    z_dir = b.add("IFCDIRECTION((0.,0.,1.))")
    x_dir = b.add(f"IFCDIRECTION(({_n(math.cos(angle_rad))},{_n(math.sin(angle_rad))},0.))")
    axis = b.add(f"IFCAXIS2PLACEMENT3D({point},{z_dir},{x_dir})")
    parent_ref = parent if parent else "$"
    return b.add(f"IFCLOCALPLACEMENT({parent_ref},{axis})")


def _extruded_box(b: StepBuilder, context: str, width: float, depth: float, height: float) -> str:
    profile = b.add(f"IFCRECTANGLEPROFILEDEF(.AREA.,$,$,{_n(width)},{_n(depth)})")
    origin = b.add("IFCCARTESIANPOINT((0.,0.,0.))")
    z_dir = b.add("IFCDIRECTION((0.,0.,1.))")
    x_dir = b.add("IFCDIRECTION((1.,0.,0.))")
    axis = b.add(f"IFCAXIS2PLACEMENT3D({origin},{z_dir},{x_dir})")
    extrude_dir = b.add("IFCDIRECTION((0.,0.,1.))")
    solid = b.add(f"IFCEXTRUDEDAREASOLID({profile},{axis},{extrude_dir},{_n(height)})")
    representation = b.add(f"IFCSHAPEREPRESENTATION({context},'Body','SweptSolid',({solid}))")
    return b.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({representation}))")


def _property_set(b: StepBuilder, owner: str, product: str, seed: str, properties: dict[str, str | float]) -> None:
    refs: list[str] = []
    for key, value in properties.items():
        if isinstance(value, (float, int)):
            wrapped = f"IFCREAL({_n(float(value))})"
        else:
            wrapped = f"IFCLABEL({_s(str(value))})"
        refs.append(b.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,{wrapped},$)"))
    pset = b.add(f"IFCPROPERTYSET('{_guid(seed + '-pset')}',{owner},'Pset_StructurAI_Structural',$,({','.join(refs)}))")
    b.add(f"IFCRELDEFINESBYPROPERTIES('{_guid(seed + '-rel-pset')}',{owner},$,$,({product}),{pset})")


def _guid(seed: str) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:22]


def _s(value: str) -> str:
    return f"'{_clean(value)}'"


def _clean(value: str) -> str:
    return value.replace("'", "''").replace("\n", " ")


def _n(value: float) -> str:
    if abs(value) < 0.000001:
        return "0."
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text + "." if "." not in text else text
