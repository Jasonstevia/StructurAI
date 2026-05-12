from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend.agent.prompts import REPAIR_PROMPT, SYSTEM_PROMPT
from backend.agent.structura_tools import StructuraTools
from backend.core.structura_model import ExtractedContext, StructuraProject
from backend.core.validator import ValidationReport, validate_project
from backend.exporters.dxf_exporter import export_dxf
from backend.exporters.ifc_exporter import export_ifc
from backend.review.drawing_reviewer import DrawingReviewReport, review_dxf


LogFn = Callable[[str], None]


@dataclass
class AgentResult:
    project: StructuraProject
    validation: ValidationReport
    drawing_review: DrawingReviewReport | None
    output_dir: Path
    json_path: Path
    dxf_path: Path
    ifc_path: Path
    dxf_review_path: Path
    preview_path: Path


def load_env(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class AgentController:
    def __init__(self, model_name: str = "gemini-3.1-flash-lite", max_retries: int = 3, use_ai: bool = True, logger: LogFn | None = None):
        load_env()
        self.model_name = os.getenv("GEMINI_MODEL", model_name)
        self.max_retries = max_retries
        self.use_ai = use_ai
        self.logger = logger or (lambda message: None)

    def run(self, prompt: str, context: ExtractedContext | None = None, output_dir: Path = Path("outputs/latest")) -> AgentResult:
        self.logger("Agent: Creating structural JSON model...")
        project = self._generate_project(prompt, context)
        StructuraTools(project).ensure_professional_drawing_package()
        validation = validate_project(project)

        for attempt in range(1, self.max_retries + 1):
            if validation.passed:
                break
            issue_text = "; ".join(f"{issue.code}: {issue.message}" for issue in validation.errors())
            self.logger(f"Validator: {issue_text}")
            self.logger(f"Agent: Repairing model, pass {attempt}/{self.max_retries}...")
            project = self._repair_project(project, validation)
            validation = validate_project(project)

        if validation.passed:
            self.logger("Validator: Pass. Compiling files.")
        else:
            self.logger("Validator: Exporting blocked by remaining fatal errors.")

        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "structurai_project.json"
        dxf_path = output_dir / "structurai_sheets.dxf"
        ifc_path = output_dir / "structurai_3D.ifc"
        report_path = output_dir / "validation_report.json"
        dxf_review_path = output_dir / "dxf_review_report.json"
        preview_path = output_dir / "structurai_preview.png"
        project.save_json(json_path)
        report_path.write_text(json.dumps(validation.to_dict(), indent=2), encoding="utf-8")
        drawing_review: DrawingReviewReport | None = None
        if validation.passed:
            for attempt in range(1, self.max_retries + 1):
                export_dxf(project, dxf_path)
                export_ifc(project, ifc_path)
                drawing_review = review_dxf(dxf_path, preview_path=preview_path)
                drawing_review.save_json(dxf_review_path)
                if drawing_review.passed:
                    self.logger(f"Drawing reviewer: Pass with score {drawing_review.score}/100.")
                    break
                issue_text = "; ".join(f"{issue.code}: {issue.message}" for issue in drawing_review.errors())
                self.logger(f"Drawing reviewer: {issue_text or 'review warnings require cleanup'}")
                if attempt == self.max_retries:
                    break
                self.logger(f"Agent: Revising compiled drawing package, pass {attempt}/{self.max_retries}...")
                self._repair_drawing_review(project, drawing_review)
                validation = validate_project(project)
                report_path.write_text(json.dumps(validation.to_dict(), indent=2), encoding="utf-8")
                project.save_json(json_path)
                if not validation.passed:
                    break
        return AgentResult(project, validation, drawing_review, output_dir, json_path, dxf_path, ifc_path, dxf_review_path, preview_path)

    def _generate_project(self, prompt: str, context: ExtractedContext | None) -> StructuraProject:
        if self.use_ai:
            ai_project = self._ask_gemini_for_project(prompt, context)
            if ai_project is not None:
                return ai_project
        return self._deterministic_bootstrap(prompt, context)

    def _ask_gemini_for_project(self, prompt: str, context: ExtractedContext | None) -> StructuraProject | None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None
        try:
            from google import genai

            schema = StructuraProject.model_json_schema()
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=self.model_name,
                contents=[
                    SYSTEM_PROMPT,
                    f"User request: {prompt}",
                    f"Existing extracted context: {context.model_dump() if context else {}}",
                    f"JSON schema: {json.dumps(schema)}",
                ],
            )
            text = getattr(response, "text", "") or ""
            return StructuraProject.model_validate_json(_extract_json(text))
        except Exception as exc:
            self.logger(f"Agent: Gemini unavailable or returned invalid JSON; using deterministic bootstrap ({exc.__class__.__name__}).")
            return None

    def _repair_project(self, project: StructuraProject, validation: ValidationReport) -> StructuraProject:
        if self.use_ai:
            repaired = self._ask_gemini_for_repair(project, validation)
            if repaired is not None:
                return repaired
        tools = StructuraTools(project)
        errors = {issue.code for issue in validation.errors()}
        if "NO_FOOTINGS" in errors or "COLUMN_UNSUPPORTED" in errors:
            for index, column in enumerate(project.columns, start=1):
                tools.add_footing(f"F{index}", column.center.x, column.center.y, 1400, 1400, 450, column.base_elevation_mm)
        if "NO_COLUMNS" in errors:
            tools.create_small_rc_room(3000, 4000, project.title)
        if {
            "FOOTING_REBAR_MISSING",
            "COLUMN_REBAR_MISSING",
            "BEAM_REBAR_MISSING",
            "SLAB_REBAR_MISSING",
        } & errors:
            tools.ensure_reinforcement_defaults()
        if "VIEW_MISSING" in errors:
            tools.ensure_professional_drawing_package()
        if {
            "SECTION_MISSING",
            "DIMENSIONS_MISSING",
            "DETAILS_MISSING",
            "SCHEDULES_MISSING",
            "SHEETS_MISSING",
        } & errors:
            tools.ensure_professional_drawing_package()
        return project

    def _repair_drawing_review(self, project: StructuraProject, review: DrawingReviewReport) -> None:
        tools = StructuraTools(project)
        tools.ensure_professional_drawing_package()
        issue_codes = {issue.code for issue in review.issues}
        if {"ENTITY_DENSITY_LOW", "DRAWING_LABELS_MISSING", "LAYERS_MISSING"} & issue_codes:
            project.change_log.append("Drawing reviewer requested a denser professional package; regenerated details, schedules, labels, and notes.")
        if "PREVIEW_TOO_EMPTY" in issue_codes:
            project.change_log.append("Drawing reviewer detected a sparse preview; package will be re-exported from the full model.")

    def _ask_gemini_for_repair(self, project: StructuraProject, validation: ValidationReport) -> StructuraProject | None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=self.model_name,
                contents=[
                    SYSTEM_PROMPT,
                    REPAIR_PROMPT,
                    json.dumps(validation.to_dict()),
                    project.model_dump_json(),
                ],
            )
            text = getattr(response, "text", "") or ""
            return StructuraProject.model_validate_json(_extract_json(text))
        except Exception:
            return None

    def _deterministic_bootstrap(self, prompt: str, context: ExtractedContext | None) -> StructuraProject:
        project = StructuraProject(title="StructurAI Drafting Package", extracted_context=context)
        width, length = _infer_dimensions(prompt)
        lower = prompt.lower()
        title = "RC Pump Room" if "pump" in lower else "RC Structural Room"
        return StructuraTools(project).create_small_rc_room(width, length, title)


def _extract_json(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first == -1 or last == -1:
        raise ValueError("no JSON object found")
    return cleaned[first : last + 1]


def _infer_dimensions(prompt: str) -> tuple[float, float]:
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:x|by|\*)\s*(\d+(?:\.\d+)?)\s*(mm|m)?", prompt, flags=re.IGNORECASE)
    if matches:
        a, b, unit = matches[0]
        width = float(a)
        length = float(b)
        if unit.lower() == "m" or (width < 100 and length < 100):
            width *= 1000
            length *= 1000
        return width, length
    return 3000.0, 4000.0
