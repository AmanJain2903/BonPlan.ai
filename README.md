# BonPlan.ai ✈️
**Tell us When. We Tell the How.**

BonPlan.ai is an autonomous, constraint-based AI travel scheduling engine. Unlike standard generative AI planners that build rigid, unverified lists from scratch, BonPlan uses an agentic architecture to mathematically build itineraries *around* a user's non-negotiable logistical constraints (Smart Anchors).

### 🚀 Core Concept: Smart Anchors
Feed the system your pre-booked flights or non-refundable dinner reservations. BonPlan locks these anchors in place, calculates the localized transit buffers, and intelligently routes the rest of your trip to fit the available whitespace seamlessly. 

### 🛠️ Proposed Tech Stack
* **Frontend:** React, Vite, `dnd-kit` (for the interactive drag-and-drop canvas)
* **Backend:** FastAPI (Python) for asynchronous, high-performance orchestration
* **Database:** PostgreSQL (for strict relational mapping of constraints)
* **AI Orchestration:** LangChain / LlamaIndex (ReAct loop)
* **External Integrations:** Google Maps API, Google Places API

### 📂 Documentation
Before development began, the system architecture and product vision were strictly defined. You can view the foundational documents in the `/docs` directory:
1. **[PRD] Product Requirements Document:** The core vision and user personas.
2. **[SRS] Software Requirements Specification:** The strict functional and non-functional requirements (latency, token limits).
3. **[TDD] Technical Design Document:** The database schema, API contracts, and agentic loop architecture.

### 🚧 Current Status
* **Phase 1: Architecture & Planning** - ✅ Complete
* **Phase 2: MVP Development** - ⏳ Ongoing

### 🛠️ Requirements
- Python `3.13.3`
- Node.js `v20.16.0`
- npm `10.8.1`
- npx `10.8.1`

### 🚀 How to Run Locally

#### 1 Frontend setup
```bash
cd frontend
npm install
```

#### 2 Backend setup
```bash
cd backend
brew bundle
python3.13 -m venv .bonplan
source .bonplan/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3 Start frontend
From `frontend/`:
```bash
npm run dev
```

#### 4 Start backend
From `backend/`:
```bash
uvicorn app.app:app --port 8000 --workers 4 # Or -- reload but this will ignore workers flag. You can choose any number of workers.
```

#### 5 Start agent
From `backend/`:
```bash
uvicorn app.ai:app --port 8001 --workers 2 # Or -- reload but this will ignore workers flag. You can choose any number of workers.
```

#### 6 Run MCP Inspector (Optional - Just for local testing the MCP Sever)
From `backend/`:
```bash
npx @modelcontextprotocol/inspector python -m app.agent.mcp_server.main
```

---
*Built as a passion project to explore Agentic AI and constraint-based routing.*
