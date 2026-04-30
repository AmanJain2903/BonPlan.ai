# Repository Guidelines

## Project Structure & Module Organization
BonPlan.ai has a React/Vite frontend and a FastAPI backend. Frontend code lives in `frontend/src/`: UI in `components/`, API clients in `apis/` and `api/`, context in `context/`, hooks in `hooks/`, assets in `assets/`, and shared types in `types/`. Backend code lives in `backend/app/`: API entrypoints are `app.py` and `ai.py`, routers are under `api/`, LangGraph planning is under `agent/`, database code is under `database/`, services are under `services/`, and helpers are under `utils/`. Alembic migrations are in `backend/migrations/`; product docs are in `Docs/`.

## Build, Test, and Development Commands
From `frontend/`:
- `npm install` installs frontend dependencies.
- `npm run dev` starts the Vite development server.
- `npm run build` runs TypeScript build checks and creates the production bundle.
- `npm run lint` runs ESLint over the frontend.
- `npm run preview` serves the built frontend locally.

From `backend/`:
- `python3.13 -m venv .bonplan && source .bonplan/bin/activate` creates and activates the backend environment.
- `pip install -r requirements.txt` installs backend dependencies.
- `uvicorn app.app:app --port 8000 --workers 4` starts the API server.
- `uvicorn app.ai:app --port 8001 --workers 2` starts the agent server.
- `alembic upgrade head` applies database migrations.

## Coding Style & Naming Conventions
Use TypeScript and React functional components. Name React components in `PascalCase`, hooks as `useSomething`, and helpers in `camelCase`. Keep Python modules and functions `snake_case`, classes `PascalCase`, and SQLAlchemy models grouped under `backend/app/database/models/`. Use 2-space indentation in TypeScript/TSX and 4-space indentation in Python.

## Testing Guidelines
The repository currently has limited automated tests. Backend planner tests are under `backend/app/agent/test/`; run them from `backend/` with `python -m pytest app/agent/test` if pytest is installed. Add backend tests beside the feature area they cover, using `test_*.py`. For frontend changes, at minimum run `npm run build` and `npm run lint`.

## Commit & Pull Request Guidelines
Recent commits use short summaries such as `Added the Currency Conversion Tool`; keep messages concise and action oriented. Pull requests should explain the user-visible change, list verification commands, reference related issues, and include screenshots or recordings for UI changes.

## Agent-Specific Instructions
This project maintains a graphify knowledge graph in `graphify-out/`. Before answering architecture or codebase questions, read `graphify-out/GRAPH_REPORT.md`; if `graphify-out/wiki/index.md` exists, use it for navigation. For cross-module relationship questions, prefer `graphify query`, `graphify path`, or `graphify explain` over grep. After modifying code files, run `graphify update .`.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
