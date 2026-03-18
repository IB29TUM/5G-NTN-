#!/usr/bin/env bash
# OAI-NTN-ZeroRF: Validate UE registration and PDU session
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
UE_CONTAINER="${UE_CONTAINER_NAME:-rfsim5g-oai-nr-ue}"
EXT_DN_IP="${EXT_DN_IP:-192.168.72.135}"
PING_COUNT=5

cd "$ROOT_DIR"

# 1. Check gNB is connected to AMF
if docker compose logs oai-amf 2>/dev/null | tail -100 | grep -q "Connected.*gnb\|gNB.*Connected"; then
  echo "AMF: gNB connected"
else
  echo "AMF: gNB connection not seen in recent logs (may still be ok)"
fi

# 2. Check UE has tunnel interface
if docker exec "$UE_CONTAINER" ip link show oaitun_ue1 &>/dev/null; then
  echo "UE: oaitun_ue1 interface present"
else
  echo "FAIL: UE tunnel interface oaitun_ue1 not found"
  exit 1
fi

# 3. Ping ext-dn via tunnel
echo "Pinging ext-dn ($EXT_DN_IP) via UE tunnel..."
if docker exec "$UE_CONTAINER" ping -I oaitun_ue1 -c "$PING_COUNT" -W 10 "$EXT_DN_IP" 2>/dev/null; then
  echo "PASS: UE attach and data path validated"
else
  echo "FAIL: Ping via oaitun_ue1 failed"
  exit 1
fi
