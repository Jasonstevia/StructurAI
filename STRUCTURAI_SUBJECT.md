# StructurAI — AI CAD / Structural Drafting Agent Subject

## 0. Purpose

Build an AI chatbot/agent that can create, edit, validate, and export professional structural/CAD drawings from user instructions and uploaded files.

The product is not a demo drawing generator.

The product is not a fixed pump-room template.

The product is not a hardcoded structural layout engine.

The product is an autonomous AI CAD drafting agent for engineers, behaving similarly to a coding agent (like Devin or Codex) but for structural engineering.

The final goal is for an engineer to upload a file or describe a task, and the AI produces or edits a detailed drawing package that is good enough for the engineer to review, continue editing, send to a client, or use as the basis for a commercial structural project.

The AI must behave like a civil/structural drafting assistant:

- understand the user request
- understand uploaded CAD/BIM/drawing context when available
- decide what structural/drafting elements are required
- mutate a strictly-typed internal JSON project model
- run deterministic validation checks on the model
- read error logs and fix errors through a closed loop (max retries)
- export the final deterministic files (DXF for 2D, IFC for 3D BIM)

The user is not asking for a toy drawing.

The user is building a startup-grade AI CAD agent.

---

## 1. Core Product Definition

StructurAI is an AI CAD agent that produces professional structural models and drawings.

The agent receives:

1. A user query
2. Optional uploaded file(s)
3. Optional project requirements
4. Optional design constraints
5. Optional drafting standard preferences (e.g., specific company layers/styles)

The agent outputs:

1. A structured JSON project model (The Single Source of Truth)
2. A 2D DXF drawing file (for AutoCAD)
3. A 3D IFC model file (for Revit/BIM software)
4. A validation report
5. A summary of changes made

The agent must support both workflows:

### Workflow A — Create from scratch

Example:

> Create a one-story reinforced concrete pump-room structural drawing package with foundation plan, roof framing plan, sections, isolated footing details, reinforcement notes, dimensions, and schedules.

The agent must generate a full project model and export the drawing package.

### Workflow B — Edit/fix uploaded drawing

Example:

> I uploaded a DXF. Add missing footing details, fix beam labels, add section A-A and B-B, and add a footing schedule.

The agent must extract the existing drawing into lightweight JSON context, edit or rebuild the necessary parts, validate the result, and export the new files.

---

## 2. Non-Negotiable Principle

The AI decides engineering/drafting intent.

The deterministic code executes safe CAD operations.

The validator checks the result.

The AI repairs issues until acceptable.

The AI must NEVER directly write raw DXF or IFC code.

The system must not be built as a set of hardcoded examples.

Forbidden architecture:

```text
if pump_room:
    footing_size = 1.5m x 1.5m
    draw_fixed_plan()
```

Correct architecture:

```text
user input
→ AI interprets requirements
→ AI chooses elements, sizes, views, details, notes
→ tool layer updates the strictly-typed internal JSON model
→ validator mathematically checks completeness, collisions, and consistency
→ AI reads validation errors and fixes the JSON model
→ deterministic exporters draw the final DXF and IFC from the valid JSON
```

---

## 3. First-Principles Architecture

The backend must be built around these layers, supporting a "Claude Artifacts" style web UI where the chat is side-by-side with a live-rendering web viewer.

```text
Frontend (Chat + Web Canvas Viewer)
    ↓
Input router (handles prompts & files)
    ↓
Extractor (parses DXF/IFC into lightweight JSON context)
    ↓
AI agent controller (The Loop)
    ↓
Tool layer (mutates Internal Project Model)
    ↓
Validator (deterministic checker)
    ↓
Dual Exporters (DXF & IFC)
    ↓
Final files & Frontend Web Render
```

Required backend files:

```text
input_router.py       # detects file type and decides processing route
structura_model.py    # strictly-typed Pydantic classes (The absolute source of truth)
structura_tools.py    # AI-callable functions that mutate the structura_model
agent_controller.py   # AI loop / tool-calling controller with max-retry limits
validator.py          # deterministic engineering and geometric rule checks
dxf_importer.py       # extracts uploaded DXF lines into structured JSON context
dxf_exporter.py       # exports the Pydantic model into 2D DXF using ezdxf
ifc_exporter.py       # exports the Pydantic model into 3D BIM using IfcOpenShell
```

No separate hardcoded demo generators should exist in the production backend.

---

## 4. Input Types

The agent should eventually support:

- prompt only
- DXF
- DWG
- PDF
- PNG/JPG screenshots
- IFC
- RVT
- JSON project model

Current MVP support

Required now:

- prompt only → generate JSON → export DXF & IFC
- DXF upload → extract into JSON context, edit → export DXF & IFC

