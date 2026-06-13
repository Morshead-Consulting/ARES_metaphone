# ARES Capture Simulation — Proof of Concept

**Spec reference:** ARES-SIM-001 v1.0  
**Classification:** OFFICIAL  
**Purpose:** Pre-bid PoC evidencing the lead technical differentiator for the ARES bid.

---

## What this does

`python run_poc.py` loads a representative wargame room configuration, runs a
placement sweep across three candidate microphone array designs, and prints a
ranked justification table showing which design achieves the highest robust
separation quality — measured as 5th-percentile minimum-speaker SINR.

The central bid claim this evidences: **capture geometry is the highest-leverage
pre-deployment decision, and we can quantify it before buying any hardware.**

---

## Quick start

```
# Windows
.venv\Scripts\python run_poc.py

# Mac/Linux
.venv/bin/python run_poc.py

# Save results to CSV
python run_poc.py --csv results.csv
```

**Dependencies (pinned):**

| Package            | Version  |
|--------------------|----------|
| pyroomacoustics    | 0.10.1   |
| numpy              | 2.4.6    |
| scipy              | 1.17.1   |
| matplotlib         | 3.11.0   |
| pyyaml             | (latest) |

Install: `.venv/Scripts/pip install -r requirements.txt`

---

## Running the tests

```
python -m pytest tests/ -v
```

---

## Module summary

| Module                       | Role                                                          |
|------------------------------|---------------------------------------------------------------|
| `src/ares_sim/room_model.py` | pyroomacoustics ShoeBox wrapper; computes room impulse responses |
| `src/ares_sim/mic_model.py`  | Omni and hypercardioid directivity patterns                   |
| `src/ares_sim/behaviour_model.py` | Participant + scenario generation (3 PoC scenarios)      |
| `src/ares_sim/propagation.py` | Convolves source signals with RIRs; applies directivity      |
| `src/ares_sim/beamform_eval.py` | MVDR beamforming + SINR metric + placement FOM            |
| `src/ares_sim/optimise.py`   | Placement sweep; ranks by P5 minimum-speaker SINR             |
| `run_poc.py`                 | Entry point; prints justification table                       |
| `scenarios/poc_room.yaml`    | Room and placement configuration                              |

### Reuse from ARES-PROTO-001 (`generate_dataset.py`)

`behaviour_model.py` is aligned with `generate_dataset.py`'s participant identity
and activity structure (team role: Blue/Red/umpire/observer; hierarchy_level for
activity weighting; zone assignment). It **extends** those fields with spatial and
acoustic attributes that do not exist in the graph-prototype dataset (3-D seat
position, voice energy in dB, activity weight) — as documented in ARES-SIM-001 §3.3.
The two datasets remain compatible at the participant-identity level.

---

## Honest limitations

The spec (§6.2) is clear that **candour about limitations is a bid strength**:

1. **SINR is not WER.** This tool predicts Signal-to-Interference-plus-Noise Ratio
   (separation quality), which is *upstream* of Word Error Rate or Diarisation Error
   Rate. The SINR → WER/DER mapping is established at the Sprint 3 live test, not here.

2. **Synthetic source signals.** Speech excitation is band-limited noise (300–3400 Hz),
   not real speech. Real speech has temporal structure (pauses, formants, pitch) that
   affects beamformer performance. The acoustic geometry is correct; the temporal
   statistics are a placeholder.

3. **MVDR placeholder.** The spec requires the same MVDR algorithm as the live ARES
   system. That shared code does not yet exist in this workspace. `beamform_eval.mvdr_weights()`
   is a clean, isolated implementation behind a single function — swap the body for
   the shared code before Sprint 3 without changing any callers.

4. **Scalar absorption coefficient.** Per-surface material modelling is deferred.
   A scalar coefficient (~0.3 for a furnished room) is adequate for the PoC sweep.

5. **Design-space explorer, not a digital twin.** Pyroomacoustics image-source
   modelling approximates early reflections well but omits late diffuse reverberation
   accurately. Results are sufficient to rank placement candidates; they are not a
   calibrated prediction of measured SINR in a specific room.

6. **Reproducibility.** All numpy RNG seeds are fixed (default 42). Re-running
   `python run_poc.py` produces identical output. Change `--seed` to explore variance.

---

## PoC success criterion (spec §7.1)

`python run_poc.py` must produce a ranked table showing that a directional
(hypercardioid) placement achieves measurably higher robust SINR than the omni
baseline on at least the simultaneous-speech and low-energy-background scenarios.

**Observed result (seed=42):**

| Rank | Placement                        | P5 SINR (dB) | vs omni  |
|------|----------------------------------|-------------|----------|
| 1    | Per-seat hypercardioid (5 mics)  | +0.64       | +10.6 dB |
| 2    | Hybrid (2 ceiling + 3 per-seat)  | −0.81       | +9.2 dB  |
| 3    | 4-mic ceiling omni (baseline)    | −9.96       | —        |

The directional per-seat design achieves **~10 dB improvement** in robust SINR
over the ceiling omni baseline, driven primarily by the simultaneous-speech
scenario (+14 dB min-speaker SINR: 13.2 dB vs −0.9 dB).
