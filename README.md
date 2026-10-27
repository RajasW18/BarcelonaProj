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

    subgraph Browser[Browser at localhost:5173]
        Landing[Landing page]
        Login[Login page]
        Chat[Authenticated workspace]
        History[History sidebar]
        Attachments[Files, images, URLs, voice]
        Normalize[Normalize saved sources]
        Boundary[Workspace error boundary]
    end

    subgraph API[FastAPI at localhost:8000]
        Auth[Authentication routes]
        ChatRoute[POST /chat]
        SessionRoutes[Chat session routes]
        ContextRoute[POST /attachments/prepare]
        Router[Question router]
        Direct[Direct generation]
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

    User --> Landing
    Login --> Auth
    Auth --> Google
    Auth --> Gmail
    Auth --> Postgres

    Chat --> SessionRoutes
    History --> SessionRoutes
    SessionRoutes --> Normalize
    Normalize --> Chat
    Chat -. rendering failure .-> Boundary
    Chat --> ChatRoute
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
10. History responses normalize `sources` into string arrays before rendering.
    This keeps older records with JSON-encoded or plain-string sources from
    crashing the workspace.
11. A React error boundary displays a recovery screen if a workspace render
    error still occurs instead of leaving a blank page.

The browser sends credentials with protected requests. The session is stored
in the `ninety_session` HttpOnly cookie; PostgreSQL remains the source of truth
for users, sessions, and messages.

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

### Authenticated workspace and history flow

```mermaid
sequenceDiagram
    participant Browser
    participant App as React App
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Bubble as MessageBubble

    Browser->>App: Open workspace
    App->>API: GET /chat/sessions
    API->>DB: List sessions owned by user
    DB-->>API: Session summaries
    API-->>App: Session list
    App->>API: GET /chat/sessions/{id}
    API->>DB: Load messages and JSONB sources
    DB-->>API: Saved messages
    API-->>App: Message history
    App->>App: Normalize sources to string[]
    App->>Bubble: Render messages

    alt Unexpected workspace render error
        App->>App: Error boundary catches exception
        App-->>Browser: Recovery screen with reload action
    else Valid message data
        Bubble-->>Browser: Workspace renders normally
    end
```

The `sources` field is stored as JSONB. The frontend accepts arrays, JSON
strings containing arrays, and legacy plain strings, then renders only valid
source names. This compatibility layer is applied both while loading history
and immediately before rendering a message.

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

### The workspace shows a blank screen or a workspace error

The workspace now shows a recovery screen instead of silently displaying a
black page. If the screen reports an error such as:

```text
message.sources?.join is not a function
```

restart Vite and hard-refresh the browser so the latest frontend bundle is
loaded:

```powershell
cd frontend
npm run dev
```

Then press `Ctrl + Shift + R` in Brave. The current frontend normalizes old
`sources` values and prevents malformed history records from crashing message
rendering. If another error appears, open Brave DevTools with `F12`, check the
Console, and inspect the failing request in the Network panel.

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

## Deploying Ninety

Ninety is a two-service application in production:

```text
Vercel                  Render / Koyeb / Railway
React static site  ---> FastAPI API
                            |
                            +--> Managed PostgreSQL
                            +--> Cloud model provider
```

Vercel is appropriate for the frontend, but it is not a suitable host for the
current local Ollama process or a long-running PostgreSQL connection. Deploy
the React site to Vercel and deploy FastAPI separately.

### Recommended free starting stack

| Layer | Recommended service | Notes |
|---|---|---|
| Frontend | Vercel | Excellent fit for this Vite site |
| Python API | Render free web service | Simple GitHub deployment; may sleep when idle |
| PostgreSQL | Neon free PostgreSQL | Use its pooled connection string |
| Email | Gmail SMTP or Brevo | Keep credentials only in the API host |
| AI | OpenAI, Groq, or another hosted provider | Ollama on your laptop is not reachable by Render |

Free hosting limits change frequently. Expect cold starts on free API services,
limited database storage, and provider-specific usage limits. For a public
production app, upgrade the API and database after validating the architecture.

### Deploy the frontend to Vercel

The repository includes [vercel.json](vercel.json), which configures the
frontend build from the repository root.

