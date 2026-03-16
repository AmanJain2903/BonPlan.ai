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

---
*Built as a passion project to explore Agentic AI and constraint-based routing.*
