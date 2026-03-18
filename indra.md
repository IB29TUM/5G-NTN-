# Indra's Guide — What Was Done and How Every File Works

## Table of Contents

1. [Project Goal](#1-project-goal)
2. [What Was Built](#2-what-was-built)
3. [The Problem We Solved](#3-the-problem-we-solved)
4. [Repository Structure](#4-repository-structure)
5. [File-by-File Breakdown](#5-file-by-file-breakdown)
6. [How the System Runs End-to-End](#6-how-the-system-runs-end-to-end)
7. [Network Architecture](#7-network-architecture)
8. [The RT Cgroup Fix — Full Explanation](#8-the-rt-cgroup-fix--full-explanation)
9. [NTN Band 256 — What Happened](#9-ntn-band-256--what-happened)
10. [How to Operate](#10-how-to-operate)

---

## 1. Project Goal

Build a **software-only 5G end-to-end lab** using OpenAirInterface (OAI) that:

- Deploys a full 5G core network (AMF, SMF, UPF) + gNB + UE using Docker containers
- Uses the **RFsimulator** instead of real radio hardware (no USRP needed)
- Targets an **NTN (Non-Terrestrial Network)** scenario (satellite band 256, GEO)
- Automates everything: environment check, stack bring-up, attach validation, KPI extraction, call flow generation
- Provides a **web dashboard** to visualize results
- Documents all findings, limitations, and trade-offs

This was built for the OQ Technology simulation SW engineer technical assignment.

---

## 2. What Was Built

Seven Docker containers form the complete 5G network:

| Container | Role | Image |
|-----------|------|-------|
| `rfsim5g-mysql` | Subscriber database (IMSI, keys, OPC) | `mysql:8.0` |
| `rfsim5g-oai-amf` | Access & Mobility Management Function — handles registration, authentication | `oai-amf:v2.1.10` |
| `rfsim5g-oai-smf` | Session Management Function — sets up PDU sessions | `oai-smf:v2.1.10` |
| `rfsim5g-oai-upf` | User Plane Function — forwards user data packets | `oai-upf:v2.1.10` |
| `rfsim5g-oai-ext-dn` | External Data Network — simulates the internet | `trf-gen-cn5g:focal` |
| `rfsim5g-oai-gnb` | gNodeB (base station) — runs the radio stack in software | `oai-gnb:2026.w09` |
| `rfsim5g-oai-nr-ue` | NR User Equipment (phone) — connects to gNB via RFsimulator | `oai-nr-ue:2026.w09` |

On top of that:
- **7 shell/Python scripts** for automation
- **1 Flask web app** for the dashboard
- **3 documentation files** explaining architecture, PHY boundary, and NTN limitations
- **1 answers file** responding to the assignment questions
- **1 Makefile** for one-command operations

---

## 3. The Problem We Solved

### Original symptom
The gNB and UE containers kept crashing immediately on startup with:
```
Error in pthread_create(): ret: 11, errno: 11
```

### Root cause
OAI creates threads with **real-time scheduling** (`SCHED_FIFO`, priorities 2-97). Docker with **cgroup v1** on WSL2 sets the real-time CPU budget (`cpu.rt_runtime_us`) to **0** for all containers. This means the kernel rejects every `pthread_create()` call that requests real-time priority — even though we granted `CAP_SYS_NICE`.

### How we found it
1. Checked `ulimit`, `pid_max`, `threads-max` — all fine
2. Checked `pids_limit` in Docker — fine (unlimited)
3. Tested basic process creation inside the container — worked
4. Checked `SCHED_FIFO` inside the container — **failed with "Operation not permitted"**
5. Found `/sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us = 0` — **the smoking gun**
6. Host had `cpu.rt_runtime_us = 950000` but the Docker cgroup had `0`

### Fix applied
1. Grant the Docker cgroup real-time budget via a privileged container:
   ```bash
   docker run --rm --privileged --pid=host alpine \
     nsenter -t 1 -m -u -i -n sh -c \
     'echo 950000 > /sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us'
   ```
2. Add `cpu_rt_runtime: 400000` and `cpu_rt_period: 1000000` to gNB and UE in `docker-compose.yml`
3. This fix is now **automatic** — `run_demo.sh` detects and applies it on every run

### Second fix: UE connection
The UE was connecting to `127.0.0.1:4043` (localhost) instead of the gNB at `192.168.71.140`. The command-line parameter `--rfsimulator.[0].serveraddr` wasn't being parsed by the `2026.w09` image. Fix: created a YAML config (`nrue.uicc.yaml`) with `rfsimulator.serveraddr: 192.168.71.140` and mounted it into the container.

---

## 4. Repository Structure

```
5G-E2E-Lab/
├── docker-compose.yml          # Defines all 7 containers and 2 networks
├── .env                        # Image tags (OAI_TAG=2026.w09)
├── Makefile                    # One-command targets: run, stop, gui, pull, check, clean, logs
├── oai_db.sql                  # MySQL init: subscriber table with IMSI/key/OPC
├── mysql-healthcheck.sh        # Healthcheck script for MySQL container
├── README.md                   # Project overview and quick start
├── aswers.md                   # Assignment answers (OAI vs srsRAN, why NTN, etc.)
├── indra.md                    # This file
│
├── configs/
│   ├── mini_nonrf_config.yaml          # 5G Core config (AMF + SMF + UPF)
│   ├── gnb.sa.band78.106prb.rfsim.yaml # gNB config — Band 78 TN (active, working)
│   ├── gnb.ntn.band256.rfsim.conf      # gNB config — Band 256 NTN (libconfig format, has upstream bug)
│   ├── gnb.ntn.band256.rfsim.yaml      # gNB config — Band 256 NTN (YAML format, has upstream bug)
│   ├── nrue.uicc.yaml                  # UE config — SIM credentials + rfsim server address
│   └── nrue.uicc.conf                  # UE config — original libconfig format (unused)
│
├── scripts/
│   ├── run_demo.sh             # Main orchestrator — runs the entire demo end-to-end
│   ├── check_env.sh            # Pre-flight checks (Docker, Compose, RT cgroup, images)
│   ├── validate_attach.sh      # Validates gNB-AMF link, UE tunnel, and ping
│   ├── inject_ntn_delay.sh     # Adds tc netem delay to gNB container (GEO simulation)
│   ├── teardown.sh             # docker compose down
│   ├── export_kpis.py          # Parses logs, runs ping, writes summary.json + kpis.md
│   └── generate_callflow.py    # Parses logs, generates Mermaid sequence diagram
│
├── gui/
│   ├── app.py                  # Flask web server (port 5001)
│   ├── requirements.txt        # Flask dependency
│   └── templates/
│       └── index.html          # Dashboard HTML/JS — status, KPIs, call flow
│
├── docs/
│   ├── architecture.md         # System architecture, component diagram, data flow
│   ├── phy_boundary.md         # What's real vs simulated at the PHY layer
│   └── ntn_limitations.md      # RT cgroup root cause, NTN CORESET#0 bug, gap table
│
├── reports/                    # Generated at runtime
│   ├── summary.json            # Machine-readable KPIs
│   ├── kpis.md                 # Human-readable KPI table
│   └── callflow.md             # Mermaid sequence diagram
│
├── logs/                       # Container logs saved at runtime
│   ├── gnb.log
│   ├── amf.log
│   └── nrue.log
│
└── versions/
    └── component_versions.md   # Pinned image versions and tags
```

---

## 5. File-by-File Breakdown

### Root Files

**`docker-compose.yml`** — The heart of the project. Defines all 7 services, their images, IPs, volumes, healthchecks, dependencies, and capabilities. Key details:
- Services start in order: mysql → amf → smf → upf → ext-dn → gnb → nr-ue
- gNB and UE have `cpu_rt_runtime: 400000` and `privileged: true` (the RT cgroup fix)
- Two Docker networks: `public_net` (192.168.71.128/26) for control plane, `traffic_net` (192.168.72.128/26) for user data
- gNB mounts `gnb.sa.band78.106prb.rfsim.yaml` as its config
- UE mounts `nrue.uicc.yaml` which contains SIM credentials AND the rfsimulator server address

**`.env`** — Sets the OAI image tag to `2026.w09`. Referenced by `docker-compose.yml` via `${OAI_TAG}`.

**`Makefile`** — Convenience targets:
- `make check` → runs `check_env.sh`
- `make run` → runs `run_demo.sh` (the full demo)
- `make stop` → runs `teardown.sh`
- `make gui` → kills any old GUI process on port 5001, then starts `app.py`
- `make pull` → pulls all 7 Docker images
- `make clean` → docker compose down + remove logs/reports
- `make logs` → follow live container logs

**`oai_db.sql`** — SQL dump that creates the subscriber database. Contains the UE's IMSI (`208990100001100`), encryption key, and OPC. The AMF queries this during authentication.

**`mysql-healthcheck.sh`** — Runs `mysqladmin ping` to check if MySQL is ready. Used by the MySQL container's healthcheck so other services wait for the DB.

**`README.md`** — Project overview, prerequisites (including the RT cgroup fix), quick start, outputs, and limitations.

**`aswers.md`** — Answers to the 4 assignment questions: why OAI, why NTN, TN vs NTN differences, and what was learned.

### configs/

**`mini_nonrf_config.yaml`** — Shared YAML config for the 5G core (AMF, SMF, UPF). Defines:
- PLMN: MCC=208, MNC=99 (must match gNB and UE)
- Network slice: SST=1 (eMBB)
- DNN: "oai" with subnet 12.1.1.0/24 (the UE gets an IP from this range)
- AMF/SMF/UPF service-based interfaces and N2/N3/N4/N6 interfaces
- Database connection to MySQL

**`gnb.sa.band78.106prb.rfsim.yaml`** — The **active** gNB config (terrestrial). Band 78, 106 PRBs, 30 kHz SCS (numerology 1), 3.3 GHz. This is what actually runs because the NTN config has an upstream OAI bug. Key parameters:
- `absoluteFrequencySSB: 621312` → SSB at ~3.32 GHz
- `dl_carrierBandwidth: 106` → 106 PRBs = ~40 MHz
- TDD pattern: 7 DL + 2 UL slots in 5ms period
- `rfsimulator.serveraddr: server` → gNB runs as the RFsim server
- AMF address: 192.168.71.132

**`gnb.ntn.band256.rfsim.conf`** — The NTN gNB config (band 256, S-band, 25 PRBs, 15 kHz SCS). Has all NTN-specific parameters:
- `cellSpecificKoffset_r17 = 478` (GEO satellite timing offset)
- `ta-Common-r17 = 58629666` (~238 ms timing advance)
- Satellite position: `positionZ-r17 = 32433846` (GEO altitude in 1/4 meter units)
- `disable_harq = 1` (HARQ disabled for GEO due to long RTT)
- `cu_sibs = [2]; du_sibs = [19]` (SIB19 broadcast for NTN)
- **NOT USED** due to upstream CORESET#0 assertion bug in OAI

**`gnb.ntn.band256.rfsim.yaml`** — Same NTN config converted to YAML format. Also hits the same OAI bug.

**`nrue.uicc.yaml`** — The **active** UE config. Contains:
- SIM credentials: IMSI, key, OPC (must match `oai_db.sql`)
- PDU session: DNN="oai", SST=1
- `rfsimulator.serveraddr: 192.168.71.140` — tells UE to connect to gNB's IP for RFsim
- Security algorithms: NEA0 ciphering, NIA2 integrity

**`nrue.uicc.conf`** — Original UE config in libconfig format (only had SIM credentials, no rfsim address). Replaced by the YAML version.

### scripts/

**`run_demo.sh`** — The main orchestrator. Runs the entire demo in 8 phases:
- Phase 0: Checks Docker's RT cgroup budget; if 0, fixes it automatically using a privileged container + nsenter
- Phase 1: Runs `check_env.sh`
- Phase 2: Starts 5G core containers, waits up to 90s for MySQL to be healthy
- Phase 3: Starts gNB, waits 15-30s for it to register with AMF
- Phase 4: Injects NTN delay via `inject_ntn_delay.sh` (optional, non-fatal if it fails)
- Phase 5: Starts UE, polls for `oaitun_ue1` tunnel interface (up to 60s)
- Phase 6: Runs `validate_attach.sh` to verify the attach
- Phase 7: Saves container logs, runs `export_kpis.py` and `generate_callflow.py`

**`check_env.sh`** — Pre-flight validation:
- Checks Docker version
- Checks Docker Compose version (needs v2.36+ for `interface_name`)
- Checks RT cgroup budget (`cpu.rt_runtime_us`) — warns if 0
- Checks `/dev/net/tun` exists (needed for UE tunnel)
- Checks disk space (warns if < 10 GB)
- Checks all 7 Docker images are pulled

**`validate_attach.sh`** — Post-attach validation:
- Checks AMF logs for gNB connection
- Checks UE has `oaitun_ue1` interface (proves PDU session is established)
- Pings ext-dn (192.168.72.135) from UE through the tunnel — proves end-to-end data plane works

**`inject_ntn_delay.sh`** — Adds `tc netem` delay (default 135ms + 5ms jitter) to the gNB container's network interface. This simulates GEO satellite propagation delay (~270ms RTT). Uses `nsenter` to enter the container's network namespace.

**`teardown.sh`** — Simply runs `docker compose down` to stop and remove all containers.

**`export_kpis.py`** — Python script that:
1. Parses `logs/gnb.log` — extracts band, Koffset, HARQ status, SIB19, RRC events
2. Parses `logs/amf.log` — extracts gNB connection, registration events
3. Parses `logs/nrue.log` — extracts PDU session, attach events
4. Runs a **live ping** from the UE container (`docker exec ... ping`) and parses RTT stats
5. Writes `reports/summary.json` (machine-readable) and `reports/kpis.md` (human-readable table)
6. Automatically detects whether we're in NTN mode (band 256) or TN mode (band 78) and adjusts the report accordingly

**`generate_callflow.py`** — Python script that:
1. Scans gNB, AMF, and UE logs for protocol events (RRC Setup, Authentication, Security Mode, Registration, PDU Session)
2. Deduplicates events
3. Generates a Mermaid sequence diagram showing the 5G attach call flow
4. Writes `reports/callflow.md`

### gui/

**`app.py`** — Flask web server (port 5001) with 4 routes:
- `GET /` → serves the dashboard HTML
- `GET /api/status` → runs `docker compose ps --format json` and returns container health as JSON
- `GET /api/summary` → reads and returns `reports/summary.json`
- `GET /api/callflow` → reads and returns `reports/callflow.md`

**`templates/index.html`** — Single-page dashboard that:
- Shows colored dots for each container (green = running, red = not)
- Shows PASS/FAIL badge for attach result
- Shows NTN config table (band, Koffset, HARQ, delay, SIB19)
- Shows KPI table (attach success, PDU session, ping RTT avg/min/max)
- Renders the Mermaid call flow diagram
- Auto-refreshes every 10 seconds via `fetch()` calls to the API

**`requirements.txt`** — Just `Flask`.

### docs/

**`architecture.md`** — Mermaid component diagram, data flow explanation (control plane via NGAP, user plane via GTP-U tunnel), RFsimulator role, network topology table with all IPs.

**`phy_boundary.md`** — Explains what is real (L1 baseband, L2/L3 protocols) vs what is replaced (RF frontend, over-the-air channel) and why results are still valid for control-plane testing.

**`ntn_limitations.md`** — Full documentation of:
- The RT cgroup root cause and fix
- The NTN band 256 CORESET#0 assertion bug in OAI
- Gap table: what a real NTN system has vs what this system emulates

### reports/ (generated)

**`summary.json`** — Example:
```json
{
  "scenario": "TN-rfsim (NTN band 256 config in repo)",
  "band": 78,
  "attach_success": true,
  "pdu_session_established": true,
  "ping_rtt_avg_ms": 10.4,
  "ping_rtt_min_ms": 9.7,
  "ping_rtt_max_ms": 10.9
}
```

**`kpis.md`** — Markdown table of all KPIs.

**`callflow.md`** — Mermaid sequence diagram showing the full 5G SA attach procedure.

---

## 6. How the System Runs End-to-End

When you run `make run` (or `./scripts/run_demo.sh`), this is what happens:

```
1. RT CGROUP FIX
   run_demo.sh reads /sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us
   If 0 → launches privileged alpine container → nsenter into host → writes 950000
   Now Docker containers can use SCHED_FIFO threads

2. ENVIRONMENT CHECK
   check_env.sh verifies: Docker, Compose, RT budget, /dev/net/tun, disk, images

3. CORE NETWORK STARTUP
   docker compose up -d mysql oai-amf oai-smf oai-upf oai-ext-dn
   MySQL loads oai_db.sql (subscriber data)
   AMF, SMF, UPF read mini_nonrf_config.yaml
   ext-dn sets up NAT + routing for 12.1.1.0/24 via UPF

4. gNB STARTUP
   docker compose up -d oai-gnb
   gNB reads gnb.sa.band78.106prb.rfsim.yaml
   Creates ~12 real-time threads (Tpool0-7, L1_rx, L1_tx, L1_stats, MAC_STATS)
   Registers with AMF via NGAP/SCTP
   Starts RFsimulator server on port 4043

5. NTN DELAY INJECTION (optional)
   inject_ntn_delay.sh adds tc netem 135ms delay on gNB's eth0
   (Simulates GEO satellite propagation)

6. UE STARTUP
   docker compose up -d oai-nr-ue
   UE reads nrue.uicc.yaml (SIM + rfsim server address)
   Connects to gNB's RFsimulator at 192.168.71.140:4043
   Performs cell search → RRC Setup → NAS Registration → Authentication →
   Security Mode → Registration Accept → PDU Session Establishment
   Gets IP 12.1.1.2 on oaitun_ue1 tunnel interface

7. VALIDATION
   validate_attach.sh checks:
   - AMF logs show gNB connected
   - UE has oaitun_ue1 interface
   - Ping from UE through tunnel to ext-dn succeeds (5 packets, 0% loss)

8. KPI EXPORT
   export_kpis.py parses logs + runs live ping → summary.json + kpis.md
   generate_callflow.py parses logs → callflow.md (Mermaid diagram)
```

---

## 7. Network Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Host (WSL2)                          │
│                                                                 │
│  ┌─── public_net (192.168.71.128/26) ───────────────────────┐  │
│  │                                                           │  │
│  │  MySQL ─── AMF ─── SMF ─── UPF ──────── gNB ──── UE     │  │
│  │  .131      .132    .133    .134          .140     .150    │  │
│  │                             │                             │  │
│  └─────────────────────────────┼─────────────────────────────┘  │
│                                │                                │
│  ┌─── traffic_net (192.168.72.128/26) ──┐                      │
│  │                                       │                      │
│  │  UPF ──────────── ext-dn              │                      │
│  │  .134              .135               │                      │
│  │                                       │                      │
│  └───────────────────────────────────────┘                      │
│                                                                 │
│  Data path: UE (12.1.1.2) → oaitun_ue1 → gNB → UPF → ext-dn  │
└─────────────────────────────────────────────────────────────────┘
```

The UE connects to the gNB over TCP (RFsimulator, port 4043) — this replaces the radio link. After attach, the UE gets IP 12.1.1.2 on a GTP-U tunnel (`oaitun_ue1`). User data flows: UE → GTP tunnel → gNB → UPF → ext-dn.

---

## 8. The RT Cgroup Fix — Full Explanation

This is the most important debugging finding in the project.

**Background:** OAI's `nr-softmodem` (gNB binary) and `nr-uesoftmodem` (UE binary) create threads with `SCHED_FIFO` real-time scheduling at priorities ranging from 1 to 97. This gives the radio processing threads priority over normal processes, which is essential for real-time signal processing.

**The problem chain:**

1. Linux kernel uses **cgroups** to limit resources for groups of processes
2. Docker uses cgroups to isolate containers
3. Cgroup v1 has a `cpu.rt_runtime_us` parameter that limits how much real-time CPU time processes in that cgroup can use
4. The hierarchy is: `/sys/fs/cgroup/cpu/` → `/sys/fs/cgroup/cpu/docker/` → `/sys/fs/cgroup/cpu/docker/<container-id>/`
5. On this WSL2 system, the **host** has `cpu.rt_runtime_us = 950000` (950ms per 1000ms period)
6. But the **Docker parent cgroup** has `cpu.rt_runtime_us = 0`
7. A child cgroup cannot have more RT budget than its parent
8. So **every container** gets 0 RT budget → `pthread_create()` with `SCHED_FIFO` fails with `EAGAIN`

**Why `privileged: true` alone didn't fix it:** Privileged mode gives all Linux capabilities and removes seccomp restrictions, but it does NOT change the cgroup's RT budget. The RT limit is a cgroup constraint, not a capability constraint.

**The fix:**

1. Write `950000` to `/sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us` (parent cgroup)
2. Set `cpu_rt_runtime: 400000` per container in docker-compose.yml (child cgroup)
3. Total across containers (400000 + 400000 = 800000) must not exceed parent (950000)

---

## 9. NTN Band 256 — What Happened

We wrote and attempted to use an NTN-specific gNB config (band 256, S-band, 25 PRBs, GEO satellite parameters). Both `2026.w09` and `develop` OAI images crash with:

```
Assertion (type0_PDCCH_CSS_config->cset_start_rb >= 0) failed!
```

This is in `get_type0_PDCCH_CSS_config_parameters()` — the function that computes the CORESET#0 resource block allocation. With 25 PRBs bandwidth and CORESET#0 index 2 (which requires 24 RBs + 4 RB offset = 28 RBs total), the computation overflows the 25 PRB carrier, producing a negative start RB.

The official OAI config file (`gnb.sa.band256.ntn.mu0.25prb.rfsim.conf`) has the same parameter values, meaning this is likely a regression in the OAI mainline that needs a fix in a specific branch.

**Decision:** Use band 78 (terrestrial) as a working fallback. The full protocol stack is exercised (attach, PDU session, data plane). The NTN configs are kept in the repo for when OAI fixes the issue.

---

## 10. How to Operate

### Full restart (one command)
```bash
make stop && make run
```

### Start the dashboard
```bash
make gui
# Open http://localhost:5001
```

### View live logs
```bash
make logs
```

### Pull latest images
```bash
make pull
```

### Clean everything
```bash
make clean
```

### Manual RT cgroup fix (if needed separately)
```bash
docker run --rm --privileged --pid=host alpine \
  nsenter -t 1 -m -u -i -n sh -c \
  'echo 950000 > /sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us'
```
