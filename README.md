# Intelligent Syntax Error Recovery System

Interactive compiler assistant for a **mini C-like language**. It detects syntax errors, classifies them, generates ranked correction candidates with explainable scores, applies high-confidence fixes, and **continues parsing** instead of stopping at the first error.

No cloud LLM is required for the analysis pipeline — recovery is local and deterministic.

**Repository:** [SahithiUppala/Intelligent-Syntax-Error-Recovery-System](https://github.com/SahithiUppala/Intelligent-Syntax-Error-Recovery-System)

---

## Features

- Custom **lexer** + **recursive-descent parser**
- Structured **error detection** and **classification**
- Grammar-constrained **candidate generation** (`insert` / `delete` / `replace`)
- Deterministic **explainable scoring** (grammar, context, token fit, parse progress − edit cost)
- Iterative **recovery** with confidence thresholds and continue-parsing
- Dark-theme **interactive IDE UI** (React + Vite + Monaco + plain CSS)
  - Clickable pipeline stages → Inspector
  - Error navigation (Previous / Next) with Monaco jump + highlight
  - Preview / Apply corrections (corrected-code state separate from editor)
  - Result tabs: DIFF · HOW WAS THIS FIXED? · PARSE RESULT
- Built-in **example programs** for demos

### Pipeline

```text
Source Code
  → Lexical Analysis
  → Parsing
  → Error Detection
  → Classification
  → Candidate Generation
  → Correction Scoring
  → Recovery
  → Result
```

---

## Quick start

### Requirements

- Python **3.10+**
- Node.js **18+**

### 1. Backend

```powershell
cd IntelligentSyntaxErrorDetectionSystem
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

| Resource | URL |
|----------|-----|
| API | http://127.0.0.1:8000 |
| Health | http://127.0.0.1:8000/api/health |
| Swagger docs | http://127.0.0.1:8000/docs |
| Examples | http://127.0.0.1:8000/api/examples |

### 2. Frontend

```powershell
cd IntelligentSyntaxErrorDetectionSystem\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open **http://127.0.0.1:5173**

Optional: set `VITE_API_BASE_URL` if the API is not on `http://127.0.0.1:8000`.

### 3. Tests

```powershell
.\venv\Scripts\Activate.ps1
cd backend
python -m pytest tests/ -v
```

---

## Interactive UI guide

### Layout

| Region | Contents |
|--------|----------|
| Header + Toolbar | Run Analysis, Clear, Load Example, compact summary |
| Pipeline | Clickable stages (PENDING → RUNNING → COMPLETED / ERROR DETECTED / RECOVERED) |
| Workspace | **Code Editor (~60%)** + **Inspector (~40%)** |
| Inspector tabs | TOKENS · ERRORS · CORRECTIONS · AST |
| Result tabs | DIFF · HOW WAS THIS FIXED? · PARSE RESULT |

On mobile, the editor and inspector stack vertically.

### Recommended flow

1. **Load Example** or write mini-C code
2. **Run Analysis** (`Ctrl/Cmd + Enter`) — watch the pipeline progress
3. Click a **detected error** (or use **Previous / Next** / `Alt+↑` / `Alt+↓`)
   - Monaco jumps to the line and highlights it
   - Inspector opens **ERRORS**
4. Open **CORRECTIONS** — compare candidates with backend score breakdowns
5. **Preview** a candidate (updates DIFF only; Monaco stays unchanged)
6. **Apply** a candidate (updates corrected-code state; marks ✓ APPLIED)
7. Optionally **Apply All Best Corrections** / **Reset Corrections**
8. Review **DIFF**, **HOW WAS THIS FIXED?**, and **PARSE RESULT**
9. **Apply Corrected Code to Editor** when you want Monaco replaced

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + Enter` | Run Analysis |
| `Alt + ↓` | Next error |
| `Alt + ↑` | Previous error |

### Example programs

- Missing Semicolon
- Missing Parenthesis
- Missing Brace
- Expression Error
- Multiple Errors
- Valid Program

---

## Demo program

**Input**

```c
int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}
```

**Detected**

1. Missing semicolon after `int x = 10` → `INSERTION_ERROR`
2. Missing `)` in the if condition → `DELIMITER_ERROR`

**Corrected**

```c
int x = 10;
int y = 20;

