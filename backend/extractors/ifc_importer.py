from __future__ import annotations

import re
from pathlib import Path

from backend.core.structura_model import ExtractedContext


def extract_ifc_context(path: Path) -> ExtractedContext:
    try:
        import ifcopenshell  # type: ignore
    except ImportError:
        return _regex_ifc_context(path)

    model = ifcopenshell.open(str(path))
    layers: dict[str, int] = {}
    for ifc_class in ("IfcFooting", "IfcColumn", "IfcBeam", "IfcSlab", "IfcWall", "IfcOpeningElement"):
        count = len(model.by_type(ifc_class))
        if count:
            layers[ifc_class] = count
    return ExtractedContext(
        source_path=str(path),
        file_type="ifc",
        layers=layers,
        notes=[f"Extracted IFC context with IfcOpenShell: {sum(layers.values())} structural entities."],
    )


def _regex_ifc_context(path: Path) -> ExtractedContext:
    text = path.read_text(encoding="utf-8", errors="ignore")
    layers: dict[str, int] = {}
    for ifc_class in ("IFCFOOTING", "IFCCOLUMN", "IFCBEAM", "IFCSLAB", "IFCWALL", "IFCOPENINGELEMENT"):
        count = len(re.findall(rf"\b{ifc_class}\s*\(", text))
        if count:
            layers[ifc_class.title()] = count
    return ExtractedContext(
        source_path=str(path),
        file_type="ifc",
        layers=layers,
        notes=["Extracted lightweight IFC context without IfcOpenShell. Install IfcOpenShell for full BIM geometry extraction."],
    )

