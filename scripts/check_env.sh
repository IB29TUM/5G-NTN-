#!/usr/bin/env bash
# OAI-NTN-ZeroRF: Pre-flight environment check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

fail() { echo -e "${RED}FAIL: $*${NC}"; exit 1; }
ok()   { echo -e "${GREEN}OK: $*${NC}"; }
warn() { echo -e "${YELLOW}WARN: $*${NC}"; }

echo "=== OAI-NTN-ZeroRF Environment Check ==="

# Docker
if ! command -v docker &>/dev/null; then
  fail "Docker not found. Install Docker CE >= 22.0.5"
fi
DOCKER_VER=$(docker version --format '{{.Server.Version}}' 2>/dev/null || docker version -f '{{.Server.Version}}' 2>/dev/null || echo "0")
if [[ "$DOCKER_VER" == "0" ]]; then
  DOCKER_VER=$(docker version 2>/dev/null | grep -oP 'Version:\s*\K[0-9.]+' | head -1 || echo "0")
fi
ok "Docker found (version: ${DOCKER_VER})"

# Docker Compose v2
if ! docker compose version &>/dev/null; then
  if docker-compose version &>/dev/null; then
    COMPOSE_VER=$(docker-compose version --short 2>/dev/null || echo "unknown")
    warn "Using docker-compose (legacy). For interface_name support, use 'docker compose' v2.36+"
  else
    fail "Docker Compose not found. Need docker compose v2.36.0 or later."
  fi
else
  COMPOSE_VER=$(docker compose version --short 2>/dev/null || echo "unknown")
  ok "Docker Compose found (version: ${COMPOSE_VER})"
fi

# RT scheduling cgroup check (critical for OAI on WSL2/Docker cgroup v1)
DOCKER_RT=$(cat /sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us 2>/dev/null || echo "N/A")
if [[ "$DOCKER_RT" == "0" ]]; then
  warn "Docker cgroup cpu.rt_runtime_us is 0 — OAI gNB/UE will crash on pthread_create."
  warn "Fix: docker run --rm --privileged --pid=host alpine nsenter -t 1 -m -u -i -n sh -c 'echo 950000 > /sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us'"
elif [[ "$DOCKER_RT" == "N/A" ]]; then
  ok "RT cgroup check skipped (not cgroup v1 or path not found)"
else
  ok "Docker cgroup RT budget: ${DOCKER_RT} us"
fi

# /dev/net/tun for UE tunnel
if [[ ! -c /dev/net/tun ]]; then
  warn "/dev/net/tun not found. UE tunnel may fail. On WSL2, it is usually present."
else
  ok "/dev/net/tun exists"
fi

# Disk space (optional check)
if command -v df &>/dev/null; then
  AVAIL_GB=$(df -BG "$ROOT_DIR" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
  if [[ -n "${AVAIL_GB:-}" && "${AVAIL_GB:-0}" -lt 10 ]]; then
    warn "Low disk space: ${AVAIL_GB}GB. Recommend at least 10GB."
  else
    ok "Disk space sufficient"
  fi
fi

# Required images (presence check via docker images)
OAI_TAG="${OAI_TAG:-2026.w09}"
IMAGES=(
  "mysql:8.0"
  "oaisoftwarealliance/oai-amf:v2.1.10"
  "oaisoftwarealliance/oai-smf:v2.1.10"
  "oaisoftwarealliance/oai-upf:v2.1.10"
  "oaisoftwarealliance/oai-gnb:${OAI_TAG}"
  "oaisoftwarealliance/oai-nr-ue:${OAI_TAG}"
  "oaisoftwarealliance/trf-gen-cn5g:focal"
)
MISSING=()
for img in "${IMAGES[@]}"; do
  if ! docker image inspect "$img" &>/dev/null; then
    MISSING+=("$img")
  fi
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo ""
  warn "Missing images (run 'make pull' or pull manually):"
  printf '  - %s\n' "${MISSING[@]}"
  echo "  Pull with: docker pull <image>"
  exit 1
fi
ok "All required Docker images present"

echo ""
echo "Environment check passed."
