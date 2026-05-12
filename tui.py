from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from backend.input_router import route_input

app = typer.Typer(help="StructurAI terminal interface", no_args_is_help=True)
console = Console()


def _log(message: str) -> None:
    console.print(message)


@app.command()
def run(
    prompt: str = typer.Option("Design a 3000x4000mm reinforced concrete pump room. Provide isolated footings, roof slab, and a bar bending schedule.", "--prompt", "-p"),
    upload: Path | None = typer.Option(None, "--upload", "-u", exists=True, file_okay=True, dir_okay=False),
    output: Path = typer.Option(Path("outputs/latest"), "--output", "-o"),
    offline: bool = typer.Option(False, "--offline", help="Skip Gemini and use deterministic local drafting bootstrap."),
) -> None:
    console.print(Panel.fit("StructurAI Backend TUI", subtitle="AI CAD agent loop"))
    result = route_input(prompt=prompt, upload_path=upload, output_dir=output, use_ai=not offline, logger=_log)

    table = Table(title="Validation")
    table.add_column("Severity")
    table.add_column("Code")
    table.add_column("Message")
    for issue in result.validation.issues:
        table.add_row(issue.severity, issue.code, issue.message)
    if not result.validation.issues:
        table.add_row("pass", "OK", "No issues.")
    console.print(table)

    files = Table(title="Output Package")
    files.add_column("Artifact")
    files.add_column("Path")
    files.add_row("JSON", str(result.json_path))
    files.add_row("DXF", str(result.dxf_path) if result.dxf_path.exists() else "not exported")
    files.add_row("IFC", str(result.ifc_path) if result.ifc_path.exists() else "not exported")
    files.add_row("DXF Review", str(result.dxf_review_path) if result.dxf_review_path.exists() else "not reviewed")
    files.add_row("Preview PNG", str(result.preview_path) if result.preview_path.exists() else "not rendered")
    console.print(files)

    if result.drawing_review:
        review = Table(title=f"Drawing Review Score {result.drawing_review.score}/100")
        review.add_column("Severity")
        review.add_column("Code")
        review.add_column("Message")
        if result.drawing_review.issues:
            for issue in result.drawing_review.issues:
                review.add_row(issue.severity, issue.code, issue.message)
        else:
            review.add_row("pass", "OK", "Compiled DXF passed CAD review.")
        console.print(review)


@app.command()
def version() -> None:
    console.print("StructurAI backend MVP 0.1.0")


if __name__ == "__main__":
    app()
