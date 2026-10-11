#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/check-deployed-api.sh https://your-api.example" >&2
  exit 2
fi

BASE_URL="${1%/}"
if [[ ! "$BASE_URL" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?$ ]]; then
  echo "Expected an HTTPS API origin without a path, query, or credentials." >&2
  exit 2
fi

check_json() {
  local path="$1"
  local key="$2"
  local expected="$3"
  local response
  response="$(curl --fail --silent --show-error --location --max-time 20 "$BASE_URL$path")"
  CHECK_BODY="$response" python3 - "$key" "$expected" <<'PY'
import json
import os
import sys

try:
    body = json.loads(os.environ["CHECK_BODY"])
except (ValueError, TypeError) as exc:
    raise SystemExit(f"Invalid JSON response: {exc}")

if body.get(sys.argv[1]) != sys.argv[2]:
    raise SystemExit(f"Unexpected {sys.argv[1]!r} health status")
PY
  echo "OK $path"
}

check_json /health status ok
check_json /health/database database connected
echo "HTTPS and database health probes passed. Full upload/restart verification is still required."
