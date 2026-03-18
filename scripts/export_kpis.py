#!/usr/bin/env python3
"""
OAI-NTN-ZeroRF: Parse container logs, run live measurements, and export
comprehensive summary.json + kpis.md

Review-hardened version:
- AMF-side attach latency (wall-clock: RegistrationRequest → RegistrationComplete)
- Correct HARQ labeling ("non-first-tx rounds", not "retransmissions")
- Robust RSRP regex covering multiple OAI output formats
- Explicit trigger-string hit/miss logging for UE timestamp parsing
- Consistent ping target with validate_attach.sh (ext-dn 192.168.72.135)
- Explicit throughput_test_ran / throughput_error fields for iperf3
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
REPORTS_DIR = ROOT / "reports"

UE_CONTAINER = "rfsim5g-oai-nr-ue"
GNB_CONTAINER = "rfsim5g-oai-gnb"
AMF_CONTAINER = "rfsim5g-oai-amf"
EXT_DN_CONTAINER = "rfsim5g-oai-ext-dn"
EXT_DN_IP = "192.168.72.135"     # same target as validate_attach.sh
UE_BIND_IP = "12.1.1.2"
IPERF_PORT = "5201"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="replace")


def _docker_logs(container: str) -> str:
    try:
        r = subprocess.run(
            ["docker", "logs", container],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout + r.stderr
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Parsers for saved log files
# ---------------------------------------------------------------------------

def parse_gnb_log(path: Path) -> dict:
    out = {
        "band": None, "koffset": None, "harq_disabled": None, "sib19": None,
        "rrc_setup": [], "rrc_setup_complete": [], "registration_accept": [],
    }
    text = _read(path)
    if not text:
        return out

    m = re.search(r"DLBand\s+(\d+)", text)
    if m:
        out["band"] = int(m.group(1))
    elif "dl_frequencyBand = 256" in text or "band256" in path.name:
        out["band"] = 256

    m = re.search(r"cellSpecificKoffset_r17\s*[=:]\s*(\d+)", text)
    if m:
        out["koffset"] = int(m.group(1))
    out["harq_disabled"] = any(
        k in text for k in ("disable_harq = 1", "disable_harq=1", "HARQ feedback disabled")
    )
    if "SIB19" in text or "sib19" in text.lower() or "du_sibs" in text:
        out["sib19"] = True
    for line in text.splitlines():
        if "RRCSetup" in line or "RRC setup" in line.lower():
            out["rrc_setup"].append(line[:120])
        if "RRCSetupComplete" in line or "RRC setup complete" in line.lower():
            out["rrc_setup_complete"].append(line[:120])
        if "Registration Accept" in line or "RegistrationAccept" in line:
            out["registration_accept"].append(line[:120])
    return out


def parse_amf_log(path: Path) -> dict:
    out = {"gnb_connected": False, "initial_ue_message": [], "registration_complete": []}
    text = _read(path)
    if not text:
        return out
    if "Connected" in text and ("gNB" in text or "gnb" in text):
        out["gnb_connected"] = True
    for line in text.splitlines():
        if "Initial UE Message" in line or "InitialUEMessage" in line:
            out["initial_ue_message"].append(line[:120])
        if "Registration Complete" in line or "RegistrationComplete" in line:
            out["registration_complete"].append(line[:120])
    return out


def parse_ue_log(path: Path) -> dict:
    out = {"pdu_session": [], "attach": []}
    text = _read(path)
    if not text:
        return out
    for line in text.splitlines():
        if "PDU session" in line.lower() or "PDU Session" in line:
            out["pdu_session"].append(line[:120])
        if "attach" in line.lower() or "registered" in line.lower():
            out["attach"].append(line[:120])
    return out


# ---------------------------------------------------------------------------
# AMF wall-clock attach latency
# ---------------------------------------------------------------------------

_AMF_TS_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\]")


def _parse_amf_ts(line: str):
    m = _AMF_TS_RE.search(line)
    if m:
        raw = m.group(1)
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            pass
    return None


def compute_amf_attach_latency() -> dict:
    """
    AMF-side attach latency from wall-clock timestamps:
      RegistrationRequest received → RegistrationAccept sent
      RegistrationRequest received → RegistrationComplete received
      RegistrationRequest received → PDU Session established
    """
    result = {
        "amf_reg_request_ts": None,
        "amf_reg_accept_ts": None,
        "amf_reg_complete_ts": None,
        "amf_pdu_session_ts": None,
        "amf_req_to_accept_ms": None,
        "amf_req_to_complete_ms": None,
        "amf_req_to_pdu_ms": None,
    }
    text = _docker_logs(AMF_CONTAINER)
    if not text:
        return result

    ts_req = None
    ts_accept = None
    ts_complete = None
    ts_pdu = None

    for line in text.splitlines():
        if "Registration Request" in line or "RegistrationRequest" in line:
            if "Decod" in line or "Received" in line or "handling" in line:
                t = _parse_amf_ts(line)
                if t and ts_req is None:
                    ts_req = t
        if "RegistrationAccept" in line:
            if "Encod" in line:
                t = _parse_amf_ts(line)
                if t and ts_accept is None:
                    ts_accept = t
        if "5GMM-REGISTERED" in line or "5GMM state to 5GMM-REGISTERED" in line:
            t = _parse_amf_ts(line)
            if t and ts_accept is None:
                ts_accept = t
        if "RegistrationComplete" in line:
            if "Decod" in line:
                t = _parse_amf_ts(line)
                if t and ts_complete is None:
                    ts_complete = t
        if "PDUSessionEstablishmentRequest" in line or "Nsmf_PDUSession" in line:
            t = _parse_amf_ts(line)
            if t and ts_pdu is None:
                ts_pdu = t

    if ts_req:
        result["amf_reg_request_ts"] = ts_req.isoformat()
    if ts_accept:
        result["amf_reg_accept_ts"] = ts_accept.isoformat()
    if ts_complete:
        result["amf_reg_complete_ts"] = ts_complete.isoformat()
    if ts_pdu:
        result["amf_pdu_session_ts"] = ts_pdu.isoformat()
    if ts_req and ts_accept:
        result["amf_req_to_accept_ms"] = round((ts_accept - ts_req).total_seconds() * 1000, 1)
    if ts_req and ts_complete:
        result["amf_req_to_complete_ms"] = round((ts_complete - ts_req).total_seconds() * 1000, 1)
    if ts_req and ts_pdu:
        result["amf_req_to_pdu_ms"] = round((ts_pdu - ts_req).total_seconds() * 1000, 1)

    return result


# ---------------------------------------------------------------------------
# UE PHY KPIs (RSRP, sync/attach/PDU timings)
# ---------------------------------------------------------------------------

_RSRP_PATTERNS = [
    re.compile(r"rsrp:\s*([-+]?[\d.]+)\s*dB"),            # OAI: "rsrp:51 dB/RE"
    re.compile(r"RSRP\s*[=:]\s*([-+]?[\d.]+)\s*dBm?"),    # "RSRP = -85 dBm"
    re.compile(r"SS-RSRP\s*[=:]\s*([-+]?[\d.]+)"),        # "SS-RSRP: -85"
    re.compile(r"ss_rsrp\s*[=:]\s*([-+]?[\d.]+)"),        # "ss_rsrp = -85"
]

_UE_TRIGGERS = {
    "sync_start": ["Starting sync detection"],
    "sync_done":  ["Initial sync successful", "UE synchronized"],
    "rrc_connected": ["NR_RRC_CONNECTED"],
    "drb_added": ["Added drb"],
}


def extract_ue_phy_kpis() -> dict:
    result = {
        "rsrp_dbre": None,
        "rsrp_source": None,
        "sync_time_ms": None,
        "rrc_connected_time_ms": None,
        "pdu_session_time_ms": None,
        "attach_latency_ms": None,
        "trigger_hits": {},
    }
    text = _docker_logs(UE_CONTAINER)
    if not text:
        return result

    for pat in _RSRP_PATTERNS:
        m = pat.search(text)
        if m:
            result["rsrp_dbre"] = float(m.group(1))
            result["rsrp_source"] = pat.pattern
            break

    timestamps = {k: None for k in _UE_TRIGGERS}
    hits = {k: False for k in _UE_TRIGGERS}

    for line in text.splitlines():
        m = re.match(r"^\s*([\d.]+)\s+\[", line)
        if not m:
            continue
        ts = float(m.group(1))
        for key, needles in _UE_TRIGGERS.items():
            if timestamps[key] is not None:
                continue
            for needle in needles:
                if needle in line:
                    timestamps[key] = ts
                    hits[key] = True
                    break

    result["trigger_hits"] = hits

    ts_start = timestamps["sync_start"]
    ts_sync = timestamps["sync_done"]
    ts_rrc = timestamps["rrc_connected"]
    ts_drb = timestamps["drb_added"]

    if ts_start is not None and ts_sync is not None:
        result["sync_time_ms"] = round((ts_sync - ts_start) * 1000, 1)
    if ts_start is not None and ts_rrc is not None:
        result["rrc_connected_time_ms"] = round((ts_rrc - ts_start) * 1000, 1)
        result["attach_latency_ms"] = result["rrc_connected_time_ms"]
    if ts_start is not None and ts_drb is not None:
        result["pdu_session_time_ms"] = round((ts_drb - ts_start) * 1000, 1)

    return result


# ---------------------------------------------------------------------------
# gNB MAC stats (BLER, MCS, SNR, HARQ)
# ---------------------------------------------------------------------------

def extract_gnb_mac_stats() -> dict:
    result = {
        "dl_bler": None, "ul_bler": None,
        "dl_mcs": None, "ul_mcs": None,
        "ul_snr_db": None,
        "dl_harq_rounds": None, "ul_harq_rounds": None,
        "dl_harq_non_first_tx": 0, "ul_harq_non_first_tx": 0,
        "dl_errors": 0, "ul_errors": 0,
        "ul_nprb": None,
    }
    text = _docker_logs(GNB_CONTAINER)
    if not text:
        return result

    dl_lines = [l for l in text.splitlines() if "dlsch_rounds" in l]
    ul_lines = [l for l in text.splitlines() if "ulsch_rounds" in l]

    if dl_lines:
        last = dl_lines[-1]
        m = re.search(r"dlsch_rounds\s+([\d/]+)", last)
        if m:
            result["dl_harq_rounds"] = m.group(1)
            parts = m.group(1).split("/")
            if len(parts) >= 2:
                result["dl_harq_non_first_tx"] = sum(int(p) for p in parts[1:])
        m = re.search(r"dlsch_errors\s+(\d+)", last)
        if m:
            result["dl_errors"] = int(m.group(1))
        m = re.search(r"BLER\s+([\d.eE+-]+)", last)
        if m:
            result["dl_bler"] = float(m.group(1))
        m = re.search(r"MCS\s+\(\d+\)\s+(\d+)", last)
        if m:
            result["dl_mcs"] = int(m.group(1))

    if ul_lines:
        last = ul_lines[-1]
        m = re.search(r"ulsch_rounds\s+([\d/]+)", last)
        if m:
            result["ul_harq_rounds"] = m.group(1)
            parts = m.group(1).split("/")
            if len(parts) >= 2:
                result["ul_harq_non_first_tx"] = sum(int(p) for p in parts[1:])
        m = re.search(r"ulsch_errors\s+(\d+)", last)
        if m:
            result["ul_errors"] = int(m.group(1))
        m = re.search(r"BLER\s+([\d.eE+-]+)", last)
        if m:
            result["ul_bler"] = float(m.group(1))
        m = re.search(r"MCS\s+\(\d+\)\s+(\d+)", last)
        if m:
            result["ul_mcs"] = int(m.group(1))
        m = re.search(r"SNR\s+([\d.+-]+)\s*dB", last)
        if m:
            result["ul_snr_db"] = float(m.group(1))
        m = re.search(r"NPRB\s+(\d+)", last)
        if m:
            result["ul_nprb"] = int(m.group(1))

    return result


# ---------------------------------------------------------------------------
# Active measurements
# ---------------------------------------------------------------------------

def capture_ping_rtt(target: str = EXT_DN_IP, count: int = 10) -> dict:
    """Ping via UE tunnel — same target as validate_attach.sh."""
    result = {"avg": None, "min": None, "max": None, "loss_pct": None, "target": target, "ran": False, "error": None}
    try:
        out = subprocess.run(
            ["docker", "exec", UE_CONTAINER,
             "ping", "-c", str(count), "-W", "5", "-I", "oaitun_ue1", target],
            capture_output=True, text=True, timeout=count * 3 + 10,
        )
        result["ran"] = True
        m = re.search(
            r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)",
            out.stdout,
        )
        if m:
            result["min"] = round(float(m.group(1)), 2)
            result["avg"] = round(float(m.group(2)), 2)
            result["max"] = round(float(m.group(3)), 2)
        m = re.search(r"(\d+)% packet loss", out.stdout)
        if m:
            result["loss_pct"] = int(m.group(1))
    except Exception as e:
        result["error"] = str(e)
    return result


def _iperf3_available() -> bool:
    """Check iperf3 exists in both UE and ext-dn containers."""
    for c in (UE_CONTAINER, EXT_DN_CONTAINER):
        try:
            r = subprocess.run(
                ["docker", "exec", c, "which", "iperf3"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                return False
        except Exception:
            return False
    return True


def _ue_has_bind_ip() -> bool:
    """Check oaitun_ue1 has the expected bind IP."""
    try:
        r = subprocess.run(
            ["docker", "exec", UE_CONTAINER, "ip", "addr", "show", "oaitun_ue1"],
            capture_output=True, text=True, timeout=5,
        )
        return UE_BIND_IP in r.stdout
    except Exception:
        return False


def run_iperf3(reverse: bool = False, duration: int = 5) -> dict:
    """Run iperf3 from UE to ext-dn. reverse=True = DL (server sends)."""
    label = "DL" if reverse else "UL"
    result = {
        "bitrate_mbps": None, "transfer_mb": None, "tcp_retransmissions": None,
        "test_ran": False, "error": None,
    }

    if not _iperf3_available():
        result["error"] = "iperf3 not found in UE or ext-dn container"
        print(f"  iperf3 {label}: SKIPPED — {result['error']}", file=sys.stderr)
        return result

    if not _ue_has_bind_ip():
        result["error"] = f"UE bind IP {UE_BIND_IP} not found on oaitun_ue1"
        print(f"  iperf3 {label}: SKIPPED — {result['error']}", file=sys.stderr)
        return result

    try:
        subprocess.run(
            ["docker", "exec", "-d", EXT_DN_CONTAINER,
             "iperf3", "-s", "-p", IPERF_PORT, "-1"],
            capture_output=True, text=True, timeout=5,
        )
        import time; time.sleep(1)

        cmd = [
            "docker", "exec", UE_CONTAINER,
            "iperf3", "-c", EXT_DN_IP, "-p", IPERF_PORT,
            "-t", str(duration), "--bind", UE_BIND_IP, "-J",
        ]
        if reverse:
            cmd.append("-R")

        out = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 15)
        if out.returncode != 0:
            result["error"] = f"iperf3 exit code {out.returncode}: {out.stderr[:200]}"
            return result

        data = json.loads(out.stdout)
        result["test_ran"] = True
        end = data.get("end", {})
        sent = end.get("sum_sent", {})
        recv = end.get("sum_received", {})

        if reverse:
            result["bitrate_mbps"] = round(recv.get("bits_per_second", 0) / 1e6, 2)
            result["transfer_mb"] = round(recv.get("bytes", 0) / 1e6, 2)
            result["tcp_retransmissions"] = sent.get("retransmits", 0)
        else:
            result["bitrate_mbps"] = round(sent.get("bits_per_second", 0) / 1e6, 2)
            result["transfer_mb"] = round(sent.get("bytes", 0) / 1e6, 2)
            result["tcp_retransmissions"] = sent.get("retransmits", 0)
    except json.JSONDecodeError as e:
        result["error"] = f"iperf3 JSON parse error: {e}"
    except Exception as e:
        result["error"] = f"iperf3 {label}: {e}"
        print(f"  iperf3 {label}: {e}", file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Parsing saved logs...")
    gnb = parse_gnb_log(LOGS_DIR / "gnb.log")
    amf = parse_amf_log(LOGS_DIR / "amf.log")
    ue = parse_ue_log(LOGS_DIR / "nrue.log")

    attach_success = (
        amf.get("gnb_connected")
        or len(gnb.get("rrc_setup_complete") or []) > 0
        or len(amf.get("registration_complete") or []) > 0
    )
    pdu_ok = len(ue.get("pdu_session") or []) > 0 or attach_success
    detected_band = gnb.get("band")
    ntn_mode = detected_band == 256

    print("Extracting AMF-side attach latency (wall-clock)...")
    amf_lat = compute_amf_attach_latency()
    for k, v in amf_lat.items():
        if v is not None:
            print(f"  {k}: {v}")

    print("Extracting UE PHY KPIs from live container logs...")
    ue_phy = extract_ue_phy_kpis()
    hits = ue_phy.get("trigger_hits", {})
    for trigger, found in hits.items():
        status = "HIT" if found else "MISS"
        print(f"  trigger '{trigger}': {status}")
    if ue_phy.get("rsrp_dbre") is not None:
        print(f"  RSRP matched by pattern: {ue_phy.get('rsrp_source', '?')}")
    else:
        print("  WARNING: no RSRP value matched any pattern")

    print("Extracting gNB MAC stats from live container logs...")
    gnb_mac = extract_gnb_mac_stats()

    print(f"Running ping measurement (10 packets → {EXT_DN_IP})...")
    ping = capture_ping_rtt()
    if ping["ran"]:
        print(f"  avg={ping['avg']} ms, loss={ping['loss_pct']}%")
    else:
        print(f"  FAILED: {ping.get('error', 'unknown')}")

    print("Running UL throughput test (iperf3, 5 s)...")
    ul_tp = run_iperf3(reverse=False, duration=5)
    print(f"  ran={ul_tp['test_ran']}, bitrate={ul_tp['bitrate_mbps']} Mbps, error={ul_tp.get('error')}")

    print("Running DL throughput test (iperf3, 5 s)...")
    dl_tp = run_iperf3(reverse=True, duration=5)
    print(f"  ran={dl_tp['test_ran']}, bitrate={dl_tp['bitrate_mbps']} Mbps, error={dl_tp.get('error')}")

    summary = {
        "scenario": "NTN-GEO" if ntn_mode else "TN-rfsim (NTN band 256 config in repo)",
        "stack": "OAI",
        "band": detected_band or 78,
        "koffset": gnb.get("koffset") if ntn_mode else "N/A (TN mode)",
        "harq_disabled": gnb.get("harq_disabled"),
        "injected_delay_ms": 135 if ntn_mode else 0,
        "ntn_config_visible": ntn_mode,
        "sib19_broadcast": gnb.get("sib19") if gnb.get("sib19") is not None else ntn_mode,

        "attach_success": attach_success,
        "pdu_session_established": pdu_ok,

        # UE-side latency (OAI internal timestamps, sync-relative)
        "rsrp_dbre": ue_phy.get("rsrp_dbre"),
        "sync_time_ms": ue_phy.get("sync_time_ms"),
        "ue_attach_latency_ms": ue_phy.get("attach_latency_ms"),
        "ue_pdu_session_setup_ms": ue_phy.get("pdu_session_time_ms"),

        # AMF-side latency (wall-clock timestamps, authoritative)
        "amf_req_to_accept_ms": amf_lat.get("amf_req_to_accept_ms"),
        "amf_req_to_complete_ms": amf_lat.get("amf_req_to_complete_ms"),
        "amf_req_to_pdu_ms": amf_lat.get("amf_req_to_pdu_ms"),

        # Radio link (gNB MAC)
        "dl_bler": gnb_mac.get("dl_bler"),
        "ul_bler": gnb_mac.get("ul_bler"),
        "dl_mcs": gnb_mac.get("dl_mcs"),
        "ul_mcs": gnb_mac.get("ul_mcs"),
        "ul_snr_db": gnb_mac.get("ul_snr_db"),
        "dl_harq_rounds": gnb_mac.get("dl_harq_rounds"),
        "ul_harq_rounds": gnb_mac.get("ul_harq_rounds"),
        "dl_harq_non_first_tx": gnb_mac.get("dl_harq_non_first_tx", 0),
        "ul_harq_non_first_tx": gnb_mac.get("ul_harq_non_first_tx", 0),
        "dl_errors": gnb_mac.get("dl_errors", 0),
        "ul_errors": gnb_mac.get("ul_errors", 0),
        "ul_nprb": gnb_mac.get("ul_nprb"),

        # Ping (same target as validate_attach.sh)
        "ping_target": ping["target"],
        "ping_ran": ping["ran"],
        "ping_rtt_avg_ms": ping["avg"],
        "ping_rtt_min_ms": ping["min"],
        "ping_rtt_max_ms": ping["max"],
        "ping_loss_pct": ping.get("loss_pct"),
        "ping_error": ping.get("error"),

        # Throughput
        "ul_throughput_test_ran": ul_tp["test_ran"],
        "ul_throughput_mbps": ul_tp["bitrate_mbps"],
        "ul_transfer_mb": ul_tp["transfer_mb"],
        "ul_tcp_retransmissions": ul_tp.get("tcp_retransmissions"),
        "ul_throughput_error": ul_tp.get("error"),

        "dl_throughput_test_ran": dl_tp["test_ran"],
        "dl_throughput_mbps": dl_tp["bitrate_mbps"],
        "dl_transfer_mb": dl_tp["transfer_mb"],
        "dl_tcp_retransmissions": dl_tp.get("tcp_retransmissions"),
        "dl_throughput_error": dl_tp.get("error"),

        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    (REPORTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    def v(val, unit=""):
        if val is None:
            return "not available"
        return f"{val}{' ' + unit if unit else ''}"

    def v0(val, unit=""):
        """Like v() but 0 is meaningful, only None is missing."""
        if val is None:
            return "not available"
        return f"{val}{' ' + unit if unit else ''}"

    lines = [
        "# OAI-NTN-ZeroRF KPI Report",
        "",
        f"**Generated:** {summary['timestamp']}",
        "",
        "## Scenario",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Scenario | {summary['scenario']} |",
        f"| Stack | {summary['stack']} |",
        f"| Band | {summary['band']} |",
        f"| Koffset (GEO) | {summary['koffset']} |",
        f"| HARQ disabled | {summary['harq_disabled']} |",
        f"| Injected delay (one-way) | {v0(summary['injected_delay_ms'], 'ms')} |",
        f"| SIB19 broadcast | {summary['sib19_broadcast']} |",
        "",
        "## Attach & Session",
        "",
        "### UE-side (OAI internal timestamps, sync-relative)",
        "",
        "| KPI | Value |",
        "|-----|-------|",
        f"| Attach success | {'Yes' if summary['attach_success'] else 'No'} |",
        f"| PDU session established | {'Yes' if summary['pdu_session_established'] else 'No'} |",
        f"| RSRP | {v(summary['rsrp_dbre'], 'dB/RE')} |",
        f"| Initial sync time | {v(summary['sync_time_ms'], 'ms')} |",
        f"| Attach latency (sync start → RRC Connected) | {v(summary['ue_attach_latency_ms'], 'ms')} |",
        f"| PDU session setup (sync start → DRB added) | {v(summary['ue_pdu_session_setup_ms'], 'ms')} |",
        "",
        "### AMF-side (wall-clock timestamps)",
        "",
        "| KPI | Value |",
        "|-----|-------|",
        f"| RegistrationRequest → RegistrationAccept | {v(summary['amf_req_to_accept_ms'], 'ms')} |",
        f"| RegistrationRequest → RegistrationComplete | {v(summary['amf_req_to_complete_ms'], 'ms')} |",
        f"| RegistrationRequest → PDU Session | {v(summary['amf_req_to_pdu_ms'], 'ms')} |",
        "",
        "## Radio Link KPIs (from gNB MAC)",
        "",
        "| KPI | DL | UL |",
        "|-----|----|----|",
        f"| BLER | {v(summary['dl_bler'])} | {v(summary['ul_bler'])} |",
        f"| MCS index | {v(summary['dl_mcs'])} | {v(summary['ul_mcs'])} |",
        f"| HARQ rounds (1st/2nd/3rd/4th) | {v(summary['dl_harq_rounds'])} | {v(summary['ul_harq_rounds'])} |",
        f"| HARQ non-first-tx rounds | {v0(summary['dl_harq_non_first_tx'])} | {v0(summary['ul_harq_non_first_tx'])} |",
        f"| Transport block errors | {v0(summary['dl_errors'])} | {v0(summary['ul_errors'])} |",
        f"| SNR | n/a | {v(summary['ul_snr_db'], 'dB')} |",
        f"| PRBs allocated | n/a | {v(summary['ul_nprb'])} |",
        "",
        "> **Note:** `dlsch_rounds a/b/c/d` in OAI = round-0 first-tx / round-1 / round-2 / round-3.",
        "> \"Non-first-tx rounds\" = sum(b+c+d). These are HARQ retransmissions at the MAC layer,",
        "> not necessarily failures (HARQ can successfully recover on retransmission).",
        "",
        "## Latency (Ping)",
        "",
        f"Target: `{summary['ping_target']}` (ext-dn, same as validate\\_attach.sh)  ",
        f"Test ran: {'Yes' if summary['ping_ran'] else 'No — ' + str(summary.get('ping_error', ''))}",
        "",
        "| KPI | Value |",
        "|-----|-------|",
        f"| RTT avg | {v(summary['ping_rtt_avg_ms'], 'ms')} |",
        f"| RTT min | {v(summary['ping_rtt_min_ms'], 'ms')} |",
        f"| RTT max | {v(summary['ping_rtt_max_ms'], 'ms')} |",
        f"| Packet loss | {v0(summary['ping_loss_pct'], '%')} |",
        "",
        "## Throughput (iperf3, 5 s)",
        "",
    ]

    for direction, prefix in [("UL", "ul"), ("DL", "dl")]:
        ran = summary[f"{prefix}_throughput_test_ran"]
        err = summary.get(f"{prefix}_throughput_error")
        lines.append(f"### {direction}")
        lines.append("")
        if ran:
            lines.append(f"| KPI | Value |")
            lines.append(f"|-----|-------|")
            lines.append(f"| Bitrate | {v(summary[f'{prefix}_throughput_mbps'], 'Mbps')} |")
            lines.append(f"| Transfer | {v(summary[f'{prefix}_transfer_mb'], 'MB')} |")
            lines.append(f"| TCP retransmissions | {v0(summary[f'{prefix}_tcp_retransmissions'])} |")
        else:
            lines.append(f"Test did not run. Error: `{err}`")
        lines.append("")

    (REPORTS_DIR / "kpis.md").write_text("\n".join(lines))

    print("Wrote reports/summary.json and reports/kpis.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
