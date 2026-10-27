# Ninety

Ninety is a football intelligence chatbot. It combines local AI generation,
live football data, attachment analysis, voice input, passwordless sign-in, and
account-scoped chat history in one workspace.

The application is designed to run locally:

- React and Vite provide the browser experience.
- FastAPI provides authentication, attachment processing, chat routing, and
  server-sent event responses.
- Ollama runs the local language and vision models.
- PostgreSQL with pgvector stores football data, users, chat sessions, messages,
  and optional knowledge embeddings.
- Docker Compose runs PostgreSQL and pgvector.

## What Ninety does

You can use Ninety to:

- Ask qualitative football questions and receive generated answers.
- Query live or recently ingested standings, fixtures, scores, and player data.
- Discuss formations, pressing, transitions, roles, and match patterns.
- Upload PDFs, DOCX files, text files, CSV, JSON, source code, and images.
- Paste a public website URL for extraction and analysis.
- Ask questions by voice through the browser Web Speech API.
- Sign in with Google OAuth or an email one-time password.
- Create multiple chat rooms and reopen saved conversations later.

Ninety is football-focused, but it is not restricted to FC Barcelona. The
structured data depends on the competitions and teams that have been ingested.

## Architecture

```mermaid
flowchart LR
    User[User]

    subgraph Browser[Browser]
        Landing[Landing page]
        Login[Login page]
        Chat[Chat workspace]
        History[Saved chat history]
        Attachments[Files, images, URLs, voice]
    end

    subgraph API[FastAPI on port 8000]
        Auth[Authentication]
        ChatRoute[POST /chat]
        SessionRoutes[Chat session routes]
        ContextRoute[POST /attachments/prepare]
        Router[Question router]
        Direct[Direct local generation]
        Stats[Stats agent]
    end

    subgraph Local[Local services]
        Ollama[Ollama<br/>Qwen + LLaVA]
        Postgres[(PostgreSQL + pgvector)]
    end

    subgraph External[Optional external services]
        Google[Google OAuth]
        Gmail[Gmail SMTP]
        FootballData[football-data.org]
    end

    User --> Browser
    Landing --> Login
    Login --> Auth
    Auth --> Google
    Auth --> Gmail
    Auth --> Postgres

    Chat --> ChatRoute
    History --> SessionRoutes
    Attachments --> ContextRoute
    ChatRoute --> Router
    Router --> Direct
    Router --> Stats
    Direct --> Ollama
    Stats --> Postgres
    ContextRoute --> Ollama
    ChatRoute --> Postgres
    FootballData --> Postgres
```

### Request flow

1. The browser loads the React application from Vite on port `5173`.
2. Vite proxies `/auth`, `/chat`, `/attachments`, and `/health` to FastAPI on
   port `8000`.
3. FastAPI validates the signed HttpOnly session cookie for protected routes.
4. A chat request is associated with a PostgreSQL chat session owned by the
   signed-in user.
5. FastAPI loads previous messages from that chat session.
6. The question router chooses the generation path:
   - General or tactical questions use direct Ollama generation.
   - Questions containing football-stat terms use the SQL-enabled agent.
7. The assistant answer is streamed to the browser as SSE token events.
8. The user and assistant messages are written to PostgreSQL after generation.
9. Refreshing the browser reloads the user's saved sessions and messages.

## AI providers and models

The default configuration uses Ollama, so normal generation does not require a
paid AI API:

| Purpose | Default model | Configuration |
|---|---|---|
| Text generation | `qwen2.5:7b` | `MODEL` |
| Image analysis | `llava` | `OLLAMA_VISION_MODEL` |
| Embeddings | `nomic-embed-text` | `EMBEDDING_MODEL` |

Ollama must be installed and running at `http://localhost:11434`. Download the
models once:

```powershell
ollama pull qwen2.5:7b
ollama pull llava
ollama pull nomic-embed-text
```

`OPENAI_BASE_URL` points the OpenAI-compatible client at Ollama. The variable
name is retained because the Python OpenAI client and Agents SDK use that
interface. `OPENAI_API_KEY=ollama` is a local placeholder and is not a real
cloud credential.

## Database architecture

PostgreSQL is used for durable application state and football data. The
frontend never connects directly to PostgreSQL.

```mermaid
erDiagram
    USERS ||--o{ CHAT_SESSIONS : owns
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : contains
    USERS ||--o{ AUTH_OTPS : requests

    USERS {
        bigint id PK
        varchar email UK
        varchar display_name
        text avatar_url
        timestamptz created_at
        timestamptz updated_at
    }

    AUTH_OTPS {
        bigint id PK
        varchar email
        char code_hash
        timestamptz expires_at
        timestamptz consumed_at
    }

    CHAT_SESSIONS {
        uuid id PK
        bigint user_id FK
        varchar title
        timestamptz created_at
        timestamptz updated_at
    }

    CHAT_MESSAGES {
        bigint id PK
        uuid session_id FK
        varchar role
        text content
        jsonb sources
        timestamptz created_at
    }
```

