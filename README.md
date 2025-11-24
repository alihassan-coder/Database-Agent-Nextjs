                 # Database Agent – Backend (FastAPI)

FastAPI backend for the **Database Agent** application. It connects to a PostgreSQL database, inspects the schema, and exposes endpoints that the frontend uses to:

- chat with an LLM‑powered agent about the database
- run safe SQL queries
- inspect tables / schema metadata

This backend is designed to work together with the Next.js frontend in:

`database-agent-frountend-nextjs/`

---

## Features

- FastAPI‑based HTTP API
- Database schema inspection (PostgreSQL)
- Agent orchestration logic (LLM tools, prompts, approvals)
- Alembic migrations
- Example scripts for database setup and tests

---

## Project Structure

Top‑level view:

```text
.
├── main.py                  # FastAPI app entrypoint
├── agent/                   # Core agent logic
│   ├── __init__.py
│   ├── config.py            # Agent / model configuration helpers
│   ├── human_approval.py    # Human-in-the-loop approval logic
│   ├── main_agent.py        # Main agent orchestration
│   ├── simple_approval.py   # Simple approval flow
│   ├── system_prompts.py    # Prompt templates for the agent
│   ├── tools.py             # Tools (DB access, etc.) used by the agent
│   └── utils.py             # Shared utilities
├── agent_backup/            # Backup / experimental agent versions
├── alembic/                 # Alembic migration environment
│   ├── env.py
│   ├── script.py.mako
│   └── versions/            # Individual migration scripts
├── config/                  # App / DB configuration modules
├── examples/                # Example usage / scripts
├── model/                   # Pydantic models / domain models
├── setup_database.py        # Helper script to initialize DB
├── chack_databse_status.py  # Script to verify DB connectivity / status
├── test_table_creation.py   # Basic DB table creation tests
├── test_table_extraction_unit.py  # Unit tests for table extraction
├── pyproject.toml           # Python project metadata & dependencies
├── uv.lock                  # Lockfile (uv / pip) for reproducible installs
├── .env.example             # Example environment variables
├── .env                     # Local environment configuration (not committed)
└── .venv/                   # Local virtual environment (ignored)
```

---

## Setup

### 1. Create & activate virtual environment

You can use any tool you like. One option (Python 3.12+):

```bash
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
```

### 2. Install dependencies

Dependencies are defined in `pyproject.toml` / `uv.lock`.

If you use `uv`:

```bash
uv sync
```

Or with `pip` (if you export requirements):

```bash
pip install -e .
```

### 3. Configure environment

Copy the example file and fill your values:

```bash
cp .env.example .env
```

Then set at least:

- `DATABASE_URL` – PostgreSQL connection string
- any LLM / API keys used by the agent (if applicable in your local config)

### 4. Initialize the database (optional helper)

Run the helper script or Alembic migrations depending on your workflow.

Example:

```bash
python setup_database.py
```

You can also use Alembic directly to run migrations from the `alembic/` folder.

### 5. Run the API server

From the project root:

```bash
uvicorn main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`.

---

## High‑Level Architecture

```text
Frontend (Next.js UI)
        │
        ▼
FastAPI (this project) ──► Agent layer (agent/main_agent.py, tools.py, prompts)
        │
        ▼
PostgreSQL database (+ optional vector / RAG layer)
```

- `main.py` exposes API endpoints used by the frontend.
- `agent/` contains the orchestration logic to decide how to respond.
- `tools.py` and related utilities talk to the database and other tools.

---

## Tests & Utilities

- `test_table_creation.py` – verifies tables exist / can be created
- `test_table_extraction_unit.py` – tests schema extraction logic
- `chack_databse_status.py` – quick script to check DB connection & status

Run tests, for example, with:

```bash
pytest
```

---

## Connecting the Frontend

The Next.js frontend expects this backend at:

- `http://localhost:8000`

If you deploy the backend elsewhere, update the base URL in the frontend service layer (`src/app/services` in the Next.js project).

---

## Notes

- Keep your `.env` file private; do **not** commit it to version control.
- Make sure your database is reachable from the machine where this backend runs.