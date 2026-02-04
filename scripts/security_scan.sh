#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks not found. Install it to run secret scanning."
  exit 1
fi

if ! command -v pip-audit >/dev/null 2>&1; then
  echo "pip-audit not found. Install it with: python -m pip install pip-audit"
  exit 1
fi

echo "[1/2] Running gitleaks..."
gitleaks detect --source . --no-banner --redact

echo "[2/2] Running pip-audit..."
pip-audit -r requirements.txt

echo "Security scan completed successfully."
