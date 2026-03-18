#!/usr/bin/env bash
# OAI-NTN-ZeroRF: Inject GEO-equivalent one-way delay on gNB container network
# Usage: inject_ntn_delay.sh [delay_ms] [jitter_ms]
# Default: 135ms delay, 5ms jitter (~270ms RTT for GEO)
set -euo pipefail

DELAY_MS="${1:-135}"
JITTER_MS="${2:-5}"
CONTAINER="${CONTAINER_NAME:-rfsim5g-oai-gnb}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "WARN: Container $CONTAINER not running. Skip delay injection."
  exit 0
fi

GNB_PID=$(docker inspect -f '{{.State.Pid}}' "$CONTAINER" 2>/dev/null) || true
if [ -z "${GNB_PID:-}" ]; then
  echo "WARN: Could not get PID for $CONTAINER. Skip delay injection."
  exit 0
fi

# Check if tc already applied (idempotent: replace if exists)
if nsenter -t "$GNB_PID" -n tc qdisc show dev eth0 2>/dev/null | grep -q netem; then
  echo "NTN delay already applied on $CONTAINER (eth0)."
  exit 0
fi

if ! nsenter -t "$GNB_PID" -n tc qdisc add dev eth0 root netem delay "${DELAY_MS}ms" "${JITTER_MS}ms" 2>/dev/null; then
  echo "WARN: Could not apply tc netem (need NET_ADMIN or run from host with nsenter). Skip."
  exit 0
fi

echo "Applied NTN delay: ${DELAY_MS}ms + ${JITTER_MS}ms jitter on $CONTAINER (eth0)."
nsenter -t "$GNB_PID" -n tc qdisc show dev eth0 2>/dev/null || true
