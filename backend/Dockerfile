FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Apply migrations before accepting API requests.
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
RUN mkdir -p /app/storage

EXPOSE 8000

# Platform runtime supplies PORT (Render: 10000); local Compose defaults to 8000.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
