from __future__ import annotations

from pathlib import Path

from backend.core.structura_model import ExtractedContext


def extract_pdf_context(path: Path) -> ExtractedContext:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires PyMuPDF. Install pymupdf to parse drawing PDFs.") from exc

    doc = fitz.open(path)
    layers = {"PDF_PAGE": doc.page_count}
    lines: list[dict[str, object]] = []
    notes = [f"Extracted PDF drawing context from {doc.page_count} page(s)."]

    for page_index, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        rect = page.rect
        if text:
            lines.append(
                {
                    "page": page_index,
                    "width_pt": round(rect.width, 2),
                    "height_pt": round(rect.height, 2),
                    "text": _compact(text, 5000),
                }
            )
            _append_detected_notes(notes, text, page_index)
        else:
            lines.append(
                {
                    "page": page_index,
                    "width_pt": round(rect.width, 2),
                    "height_pt": round(rect.height, 2),
                    "text": "",
                }
            )

    return ExtractedContext(source_path=str(path), file_type="pdf", layers=layers, lines=lines, notes=notes)


def _compact(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    return normalized[:limit]


def _append_detected_notes(notes: list[str], text: str, page_index: int) -> None:
    lower = text.lower()
    if "element without support" in lower or "add adequate bracing" in lower:
        notes.append(f"Page {page_index}: detected red-pen structural comment requiring adequate bracing for an unsupported element.")
    if "fire fighting" in lower or "fire-fighting" in lower:
        notes.append(f"Page {page_index}: detected fire-fighting pipe/support layout context.")
    if "bill  of  materials" in lower or "bill of materials" in lower:
        notes.append(f"Page {page_index}: detected bill of materials table.")
    if "revision" in lower or "comments" in lower:
        notes.append(f"Page {page_index}: detected revision/comment workflow metadata.")