if (x < y) {
    x = x + 1;
}
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Service health |
| `GET` | `/api/examples` | Built-in demo programs |
| `POST` | `/api/tokenize` | Lexical analysis `{ "code": "..." }` |
| `POST` | `/api/parse` | Parse + AST + structured errors |
| `POST` | `/api/analyze` | Full pipeline + recovery + report |

### `/api/analyze` response (summary)

```json
{
  "tokens": [],
  "ast": {},
  "errors": [],
  "corrections": [],
  "corrected_code": "",
  "original_code": "",
  "report": {},
  "stages": [],
  "pipeline": {},
  "success": true,
  "message": "..."
}
```

Each `stages[]` entry includes `name`, `status`, `detail`, and `data` for the interactive pipeline UI.

---

## Architecture

```text
backend/
  main.py                 # FastAPI routes
  models.py               # Pydantic models
  pipeline.py             # Orchestrator + example catalog
  compiler/
    lexer.py
    grammar.py
    parser.py
    errors/
      detector.py
      classifier.py
    recovery/
      candidate_generator.py
      scorer.py
      recovery_engine.py
    reports/
      report_generator.py
  tests/                  # 100+ unit / integration / API tests

frontend/
  src/
    pages/Home.jsx
    components/           # Editor, pipeline, inspector, corrections, results
    services/api.js
    utils/                # Correction helpers, featured examples
    styles/               # Plain CSS dark theme (no Tailwind)
```

Compiler logic stays separate from the API and UI so an optional ML ranker could replace scoring later without touching the lexer/parser.

---

## Scoring model

| Component | Range |
|-----------|------:|
| Grammar validity | 0–40 |
| Local context | 0–25 |
| Token compatibility | 0–15 |
| Parse progress | 0–20 |
| Edit penalty | −0–10 |

### Recovery confidence

| Score | Label | Behavior |
|------:|-------|----------|
| ≥ 75 | high | Auto-applied |
| 50–74 | probable | Recommended |
| < 50 | uncertain | Skipped |

UI candidate scores and breakdown bars use **backend values only** (nothing is invented on the frontend).

---

## Supported mini-language

- Variable declarations (`int` / `float`)
- Assignments
- Arithmetic & relational expressions
- `if` / `else`, `while`, blocks `{ }`
- Semicolon-terminated statements
- `//` and `/* */` comments

---

## Development status

### Compiler / system (Phases 1–17) — complete

| Phase | Description |
|------:|-------------|
| 1 | Project structure + FastAPI + React/Vite |
| 2 | Lexical analyzer + tests |
| 3 | Grammar + recursive-descent parser |
| 4 | Structured syntax error detection |
| 5 | Error classification |
| 6 | Candidate correction generation |
| 7 | Explainable correction scoring |
| 8 | Recovery + continue-parsing |
| 9 | Error report generation |
| 10 | API endpoint wiring |
| 11 | Monaco code editor UI |
| 12 | Interactive pipeline visualization |
| 13 | Token / error / correction panels |
| 14 | Original vs corrected comparison |
| 15 | Frontend–backend integration |
| 16 | Example programs + test cases |
| 17 | UI polish, error handling, README |

### Interactive IDE redesign — complete

| Phase | Description |
|------:|-------------|
| 1 | Interactive workspace (Header, Pipeline, Editor 60% / Inspector 40%, Result tabs) |
| 2 | Clickable pipeline + error navigation + Monaco sync |
| 3 | Interactive correction system (Preview / Apply / Apply All Best / Reset / Apply to Editor) |
| 4 | Results polish, examples, keyboard shortcuts, animations, responsive layout |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend: offline in UI | Start uvicorn from `backend/` on port **8000** |
| CORS / wrong API host | Set `VITE_API_BASE_URL` or use the Vite proxy (`/api`) |
| Empty analysis | Ensure the editor has code; use **Load Example** |
| Monaco not updating after Apply | **Apply** updates corrected-code only — use **Apply Corrected Code to Editor** |
| Tests fail importing modules | Run pytest from `backend/` (see `pytest.ini` `pythonpath`) |

---

## License / notes

Academic / compiler-design demonstration project. Core recovery is local and deterministic — no cloud LLM dependency for the analysis pipeline.
