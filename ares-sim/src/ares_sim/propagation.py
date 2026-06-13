"""
propagation.py — ARES-SIM-001
Compute multichannel audio for a given placement + scenario.

For each source:
  1. Generate a short band-limited noise burst (speech-like excitation).
     Placeholder — real speech signals deferred; flagged in README.
  2. Compute RIRs via room_model.
  3. Convolve source signal with each per-mic RIR.
  4. Scale by distance and energy, apply directivity gain from mic_model.
  5. Sum per-mic contributions from all sources → multichannel array.

Output: dict mapping source label to ndarray (n_mics, n_samples).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

from ares_sim.room_model import build_room, compute_rirs
from ares_sim.mic_model import apply_directivity
from ares_sim.behaviour_model import Scenario, ActiveSource


def _db_to_linear(db: float) -> float:
    """Convert dB SPL to linear amplitude (reference 1 Pa)."""
    return 10 ** (db / 20.0)


def _speech_excitation(n_samples: int, energy_db: float, rng: np.random.Generator) -> np.ndarray:
    """
    Band-limited noise burst as speech-like excitation (placeholder).

    300–3400 Hz band (telephony speech band) at specified energy level.
    Flagged as a simplification — real speech signals would be used in Sprint 3.
    """
    white = rng.standard_normal(n_samples)
    # Simple bandpass via masking in frequency domain
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / 16000)
    spec  = np.fft.rfft(white)
    mask  = (freqs >= 300) & (freqs <= 3400)
    spec *= mask
    signal = np.fft.irfft(spec, n=n_samples)
    # Normalise to unit RMS then scale by desired amplitude
    rms = np.sqrt(np.mean(signal ** 2))
    if rms > 1e-9:
        signal /= rms
    amplitude = _db_to_linear(energy_db)
    return signal * amplitude


def run_propagation(
    room_cfg: dict,
    mic_positions: list[list[float]],
    mic_pattern: str,
    scenario: Scenario,
    duration_s: float = 0.5,
    seed: int = 42,
) -> dict[str, np.ndarray]:
    """
    Simulate sound propagation for one placement + scenario.

    Parameters
    ----------
    room_cfg      : dict with keys dimensions, absorption, sample_rate, max_order
    mic_positions : list of [x, y, z]
    mic_pattern   : "omni" | "hypercardioid"
    scenario      : Scenario from behaviour_model
    duration_s    : source signal duration in seconds
    seed          : RNG seed for reproducibility

    Returns
    -------
    dict: source_label -> ndarray (n_mics, n_samples)
      Also includes "mix" key with all sources summed.
    """
    rng = np.random.default_rng(seed)
    fs  = room_cfg.get("sample_rate", 16000)
    n_samples = int(duration_s * fs)

    source_positions = [s.participant.position for s in scenario.sources]

    room = build_room(
        dimensions=room_cfg["dimensions"],
        absorption=room_cfg["absorption"],
        mic_positions=mic_positions,
        source_positions=source_positions,
        sample_rate=fs,
        max_order=room_cfg.get("max_order", 12),
        seed=seed,
    )
    rirs = compute_rirs(room)  # list[ndarray (n_mics, rir_len)]

    n_mics = len(mic_positions)
    # Global output length: longest convolution across all sources
    global_out_len = n_samples + max(r.shape[1] for r in rirs) - 1
    result: dict[str, np.ndarray] = {}
    mix = np.zeros((n_mics, global_out_len))

    mic_look_up = np.array([0.0, 0.0, 1.0])  # default: mics point upward

    for src_idx, active in enumerate(scenario.sources):
        excitation = _speech_excitation(n_samples, active.energy_db, rng)
        rir_matrix = rirs[src_idx]  # (n_mics, rir_len_for_this_source)

        # Per-source convolution length; pad to global_out_len before accumulating
        src_out_len = n_samples + rir_matrix.shape[1] - 1
        channel_signals = np.zeros((n_mics, global_out_len))

        for mic_idx in range(n_mics):
            rir = rir_matrix[mic_idx]
            convolved = fftconvolve(excitation, rir)  # length = src_out_len

            mic_pos = np.array(mic_positions[mic_idx])
            src_pos = np.array(active.participant.position)
            src_vec = src_pos - mic_pos

            p_raw = np.mean(convolved ** 2) + 1e-30
            p_dir = apply_directivity(p_raw, src_vec, mic_look_up, mic_pattern)
            gain  = np.sqrt(p_dir / p_raw)
            channel_signals[mic_idx, :src_out_len] = convolved * gain

        label = active.label
        result[label] = channel_signals
        mix += channel_signals

    result["mix"] = mix
    return result
