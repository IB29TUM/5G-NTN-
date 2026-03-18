# Component Versions

Exact image tags and references for reproducibility.

## Docker Images

| Component | Image | Tag / Version |
|-----------|-------|----------------|
| MySQL | mysql | 8.0 |
| AMF | oaisoftwarealliance/oai-amf | v2.1.10 |
| SMF | oaisoftwarealliance/oai-smf | v2.1.10 |
| UPF | oaisoftwarealliance/oai-upf | v2.1.10 |
| gNB | oaisoftwarealliance/oai-gnb | develop |
| NR-UE | oaisoftwarealliance/oai-nr-ue | develop |
| External DN | oaisoftwarealliance/trf-gen-cn5g | focal |

## OAI RAN Reference

- **gNB/NR-UE**: OpenAirInterface 5G RAN (develop branch).
- **NTN gNB config reference**: OAI `gnb.sa.band256.ntn.mu0.25prb.rfsim.conf` (commit `03b4dfaf1a382b0520d277d561fd69b4d1fc6866` on GitLab Eurecom).
- **CN5G**: OAI 5G Core v2.1.x compatible (AMF/SMF/UPF v2.1.10).

## Pinning a Specific Weekly Build

If `develop` is unstable, pin to a weekly integration tag, e.g.:

- `oaisoftwarealliance/oai-gnb:2026.w11`
- `oaisoftwarealliance/oai-nr-ue:2026.w11`

Update `.env` and this file accordingly. Record digest after first successful run:

```bash
docker image inspect oaisoftwarealliance/oai-gnb:develop --format '{{.RepoDigests}}'
```
