# Multilingual Citizen Grievance Chatbot

## Project

HI-02 multilingual citizen grievance chatbot. The system accepts complaints in Indian languages, classifies and routes them to departments, creates tickets, tracks status and notifies citizens.

## Stack

- Python 3.11+ compatible code
- FastAPI and Pydantic
- SQLAlchemy with PostgreSQL as the primary database and SQLite as the local fallback
- Telegram Bot API and a small web fallback
- Hugging Face models for multilingual NLP
- LangChain only for optional conversation orchestration
- Whisper or faster-whisper as an optional voice feature

## Rules

- Keep the application simple and runnable.
- Preserve the original citizen complaint text.
- Keep all user-facing bot text in `app/bot/i18n/en.json`, `hi.json` and `te.json`.
- Never commit secrets. Use `.env` and update `.env.example`.
- Every service function must have type hints and tests as the service is implemented.
- Keep deterministic fallbacks when model, translation or external services are unavailable.
- Do not claim model quality without reporting evaluation results.
- After each task, run the available tests and lint checks, then update the README when commands or environment variables change.
