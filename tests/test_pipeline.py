from pathlib import Path
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("XDG_CACHE_HOME", "/tmp/structurai-cache")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/structurai-mpl")

import ezdxf

from backend.agent.agent_controller import AgentController
from backend.agent.structura_tools import StructuraTools
from backend.core.structura_model import StructuraProject
from backend.extractors.dwg_importer import DwgConversionRequired
from backend.extractors.ifc_importer import extract_ifc_context
from backend.input_router import route_input
from backend.core.validator import validate_project
from backend.review.drawing_reviewer import review_dxf


class PipelineTests(unittest.TestCase):
    def test_bootstrap_project_validates_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = AgentController(use_ai=False).run(
                "Design a 3000x4000mm reinforced concrete pump room. Provide isolated footings, roof slab, and a bar bending schedule.",
                output_dir=Path(tmp),
            )
            self.assertTrue(result.validation.passed, result.validation.to_dict())
            self.assertTrue(result.json_path.exists())
            self.assertTrue(result.dxf_path.exists())
            self.assertTrue(result.ifc_path.exists())
            self.assertGreaterEqual(len(result.project.drawing_package.views), 8)
            self.assertGreaterEqual(len(result.project.drawing_package.sections), 2)
            self.assertGreaterEqual(len(result.project.drawing_package.details), 3)
            self.assertGreaterEqual(len(result.project.drawing_package.schedules), 5)
            self.assertIsNotNone(result.drawing_review)
            self.assertTrue(result.drawing_review.passed)
            self.assertGreaterEqual(result.drawing_review.score, 85)
            self.assertTrue(result.dxf_review_path.exists())
            self.assertTrue(result.preview_path.exists())

    def test_validator_catches_and_repair_adds_footing(self) -> None:
        project = StructuraProject(title="Broken")
        tools = StructuraTools(project)
        tools.add_column("C1", 0, 0, 300, 300, -500, 3000)
        tools.ensure_standard_views()
        report = validate_project(project)
        self.assertFalse(report.passed)
        self.assertIn("NO_FOOTINGS", {issue.code for issue in report.errors()})

        with tempfile.TemporaryDirectory() as tmp:
            result = AgentController(use_ai=False).run("Design a 3000x4000mm reinforced concrete pump room.", output_dir=Path(tmp))
            self.assertTrue(result.validation.passed)

    def test_validator_requires_lateral_system_for_multistory(self) -> None:
        project = StructuraProject(title="Tall Broken Frame")
        tools = StructuraTools(project)
        tools.add_level("L-GROUND", 0, "Ground")
        tools.add_level("L-ROOF", 9000, "Roof")
        tools.add_footing("F1", 0, 0, 1400, 1400, 500, -500)
        tools.add_column("C1", 0, 0, 300, 300, -500, 9000)
        tools.ensure_professional_drawing_package()
        report = validate_project(project)
        self.assertFalse(report.passed)
        self.assertIn("LATERAL_SYSTEM_MISSING", {issue.code for issue in report.errors()})

    def test_dxf_package_is_professional_density(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = AgentController(use_ai=False).run(
                "Design a 3000x4000mm reinforced concrete pump room with professional details and schedules.",
                output_dir=Path(tmp),
            )
            doc = ezdxf.readfile(result.dxf_path)
            entities = list(doc.modelspace())
            hatches = [entity for entity in entities if entity.dxftype() == "HATCH"]
            layers = {entity.dxf.layer for entity in entities}
            self.assertGreaterEqual(len(entities), 900)
            self.assertGreaterEqual(len(hatches), 30)
            self.assertIn("SAI-S-REBAR", layers)
            self.assertIn("SAI-SCHEDULE", layers)
            self.assertIn("SAI-H-CONCRETE", layers)
            self.assertEqual(len(doc.audit().errors), 0)

    def test_adaptive_grid_for_larger_pump_room(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = AgentController(use_ai=False).run(
                "Design a 6200x6200mm reinforced concrete pump room with professional details and schedules.",
                output_dir=Path(tmp),
            )
            self.assertEqual(len(result.project.footings), 6)
            self.assertEqual(len(result.project.columns), 6)
            self.assertGreaterEqual(len(result.project.beams), 7)
            self.assertTrue(result.drawing_review and result.drawing_review.passed)

    def test_three_story_metric_prompt_completes_frame_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = AgentController(use_ai=False).run(
                "Design a three-story reinforced concrete office building, 18m x 12m footprint, with central stair/elevator core shear walls, foundation plan, floor framing plans, roof plan, sections, details, and schedules.",
                output_dir=Path(tmp),
            )
            self.assertTrue(result.validation.passed, result.validation.to_dict())
            self.assertGreaterEqual(len(result.project.footings), 16)
            self.assertGreaterEqual(len(result.project.strip_footings), 4)
            self.assertGreaterEqual(len(result.project.columns), 16)
            self.assertGreaterEqual(len(result.project.slabs), 3)
            self.assertGreaterEqual(len(result.project.walls), 4)
            self.assertGreaterEqual(len(result.project.openings), 3)
            self.assertGreaterEqual(max(column.top_elevation_mm for column in result.project.columns), 9000)
            self.assertIn("wall", {schedule.schedule_type for schedule in result.project.drawing_package.schedules})
            self.assertTrue(result.drawing_review and result.drawing_review.passed, result.drawing_review.to_dict() if result.drawing_review else None)
            self.assertTrue(result.preview_path.exists())

            ifc_text = result.ifc_path.read_text(encoding="utf-8")
            self.assertIn("IFCWALL", ifc_text)
            self.assertIn("IFCOPENINGELEMENT", ifc_text)

    def test_pdf_redline_comment_generates_steel_bracing_response(self) -> None:
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not installed.")
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "comment.pdf"
            doc = fitz.open()
            page = doc.new_page(width=1191, height=842)
            page.insert_text((72, 120), "COOKER OVERHEAD CONVEYOR (CC6)")
            page.insert_text((72, 160), "Element without support, Add adequate bracing to support the structure")
            page.insert_text((72, 200), "BILL OF MATERIALS")
            doc.save(pdf_path)
            doc.close()

            result = route_input(
                "Resolve the red-pen comment by adding adequate bracing and a steel member schedule.",
                pdf_path,
                Path(tmp) / "out",
                use_ai=False,
            )
            self.assertTrue(result.validation.passed, result.validation.to_dict())
            self.assertGreaterEqual(len(result.project.steel_members), 10)
            self.assertIn("brace", {member.member_type for member in result.project.steel_members})
            self.assertTrue(result.drawing_review and result.drawing_review.passed, result.drawing_review.to_dict() if result.drawing_review else None)

    def test_pdf_fire_fighting_layout_generates_pipe_support_package(self) -> None:
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not installed.")
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "fire.pdf"
            doc = fitz.open()
            page = doc.new_page(width=1684, height=2384)
            page.insert_text((72, 120), "SITE WATER SUPPLY AND FIRE-FIGHTING SYSTEM LAYOUT")
            page.insert_text((72, 160), "NPS 6 CS,SCH40 NPS 4 CS,SCH40 NPS 2 1/2 CS,SCH40")
            page.insert_text((72, 200), "UPN 160 Existing Columns For Production Shed")
            doc.save(pdf_path)
            doc.close()

            result = route_input(
                "Generate a support coordination package for the fire-fighting lines inside the production shed.",
                pdf_path,
                Path(tmp) / "out",
                use_ai=False,
            )
            self.assertTrue(result.validation.passed, result.validation.to_dict())
            self.assertGreaterEqual(len(result.project.steel_members), 20)
            self.assertIn("pipe_support", {member.member_type for member in result.project.steel_members})
            self.assertTrue(result.drawing_review and result.drawing_review.passed, result.drawing_review.to_dict() if result.drawing_review else None)

    def test_ifc_contains_structural_geometry_and_properties(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = AgentController(use_ai=False).run(
                "Design a 3000x4000mm reinforced concrete pump room.",
                output_dir=Path(tmp),
            )
            text = result.ifc_path.read_text(encoding="utf-8")
            self.assertIn("IFCFOOTING", text)
            self.assertIn("IFCCOLUMN", text)
            self.assertIn("IFCBEAM", text)
            self.assertIn("IFCSLAB", text)
            self.assertGreaterEqual(text.count("IFCEXTRUDEDAREASOLID"), 10)
            self.assertGreaterEqual(text.count("IFCPROPERTYSET"), 10)

            context = extract_ifc_context(result.ifc_path)
            self.assertEqual(context.file_type, "ifc")
            self.assertTrue(context.layers)

    def test_drawing_reviewer_rejects_sparse_dxf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sparse.dxf"
            doc = ezdxf.new("R2018")
            doc.modelspace().add_line((0, 0), (100, 0))
            doc.saveas(path)
            report = review_dxf(path, preview_path=Path(tmp) / "sparse.png")
            self.assertFalse(report.passed)
            self.assertTrue(report.errors())

    def test_dwg_upload_requires_converter_when_no_converter_exists(self) -> None:
        if os.name != "nt":
            self.skipTest("DWG converter discovery is environment-specific.")
        if shutil.which("dwg2dxf"):
            self.skipTest("Local DWG converter is installed.")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.dwg"
            path.write_bytes(b"AC1032")
            with self.assertRaises(DwgConversionRequired):
                route_input("Use this DWG as context.", path, Path(tmp) / "out", use_ai=False)


if __name__ == "__main__":
    unittest.main()
