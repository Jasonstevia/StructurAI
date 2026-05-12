from pathlib import Path
import os
import tempfile
import unittest

os.environ.setdefault("XDG_CACHE_HOME", "/tmp/structurai-cache")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/structurai-mpl")

import ezdxf

from backend.agent.agent_controller import AgentController
from backend.agent.structura_tools import StructuraTools
from backend.core.structura_model import StructuraProject
from backend.extractors.ifc_importer import extract_ifc_context
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


if __name__ == "__main__":
    unittest.main()