The football tables are independent of authentication:

- `teams`: team identity and crest metadata.
- `players`: player identity and team relationships.
- `competitions`: competition and season metadata.
- `matches`: fixtures, scores, dates, status, and team relationships.
- `standings`: competition table snapshots.
- `player_stats`: season-level player statistics.
- `knowledge_chunks`: optional embedded documents for semantic search.

The API creates the authentication and chat tables during startup. The
definitions are also kept in [api/db/schema.sql](api/db/schema.sql). If an
older development database contains the previous single-session table, the API
renames it to `legacy_chat_sessions` before creating the user-scoped schema.

## Authentication

### Google OAuth

The browser opens `/auth/google/login`. FastAPI redirects to Google, validates
the OAuth state on return, fetches the Google profile, creates or updates the
local user, and sets a signed HttpOnly cookie.

For local development, configure this redirect URI in Google Cloud:

```text
http://localhost:8000/auth/google/callback
```

Also add this authorized JavaScript origin:

```text
http://localhost:5173
```

The app can remain in Google's Testing mode while you develop. Add your own
Google account as a test user.

### Email OTP

The email flow does not store passwords:

1. The user submits an email address.
2. FastAPI generates a six-digit code.
3. Only a hash of the code is stored in `auth_otps`.
4. Gmail SMTP sends the code.
5. The code expires after ten minutes and can be consumed once.
6. Successful verification creates the user and sets the session cookie.

For Gmail SMTP, use a Gmail App Password, not your normal Gmail password.

## Attachment processing

The frontend sends selected files and an optional public URL to
`POST /attachments/prepare`. The backend:

1. Validates the input and file size.
2. Extracts text from supported documents.
3. Fetches and extracts readable content from public URLs.
4. Sends images to the configured vision model.
5. Returns a context string and source names.

The frontend includes that approved context in the following `/chat` request.
Attachments are processed for the request and are not currently stored as
permanent files in PostgreSQL.

Supported inputs include PDF, DOCX, TXT, Markdown, CSV, JSON, common source
files, HTML, CSS, SQL, YAML, and images. The maximum upload size is 25 MB.

## Chat routing

```mermaid
sequenceDiagram
    participant Browser
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Ollama

    Browser->>API: POST /chat with session_id
    API->>DB: Verify owner and load messages
    API->>API: Detect stats-related terms

    alt General or tactical question
        API->>Ollama: Generate using conversation context
        Ollama-->>API: Answer
    else Stats question
        API->>DB: Execute read-only football query through agent tool
        DB-->>API: Current structured data
        API-->>API: Compose grounded answer
    end

    API->>DB: Save user and assistant messages
    API-->>Browser: SSE tokens, sources, done
```

The stats tool is intended for structured facts. Qualitative analysis is
generated by the local language model and should be treated as analysis rather
than an official data feed.

## Project structure

```text
BarcelonaProj/
├── api/
│   ├── main.py                 FastAPI routes and application lifecycle
│   ├── auth.py                 OAuth, OTP, cookies, and user helpers
│   ├── agent.py                Local generation and stats agent setup
│   ├── context.py              File, image, and URL context extraction
│   ├── config.py               Typed environment configuration
│   ├── requirements.txt        Python dependencies
│   ├── db/
│   │   ├── connection.py        Async PostgreSQL pool
│   │   └── schema.sql           Database schema
│   └── tools/
│       ├── sql_tool.py          Read-only structured data tool
│       └── rag_tool.py          Optional vector search tool
├── frontend/
│   ├── vite.config.ts           Dev server and backend proxy
│   └── src/
│       ├── App.tsx              Auth and landing-page routing
│       ├── components/
│       │   ├── LoginPage.tsx    Google and email login
│       │   ├── LandingPage.tsx  Product landing page
│       │   ├── ChatInterface.tsx Chat workspace and history sidebar
│       │   ├── MessageBubble.tsx Rendered chat messages
│       │   └── VoiceButton.tsx  Browser voice input
│       ├── hooks/
│       │   ├── useChat.ts       Sessions, history, and SSE state
│       │   └── useSpeech.ts     Speech recognition helper
│       └── index.css             Football visual system and responsive UI
├── scripts/
│   ├── ingest_openfootball.py   Historical match ingestion
│   ├── ingest_football_api.py   football-data.org ingestion
│   └── ingest_rag.py            Knowledge embedding ingestion
├── docker-compose.yml            PostgreSQL + pgvector service
└── .env                          Local secrets, never commit this file
```