Later:

- DWG → convert to DXF, then parse
- RVT → process via native Revit Add-in adapter
- PDF/image → use vision/OCR/vector extraction

---

## 5. Output Requirements

The final outputs must be generated strictly from the internal JSON model.

### 2D DXF Output (AutoCAD)

Must support precise drafting:

- lines, polylines, hatches (soil, concrete)
- text, dimensions (avoiding overlaps)
- blocks/symbols, dynamic layers
- Bar Bending Schedules (BBS) generated parametrically

### 3D IFC Output (Revit/BIM)

Must support geometric structural models:

- 3D columns, beams, footings, slabs
- structural properties attached to entities

Documentation objects (DXF focus)

- foundation plans, framing plans
- sections, elevations
- parameter-driven details (footings, joints, splices)
- general notes, title blocks, sheet layout

---

## 6. Agent Capabilities

The AI must be able to call tools to modify the internal model.

Context tools

- summarize drawing layers
- extract existing entities into context
- summarize previous validation errors

Structural model tools (Mutates Pydantic State)

- add/edit/delete level, grid line
- add/edit/delete column, beam, slab, wall, footing
- add/edit/delete opening, rebar configuration

Annotation & Detail Tools

- add section marker, dimension, tag
- generate detail parameters:

Example:

```json
{
  "detail_type": "isolated_footing",
  "footing_id": "F1",
  "width": 1800,
  "depth": 500,
  "bottom_rebar": "T16 @150 each way",
  "concrete_cover": 75
}
```

The exporter takes these parameters and parametrically draws the lines/hatches.

---

## 7. Validation Requirements

The system must include a closed-loop validation process. The agent must not export blindly.

The loop is:

```text
AI edits JSON model
↓
Python validates JSON model
↓
if errors exist:
    AI reads error log, fixes JSON model
    validate again (max retries: 3)
↓
if acceptable:
    Export DXF & IFC
```

Model validation (Deterministic)

- footings support columns when required
- slabs have closed boundaries
- beams connect to supports
- minimum depths/covers are respected
- duplicate IDs are avoided

Drawing package validation

- sections exist where required
- schedules align with model quantities
- annotations do not conflict with boundaries

---

## 8. Quality Standard

The goal is not 100% autonomous legal engineering approval.

The goal is:

```text
A detailed, editable, engineer-reviewable DXF/BIM package
that removes the boring detailing work and catches catastrophic mistakes.
```

Unacceptable output:

- random lines hallucinated by the LLM
- overlapping dimension text rendering a drawing unreadable
- a hardcoded template unrelated to the user input

Acceptable MVP output:

- structurally coherent project model
- clean DXF sheets with layers, hatches, tags, and parametric details
- 3D IFC model that drops natively into Revit
- engineer can continue from it instead of starting from zero

---

## 9. What the AI Should Decide

The AI should decide:

- engineering intent (what elements are required)
- sizes, dimensions, rebar requirements
- what views/details/schedules are necessary for the package
- how to fix errors presented by the validator

The code should not decide these by hardcoded project type.

---

## 10. What the Code Should Decide

The deterministic Python code should decide:

- exactly where to place a dimension text so it doesn't overlap a line
- calculating the mathematical Bar Bending Schedule from the rebar data
- how the IFC STEP file syntax is written
- how the DXF tags are formatted
- validation passes/fails

The deterministic code must behave like a rigid compiler.

---

## 11. Initial MVP Scope

The first realistic MVP should handle:

- Prompt-only generation
- Simple DXF upload as context extraction
- Reinforced concrete small-room / pump-room style logic
- Internal Pydantic State definition
- Validation loop (Agentic CI/CD)
- 2D Auto-drafting via ezdxf (Plans, Sections, Details, Schedules)
- 3D Model export via IfcOpenShell (Columns, Footings, Beams)
- Frontend Claude-style web viewer UI (showing 2D/3D output instantly)

---

## 12. Future Scope

- Full DXF entity-preserving complex edits
- Direct Revit Add-in adapter (bypassing IFC)
- Structural calculation engine integration
- Office drafting standards memory
- Multi-agent collaboration (Architect Agent + Structural Agent)

---

## 13. Success Criteria

The backend is successful when this works:

```text
User: Uploads file or writes prompt
Agent: Updates Pydantic Model
Agent: Validator catches a missing footing
Agent: Agent fixes the footing
Exporters: Generate DXF and IFC
Frontend: Displays output in web viewer instantly
User: Downloads IFC into Revit and DXF into AutoCAD to finalize the design
```

The product direction is successful when engineers say:

> "This saves me hours of detailing and schedule creation. I can use this as a starting point."

---

## 14. Important Development Rule

