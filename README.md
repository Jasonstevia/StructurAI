# StructurAI Backend

StructurAI compiles structural drafting intent into a strictly typed JSON model, validates it deterministically, then exports professional DXF and IFC artifacts.

The exporter is no longer a primitive demo drawing. The current backend generates a model-space structural package with:

- foundation plan and roof framing/reinforcement plan
- grid bubbles, section markers, dimensions, structural notes, and title block
- concrete/soil/paving hatches and layered RC drafting conventions
- sections A-A and B-B
- isolated footing plan/section detail
- column starter/rebar detail
- roof slab reinforcement detail
- bar bending schedule, footing schedule, column schedule, beam schedule, reinforcement legend, and material takeoff
- IFC4-style BIM geometry with structural entity classes and property sets

The controller now runs a Codex-style compiled-output loop:

```text
typed model -> deterministic validation -> DXF/IFC export
-> DXF audit + rendered PNG preview + CAD density/layer/text checks
-> repair/re-export when the compiled drawing fails review
```

Each run writes:

- `structurai_project.json`
- `structurai_sheets.dxf`
- `structurai_3D.ifc`
- `dxf_review_report.json`
- `structurai_preview.png`

## Run the TUI

```bash
python3 tui.py run --offline
```

Use Gemini when `GEMINI_API_KEY` or `GOOGLE_API_KEY` is present in `.env`:

```bash
python3 tui.py run --prompt "Design a 3000x4000mm reinforced concrete pump room. Provide isolated footings, roof slab, and a bar bending schedule."
```

The default model is `gemini-3.1-flash-lite`; override with `GEMINI_MODEL` if needed.

Use an uploaded DXF or IFC as context:

```bash
python3 tui.py run --upload path/to/existing.dxf --prompt "Add missing footing details, sections, and schedules."
python3 tui.py run --upload path/to/model.ifc --prompt "Generate a coordinated structural drawing package."
```

Native `.rvt` files require a Revit adapter or Autodesk Design Automation step that exports IFC/DXF before backend processing. The backend refuses to fake RVT parsing.

## Run the API

```bash
python3 -m uvicorn backend.main:app --reload
```

## Architecture

The source of truth is `backend/core/structura_model.py`. The AI agent can only produce or repair that model. Validation and exporters are deterministic and live in separate modules.

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall backend tui.py tests
```
