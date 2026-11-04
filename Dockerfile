FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-optional.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt -r requirements-optional.txt

COPY app ./app
COPY ml ./ml

EXPOSE 8000

CMD ["sh", "-c", "python -m app.init_db && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
