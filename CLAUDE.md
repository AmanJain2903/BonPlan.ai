# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Codebase Discovery
- For any query about project structure, architecture, or cross-file logic, **always call `graphify` tool**
- Do not attempt to use `grep` or `ls` for codebase mapping; use the graph representation to save context tokens.
- **Always** browse codebase using **graphify** only.

### 3-Layer Query Rule
1. **First:** query `graphify-out/graph.json` or `graphify-out/wiki/index.md`
   to understand code structure and connections
2. **Second:** only read raw code files when editing
   or when the first layer don't have the answer

### When to rebuild the graph
- After structural changes (new modules, major refactors)
- Command: ` graphify update . ` (only processes modified files)
- The graph is persistent — NO need to rebuild every session

### Do NOT
- Don't manually modify files inside `graphify-out/`
- Don't re-read the entire codebase if the graph already has the information

## Response
Always respond using Caveman:ultra intensity. No pleasantries, no 'I'd be happy to help,' just pure technical signal.

---

## Dev Commands

### Backend (from `backend/`)
```bash
# Activate venv (required first)
source .bonplan/bin/activate

# Install deps
pip install -r requirements.txt

# Start main API (port 8000)
uvicorn app.app:app --port 8000 --workers 4

# Start agent API (port 8001)
uvicorn app.ai:app --port 8001 --workers 2

# Use --reload instead of --workers during dev (mutually exclusive)
uvicorn app.app:app --port 8000 --reload

# Run E2E agent smoke test (N runs against real DB)
python -m app.agent.test.test_planner [N]

# DB migrations
alembic revision --autogenerate -m "message"
alembic upgrade head

# MCP Inspector (test MCP server locally)
npx @modelcontextprotocol/inspector python -m app.agent.mcp_server.main
```

### Frontend (from `frontend/`)
```bash
npm install
npm run dev      # Vite dev server — port 5173
npm run build
```

### Infrastructure
```bash
brew services start redis   # Redis required for rate limiter
```

### Requirements
- Python 3.13.3 | Node v20.16.0 | npm 10.8.1

---

## Architecture

Two FastAPI apps run as separate processes:

| Process | Entry | Port | Purpose |
|---------|-------|------|---------|
| Main API | `backend/app/app.py` | 8000 | Auth, trips, places, rate limiting |
| Agent API | `backend/app/ai.py` | 8001 | LangGraph planner, streaming, editing |

### Backend (`backend/app/`)

```
app.py          ← Main FastAPI (DB init, Redis restore, rate limiter lifespan)
ai.py           ← Agent FastAPI (MCP subprocess + GenAI client lifespan)
core/config.py  ← All env vars via pydantic-settings (single source of truth)
api/v1/endpoints/
  auth.py             — Google OAuth + local auth
  plan.py             — POST /draft_plan → triggers agent
  places.py           — Google Places proxy + image endpoints
  rate_limiting.py    — User-facing quota check
  rate_limiting_admin.py — CRUD for RateLimitConfigs
  api_cache.py        — Generic API response cache (Redis-backed)
database/models/      — SQLAlchemy ORM (Postgres, async)
services/rate_limiter/rate_limiter.py  ← Redis+Lua SKU-based rate limiter
```

### Agent (`backend/app/agent/`)

```
ai.py → agent_runtime_context() → spins up MCP subprocess + GenAI client
solo_planner.py             — generate_trip_itinerary() / edit_trip_itinerary()
langgraph_runtime/
  graph.py                  — LangGraph StateGraph definition (see topology below)
  state.py                  — PlannerState TypedDict (single shared state)
  streaming.py              — emit() SSE chunks to frontend
  validator.py              — validate_itinerary_event()
  context_pruning.py        — _prune_history() (Gemini-based, 1M context window)
  gemini_adapter.py         — run_chat_loop() wrapping Gemini API calls
  nodes/
    bootstrap.py            — load trip + prior events, set is_resuming
    research.py             — web search + research_facts (≤2KB JSON)
    collaboration_checkpoint.py — generates seed question in collab mode, awaits reply
    day_planner.py          — LLM call per day → structured itinerary events
    day_validator.py        — validates each day's events; retries up to MAX_VALIDATION_ATTEMPTS
    open_booking_guard.py   — detects un-closed bookings (e.g. HOTEL_CHECKIN without CHECKOUT)
    finalizer.py            — emits END event, persists to DB
mcp_server/tools/           — MCP tools (each is a standalone async function)
  flights.py / accommodations.py / places.py / geocoding.py / routes.py
  route_matrix.py / weather.py / air_quality.py / car_rental.py
  currency.py / web_search.py / timezone.py
schemas/
  structuredInput.py        — TripInput (agent entry payload)
  structuredOutput.py       — AddItineraryEvent and variants
```

### LangGraph Topology

```
START → bootstrap → research_and_start → collaboration_checkpoint
  → day_planner → day_validator ─┐ (error + attempts ≤ MAX: retry same day)
                  ↑──────────────┘
  → open_booking_guard ─→ day_planner (close_pass=True, one-time)
  → finalizer → END
```

`cancelled` flag at any node routes directly to END.

### Key Design Constraints

- **Two separate Uvicorn processes** — main API and agent API are never merged. Frontend talks to both on different ports.
- **`PlannerState`** is the single source of truth for all LangGraph state. Reducer fields (`operator.add`) are append-only.
- **Rate limiter** is Redis+Lua SKU-based, persists counters to Postgres, restores on startup. `RATE_LIMITER_MODE=lenient` (fail-open default); set `strict` in prod.
- **Context pruning** uses a separate Gemini model with 1M context window to compress history between day-planner iterations.
- **Gemini models** are configured per-role in `config.py` — planner uses `gemma-4-31b-it`, pruner uses `gemini-3.1-flash-lite-preview`. Do not mix keys/models across roles.
- **Editing mode** (`build_editor_graph()`) is stubbed — graph returns `None`. Do not implement features that assume it exists.
- **MCP server** runs as a subprocess owned by `agent_runtime_context`. Tools in `mcp_server/tools/` are invoked by the planner LLM, not called directly by backend code.

### Frontend (`frontend/src/`)

React + Vite + TypeScript. Communicates with both backend ports via `src/api/` and `src/apis/`.

### Database

Postgres (async SQLAlchemy). Alembic for migrations. Key tables:
- `trips`, `trip_members`, `trip_itineraries`, `trip_itinerary_snapshots`
- `trip_collab_qa` — Q&A pairs from collaborative mode
- `rate_limit_configs`, `rate_limit_usage` — SKU rate limiting
- `api_cache` — generic response cache
