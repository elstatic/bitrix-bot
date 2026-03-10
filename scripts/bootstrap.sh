#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

say() {
  printf '%s\n' "$1"
}

check_cmd() {
  local cmd="$1"
  if command -v "${cmd}" >/dev/null 2>&1; then
    say "[ok] ${cmd}: $(command -v "${cmd}")"
    return 0
  fi

  say "[warn] ${cmd}: not found"
  return 1
}

say "Bitrix Bot bootstrap"
say "Repository: ${REPO_ROOT}"

missing_core=0
check_cmd python3 || missing_core=1

client_found=0
if check_cmd claude; then
  client_found=1
fi
if check_cmd codex; then
  client_found=1
fi

if [[ "${client_found}" -eq 0 ]]; then
  say "[warn] Neither claude nor codex was found. Install at least one client before using the skills."
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  say "[ok] Created .env from .env.example"
else
  say "[ok] .env already exists"
fi

if grep -q '^export BITRIX24_WEBHOOK_URL=' .env 2>/dev/null; then
  say "[ok] BITRIX24_WEBHOOK_URL already present in .env"
else
  say "[next] Open .env and set BITRIX24_WEBHOOK_URL"
fi

say "[info] PROJECTS_DIRS is optional; leave it empty if you do not need local git activity scans."
say "[info] Run ./scripts/doctor.sh after editing .env"

if [[ "${missing_core}" -ne 0 ]]; then
  exit 1
fi
