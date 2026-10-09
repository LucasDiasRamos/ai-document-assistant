#!/usr/bin/env bash
set -euo pipefail

# Local smoke test; requires Docker Compose v2 and Python 3.
docker compose up --build --wait -d

python3 - <<'PY'
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:8000/health", timeout=10) as response:
    assert json.load(response) == {"status": "ok"}

with urlopen("http://127.0.0.1:8000/health/database", timeout=10) as response:
    assert json.load(response) == {"status": "ok", "database": "connected"}
PY

docker compose restart postgres api
docker compose up --wait -d
docker compose exec -T postgres sh -c 'test -d /var/lib/postgresql/data'
docker compose exec -T api sh -c 'test -d /app/storage'
echo "Compose API + database smoke check passed."
