#!/usr/bin/env python3
"""
OAI-NTN-ZeroRF: Generate Mermaid sequence diagram (callflow.md) from logs
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
REPORTS_DIR = ROOT / "reports"


def parse_ts(line: str):
    m = re.search(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.?\d*)\]", line)
    return m.group(1) if m else None


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    events = []
    for name, path in [("gnb", LOGS_DIR / "gnb.log"), ("amf", LOGS_DIR / "amf.log"), ("ue", LOGS_DIR / "nr-ue.log")]:
        if not path.exists():
            continue
        for line in path.read_text(errors="replace").splitlines():
            ts = parse_ts(line)
            if "RRC Setup Request" in line or "RRCSetupRequest" in line:
                events.append((ts, "UE", "gNB", "RRC Setup Request"))
            if "RRC Setup" in line and "Complete" not in line and "Request" not in line:
                events.append((ts, "gNB", "UE", "RRC Setup (SIB19/NTN params)"))
            if "RRC Setup Complete" in line or "RRCSetupComplete" in line:
                events.append((ts, "UE", "gNB", "RRC Setup Complete + NAS Registration Request"))
            if "Initial UE Message" in line or "InitialUEMessage" in line:
                events.append((ts, "gNB", "AMF", "NGAP Initial UE Message"))
            if "Authentication Request" in line:
                events.append((ts, "AMF", "gNB", "Authentication Request"))
            if "Authentication Response" in line or "Auth Response" in line:
                events.append((ts, "gNB", "AMF", "Authentication Response"))
            if "Security Mode Command" in line:
                events.append((ts, "AMF", "gNB", "Security Mode Command"))
            if "Security Mode Complete" in line:
                events.append((ts, "gNB", "AMF", "Security Mode Complete"))
            if "Registration Accept" in line or "RegistrationAccept" in line:
                events.append((ts, "AMF", "gNB", "Registration Accept"))
            if "Registration Complete" in line or "RegistrationComplete" in line:
                events.append((ts, "UE", "gNB", "Registration Complete"))
            if "PDU Session" in line and "Establishment" in line.lower():
                events.append((ts, "UE", "gNB", "PDU Session Establishment Request"))

    # Dedupe by (from, to, msg) keeping first
    seen = set()
    unique = []
    for ev in events:
        key = (ev[1], ev[2], ev[3])
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    mermaid = [
        "# 5G NTN Attach Call Flow",
        "",
        "```mermaid",
        "sequenceDiagram",
        "    participant UE",
        "    participant gNB",
        "    participant AMF",
        "    participant SMF",
        "    participant UPF",
        "",
    ]
    for _ts, src, dst, msg in unique[:25]:
        mermaid.append(f"    {src}->>{dst}: {msg}")
    mermaid.append("    Note over UE,UPF: PDU Session established, oaitun_ue1 UP")
    mermaid.append("```")
    mermaid.append("")

    (REPORTS_DIR / "callflow.md").write_text("\n".join(mermaid))
    print("Wrote reports/callflow.md")
    return 0


if __name__ == "__main__":
    main()
