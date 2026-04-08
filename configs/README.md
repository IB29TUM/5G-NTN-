# Config files

This folder contains all configuration files used by the OAI-NTN-ZeroRF demo. Here is how each one was obtained or created.

---

## 5G Core (AMF, SMF, UPF)

| File | Origin |
|------|--------|
| **mini_nonrf_config.yaml** | Derived from OAI’s “mini” 5GC non-RF setup used in their tutorials (e.g. [OAI 5G SA with RFsimulator](https://gitlab.eurecom.fr/oai/openairinterface5g/-/tree/develop/doc/tutorials)). Adapted for this project: same PLMN (208/99), DNN `oai`, and NF hostnames/ports; IPs and bindings aligned with our `docker-compose.yml` (AMF 192.168.71.132, SMF, UPF, etc.). One file is shared by AMF, SMF, and UPF. |

---

## gNB (RAN)

| File | Origin |
|------|--------|
| **gnb.sa.band78.106prb.rfsim.yaml** | Based on OAI’s Band 78 (n78) RFsimulator gNB configs. Used as the **active demo config** because Band 256 hits the CORESET#0 bug. Parameters (106 PRBs, 30 kHz SCS, PLMN 208/99, AMF IP 192.168.71.132, gNB IP 192.168.71.140) aligned with our network and core. |
| **gnb.ntn.band256.rfsim.conf** | Our NTN Band 256 config in **libconfig** format. Built from OAI’s NTN reference (`gnb.sa.band256.ntn.mu0.25prb.rfsim.conf`); same radio params (25 PRBs, band 256, Koffset 478, SIB19, HARQ disabled). AMF/gNB IPs set to 192.168.71.132 / 192.168.71.140. Kept for reference; **not used** in the demo because the gNB crashes (see `docs/oai_ntn_band256_bug_report.md`). |
| **gnb.ntn.band256.rfsim.yaml** | **YAML version** of `gnb.ntn.band256.rfsim.conf`, same content and purpose. |
| **oai_official_ntn_band256.conf** | **Downloaded from OAI GitLab** (develop branch): `targets/PROJECTS/GENERIC-NR-5GC/CONF/gnb.sa.band256.ntn.mu0.25prb.rfsim.conf`. Stored here under a fixed name for the bug report and repro. Unchanged from upstream except for the filename. |

---

## NR-UE

| File | Origin |
|------|--------|
| **nrue.uicc.conf** | Original UE config in **libconfig** format. Contains the **SIM credentials** (IMSI 208990100001100, key, OPc) that match the MySQL `users` table in `oai_db.sql` — these come from OAI’s standard RFsimulator/5G SA tutorial (same test subscriber set). No RFsimulator server address; that caused the UE to try 127.0.0.1. |
| **nrue.uicc.yaml** | **YAML version** used by the demo. Same SIM data as `nrue.uicc.conf`, plus a **`rfsimulator`** section with `serveraddr: 192.168.71.140` (gNB IP) so the UE connects to the gNB’s RFsimulator. The OAI 2026.w09 image did not reliably take the RFsim server from the command line, so the YAML file is mounted and supplies the address. |

---

## Summary

- **From OAI upstream (tutorials / GitLab):** core “mini” non-RF layout, Band 78 RFsim gNB layout, NTN Band 256 reference config, test subscriber credentials (IMSI/key/OPc) and `oai_db.sql`.
- **Project-specific:** single `mini_nonrf_config.yaml` with our IPs and topology; Band 78 gNB YAML aligned with docker-compose; UE YAML with SIM + `rfsimulator.serveraddr`; NTN Band 256 .conf/.yaml with our IPs; local copy of OAI’s NTN config as `oai_official_ntn_band256.conf`.

All IPs (192.168.71.x, 192.168.72.x) and PLMN (208/99) are consistent across configs, `docker-compose.yml`, and `oai_db.sql`.
