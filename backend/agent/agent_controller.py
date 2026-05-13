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


@dataclass(frozen=True)
class DesignBrief:
    width_mm: float
    length_mm: float
    story_count: int
    title: str


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
        self.gemini_timeout_ms = int(os.getenv("GEMINI_TIMEOUT_MS", "20000"))
        self.max_retries = max_retries
        self.use_ai = use_ai
        self.logger = logger or (lambda message: None)

    def run(self, prompt: str, context: ExtractedContext | None = None, output_dir: Path = Path("outputs/latest")) -> AgentResult:
        self.logger("Agent: Creating structural JSON model...")
        brief = _infer_design_brief(prompt)
        steel_comment_task = _is_steel_comment_task(prompt, context)
        pipe_support_task = _is_pipe_support_task(prompt, context)
        project = self._generate_project(prompt, context)
        if pipe_support_task:
            self.logger("Compiler: Building fire-fighting pipe support coordination package from drawing context.")
            StructuraTools(project).create_pipe_support_coordination_package()
        elif steel_comment_task:
            self.logger("Compiler: Building structural steel bracing response from drawing/comment context.")
            StructuraTools(project).create_steel_bracing_comment_resolution()
        else:
            self.logger(
                "Compiler: Completing structural scope "
                f"({brief.width_mm:.0f}x{brief.length_mm:.0f}mm, {brief.story_count} "
                f"{'story' if brief.story_count == 1 else 'stories'})."
            )
            StructuraTools(project).ensure_building_frame(brief.width_mm, brief.length_mm, brief.story_count, brief.title)
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
            client = genai.Client(api_key=api_key, http_options={"timeout": self.gemini_timeout_ms})
            last_error: Exception | None = None
            for model_name in _candidate_models(self.model_name):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[
                            SYSTEM_PROMPT,
                            f"User request: {prompt}",
                            f"Existing extracted context: {context.model_dump() if context else {}}",
                            f"JSON schema: {json.dumps(schema)}",
                        ],
                    )
                    text = getattr(response, "text", "") or ""
                    project = StructuraProject.model_validate_json(_extract_json(text))
                    if model_name != self.model_name:
                        self.logger(f"Agent: Gemini generated model with fallback model {model_name}.")
                    return project
                except Exception as exc:
                    last_error = exc
                    self.logger(f"Agent: Gemini model {model_name} did not return a valid project ({exc.__class__.__name__}).")
            if last_error:
                self.logger(f"Agent: Gemini unavailable or returned invalid JSON; using deterministic bootstrap ({last_error.__class__.__name__}).")
        except Exception as exc:
            self.logger(f"Agent: Gemini client unavailable; using deterministic bootstrap ({exc.__class__.__name__}).")
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

            client = genai.Client(api_key=api_key, http_options={"timeout": self.gemini_timeout_ms})
            for model_name in _candidate_models(self.model_name):
                try:
                    response = client.models.generate_content(
                        model=model_name,
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
                    continue
        except Exception:
            return None
        return None

    def _deterministic_bootstrap(self, prompt: str, context: ExtractedContext | None) -> StructuraProject:
        project = StructuraProject(title="StructurAI Drafting Package", extracted_context=context)
        if _is_pipe_support_task(prompt, context):
            return StructuraTools(project).create_pipe_support_coordination_package()
        if _is_steel_comment_task(prompt, context):
            return StructuraTools(project).create_steel_bracing_comment_resolution()
        brief = _infer_design_brief(prompt)
        return StructuraTools(project).ensure_building_frame(brief.width_mm, brief.length_mm, brief.story_count, brief.title)


def _candidate_models(primary: str) -> list[str]:
    fallback_text = os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.1-flash-lite-preview,gemini-flash-lite-latest,gemini-2.5-flash-lite,gemini-2.0-flash-lite",
    )
    names = [primary, *(name.strip() for name in fallback_text.split(",") if name.strip())]
    deduped: list[str] = []
    for name in names:
        if name not in deduped:
            deduped.append(name)
    return deduped


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
    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*(mm|m)?\s*(?:x|by|\*)\s*(\d+(?:\.\d+)?)\s*(mm|m)?",
        prompt,
        flags=re.IGNORECASE,
    )
    if matches:
        a, unit_a, b, unit_b = matches[0]
        width = _to_mm(float(a), unit_a, float(a) < 100 and float(b) < 100)
        length = _to_mm(float(b), unit_b or unit_a, float(a) < 100 and float(b) < 100)
        return width, length
    return 3000.0, 4000.0


def _to_mm(value: float, unit: str, assume_meters: bool) -> float:
    normalized = unit.lower()
    if normalized == "m" or (not normalized and assume_meters):
        return value * 1000
    return value


def _infer_story_count(prompt: str) -> int:
    lower = prompt.lower()
    numeric = re.search(r"\b(\d+)\s*[- ]?\s*(?:story|stories|storey|storeys)\b", lower)
    if numeric:
        return max(1, int(numeric.group(1)))
    words = {
        "one": 1,
        "single": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
    }
    for word, value in words.items():
        if re.search(rf"\b{word}\s*[- ]?\s*(?:story|stories|storey|storeys)\b", lower):
            return value
    return 1


def _infer_title(prompt: str) -> str:
    lower = prompt.lower()
    if "pump" in lower:
        return "RC Pump Room"
    if "office" in lower:
        return "RC Office Building"
    if "building" in lower:
        return "RC Building"
    return "RC Structural Room"


def _infer_design_brief(prompt: str) -> DesignBrief:
    width, length = _infer_dimensions(prompt)
    return DesignBrief(width_mm=width, length_mm=length, story_count=_infer_story_count(prompt), title=_infer_title(prompt))


def _is_steel_comment_task(prompt: str, context: ExtractedContext | None) -> bool:
    text = prompt.lower()
    if context:
        text += " " + " ".join(context.notes).lower()
        for line in context.lines:
            text += " " + str(line.get("text", "")).lower()
    steel_signals = {"bracing", "unsupported", "steel", "conveyor", "platform", "square hollow", "shs", "pipe", "red pen"}
    return any(signal in text for signal in steel_signals) and any(signal in text for signal in {"bracing", "unsupported", "red pen"})


def _is_pipe_support_task(prompt: str, context: ExtractedContext | None) -> bool:
    text = prompt.lower()
    if context:
        text += " " + " ".join(context.notes).lower()
        for line in context.lines:
            text += " " + str(line.get("text", "")).lower()
    pipe_signals = {"fire fighting", "fire-fighting", "nps", "cs,sch40", "pipe", "hose cabinet", "production shed"}
    support_signals = {"support", "coordination", "shed", "pipe support", "fire-fighting lines"}
    return any(signal in text for signal in pipe_signals) and any(signal in text for signal in support_signals)