Do not add isolated demo files that bypass the agent architecture.

Any new capability must integrate into the established pipeline (input -> extraction -> agent loop -> state update -> validation -> export).

---

## 15. Immediate Next Development Tasks

- Define structura_model.py using Pydantic (Footings, Columns, Rebar, Views).
- Build structura_tools.py so the LLM can edit the Pydantic state.
- Write validator.py to check the Pydantic state for logic errors.
- Build dxf_exporter.py to take a valid state and draw Parametric Details and Schedules using ezdxf.
- Wire up the Agentic while loop in agent_controller.py with Prompt Caching.

---

## 16. One-Sentence Product Statement

StructurAI is "Devin for Structural CAD"—an autonomous agent that compiles structural engineering intent into strictly-validated 2D DXF drawings and 3D IFC models through a continuous loop of drafting, checking, and repairing.

---

## 17. Minimum Viable Demo (MVD) for smartESA

For the accelerator pitch, the product must flawlessly execute this exact sequence live (or recorded):

1. **The Input:** The user types into a chat interface: *"Design a 3000x4000mm reinforced concrete pump room. Provide the isolated footings, roof slab, and a bar bending schedule."*
2. **The Loop (Visible to User):** The UI must show the agent's thought process.
   - *Agent:* "Creating structural JSON model..."
   - *Validator:* "Error: Columns are missing depth dimensions to reach footings."
   - *Agent:* "Fixing column depth to match foundation level..."
   - *Validator:* "Pass. Compiling files."
3. **The Web Render:** A split-screen UI instantly loads the 3D IFC model (using IFC.js) that the user can spin around.
4. **The Export:** The user clicks "Download Package" and receives a ZIP containing:
   - `pump_room_3D.ifc` (Ready for Revit)
   - `pump_room_sheets.dxf` (Ready for AutoCAD, complete with Bar Bending Schedule)

---

## 18. Expected Repository Structure

To maintain a clean, 42-norm-style architecture and keep the LLM, physics, and exporters strictly separated, the repository must follow this structure:

```text
structurAI/
├── frontend/                  # React/Next.js UI with Claude-Artifacts style viewer
│   ├── components/            # ChatBox, IfcViewer (IFC.js), DxfViewer
│   └── ...
├── backend/
│   ├── main.py                # FastAPI server & endpoints
│   ├── core/
│   │   ├── structura_model.py # Pydantic Classes (The JSON source of truth)
│   │   └── validator.py       # Deterministic physics/geometry checker
│   ├── agent/
│   │   ├── agent_controller.py# The AI Loop with Max-Retries
│   │   ├── structura_tools.py # Tools to mutate the Pydantic model
│   │   └── prompts.py         # System instructions & Prompt Caching logic
│   ├── extractors/
│   │   └── dxf_importer.py    # ezdxf script to turn 2D lines into JSON context
│   └── exporters/
│       ├── dxf_exporter.py    # ezdxf script (Draws 2D Sheets & Schedules)
│       └── ifc_exporter.py    # IfcOpenShell script (Generates 3D BIM)
├── data/
│   └── templates/             # AutoCAD .dwt/.dxf template files (Title blocks, layers)
├── requirements.txt
└── README.md
```

---

## 19. Bonus Part

As with any 42 project, the bonus part is only evaluated if the mandatory part is perfectly functional.

If time permits before the accelerator demo day, implement the following:

- Speckle Integration: Instead of just downloading files, push the JSON model directly to Speckle.systems via their Python SDK. This allows the structural model to appear instantly inside the engineer's native Revit or AutoCAD window without downloading or importing anything.
- Cost Estimation Engine: Since the internal Pydantic model knows the exact volume of concrete and the exact length/weight of rebar, calculate the material cost automatically and append it to the chat response.
- Vision Context: Allow the user to upload a screenshot of an architectural floor plan. Pass it to GPT-4o / Claude 3.5 Sonnet vision to extract the rough grid lines and room boundaries as the starting JSON context.

---

## 20. Final Warning

> "Machines should work. People should think."

Do not let the AI draw lines.

Do not let the AI format DXF strings.

Let the AI think about engineering intent, and let your Python code do the heavy lifting of drawing lines.

Stick to the architecture, build the loop, and ship it.

Good luck.

***

### Final Advice for You (as a 42 Student & Founder)

Save the combined file. Whenever you open a new chat with Claude, ChatGPT, or Cursor to help you write code, upload this **entire** `.md` file first and say: *"Read the project subject. I am now working on `validator.py`. Write the validation logic for isolated footings."*

Because the subject is written so clearly and rigidly, the AI will understand exactly what architecture you are forcing it to use and will stop giving you bad, hallucinated boilerplate code.

Go crush the smartESA program!
