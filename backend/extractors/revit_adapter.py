from __future__ import annotations

from pathlib import Path


class RevitAdapterRequired(RuntimeError):
    """Raised when a native RVT file is provided without a Revit-side adapter."""


def extract_revit_context(path: Path) -> None:
    raise RevitAdapterRequired(
        f"Native RVT parsing is not available for {path}. Route the file through the StructurAI Revit add-in "
        "or Autodesk Design Automation to export IFC/DXF plus element metadata before backend processing."
    )

