#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

pass_count=0
warn_count=0
fail_count=0

pass() {
  pass_count=$((pass_count + 1))
  printf '[ok] %s\n' "$1"
}

warn() {
  warn_count=$((warn_count + 1))
  printf '[warn] %s\n' "$1"
}

fail() {
  fail_count=$((fail_count + 1))
  printf '[fail] %s\n' "$1"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

load_env() {
  if [[ ! -f .env ]]; then
    return 1
  fi

  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  return 0
}

printf 'Bitrix Bot doctor\n'
printf 'Repository: %s\n' "${REPO_ROOT}"

if has_cmd python3; then
  pass "python3 is installed"
else
  fail "python3 is missing"
fi

if has_cmd claude; then
  pass "claude is installed"
else
  warn "claude is not installed"
fi

if has_cmd codex; then
  pass "codex is installed"
else
  warn "codex is not installed"
fi

if [[ -f .env ]]; then
  pass ".env exists"
else
  fail ".env is missing. Run ./scripts/bootstrap.sh first"
fi

if load_env; then
  if [[ -n "${BITRIX24_WEBHOOK_URL:-}" ]] && [[ "${BITRIX24_WEBHOOK_URL}" != *"your-domain.bitrix24.ru"* ]]; then
    pass "BITRIX24_WEBHOOK_URL is configured"
  else
    fail "BITRIX24_WEBHOOK_URL is missing or still uses the example value"
  fi

  if [[ -n "${PROJECTS_DIRS:-}" ]]; then
    pass "PROJECTS_DIRS is configured"
  else
    warn "PROJECTS_DIRS is not set; local project activity scans will be skipped"
  fi
else
  fail "Could not load .env"
fi

if [[ -n "${BITRIX24_WEBHOOK_URL:-}" ]] && has_cmd python3; then
  if profile_output="$(python3 .claude/scripts/bitrix_call.py profile 2>&1)"; then
    if printf '%s' "${profile_output}" | python3 -c 'import json, sys; data = json.load(sys.stdin); user = data.get("result", data); sys.exit(0 if user.get("NAME") else 1)' >/dev/null 2>&1; then
      profile_name="$(printf '%s' "${profile_output}" | python3 -c 'import json, sys; data = json.load(sys.stdin); user = data.get("result", data); print(" ".join(part for part in [user.get("NAME", ""), user.get("LAST_NAME", "")] if part).strip())')"
      pass "Bitrix webhook works${profile_name:+ for ${profile_name}}"
    else
      fail "Bitrix webhook returned unexpected profile data"
    fi
  else
    fail "Bitrix webhook check failed: ${profile_output}"
  fi
fi

if [[ -f requirements-google-workspace.txt ]]; then
  if python3 - <<'PY' >/dev/null 2>&1
import importlib
mods = [
    "googleapiclient.discovery",
    "google.oauth2.credentials",
    "google_auth_oauthlib.flow",
]
for mod in mods:
    importlib.import_module(mod)
PY
  then
    pass "Google Workspace Python dependencies are installed"
  else
    warn "Google Workspace dependencies are missing; install with: pip3 install -r requirements-google-workspace.txt"
  fi
fi

oauth_path="${GOOGLE_OAUTH_CLIENT_PATH:-.claude/google-oauth-client.json}"
if [[ -f "${oauth_path}" ]]; then
  pass "Google OAuth client file exists at ${oauth_path}"
else
  warn "Google OAuth client file not found at ${oauth_path}"
fi

printf '\nSummary: %s ok, %s warnings, %s failures\n' "${pass_count}" "${warn_count}" "${fail_count}"

if [[ "${fail_count}" -ne 0 ]]; then
  exit 1
fi
