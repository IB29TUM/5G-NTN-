#!/usr/bin/env bash
# OAI-NTN-ZeroRF: Stop all containers and clean temp state
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"
echo "Stopping OAI-NTN-ZeroRF stack..."
docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
echo "Done."
