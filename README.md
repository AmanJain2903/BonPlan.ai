# BonPlan.ai

![Version](https://img.shields.io/badge/version-v1.0.0-0B0C10?style=for-the-badge)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB?style=for-the-badge&logo=react&logoColor=0B0C10)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Agent](https://img.shields.io/badge/agent-LangGraph%20%2B%20LiteLLM-6C5CE7?style=for-the-badge)
![Database](https://img.shields.io/badge/database-PostgreSQL%20%2B%20Redis-336791?style=for-the-badge&logo=postgresql&logoColor=white)

## Tell us When. We Tell the How. ✈️

Current finalized version: `v1.0.0`

BonPlan.ai is an AI travel planning application that builds editable, constraint-aware itineraries around the parts of a trip that cannot move. Instead of producing a static list of recommendations, BonPlan stores trip intent, user preferences, fixed reservations, collaborator context, and itinerary events as structured data that can be regenerated, edited, shared, locked, reverted, and exported.

The core product idea is simple: tell BonPlan when and where you are going, add any non-negotiable anchors such as flights, hotels, restaurants, or booked activities, and let the system plan the rest of the trip around those constraints.

> Flights at 7:00 AM. Dinner that cannot move. A hotel check-in window. A group chat full of preferences. BonPlan turns the mess into a trip that actually fits.

## Why BonPlan Exists 🌍

Most itinerary tools generate suggestions. BonPlan plans around reality.

Real trips have fixed commitments, transit buffers, weather, opening hours, budgets, tired travelers, group preferences, and last-minute changes. BonPlan v1.0.0 is built as a structured planning system, not just a prompt box: every trip, anchor, generated event, edit, collaborator answer, and snapshot becomes part of the planning state.

## What BonPlan Does ✨

- Creates solo and squad trip drafts from origin, destinations, dates, routing style, pace, budget, and traveler counts.
- Generates day-by-day itineraries through a streaming AI planner.
- Supports Smart Anchors for fixed trip commitments such as flights, hotels, car rentals, dining, activities, and other bookings.
- Lets users lock individual itinerary events so later edits preserve important plans.
- Provides itinerary editing through an AI chat interface.
- Supports collaborative planning questions and saved trip Q&A context.
- Shares trips with viewer or editor permissions.
- Supports email invitations, share links, access elevation requests, and role-based access control.
- Stores itinerary snapshots and supports reverting to prior versions.
- Exports itineraries as PDFs.
- Caches API responses and place photos.
- Tracks rate limits by SKU and exposes admin tools for rate-limit configuration and usage review.
- Includes account management, profile preferences, support tickets, FAQs, privacy, and terms pages.

## Tech Stack 🧱

| Area | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite |
| Styling and UI | Tailwind CSS, Framer Motion, Lucide React |
| Maps and places | Google Maps, Google Places, custom place-photo cache |
| Backend API | FastAPI, Pydantic, SQLAlchemy async |
| Agent backend | FastAPI, LangGraph, LiteLLM, MCP tools |
| Database | PostgreSQL 15 |
| Cache and counters | Redis |
| Migrations | Alembic |
| PDF export | Jinja2, WeasyPrint |
| Auth | JWT, bcrypt, Google OAuth |
| Email | Gmail SMTP app password flow |
| Code graph | graphify |

## Repository Structure 🗂️

```text
.
|-- README.md
|-- start-dev.sh
|-- Docs/
|   |-- PRD.pdf
|   |-- SRS.pdf
|   |-- TDD.pdf
|   |-- The Vision.pdf
|   `-- User Stories.pdf
|-- backend/
|   |-- app/
|   |   |-- app.py                  # Main API FastAPI app
|   |   |-- ai.py                   # Agent FastAPI app
|   |   |-- api/                    # Main API routers and endpoints
|   |   |-- agent/                  # LangGraph planner, editor, MCP, schemas
|   |   |-- core/                   # Config and Redis client
|   |   |-- database/               # SQLAlchemy database, models, schemas
|   |   |-- services/               # Rate limiting, PDF, lifecycle services
|   |   |-- templates/              # PDF templates
|   |   `-- utils/                  # Email and HTTP helpers
|   |-- migrations/                 # Alembic migrations
|   |-- tests/                      # Backend unit and integration tests
|   |-- requirements.txt
|   |-- requirements-test.txt
|   `-- brewfile
|-- frontend/
|   |-- src/
|   |   |-- apis/                   # Frontend API clients
|   |   |-- components/             # UI components and pages
|   |   |-- context/                # Auth and trip context
|   |   |-- data/                   # Static client data
|   |   |-- hooks/                  # React hooks
|   |   |-- types/                  # Shared frontend types
|   |   `-- utils/                  # Client utilities
|   |-- package.json
|   `-- vite.config.ts
`-- graphify-out/                   # Local code graph output
```

## Runtime Architecture ⚙️

BonPlan runs as four local services during development:

| Service | Default URL | Purpose |
| --- | --- | --- |
| Frontend | `http://localhost:5173` | React/Vite application |
| API backend | `http://localhost:8000` | Auth, trips, sharing, places, admin, support, PDFs |
| Agent backend | `http://localhost:8001` | Planner generation, itinerary editor chat, agent cache |
| Redis | `redis://localhost:6379/0` | Rate-limit counters and runtime cache support |

PostgreSQL is also required for normal backend operation. The backend stores users, trips, itineraries, snapshots, collaboration Q&A, support tickets, API cache rows, place photo cache rows, rate-limit configs, and usage records.

The main API is mounted under:

```text
http://localhost:8000/api/v1
```

The agent API is mounted under:

```text
http://localhost:8001/agent/api/v1
```

FastAPI documentation is available when the servers are running:

```text
http://localhost:8000/docs
http://localhost:8001/docs
```

## Main Application Areas 🧭

### Frontend Routes 🖥️

| Route | Purpose |
| --- | --- |
| `/` | Home page, active plans, feature sections |
| `/login` | Local and Google login |
| `/register` | Account registration |
| `/verify-email` | Email verification |
| `/forgot-password` | Password reset request |
| `/reset-password` | Password reset completion |
| `/share-invite` | Shared trip invitation acceptance flow |
| `/account/:section?` | Profile, preferences, settings, support |
| `/draft-plan` | Trip draft setup |
| `/plan/solo/:tripId` | Solo itinerary workspace |
| `/plan/squad/:tripId` | Squad itinerary workspace |
| `/admin/skus` | Rate-limit SKU administration |
| `/admin/usage` | Rate-limit usage viewer |
| `/admin/faq` | FAQ administration |
| `/admin/tickets` | Support ticket administration |
| `/privacy` | Privacy policy |
| `/terms` | Terms of service |

### Backend API Areas 🔌

| Area | Base Path | Responsibility |
| --- | --- | --- |
| Auth | `/api/v1/auth` | Register, login, Google auth, email verification, profile, password changes, account deletion |
| Plans | `/api/v1/plan` | Drafts, trip list, RBAC, members, sharing, downloads, snapshots, Smart Anchors, event locks |
| Places | `/api/v1/places` | Place photos and destination imagery |
| Utils | `/api/v1/utils` | Timezone lookup |
| API cache | `/api/v1/api-cache` | Cache insert and retrieve |
| Client log | `/api/v1/client-log` | Client-side event logging |
| Rate limiting | `/api/v1/rate-limiting` | Client SKU status, consumption, reset, tracking |
| Rate-limit admin | `/api/v1/rate-limiting-admin` | Admin configuration and usage views |
| Support | `/api/v1/support` | Tickets and FAQs |

### Agent API Areas 🤖

| Area | Base Path | Responsibility |
| --- | --- | --- |
| Solo planner | `/agent/api/v1/solo-planner` | Streaming itinerary generation and collaborative responses |
| Chat editor | `/agent/api/v1/chat` | Streaming itinerary edit chat |
| Agent cache | `/agent/api/v1/api-cache` | Agent-side cache access |

## Local Development 🚀

### Prerequisites ✅

Recommended local versions:

- macOS for the one-step terminal bootstrap script
- Homebrew
- Python `3.13.x`
- Node.js `20.x`
- npm `10.x`
- PostgreSQL `15`
- Redis

The project brew bundle installs:

```text
python@3.13
postgresql@15
redis
```

### One-Step Setup and Startup ⚡

From the project root:

```bash
./start-dev.sh
```

The script:

- Prints the exact config files you should review before creating env files.
- Installs Homebrew packages from discovered Brewfiles.
- Creates or refreshes `backend/.bonplan`.
- Installs backend Python requirements.
- Installs frontend dependencies with `npm ci` when `package-lock.json` exists.
- Starts Redis through Homebrew.
- Opens separate macOS Terminal windows for the API backend, agent backend, and frontend.

Useful script modes:

```bash
./start-dev.sh --setup-only
./start-dev.sh --start-only
./start-dev.sh --yes
./start-dev.sh --help
```

`--setup-only` installs dependencies without starting servers.

`--start-only` starts Redis and the app servers without reinstalling dependencies.

`--yes` skips the pause when env files are missing.

### Environment Files 🔐

Before the first real run, review these source files:

```text
backend/app/core/config.py
frontend/src/apis/config.ts
```

Then create or update:

```text
.env
frontend/.env
```

Do not commit real secrets.

#### Backend `.env` 🐍

The backend reads settings from `backend/app/core/config.py`. A local backend env file should include values like:

```bash
BACKEND_URL=http://localhost:8000
AGENT_URL=http://localhost:8001
FRONTEND_URL=http://localhost:5173

PROJECT_VERSION=v1.0.0
AGENT_VERSION=v1.0.0
LOG_ROOT=backend/logs

POSTGRES_USER=bonplan_admin
POSTGRES_PASSWORD=secure_password
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bonplan_db

REDIS_URL=redis://localhost:6379/0
RATE_LIMITER_MODE=lenient

GOOGLE_CLIENT_ID=replace_me
GOOGLE_CLIENT_SECRET=replace_me
GOOGLE_MAPS_API_KEY=replace_me

OPENROUTER_API_KEY=replace_me
SERPER_API_KEY=replace_me
RAPID_API_KEY=replace_me

SECRET_KEY=replace_me_with_a_long_random_value
SENDER_EMAIL=replace_me
GMAIL_APP_PASSWORD=replace_me

FALLBACK_IMAGE=https://images.unsplash.com/photo-1488085061387-422e29b40080
```

The model settings can also be overridden through env vars if needed:

```bash
SERPER_CONTENT_PARSER_MODEL=openrouter/nvidia/nemotron-3-nano-30b-a3b:free
CONVERSATION_AGENT_MODEL=openrouter/nvidia/nemotron-3-nano-30b-a3b:free
CONTEXT_PRUNING_MODEL=openrouter/nvidia/nemotron-3-nano-30b-a3b:free
PLANNER_AGENT_MODEL=openrouter/poolside/laguna-xs.2:free
EDITOR_AGENT_MODEL=openrouter/poolside/laguna-xs.2:free
```

#### Frontend `frontend/.env` ⚛️

The frontend reads Vite variables from `frontend/src/apis/config.ts`:

```bash
VITE_API_URL=http://localhost:8000
VITE_AGENT_URL=http://localhost:8001
VITE_GOOGLE_CLIENT_ID=replace_me
VITE_GOOGLE_MAPS_API_KEY=replace_me
VITE_GOOGLE_MAPS_MAP_ID=DEMO_MAP_ID
VITE_FALLBACK_IMAGE=https://images.unsplash.com/photo-1488085061387-422e29b40080
```

### Database Setup 🗄️

Start PostgreSQL:

```bash
brew services start postgresql@15
```

Create the local role and database if they do not exist:

```bash
psql postgres
```

```sql
CREATE ROLE bonplan_admin WITH LOGIN PASSWORD 'secure_password';
CREATE DATABASE bonplan_db OWNER bonplan_admin;
```

If you use different database credentials, update `.env` to match.

Apply migrations from `backend/`:

```bash
cd backend
source .bonplan/bin/activate
alembic upgrade head
```

The backend also ensures SQLAlchemy metadata on startup, but Alembic remains the source of migration history for schema changes.

### Manual Setup 🛠️

Use this path if you do not want to use `start-dev.sh`.

Install Homebrew packages:

```bash
brew bundle --file backend/brewfile
```

Set up the backend:

```bash
cd backend
python3.13 -m venv .bonplan
source .bonplan/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-test.txt
```

Set up the frontend:

```bash
cd frontend
npm ci
```

Start Redis:

```bash
brew services start redis
```

Start PostgreSQL:

```bash
brew services start postgresql@15
```

Start the API backend:

```bash
cd backend
source .bonplan/bin/activate
python -m uvicorn app.app:app --host 0.0.0.0 --port 8000 --reload
```

Start the agent backend:

```bash
cd backend
source .bonplan/bin/activate
python -m uvicorn app.ai:app --host 0.0.0.0 --port 8001 --reload
```

Start the frontend:

```bash
cd frontend
npm run dev
```

### Optional MCP Inspector 🧪

From `backend/` with the venv active:

```bash
npx @modelcontextprotocol/inspector python -m app.agent.mcp_server.main
```

## Development Commands 💻

### Frontend 🎨

From `frontend/`:

```bash
npm install
npm run dev
npm run build
npm run lint
npm run preview
```

### Backend 🧠

From `backend/`:

```bash
source .bonplan/bin/activate
python -m pytest
python -m pytest app/agent/test
alembic upgrade head
python -m uvicorn app.app:app --port 8000 --reload
python -m uvicorn app.ai:app --port 8001 --reload
```

## Testing 🧪

The repository includes backend unit, integration, and planner tests.

Run all backend tests:

```bash
cd backend
source .bonplan/bin/activate
python -m pytest
```

Run agent planner/editor tests:

```bash
cd backend
source .bonplan/bin/activate
python -m pytest app/agent/test
```

Run frontend checks:

```bash
cd frontend
npm run build
npm run lint
```

For UI changes, include screenshots or recordings in pull requests.

## Data Model Overview 🧬

Core persisted entities include:

- `User`: local or Google-authenticated user profile, verification state, preferences, admin flag.
- `Trip`: draft or active trip request with dates, routing style, destinations, budget, pace, travelers, and status.
- `TripMember`: owner, shared editor, or shared viewer access with invitation status.
- `TripItinerary`: generated itinerary metadata, event list, Smart Anchors, tips, status, and snapshot cursor.
- `TripItinerarySnapshot`: saved itinerary versions for revert/history flows.
- `TripCollabQA`: collaborative planner question/answer history.
- `ApiCache`: API cache records.
- `PlacePhotoCache`: cached place photo metadata.
- `RateLimitConfigs`: per-SKU limit rules.
- `RateLimitUsage`: durable rate-limit usage records.
- `FAQ`: support FAQ entries.
- `SupportTicket`: user support requests and admin responses.

Trip statuses:

```text
draft -> generating -> generated -> current -> completed
```

The lifecycle service also handles stale draft cleanup and active trip status transitions.

## Smart Anchors ⚓

Smart Anchors represent fixed constraints that the planner should honor. Supported anchor types include:

- `FLIGHT`
- `HOTEL`
- `CAR_RENTAL`
- `ACTIVITY`
- `DINING`
- `OTHER`

Anchors can include times, locations, place IDs, coordinates, booking URLs, notes, and costs. The itinerary generator and editor use anchors to preserve non-negotiable events while filling open time intelligently.

## Collaboration and Sharing 👥

BonPlan supports trip-level access control:

- `owner`: full control over the trip and sharing.
- `shared_editor`: can generate and edit plans.
- `shared_viewer`: can view shared plans.

Sharing capabilities include:

- Direct email invitations.
- Share links.
- Pending and accepted invitation states.
- Edit access requests from viewers.
- Owner/editor controls for member removal and role changes.

## Rate Limiting 🚦

Rate limiting is SKU-based and backed by Redis for fast counters plus PostgreSQL for durable usage. Redis counters are restored from Postgres on backend startup so restarts do not reset usage unexpectedly.

Admin users can manage SKU limits and inspect usage through:

```text
/admin/skus
/admin/usage
```

## Logging 📜

The backend uses structured application loggers and writes logs under:

```text
backend/logs
```

`LOG_ROOT` can be changed through the backend environment.

## Graphify Workflow 🕸️

This repository maintains a graphify code graph in:

```text
graphify-out/
```

Before architecture or cross-module codebase work, read:

```text
graphify-out/GRAPH_REPORT.md
```

For relationship questions, prefer graphify over plain text search:

```bash
graphify query "How does trip generation persist itinerary events?"
graphify path "Trip" "TripItinerary"
graphify explain "Smart Anchors"
```

After modifying code files, update the graph:

```bash
graphify update .
```

## Documentation 📚

Product and planning documents live under `Docs/`:

- `Docs/The Vision.pdf`
- `Docs/PRD.pdf`
- `Docs/SRS.pdf`
- `Docs/TDD.pdf`
- `Docs/User Stories.pdf`

These documents explain the product vision, requirements, technical design, and user journeys behind the v1 system.

## Troubleshooting 🧯

### Frontend cannot reach backend 🌐

Check `frontend/.env`:

```bash
VITE_API_URL=http://localhost:8000
VITE_AGENT_URL=http://localhost:8001
```

Then restart the Vite server. Vite env values are loaded at dev-server startup.

### CORS errors 🚧

Check backend `.env`:

```bash
FRONTEND_URL=http://localhost:5173
```

Restart both backend servers after changing it.

### Database connection fails 🗄️

Confirm Postgres is running:

```bash
brew services list
```

Confirm the configured role and database exist:

```bash
psql postgres
\du
\l
```

### Redis warnings at backend startup 🔴

Start Redis:

```bash
brew services start redis
redis-cli ping
```

The expected response is:

```text
PONG
```

### Google login or maps fail 🗺️

Check both backend and frontend Google values. The backend uses `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_MAPS_API_KEY`. The frontend uses `VITE_GOOGLE_CLIENT_ID`, `VITE_GOOGLE_MAPS_API_KEY`, and optionally `VITE_GOOGLE_MAPS_MAP_ID`.

### Agent generation fails 🤖

Check model provider keys and model names in `.env`, especially:

```bash
OPENROUTER_API_KEY
SERPER_API_KEY
RAPID_API_KEY
PLANNER_AGENT_MODEL
EDITOR_AGENT_MODEL
CONVERSATION_AGENT_MODEL
```

Also confirm the agent backend is running on port `8001`.

## Version Status 🏁

### v1.0.0 Finalized ✅

The finalized v1.0.0 system includes:

- React/Vite frontend.
- Main FastAPI backend.
- Agent FastAPI backend.
- PostgreSQL persistence.
- Redis-backed rate limiting.
- Local and Google authentication.
- Email verification and password reset.
- Trip draft creation.
- Solo and squad planning routes.
- Streaming solo itinerary generation.
- Collaborative planning Q&A.
- AI itinerary edit chat.
- Smart Anchors.
- Event locking.
- Itinerary snapshots and revert flow.
- Trip sharing with RBAC.
- PDF itinerary export.
- Places imagery and cache support.
- Account preferences.
- Support tickets and FAQs.
- Admin views for support and rate limits.
- Local one-step development bootstrap script.

### Next Version Plans 🔮

Planned post-v1 work:

- Harden production deployment configuration for separate frontend, API, agent, Redis, and PostgreSQL environments.
- Add full CI coverage for frontend build/lint and backend tests.
- Expand planner and editor regression tests with deterministic fixtures.
- Improve observability with request tracing, generation metrics, rate-limit dashboards, and agent failure reporting.
- Add richer squad collaboration flows, including real-time presence, comments, and conflict-aware edits.
- Add more Smart Anchor enrichment for flights, hotels, restaurants, bookings, and imported calendar events.
- Improve itinerary quality scoring for travel-time feasibility, opening hours, cost accuracy, and duplicate detection.
- Add itinerary export formats beyond PDF.
- Add mobile-first polish for itinerary editing and shared-trip review.
- Add user-facing billing or quota surfaces tied to SKU usage.
- Add deployment runbooks, seed data commands, and safer production migration workflows.

## Contributing 🤝

Use concise, action-oriented commits. Pull requests should include:

- User-visible change summary.
- Verification commands.
- Linked issue or context.
- Screenshots or recordings for UI changes.
- Migration notes when database schema changes.
- Env/config notes when new settings are introduced.

Before opening a PR, run the checks relevant to your change:

```bash
cd frontend && npm run build && npm run lint
cd backend && source .bonplan/bin/activate && python -m pytest
graphify update .
```

## License 📄

This repository is currently a private passion project. Add an explicit license before distributing or accepting external contributions.
