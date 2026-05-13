from __future__ import annotations

from pathlib import Path

from backend.agent.agent_controller import AgentController, AgentResult
from backend.core.structura_model import ExtractedContext
from backend.extractors.dwg_importer import extract_dwg_context
from backend.extractors.dxf_importer import extract_dxf_context
from backend.extractors.ifc_importer import extract_ifc_context
from backend.extractors.pdf_importer import extract_pdf_context
from backend.extractors.revit_adapter import extract_revit_context


def route_input(prompt: str, upload_path: Path | None = None, output_dir: Path = Path("outputs/latest"), use_ai: bool = True, logger=None) -> AgentResult:
    context: ExtractedContext | None = None
    if upload_path:
        suffix = upload_path.suffix.lower()
        if suffix == ".dxf":
            context = extract_dxf_context(upload_path)
        elif suffix == ".dwg":
            context = extract_dwg_context(upload_path)
        elif suffix == ".ifc":
            context = extract_ifc_context(upload_path)
        elif suffix == ".pdf":
            context = extract_pdf_context(upload_path)
        elif suffix == ".rvt":
            extract_revit_context(upload_path)
        elif suffix == ".json":
            context = ExtractedContext(source_path=str(upload_path), file_type="json", notes=["JSON project import is reserved for the next backend iteration."])
        else:
            raise ValueError(f"Unsupported upload type for MVP: {suffix}")
    controller = AgentController(use_ai=use_ai, logger=logger)
    return controller.run(prompt=prompt, context=context, output_dir=output_dir)
