# Multilingual Citizen Grievance Chatbot

This project implements HI-02: a multilingual citizen grievance chatbot that accepts complaints in English, Hindi, Telugu, Hinglish and Tenglish, routes them to the right department, creates a ticket and tracks resolution status.

## Current status

Task 25 is complete: the repository scaffold, GitHub-ready ignore rules, GitHub Actions CI workflow, local Git repository and initial submission commit, language-first citizen registration and login, database-backed sessions, environment-driven production configuration, deployment readiness checklist, security hardening, enforced host validation, protected admin APIs, production configuration checks, security headers, request-size limits, logging, CORS, database health reporting, SQLAlchemy schema, seeded department reference data, ticket service, FastAPI ticket endpoints, classifier inspection endpoint and tests, PostgreSQL Docker Compose deployment, browser chat endpoint, officer dashboard, lazy faster-whisper transcription, hardened ticket-management tests, deterministic multilingual language detection, reproducible training/evaluation data generation, a rule-based classifier, lazy Hugging Face embedding-model integration, cached translation fallback services, localized response catalogs, the Telegram bot foundation, the multilingual complaint-to-ticket flow, status notifications, SLA escalation workers and the browser chat frontend are in place. Remote GitHub publication and final deployment remain.

## Problem statement

Citizens may find it difficult to submit public-service complaints in a language they are comfortable using, identify the correct government department, and follow the progress of a complaint. This project provides a multilingual citizen-facing workflow that accepts text or optional voice complaints, preserves the original complaint, classifies the intent and department, creates a ticket, and displays a transparent status timeline.

## Team details

This project was developed by two team members:

Team Name:Radhakrishna- Chiluka Teja swi & Bommagani Ramanjaneyulu— full-stack developer responsible for product design, FastAPI backend, web interface, multilingual workflow, database integration, testing and deployment preparation.

## Tech stack

- Python 3.11+, FastAPI, Pydantic and Uvicorn
- SQLAlchemy with PostgreSQL as the primary database and SQLite as the local fallback
- HTML, CSS and JavaScript browser interface
- Telegram Bot API integration
- Hugging Face multilingual models and deterministic rule-based fallbacks
- Optional Sarvam AI routing for flexible complaint classification
- Optional faster-whisper/Whisper voice transcription
- Optional LangChain conversation orchestration
- Pytest, Ruff, Docker Compose and GitHub Actions

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

## Setup instructions

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-optional.txt
pip install -r requirements-dev.txt
copy .env.example .env
uvicorn app.main:app --reload
```

`requirements.txt` contains the lightweight web/API runtime used by Vercel. Install `requirements-optional.txt` for the Telegram bot, background worker, Hugging Face classifier, translation and Whisper voice features. Install `requirements-dev.txt` for tests and Ruff.

Open `http://127.0.0.1:8000/health` to verify the service.

Open `http://127.0.0.1:8000/docs` to try the ticket endpoints interactively.

Initialize the database and seed the department reference data before filing the first complaint:

```text
python -m app.init_db
```

For the full deployment configuration, set `DATABASE_URL` to PostgreSQL in `.env`. SQLite remains available for local testing. Keep all passwords, Telegram tokens and Sarvam API keys in `.env`; use `.env.example` as the safe template.

To enable optional AI routing, set `ENABLE_AI_ROUTING=true` and provide `SARVAM_API_KEY`. To enable voice transcription, set `ENABLE_VOICE=true` and install `requirements-optional.txt`.

Use `POST /classify` to inspect language, department, intent, priority, confidence and clarification status without creating a ticket.

The browser chat collects the complaint address and optional incident date/time with each new complaint. These details are saved on the ticket and shown in the citizen confirmation and officer dashboard. The address is required for a new complaint, while `/status GRV-YYYY-NNNNNN` can still be used without it.

After submission, the citizen receives a public ticket ID and can open `My Tickets` to search only their own tickets, assigned department, intent, status and complaint details. The authenticated citizen navigation also provides separate Home, Profile, Back and Logout pages.

Status tracking records the department route, department viewed state, accepted or rejected decision, work-in-progress updates, expected SLA resolution time, resolution, escalation and closure as timestamped ticket events. Officers update these states from the protected dashboard, and citizens see the timeline on the home confirmation and My Tickets page.

## PostgreSQL setup

The primary deployment uses PostgreSQL. SQLite is the default local fallback so development can begin without a running database server. Docker Compose starts both PostgreSQL and the API, waits for the database health check, initializes the schema and seeds departments. See `docs/postgresql-deployment.md` for the exact commands.

Production security settings are documented in `docs/security.md`.

## GitHub submission

The repository includes a GitHub Actions workflow at `.github/workflows/ci.yml`. It runs the test suite and Ruff checks on every push and pull request. Before publishing, confirm that `.env` is ignored and that no credentials, local database files, virtual environments or model artifacts are staged.

Initialize the configured database tables and seed the ten departments with:

```text
python -m app.init_db
```

## Demo and screenshots

The project includes a runnable browser demo. After starting the server, open these pages:

- `http://127.0.0.1:8000/welcome` — select English, Hindi or Telugu.
- `http://127.0.0.1:8000/register` — create a citizen account.
- `http://127.0.0.1:8000/login` — sign in using the selected language.
- `http://127.0.0.1:8000/chat` — submit a text or voice complaint with address and incident details.
- `http://127.0.0.1:8000/my-tickets` — view the ticket, assigned department and tracking timeline.
- `http://127.0.0.1:8000/docs` — inspect and test the FastAPI endpoints.

The demo shows language-first registration and login, multilingual complaint intake, AI/rule-based department routing, ticket creation, department assignment, status tracking, expected resolution time and citizen ticket history. For a hosted submission, replace the local URLs above with the deployed application URL and add deployment screenshots or a short screen recording link.

## AI tools used

- Hugging Face multilingual models for language-aware classification, embeddings and optional translation.
- Sarvam AI API as an optional external routing provider for flexible intent and department classification.
- Whisper/faster-whisper as an optional speech-to-text provider for voice complaints.
- LangChain is supported as an optional orchestration layer; the core workflow remains usable without it.
- Codex was used as a development assistant for implementation, debugging, test creation and documentation updates.

For Vercel deployment, keep `ENABLE_VOICE=false`, `ENABLE_AI_ROUTING=false` and `ENABLE_TRANSLATION=false` initially. Vercel installs the lightweight `requirements.txt`; installing the full optional ML and voice stack would exceed the Python Function bundle limit.

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

The development checks require `requirements-dev.txt` and the optional package set because the test suite covers the full local feature set.

## License and data

Dataset sources, model licenses and attribution will be documented before the final release.
