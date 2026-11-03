# Multilingual Citizen Grievance Chatbot

This project implements HI-02: a multilingual citizen grievance chatbot that accepts complaints in English, Hindi, Telugu, Hinglish and Tenglish, routes them to the right department, creates a ticket and tracks resolution status.

## Current status

Task 25 is complete: the repository scaffold, GitHub-ready ignore rules, GitHub Actions CI workflow, local Git repository and initial submission commit, language-first citizen registration and login, database-backed sessions, environment-driven production configuration, deployment readiness checklist, security hardening, enforced host validation, protected admin APIs, production configuration checks, security headers, request-size limits, logging, CORS, database health reporting, SQLAlchemy schema, seeded department reference data, ticket service, FastAPI ticket endpoints, classifier inspection endpoint and tests, PostgreSQL Docker Compose deployment, browser chat endpoint, officer dashboard, lazy faster-whisper transcription, hardened ticket-management tests, deterministic multilingual language detection, reproducible training/evaluation data generation, a rule-based classifier, lazy Hugging Face embedding-model integration, cached translation fallback services, localized response catalogs, the Telegram bot foundation, the multilingual complaint-to-ticket flow, status notifications, SLA escalation workers and the browser chat frontend are in place. Remote GitHub publication and final deployment remain.

## Planned pipeline

```text
Citizen text or voice
  -> language detection and transcription
  -> multilingual classification
  -> clarification when confidence is low
  -> ticket creation and department routing
  -> admin status update
  -> citizen notification and SLA escalation
```

## Local setup

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` to verify the service.

Open `http://127.0.0.1:8000/docs` to try the ticket endpoints interactively.

Use `POST /classify` to inspect language, department, intent, priority, confidence and clarification status without creating a ticket.

## PostgreSQL setup

The primary deployment uses PostgreSQL. SQLite is the default local fallback so development can begin without a running database server. Docker Compose starts both PostgreSQL and the API, waits for the database health check, initializes the schema and seeds departments. See `docs/postgresql-deployment.md` for the exact commands.

Production security settings are documented in `docs/security.md`.

## GitHub submission

The repository includes a GitHub Actions workflow at `.github/workflows/ci.yml`. It runs the test suite and Ruff checks on every push and pull request. Before publishing, confirm that `.env` is ignored and that no credentials, local database files, virtual environments or model artifacts are staged.

Initialize the configured database tables and seed the ten departments with:

```text
python -m app.init_db
```

## Configuration

Copy `.env.example` to `.env` and set credentials locally. Never commit `.env` or tokens. `DATABASE_URL` defaults to SQLite; set it to a PostgreSQL URL when PostgreSQL is available. `CORS_ORIGINS` controls which web clients may call the API.

## Project layout

```text
app/       FastAPI application and domain services
ml/        Dataset generation, training and evaluation
tests/     Automated tests
docs/      Architecture and demo documentation
```

## Development checks

```text
pytest
ruff check .
```

## License and data

Dataset sources, model licenses and attribution will be documented before the final release.
