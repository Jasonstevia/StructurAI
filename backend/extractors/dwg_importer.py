from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from backend.core.structura_model import ExtractedContext
from backend.extractors.dxf_importer import extract_dxf_context


class DwgConversionRequired(RuntimeError):
    """Raised when no local DWG-to-DXF converter is available."""


def extract_dwg_context(path: Path) -> ExtractedContext:
    converted = _convert_with_available_tool(path)
    if converted:
        context = extract_dxf_context(converted)
        context.source_path = str(path)
        context.file_type = "dwg"
        context.notes.append("Converted DWG to temporary DXF before extraction.")
        return context
    raise DwgConversionRequired(
        f"Native DWG parsing is not available for {path}. Install ODA File Converter or dwg2dxf, "
        "or export the drawing to DXF from AutoCAD before uploading."
    )


def _convert_with_available_tool(path: Path) -> Path | None:
    dwg2dxf = shutil.which("dwg2dxf")
    if dwg2dxf:
        out_dir = Path(tempfile.mkdtemp(prefix="structurai-dwg-"))
        out_path = out_dir / f"{path.stem}.dxf"
        subprocess.run([dwg2dxf, str(path), str(out_path)], check=True, capture_output=True, text=True)
        return out_path if out_path.exists() else None
    return None
