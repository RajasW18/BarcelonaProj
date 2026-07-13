# Barça Bot 🔵🔴

> A voice-enabled, agentic chatbot dedicated to FC Barcelona.  
> Ask questions by typing **or speaking** — powered by FastAPI, OpenAI Agents SDK, PostgreSQL + pgvector, React, and TypeScript.

![Blaugrana theme](https://img.shields.io/badge/theme-Blaugrana-004D98)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)

---

## Architecture

```
User (voice/text)
    │
    ▼
React Frontend (Vite + Tailwind + Web Speech API)
    │  POST /chat → SSE stream
    ▼
FastAPI Backend
    │
    ▼
OpenAI Agents SDK — BarcaBot Agent (gpt-4o)
    ├── sql_query tool ──────────────► PostgreSQL structured tables
    └── barca_knowledge tool ────────► PostgreSQL pgvector (RAG)
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | Backend |
| Node.js | 18+ | Frontend |
| Docker Desktop | Latest | PostgreSQL + pgvector |
| OpenAI API Key | — | gpt-4o + embeddings |
| football-data.org key | — | Free tier covers La Liga |

---

## Quick Start

### 1. Clone & Configure

```bash
git clone <your-repo>
cd BarcelonaProj

# Copy and fill in your API keys
cp .env.example .env
# Edit .env with your OPENAI_API_KEY and FOOTBALL_DATA_API_KEY
```

### 2. Start the Database

```bash
docker compose up -d
# Wait for the healthcheck to pass (~10 seconds)
docker compose ps  # should show "healthy"
```

### 3. Ingest Data

```bash
# Create a Python virtual environment
cd BarcelonaProj
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r api/requirements.txt

# A) Historical match data from openfootball
git clone https://github.com/openfootball/espana.git /tmp/espana
python scripts/ingest_openfootball.py --seasons-dir /tmp/espana

# B) Live data from football-data.org
python scripts/ingest_football_api.py --season 2024

# C) RAG knowledge base
python scripts/ingest_rag.py
```

### 4. Run the Backend

```bash
cd BarcelonaProj
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/health → `{"status":"ok","agent":"BarcaBot"}`

### 5. Run the Frontend

```bash
cd BarcelonaProj/frontend
npm install   # if not already done
npm run dev
```

Open: http://localhost:5173

---

## Project Structure

```
BarcelonaProj/
├── api/
│   ├── main.py              # FastAPI app + /chat SSE endpoint
│   ├── agent.py             # OpenAI Agents SDK BarcaBot configuration
│   ├── config.py            # pydantic-settings (.env reader)
│   ├── tools/
│   │   ├── sql_tool.py      # sql_query agent tool
│   │   └── rag_tool.py      # barca_knowledge RAG tool
│   └── db/
│       ├── connection.py    # asyncpg pool
│       └── schema.sql       # PostgreSQL DDL
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ChatInterface.tsx   # Main UI
│       │   ├── MessageBubble.tsx   # Chat messages
│       │   ├── VoiceButton.tsx     # Web Speech API mic
│       │   └── TypingIndicator.tsx
│       ├── hooks/
│       │   ├── useChat.ts          # SSE streaming + state
│       │   └── useSpeech.ts        # SpeechRecognition hook
│       └── index.css               # Tailwind + Blaugrana theme
├── scripts/
│   ├── ingest_openfootball.py   # Historical fixture parser
│   ├── ingest_football_api.py   # Live data from football-data.org
│   └── ingest_rag.py            # Chunk + embed → pgvector
├── data/barca_knowledge/
│   ├── history.md
│   ├── la_masia.md
│   ├── player_bios.md
│   └── tactics.md
├── docker-compose.yml
└── .env.example
```

---

## Agent Tools

### `sql_query`
Executes read-only SQL SELECT queries against structured football data.

**Example questions:**
- "What was the score in Barcelona's last match?"
- "Show me the La Liga top 5 teams by points"
- "How many goals has Lewandowski scored this season?"

### `barca_knowledge`
Semantic vector search over the curated Barça knowledge base.

**Example questions:**
- "Tell me about La Masia's philosophy"
- "What is Cruyff's legacy at Barcelona?"
- "Explain tiki-taka"

---

## Voice Input

The voice button uses the browser's native **Web Speech API**:
- Supported: Chrome, Edge, Safari (desktop)
- Not supported: Firefox (falls back to text-only, button is disabled)
- Click the 🎤 mic button → speak → transcript auto-fills and sends

---

## Customising the Knowledge Base

Add or edit markdown files in `data/barca_knowledge/`, then re-run:

```bash
python scripts/ingest_rag.py
```

The script clears and re-ingests all files. New topics are immediately searchable by the agent.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ | OpenAI API key (gpt-4o + embeddings) |
| `FOOTBALL_DATA_API_KEY` | ✅ | football-data.org API key |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `MODEL` | optional | LLM model (default: `gpt-4o`) |
| `EMBEDDING_MODEL` | optional | Embedding model (default: `text-embedding-3-small`) |
| `RAG_TOP_K` | optional | Number of RAG chunks returned (default: `5`) |

---

*Visca el Barça! Visca Catalunya!* 🔵🔴
