# Deployment readiness checklist

Task 24 verifies the production configuration before hosting the project.

## Required environment values

```text
APP_ENV=production
DEBUG=false
SECRET_KEY=<long-random-secret>
DATABASE_URL=postgresql+psycopg://<user>:<encoded-password>@<host>:5432/<database>
ADMIN_USERNAME=<officer-username>
ADMIN_PASSWORD=<strong-password>
ALLOWED_HOSTS=<deployment-host>
CORS_ORIGINS=https://<frontend-host>
```

Keep the real values in the host's secret manager or an untracked `.env` file. Never commit them to GitHub.

## Verification commands

```text
.venv\Scripts\python.exe -m app.init_db
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Confirm:

- `/health` reports `environment=production`.
- `/health` reports `database=postgresql` and `database_status=ok`.
- `/admin` returns `401` without officer credentials.
- `/chat` accepts a clear complaint and returns a ticket code.
- `/docs` exposes the documented API endpoints.
