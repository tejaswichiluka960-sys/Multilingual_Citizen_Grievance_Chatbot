# PostgreSQL deployment

Task 22 adds a complete Docker Compose deployment profile. SQLite remains the default for local development; Docker Compose runs the API against PostgreSQL.

## Start the PostgreSQL profile

1. Install Docker Desktop and confirm `docker compose version` works.
2. Copy `.env.example` to `.env` and add only the credentials or tokens you intend to use.
3. Start the database and API:

   ```text
   docker compose up --build
   ```

4. Check the service at `http://127.0.0.1:8000/health`.
5. Open the web chat at `http://127.0.0.1:8000/chat`.

The API waits for PostgreSQL to become healthy, runs `app.init_db`, creates the tables and seeds the ten departments before Uvicorn starts.

## Stop the profile

```text
docker compose down
```

To remove the local PostgreSQL data volume as well, use `docker compose down -v` only when the stored demo data is no longer needed.

## Local SQLite fallback

The normal virtual-environment workflow is unchanged:

```text
.venv\Scripts\python.exe -m app.init_db
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The active database is reported by `/health` as either `sqlite` or `postgresql`.
