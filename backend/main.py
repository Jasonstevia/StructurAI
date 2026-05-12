from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from backend.input_router import route_input

app = FastAPI(title="StructurAI Backend", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/projects")
async def create_project(prompt: str = Form(...), upload: UploadFile | None = File(default=None)) -> JSONResponse:
    upload_path: Path | None = None
    if upload and upload.filename:
        upload_dir = Path("outputs/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / upload.filename
        upload_path.write_bytes(await upload.read())
    result = route_input(prompt=prompt, upload_path=upload_path, output_dir=Path("outputs/latest"))
    return JSONResponse(
        {
            "passed": result.validation.passed,
            "issues": result.validation.to_dict()["issues"],
            "files": {
                "json": str(result.json_path),
                "dxf": str(result.dxf_path),
                "ifc": str(result.ifc_path),
                "dxf_review": str(result.dxf_review_path),
                "preview": str(result.preview_path),
            },
            "drawing_review": result.drawing_review.to_dict() if result.drawing_review else None,
            "summary": result.project.change_log[-12:],
        }
    )
