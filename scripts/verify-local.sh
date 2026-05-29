#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PYTHON="${BACKEND_PYTHON:-$ROOT_DIR/backend/.venv/bin/python}"
PYTEST_TIMEOUT="${PYTEST_TIMEOUT:-60s}"

BACKEND_TESTS=(
  "backend/tests/test_auth.py"
  "backend/tests/test_health.py"
  "backend/tests/test_cache.py"
  "backend/tests/test_rate_limit.py"
  "backend/tests/test_datasource_engine_factory.py"
  "backend/tests/test_query_executor.py"
  "backend/tests/test_sql_pagination.py"
  "backend/tests/test_semantic_metrics_api.py"
  "backend/tests/test_query_service.py"
  "backend/tests/test_nl2sql.py"
  "backend/tests/test_ai_analyst_semantic_metrics.py"
  "backend/tests/test_rca_semantic_metrics.py"
  "backend/tests/test_subscription_semantic_metrics.py"
  "backend/tests/test_subscription.py::TestSubscriptionService"
  "backend/tests/test_subscription.py::TestSubscriptionTask"
)

run_step() {
  local label="$1"
  shift
  printf "\n==> %s\n" "$label"
  "$@"
}

run_frontend() {
  run_step "frontend lint" npm --prefix "$ROOT_DIR/frontend" run lint
  run_step "frontend typecheck" npm --prefix "$ROOT_DIR/frontend" run typecheck
  run_step "frontend build" npm --prefix "$ROOT_DIR/frontend" run build
}

run_backend() {
  if [[ ! -x "$BACKEND_PYTHON" ]]; then
    printf "Backend Python not found or not executable: %s\n" "$BACKEND_PYTHON" >&2
    exit 1
  fi

  if command -v timeout >/dev/null 2>&1; then
    run_step "backend regression" timeout "$PYTEST_TIMEOUT" "$BACKEND_PYTHON" -m pytest "${BACKEND_TESTS[@]}" -q
  else
    run_step "backend regression" "$BACKEND_PYTHON" -m pytest "${BACKEND_TESTS[@]}" -q
  fi
}

main() {
  cd "$ROOT_DIR"

  if [[ "${SKIP_FRONTEND:-0}" != "1" ]]; then
    run_frontend
  fi

  if [[ "${SKIP_BACKEND:-0}" != "1" ]]; then
    run_backend
  fi

  printf "\nAll local verification checks passed.\n"
}

main "$@"
