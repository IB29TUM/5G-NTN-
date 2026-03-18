# OAI NTN Band 256 CORESET#0 Bug Report

**Date:** 2026-03-18
**OAI image:** `oaisoftwarealliance/oai-gnb:2026.w09`
**Digest:** `sha256:5938bb620430a94c88a9cbee23918f64f0faad80e36632f118ff1d61ee047dba`

---

## Summary

The OAI gNB crashes on startup when using the official NTN band 256 configuration
(`gnb.sa.band256.ntn.mu0.25prb.rfsim.conf`) published in the OAI GitLab repository.
The crash is caused by a CORESET#0 configuration that is physically incompatible with
the carrier bandwidth. This is an OAI-side issue — no user misconfiguration is involved.

## Crash Output

```
Assertion (type0_PDCCH_CSS_config->cset_start_rb >= 0) failed!
  in get_type0_PDCCH_CSS_config_parameters() /oai-ran/openair2/LAYER2/NR_MAC_COMMON/nr_mac_common.c:3881
Invalid CSET0 start PRB -3 SSB offset point A 1 RB offset 4
```

Exit code: 255

## Root Cause

The config specifies:

| Parameter | Value |
|-----------|-------|
| `dl_carrierBandwidth` | 25 PRBs (~4.5 MHz at 15 kHz SCS) |
| `initialDLBWPcontrolResourceSetZero` | 2 |

Per 3GPP TS 38.213, Table 13-1 (SS/PBCH and CORESET multiplexing pattern 1, 15 kHz SCS):

| Index | CORESET RBs | Symbols | Offset |
|-------|-------------|---------|--------|
| 0     | 24          | 2       | 0      |
| 1     | 24          | 2       | 2      |
| **2** | **48**      | **1**   | **2**  |

Index 2 requires a 48-RB CORESET. The carrier is only 25 PRBs wide.
The function `get_type0_PDCCH_CSS_config_parameters()` computes the CORESET start RB
as a negative value (-3) because 48 + offset cannot fit in 25 PRBs, triggering the
assertion.

## What Was Tested

### Test 1: OAI's official config, unmodified

- **Config source:** Downloaded from OAI GitLab, `develop` branch:
  `targets/PROJECTS/GENERIC-NR-5GC/CONF/gnb.sa.band256.ntn.mu0.25prb.rfsim.conf`
- **Binary:** `oaisoftwarealliance/oai-gnb:2026.w09` (unmodified Docker Hub image)
- **Command:**
  ```bash
  docker run --rm --privileged \
    --cpu-rt-runtime=400000 --cpu-rt-period=1000000 \
    -v oai_official_ntn_band256.conf:/opt/oai-gnb/etc/gnb.conf \
    oaisoftwarealliance/oai-gnb:2026.w09 \
    /opt/oai-gnb/bin/nr-softmodem -O /opt/oai-gnb/etc/gnb.conf --rfsim --noS1
  ```
- **Result:** CRASH — `Assertion (type0_PDCCH_CSS_config->cset_start_rb >= 0) failed!`
  Exit code 255.

### Test 2: Same config, `initialDLBWPcontrolResourceSetZero` changed from 2 to 0

- **Only change:** `initialDLBWPcontrolResourceSetZero = 0` (24-RB CORESET, fits in 25 PRBs)
- **Same binary, same command.**
- **Result:** SUCCESS — gNB initializes PHY (`Init: N_RB_DL 25`), starts RFsimulator server,
  no assertion failure. Exit code 0.

### Test 3: Parameter comparison — OAI official vs our config

Every radio parameter in our YAML config (`gnb.ntn.band256.rfsim.yaml`) was compared
against OAI's official `.conf` file. All critical values match exactly:

| Parameter | OAI official | Ours |
|-----------|-------------|------|
| `dl_frequencyBand` | 256 | 256 |
| `dl_carrierBandwidth` | 25 | 25 |
| `dl_absoluteFrequencyPointA` | 436390 | 436390 |
| `absoluteFrequencySSB` | 436810 | 436810 |
| `initialDLBWPcontrolResourceSetZero` | 2 | 2 |
| `initialDLBWPsearchSpaceZero` | 2 | 2 |
| `initialDLBWPlocationAndBandwidth` | 6600 | 6600 |
| `dl_subcarrierSpacing` | 0 (15 kHz) | 0 (15 kHz) |
| `cellSpecificKoffset_r17` | 478 | 478 |
| `ta-Common-r17` | 58629666 | 58629666 |
| `disable_harq` | 1 | 1 |

### Test 4: Cross-version check

The crash reproduces identically on both `oai-gnb:2026.w09` and `oai-gnb:develop`
image tags, ruling out a version-specific regression in the weekly build.

## Conclusion

This is confirmed as an OAI bug. The evidence:

1. **Their config, their binary, their crash.** The official config file published on
   OAI GitLab, run on OAI's own Docker image with no modifications, triggers the assertion.
2. **Root cause is clear.** CORESET#0 index 2 requires 48 RBs; the carrier is 25 PRBs.
   The code does not guard against this mismatch — it asserts instead of falling back
   or erroring gracefully.
3. **The fix is trivial.** Changing the index from 2 to 0 (24-RB CORESET) eliminates
   the crash. However, this may affect UE initial access behavior and was not adopted
   in our demo without further validation.

The bug is either:
- A config error in OAI's published NTN band 256 config (wrong CORESET#0 index for 25 PRBs), or
- A code gap where NTN narrow-band carriers need a different CORESET#0 table lookup
  that exists in a feature branch but has not been merged to `develop`.

## Mitigation

Our demo runs with the terrestrial band 78 configuration (`gnb.sa.band78.106prb.rfsim.yaml`,
106 PRBs, 30 kHz SCS), which exercises the full protocol stack successfully. The NTN-specific
config files (band 256, Koffset, SIB19, disabled HARQ) are preserved in the repository as
reference material.

## Files

| File | Description |
|------|-------------|
| `configs/oai_official_ntn_band256.conf` | OAI's official config, downloaded from GitLab `develop` branch |
| `configs/gnb.ntn.band256.rfsim.yaml` | Our equivalent YAML config (identical parameters) |
| `configs/gnb.sa.band78.106prb.rfsim.yaml` | Working terrestrial config used for the demo |
| `docs/ntn_limitations.md` | Broader NTN limitations and gap analysis |
