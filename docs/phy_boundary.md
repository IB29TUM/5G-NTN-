# PHY Boundary and RF Abstraction

## What Runs (Real)

- **L1 baseband (in RFsim mode)**: FFT/IFFT, channel estimation (based on simulated channel), modulation/demodulation, encoding/decoding. The same code path as with real RF is used; the only difference is the source/sink of IQ samples.
- **L2/L3**: MAC, RLC, PDCP, RRC, NAS. Unchanged. NTN-specific behaviour (e.g. Koffset for scheduling, extended timers) is applied in the stack when the gNB is configured for NTN (e.g. band 256).

## What Is Replaced

- **RF frontend**: Antenna, power amplifier (PA), low-noise amplifier (LNA), mixers, ADC/DAC.
- **Over-the-air channel**: Replaced by TCP socket between gNB and UE RFsimulator processes, plus an optional channel model (e.g. AWGN) and optional delay/jitter via `tc netem`.

## What Is Not Modeled Here

- **Real channel estimation**: In the simulator, the channel is known or AWGN; no multipath, no real propagation.
- **Doppler compensation**: No frequency offset due to satellite motion. In a real LEO NTN deployment, Doppler can be large (e.g. tens of kHz at Ka-band).
- **Real timing advance**: TA is configured (e.g. `ta-Common-r17`) but not derived from actual RTT measurement.
- **Beam tracking**: Single static beam is assumed.

## Why Results Are Still Valid

- **Control-plane procedures** (RRC, NAS, NGAP) are protocol-identical. Attach, authentication, PDU session establishment are the same as in a deployment with real RF, as long as the link is stable.
- **NTN scheduling (Koffset)** is applied in the MAC based on configuration; it does not depend on the physical layer source of the IQ samples.
- This setup is therefore valid for **control-plane correctness**, **NTN configuration visibility**, and **integration testing**, not for PHY-accurate or throughput benchmarking.