1. Push the repository to GitHub.
2. Open Vercel and choose **Add New Project**.
3. Import the repository.
4. Keep the repository root as the project root.
5. Vercel will use:

```text
Install command: npm --prefix frontend install
Build command: npm --prefix frontend run build
Output directory: frontend/dist
```

6. Deploy once to obtain a URL such as:
   `https://ninety-football.vercel.app`
7. Add this Vercel environment variable:

```text
VITE_API_URL=https://your-api-service.example.com
```

Do not include a trailing slash in `VITE_API_URL`. Redeploy after adding or
changing it.

### Deploy the backend to Render

The repository includes [render.yaml](render.yaml) as a starting blueprint.

1. Create a Render account and choose **New → Blueprint**.
2. Select the GitHub repository.
3. Review the `ninety-api` web service.
4. Set the environment variables listed below.
5. Deploy the service and copy its public URL, for example:
   `https://ninety-api.onrender.com`

Set these Render values:

```text
FRONTEND_URL=https://ninety-football.vercel.app
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
GOOGLE_REDIRECT_URI=https://ninety-api.onrender.com/auth/google/callback
DATABASE_URL=<Neon pooled PostgreSQL URL>
```

The deployed API also needs the email and AI provider variables:

```text
AUTH_SECRET=<long random secret>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<sender Gmail address>
SMTP_PASSWORD=<Gmail App Password>
SMTP_FROM=<sender Gmail address>
OPENAI_API_KEY=<hosted provider key>
OPENAI_BASE_URL=<provider-compatible URL>
MODEL=<hosted text model>
```

For production, do not set `OPENAI_BASE_URL` to
`http://localhost:11434/v1`. That address refers to the Render container
itself, not your personal computer. Use a hosted model endpoint, or deploy a
reachable inference service separately. If using Groq for vision, also set
`GROQ_API_KEY` and `GROQ_VISION_MODEL`.

### Create the managed database

Create a free PostgreSQL database on Neon, copy its pooled connection string,
and set it as Render's `DATABASE_URL`. The API creates the auth and chat tables
on startup. Apply the football schema and ingest data from a trusted machine
with access to the same database:

```powershell
psql "$env:DATABASE_URL" -f api\db\schema.sql
python scripts\ingest_football_api.py --season 2024
```

If `psql` is not installed locally, use Neon SQL Editor to run
[api/db/schema.sql](api/db/schema.sql), then run the ingestion script from a
machine with the project environment configured.

### Update Google OAuth for production

In Google Cloud, add the deployed frontend origin:

```text
https://ninety-football.vercel.app
```

Replace the local redirect URI with the Render API callback:

```text
https://ninety-api.onrender.com/auth/google/callback
```

Update the same value in Render's `GOOGLE_REDIRECT_URI`. The callback must be
the API URL, not the Vercel URL.

### Production cookie and CORS behavior

Local development uses a Vite proxy, so relative browser requests work on one
origin. In production, the frontend calls the API using `VITE_API_URL`.
Because the frontend and API are on different domains:

- The frontend sends `credentials: include`.
- FastAPI allows only the configured `FRONTEND_URL`.
- Auth cookies use `Secure` and `SameSite=None`.
- Both sites must use HTTPS.

Do not use `allow_origins=["*"]` with credentialed cookies.

### Other hosting options

If Vercel or Render is not suitable:

- **Netlify**: good Vite frontend alternative. Use the same `npm --prefix
  frontend run build` command and `frontend/dist` output.
- **Cloudflare Pages**: fast frontend hosting with a generous free tier.
  Pair it with a separate Python API.
- **Koyeb**: practical alternative for a small FastAPI service, subject to
  current free-tier availability.
- **Railway**: very convenient for API plus database, but its free/trial
  availability and limits change more often.
- **Hugging Face Spaces**: useful if the app later becomes a model demo, but
  free CPU Spaces are not a good fit for responsive authenticated chat with
  PostgreSQL.
- **Fly.io**: flexible for Docker deployments, but confirm current pricing
  before relying on a free allocation.

The most straightforward migration path is Vercel + Render + Neon. If cold
starts become frustrating, move only the API to a paid always-on service; the
frontend can remain on Vercel.
