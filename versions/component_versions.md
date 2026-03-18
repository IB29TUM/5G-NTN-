# Component Versions

Exact image tags and SHA256 digests for strict reproducibility.
All digests recorded from the images used in the demo run on 2026-03-18.

## Docker Images

| Component | Image | Tag | Digest (SHA256) |
|-----------|-------|-----|-----------------|
| MySQL | mysql | 8.0 | `sha256:0f34c70018dcbde655ba3eaba3d33c02198d392b9364974462eee13a903af385` |
| AMF | oaisoftwarealliance/oai-amf | v2.1.10 | `sha256:af649216e7e36957782267fdb303aacd1ff0d9d704624aff18a88763dae5e89d` |
| SMF | oaisoftwarealliance/oai-smf | v2.1.10 | `sha256:7a931cdbd7ba777e0f28dbcfc65522b5a200f70374ab6da18632043c56db4293` |
| UPF | oaisoftwarealliance/oai-upf | v2.1.10 | `sha256:d903023a6f1aeb12b8ffb9500bedbe471f5703062f658e90bd55fe1bb12117a4` |
| gNB | oaisoftwarealliance/oai-gnb | 2026.w09 | `sha256:5938bb620430a94c88a9cbee23918f64f0faad80e36632f118ff1d61ee047dba` |
| NR-UE | oaisoftwarealliance/oai-nr-ue | 2026.w09 | `sha256:d0518743f52e1da3eeeb6b5797a86f0c443a4debd3d7f779c29530cb2c4f46e5` |
| External DN | oaisoftwarealliance/trf-gen-cn5g | focal | `sha256:275d08f2c255123b6777a0a324d07ab25c091e5548fc7300fc008442e99e5e1c` |

## OAI RAN Reference

- **gNB/NR-UE**: OpenAirInterface 5G RAN, weekly integration tag `2026.w09`.
- **NTN gNB config reference**: OAI `gnb.sa.band256.ntn.mu0.25prb.rfsim.conf` (commit `03b4dfaf1a382b0520d277d561fd69b4d1fc6866` on GitLab Eurecom).
- **CN5G**: OAI 5G Core v2.1.x (AMF/SMF/UPF v2.1.10).

## Runtime Environment (tested)

| Tool | Version |
|------|---------|
| Docker Engine | 28.4.0 |
| Docker Compose | 2.39.2 |
| Linux kernel | 5.15.167.4-microsoft-standard-WSL2 |
| Python | 3.12.3 |

## Reproducing with Exact Digests

To pull the exact images used (immutable, even if tags are later overwritten):

```bash
docker pull mysql@sha256:0f34c70018dcbde655ba3eaba3d33c02198d392b9364974462eee13a903af385
docker pull oaisoftwarealliance/oai-amf@sha256:af649216e7e36957782267fdb303aacd1ff0d9d704624aff18a88763dae5e89d
docker pull oaisoftwarealliance/oai-smf@sha256:7a931cdbd7ba777e0f28dbcfc65522b5a200f70374ab6da18632043c56db4293
docker pull oaisoftwarealliance/oai-upf@sha256:d903023a6f1aeb12b8ffb9500bedbe471f5703062f658e90bd55fe1bb12117a4
docker pull oaisoftwarealliance/oai-gnb@sha256:5938bb620430a94c88a9cbee23918f64f0faad80e36632f118ff1d61ee047dba
docker pull oaisoftwarealliance/oai-nr-ue@sha256:d0518743f52e1da3eeeb6b5797a86f0c443a4debd3d7f779c29530cb2c4f46e5
docker pull oaisoftwarealliance/trf-gen-cn5g@sha256:275d08f2c255123b6777a0a324d07ab25c091e5548fc7300fc008442e99e5e1c
```

After pulling by digest, re-tag so docker-compose can find them:

```bash
docker tag oaisoftwarealliance/oai-gnb@sha256:5938bb620430a94c88a9cbee23918f64f0faad80e36632f118ff1d61ee047dba oaisoftwarealliance/oai-gnb:2026.w09
docker tag oaisoftwarealliance/oai-nr-ue@sha256:d0518743f52e1da3eeeb6b5797a86f0c443a4debd3d7f779c29530cb2c4f46e5 oaisoftwarealliance/oai-nr-ue:2026.w09
```
