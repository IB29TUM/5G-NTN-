#!/usr/bin/env bash
# OAI-NTN-ZeroRF: One-command demo launcher
# Phases: check env -> core -> gNB -> inject delay -> UE -> validate -> export KPIs
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

COMPOSE_CMD="docker compose"
docker compose version &>/dev/null || COMPOSE_CMD="docker-compose"

echo "=== OAI-NTN-ZeroRF Demo ==="
echo "Scenario: NTN (GEO) | Stack: OAI"
echo ""

# Phase 0: Fix RT cgroup for WSL2/Docker cgroup v1
DOCKER_RT=$(cat /sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us 2>/dev/null || echo "N/A")
if [[ "$DOCKER_RT" == "0" ]]; then
  echo "[0/7] Fixing Docker RT cgroup budget (currently 0)..."
  docker run --rm --privileged --pid=host alpine \
    nsenter -t 1 -m -u -i -n sh -c \
    'echo 950000 > /sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us'
  echo "  RT budget set to 950000 us"
elif [[ "$DOCKER_RT" == "N/A" ]]; then
  echo "[0/7] RT cgroup check skipped (not cgroup v1)"
else
  echo "[0/7] Docker RT cgroup OK (${DOCKER_RT} us)"
fi

# Phase 1: Environment check
echo "[1/7] Checking environment..."
"$SCRIPT_DIR/check_env.sh"

# Phase 2: Start 5G Core
echo "[2/7] Starting 5G Core (mysql, amf, smf, upf, ext-dn)..."
$COMPOSE_CMD up -d mysql oai-amf oai-smf oai-upf oai-ext-dn
echo "Waiting for core to become healthy (up to 90s)..."
for i in $(seq 1 30); do
  if $COMPOSE_CMD ps mysql 2>/dev/null | grep -q "healthy"; then
    break
  fi
  sleep 3
done
sleep 5
$COMPOSE_CMD ps

# Phase 3: Start gNB
echo "[3/7] Starting gNB (NTN band 256)..."
$COMPOSE_CMD up -d oai-gnb
echo "Waiting for gNB to register with AMF (up to 30s)..."
sleep 15
if $COMPOSE_CMD logs oai-amf 2>/dev/null | tail -50 | grep -q "Connected\|connected"; then
  echo "gNB registered with AMF"
else
  echo "Waiting a bit more for gNB-AMF link..."
  sleep 15
fi

# Phase 4: Inject NTN delay
echo "[4/7] Injecting NTN propagation delay (GEO: 135ms one-way)..."
"$SCRIPT_DIR/inject_ntn_delay.sh" 135 5 || true

# Phase 5: Start UE
echo "[5/7] Starting NR-UE..."
$COMPOSE_CMD up -d oai-nr-ue
echo "Waiting for UE attach (up to 60s)..."
for i in $(seq 1 20); do
  if docker exec rfsim5g-oai-nr-ue ip link show oaitun_ue1 &>/dev/null 2>&1; then
    echo "UE tunnel up after ${i}*3s"
    break
  fi
  sleep 3
done
sleep 5

# Phase 6: Validate
echo "[6/7] Validating attach..."
"$SCRIPT_DIR/validate_attach.sh" || true

# Phase 7: Collect logs and generate reports
echo "[7/7] Collecting logs and generating reports..."
mkdir -p logs reports
$COMPOSE_CMD logs oai-gnb    > logs/gnb.log   2>/dev/null || true
$COMPOSE_CMD logs oai-amf    > logs/amf.log   2>/dev/null || true
$COMPOSE_CMD logs oai-nr-ue  > logs/nrue.log 2>/dev/null || true

if [ -f "$SCRIPT_DIR/export_kpis.py" ]; then
  python3 "$SCRIPT_DIR/export_kpis.py" || echo "KPI export failed (non-fatal)"
fi
if [ -f "$SCRIPT_DIR/generate_callflow.py" ]; then
  python3 "$SCRIPT_DIR/generate_callflow.py" || echo "Callflow generation failed (non-fatal)"
fi

echo ""
echo "Demo run complete. Reports in reports/. Start GUI with: make gui"
