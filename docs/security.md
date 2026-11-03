# Security and deployment hardening

Task 23 adds baseline protections for the deployed application:

- `TrustedHostMiddleware` enforces the comma-separated `ALLOWED_HOSTS` list.
- Administrative dashboard and admin ticket APIs use HTTP Basic authentication when `ADMIN_PASSWORD` is configured.
- Production configuration rejects debug mode, the default secret key and an empty admin password.
- Responses include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and microphone `Permissions-Policy` headers.
- Oversized request bodies are rejected using `MAX_REQUEST_BODY_MB`; voice files retain their stricter `MAX_VOICE_UPLOAD_MB` limit.
- Pydantic request limits and SQLAlchemy parameterized queries remain active.

For deployment, set these values in the host environment or an untracked `.env` file:

```text
APP_ENV=production
DEBUG=false
SECRET_KEY=<long-random-secret>
ADMIN_USERNAME=<officer-username>
ADMIN_PASSWORD=<strong-password>
ALLOWED_HOSTS=<deployment-host>
CORS_ORIGINS=https://<frontend-host>
```

Never commit `.env`, database passwords, bot tokens or other credentials.