## Local setup on Windows

### Prerequisites

- Python 3.12 or newer.
- Node.js 18 or newer.
- Docker Desktop with the Linux engine running.
- Ollama with the required models downloaded.
- A football-data.org API key for live data ingestion.

### Create the environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r api\requirements.txt
```

If PowerShell blocks activation for the current process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### Configure `.env`

Create or edit the root `.env` file:

```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
MODEL=qwen2.5:7b
OLLAMA_VISION_MODEL=llava
EMBEDDING_MODEL=nomic-embed-text

FOOTBALL_DATA_API_KEY=your-football-data-key
DATABASE_URL=postgresql://barca:barca@localhost:5432/barcadb

AUTH_SECRET=your-long-random-secret
FRONTEND_URL=http://localhost:5173

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-gmail-address@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM=your-gmail-address@gmail.com
```

Keep `.env` local. It is ignored by Git and must not be uploaded or pasted into
issues, screenshots, or chat.

### Start PostgreSQL

Make sure Docker Desktop is open, then run:

```powershell
docker compose up -d
docker compose ps
```

The service is exposed at `localhost:5432` with:

```text
user: barca
password: barca
database: barcadb
```

### Start the backend

In the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --reload --reload-dir api --host 0.0.0.0 --port 8000
```

Check that it is running:

```powershell
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","agent":"Ninety"}
```

### Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Data ingestion

The application can operate with the existing database contents. To refresh
football data, use the ingestion scripts from the repository root.

Historical openfootball data:

```powershell
python scripts\ingest_openfootball.py --seasons-dir C:\path\to\espana
```

Live football-data.org data:

```powershell
python scripts\ingest_football_api.py --season 2024
```

Knowledge embeddings:

```powershell
python scripts\ingest_rag.py
```

The embedding model must match the database vector dimension. The current local
`nomic-embed-text` configuration uses 768 dimensions.

## Useful API routes

| Method | Route | Auth | Purpose |
|---|---|---:|---|
| `GET` | `/health` | No | Backend health check |
| `GET` | `/auth/me` | Yes | Current signed-in user |
| `GET` | `/auth/google/login` | No | Start Google OAuth |
| `GET` | `/auth/google/callback` | No | OAuth callback |
| `POST` | `/auth/request-otp` | No | Send email code |
| `POST` | `/auth/verify-otp` | No | Verify email code |
| `POST` | `/auth/logout` | Yes | Clear session cookie |
| `POST` | `/chat/session` | Yes | Create a saved chat |
| `GET` | `/chat/sessions` | Yes | List the user's chats |
| `GET` | `/chat/sessions/{id}` | Yes | Load one chat's messages |
| `DELETE` | `/chat/sessions/{id}` | Yes | Delete one saved chat |
| `POST` | `/chat` | Yes | Stream an AI response |
| `POST` | `/attachments/prepare` | No | Prepare file or URL context |

## Troubleshooting

### Docker cannot connect to the Docker API

Open Docker Desktop and wait for the Linux engine to finish starting. Then
retry:

```powershell
docker compose up -d
```

### Google redirects to an error

Check that these values match exactly:

```text
Google redirect URI:
http://localhost:8000/auth/google/callback

.env:
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

Also add `http://localhost:5173` as an authorized JavaScript origin and add
your account as a test user while the OAuth application is in Testing mode.

### Email OTP is not sent

For Gmail, use a generated App Password rather than the normal account
password. `SMTP_USERNAME` and `SMTP_FROM` should normally be the same Gmail
address. Restart FastAPI after editing `.env`.

### The app requests the wrong model

Check for duplicate `MODEL` entries in `.env`. The final effective value should
be:

```env
MODEL=qwen2.5:7b
```

Confirm Ollama can see the model:

```powershell
ollama list
```

### Attachments fail

Both servers must be running. The frontend Vite proxy must forward
`/attachments` to port `8000`. Check the browser network panel and the FastAPI
terminal for the response status.

### Chat history is empty

Confirm that:

1. You are signed in.
2. PostgreSQL is running.
3. The backend started successfully.
4. The browser is using the same `localhost` origin.

The frontend never stores the durable chat history itself. It requests sessions
from FastAPI, and FastAPI loads them from PostgreSQL.

## Security notes

- Never commit `.env`.
- Never expose `DATABASE_URL`, OAuth secrets, SMTP credentials, or API keys in
  frontend code.
- Use HTTPS, secure cookies, a production email provider, and a managed
  PostgreSQL instance before deploying publicly.
- Rotate credentials immediately if they are exposed.
- The stats SQL tool is intended to execute read-only queries.
- Treat model-generated tactical analysis as an interpretation, not a verified
  official report.
