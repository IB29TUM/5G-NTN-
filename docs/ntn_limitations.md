# NTN Limitations in This System

## Root Cause: `pthread_create()` EAGAIN (RESOLVED)

The OAI gNB and UE containers previously crashed with `pthread_create()` failing (`errno 11 EAGAIN`)
when creating threads with real-time scheduling (`SCHED_FIFO`, priority 2-97).

**Root cause:** Docker with cgroup v1 on WSL2 sets `cpu.rt_runtime_us = 0` for the
Docker parent cgroup by default, preventing any container from using real-time
thread scheduling, even with `CAP_SYS_NICE` granted.

**Fix (applied):**

1. Set the Docker cgroup's RT budget:
   ```bash
   docker run --rm --privileged --pid=host alpine \
     nsenter -t 1 -m -u -i -n sh -c \
     'echo 950000 > /sys/fs/cgroup/cpu/docker/cpu.rt_runtime_us'
   ```
2. Add `cpu_rt_runtime: ${OAI_CPU_RT_RUNTIME:-400000}` and
   `cpu_rt_period: ${OAI_CPU_RT_PERIOD:-1000000}` to gNB and UE services in
   `docker-compose.yml` (plus `privileged: true`). Values are env-var driven for
   portability; defaults match the numbers above.

This grants each container 400 ms of real-time CPU budget per 1 s period,
allowing OAI's `threadCreate()` with `SCHED_FIFO` to succeed.

**Note:** The cgroup fix is non-persistent — it must be re-applied after Docker
or WSL2 restarts. Add it to a startup script if needed.

## NTN Band 256 CORESET#0 Assertion (OPEN)

When using the NTN-specific configuration (`gnb.ntn.band256.rfsim.conf`),
the gNB crashes with:

```
Assertion (type0_PDCCH_CSS_config->cset_start_rb >= 0) failed!
  in get_type0_PDCCH_CSS_config_parameters() openair2/LAYER2/NR_MAC_COMMON/nr_mac_common.c:3881
```

This occurs with both `2026.w09` and `develop` OAI images. The issue is in the
CORESET#0 RB allocation calculation for NTN band 256 (S-band, 25 PRBs, 15 kHz SCS).
With `initialDLBWPcontrolResourceSetZero = 2`, the computed `cset_start_rb` becomes
negative because the CORESET bandwidth + offset exceeds the carrier bandwidth.

The official OAI config (`gnb.sa.band256.ntn.mu0.25prb.rfsim.conf`, stored in this
repo as `configs/oai_official_ntn_band256.conf`) uses the same parameter value,
suggesting this is a regression or requires a specific OAI branch not yet in the
`develop` mainline.

**Current mitigation:** The demo runs with terrestrial band 78 config, which
exercises the full protocol stack (attach, PDU session, data plane) successfully.
The NTN-specific config files are preserved in the repo for reference.

---

| Feature / aspect     | Real NTN (e.g. GEO/LEO)        | This system                         | Gap |
|----------------------|---------------------------------|-------------------------------------|-----|
| Propagation delay    | GEO ~270 ms RTT; LEO variable  | Emulated with `tc netem` (e.g. 135 ms one-way) | Static delay only; no orbit-driven variation |
| Doppler              | LEO: up to tens of kHz at Ka   | Not modeled                         | No frequency offset in RFsim |
| Timing advance       | Derived from RTT / ephemeris   | Configured (ta-Common-r17, Koffset) | Not measured from channel |
| HARQ                 | Often disabled or adapted (GEO)| Disabled in NTN config              | Matches GEO assumption |
| Beam tracking        | Required for moving satellites | Single beam, no tracking             | No mobility/beam model |
| SIB19 / ephemeris   | Broadcast and updated         | Broadcast from config (static)      | No dynamic ephemeris |
| Handover             | Satellite handover, cell reselection | Single cell only               | No mobility |
| Channel model        | Fading, shadowing, multipath   | AWGN (optional)                     | Simplified |

## Summary

This is a **controlled NTN validation baseline**: NTN-specific configuration (band 256,
SIB19, Koffset, extended timers) and optional delay injection are used to demonstrate
and test control-plane behaviour and observability. The actual demo runs with band 78
due to the upstream CORESET#0 bug, but the full protocol stack (5GC + gNB + UE + data
plane) is validated end-to-end. Results are valid for integration and protocol
correctness, not for link budget or throughput under realistic NTN channels.
