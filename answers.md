# Assignment Answers (answers.md)

## 1. Why did you choose OAI vs srsRAN?

**Balanced comparison**

- **OAI** was chosen for this project because it provides a **full open path** without RF hardware: the same codebase delivers both the **gNB** and the **NR-UE**, and the **RFsimulator** replaces the RF frontend with a TCP-based IQ exchange. That allows a single-vendor, single-repo stack (RAN + UE) and straightforward automation (one docker-compose, one config set).
- **srsRAN** offers a cleaner build, modular C++ design, and strong ZMQ-based RF abstraction; its 5G NTN tutorials and documentation have improved. For a **UE + gNB** software-only demo, however, OAI gives an integrated UE (nr-uesoftmodem) out of the box, whereas with srsRAN we would rely on their gNB and a separate UE implementation or emulator.
- **Trade-offs**: OAI’s NTN support (band 256, SIB19, Koffset) is present but still evolving and can be fragile. We do **not** claim OAI is “better” at NTN than srsRAN; the choice is justified by **full-stack control and RF abstraction** for this specific zero-RF validation task, with limitations clearly documented.

---

## 2. Why did you choose NTN for the demo?

- **Domain alignment**: The assignment is from **OQ Technology**, which focuses on satellite/NTN. Choosing NTN demonstrates relevance to their domain.
- **Feasibility vs risk**: NTN in OAI is feasible in software (band 256, GEO Koffset, extended timers, RFsimulator), but less mature than TN. We accepted the risk and documented fallbacks (e.g. TN baseline if NTN attach fails).
- **What we demonstrate**: NTN-specific configuration (SIB19, Koffset, HARQ disabled, optional delay injection), control-plane correctness under NTN constraints, and honest documentation of what is real vs emulated. This is more valuable for the role than a TN-only demo.

---

## 3. What are the key differences and challenges between TN and NTN setups?

| Aspect | TN | NTN (e.g. GEO/LEO) |
|--------|----|----------------------|
| **Propagation delay** | ~1 ms or less | GEO ~270 ms RTT; LEO variable |
| **Doppler** | Negligible for fixed/mobile terrestrial | LEO: up to tens of kHz at Ka-band; GEO near zero |
| **Timing advance / Koffset** | Small TA values | Large Koffset (e.g. 478 for GEO); TA common and UE-specific |
| **HARQ** | Usable with short RTT | Often disabled or adapted for GEO |
| **Synchronization** | Standard cell sync | Ephemeris-based (e.g. SIB19), cell stop time |
| **Handover / mobility** | Cell reselection, handover between gNBs | Satellite handover, beam handover, cell reselection |
| **Beam management** | Typically single or few beams per cell | Critical for LEO; beam tracking and handover |

Challenges in NTN include: long RTT breaking legacy HARQ assumptions, Doppler compensation in the UE/gNB, timing alignment (Koffset, TA), and handover under moving satellites.

---

## 4. What did you learn during this hands-on?

- **Integration reality**: Getting OAI core, gNB, and UE to work together with the right config (PLMN, AMF address, UE credentials, DNN) requires careful alignment of config files and DB entries. Small mismatches cause silent failures.
- **NTN stack maturity**: OAI’s NTN (band 256, SIB19, Koffset) is implemented but not always stable across versions. Relying on a single “develop” tag is risky; pinning to a weekly tag and documenting the exact version is important.
- **Observability**: Log parsing for KPIs and call flow is brittle (log formats change). Designing for “unavailable” or fallback values instead of hard failures makes the pipeline more robust.
- **Abstraction honesty**: Clearly separating what is real NTN behaviour (config, scheduling) from what is emulated (delay, no Doppler) makes the project credible and extensible for future NTN work.
