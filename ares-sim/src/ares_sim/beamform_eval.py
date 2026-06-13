"""
beamform_eval.py — ARES-SIM-001
MVDR beamforming and SINR metric computation (spec §2.4).

CALIBRATION CAVEAT (README §Limitations):
  The spec requires this module to use the *same MVDR algorithm as the live ARES
  system*. That shared code does not yet exist in this workspace. The implementation
  below is a clean, isolated MVDR behind a single function (mvdr_weights) so it
  can be swapped for the shared implementation without changing any callers.
  Flag for integration before Sprint 3 live tests.

SINR formula (spec §2.4.1):
  SINR(S,C) = 10·log10( P_target / (Σ P_interferers + P_noise) )

  Both target and interferer power are measured *after* applying the MVDR weights,
  so the denominator reflects actual residual leakage, not raw mic-channel power.

Placement-level figure of merit (spec §2.4.2):
  mean SINR, min SINR, 5th-percentile SINR across scenarios.
  Design objective: maximise 5th-percentile minimum-speaker SINR (robust design).
"""

from __future__ import annotations

import numpy as np


# ── MVDR beamformer ───────────────────────────────────────────────────────────

def _estimate_covariance(signals: np.ndarray, regularisation: float = 1e-4) -> np.ndarray:
    """
    Estimate spatial covariance matrix from multichannel signals.

    signals: (n_mics, n_samples), real-valued
    Returns: (n_mics, n_mics) complex Hermitian covariance matrix.
    """
    n_mics, n_samples = signals.shape
    R = (signals.astype(complex) @ signals.astype(complex).conj().T) / n_samples
    # Diagonal loading for numerical stability
    R += regularisation * np.trace(R).real / n_mics * np.eye(n_mics, dtype=complex)
    return R


def _steering_vector(mic_positions: np.ndarray, source_position: np.ndarray,
                     frequency: float, c: float = 343.0) -> np.ndarray:
    """
    Free-field narrowband steering vector.

    mic_positions : (n_mics, 3)
    source_position: (3,)
    Returns: (n_mics,) complex array
    """
    distances = np.linalg.norm(mic_positions - source_position, axis=1)
    phases = 2 * np.pi * frequency * distances / c
    return np.exp(-1j * phases)


def mvdr_weights(
    noise_signals: np.ndarray,
    mic_positions: list[list[float]],
    source_position: list[float],
    focus_freq: float = 1000.0,
) -> np.ndarray:
    """
    Compute MVDR weight vector for a target source position.

    noise_signals  : (n_mics, n_samples) — interference + noise (no target)
    mic_positions  : list of [x, y, z]
    source_position: [x, y, z] of target
    focus_freq     : Hz — analysis frequency (1 kHz, centre of speech band)

    Returns: (n_mics,) complex weight vector w such that y = w^H x.

    CALIBRATION NOTE: replace this function body with the live ARES MVDR when available.
    """
    mic_arr = np.array(mic_positions, dtype=float)
    src_arr = np.array(source_position, dtype=float)

    R_noise = _estimate_covariance(noise_signals)

    d = _steering_vector(mic_arr, src_arr, focus_freq).reshape(-1, 1)

    try:
        R_inv = np.linalg.inv(R_noise)
    except np.linalg.LinAlgError:
        R_inv = np.linalg.pinv(R_noise)

    numerator   = R_inv @ d
    denominator = (d.conj().T @ R_inv @ d).real.item() + 1e-30
    return (numerator / denominator).flatten()  # (n_mics,)


def apply_weights(weights: np.ndarray, signals: np.ndarray) -> np.ndarray:
    """Apply beamformer weights to multichannel signals; return 1-D real output."""
    return (weights.conj() @ signals).real


# ── SINR computation ──────────────────────────────────────────────────────────

_NOISE_FLOOR_POWER = 1e-6  # approximate noise floor power (~60 dB below 1 Pa)


def compute_sinr(
    target_bf: np.ndarray,
    interferer_bfs: list[np.ndarray],
    noise_power: float = _NOISE_FLOOR_POWER,
) -> float:
    """
    Compute SINR in dB.

    target_bf      : 1-D beamformed target signal
    interferer_bfs : list of 1-D beamformed interferer signals (same weights applied)
    noise_power    : additive thermal noise power

    Both target and interferer are measured *after* beamforming so the denominator
    reflects actual residual leakage after spatial filtering.
    """
    p_target = float(np.mean(target_bf ** 2))
    p_interferers = sum(float(np.mean(ibf ** 2)) for ibf in interferer_bfs)
    denominator = p_interferers + noise_power
    if denominator < 1e-30:
        return 60.0
    return 10.0 * np.log10(max(p_target / denominator, 1e-10))


# ── Placement-level figure of merit ──────────────────────────────────────────

def compute_placement_fom(sinr_values: list[float]) -> dict[str, float]:
    """
    Aggregate per-scenario SINR values to placement figure of merit (spec §2.4.2).

    Returns dict with mean_sinr, min_sinr, p5_sinr.
    Design objective is to maximise p5_sinr (robust design, not peak optimisation).
    """
    arr = np.array(sinr_values)
    return {
        "mean_sinr": float(np.mean(arr)),
        "min_sinr":  float(np.min(arr)),
        "p5_sinr":   float(np.percentile(arr, 5)),
    }


# ── Per-scenario SINR evaluation ─────────────────────────────────────────────

def evaluate_scenario(
    propagation_result: dict[str, np.ndarray],
    mic_positions: list[list[float]],
    scenario_sources: list,
    fs: int = 16000,
) -> dict[str, float]:
    """
    Run MVDR + SINR evaluation for every source in a scenario.

    For each source S treated as target:
      1. Build noise covariance from all other sources.
      2. Compute MVDR weights toward S.
      3. Apply weights to S's signal → target beam.
      4. Apply same weights to each interferer's signal → leakage estimate.
      5. SINR = P_target_beam / (Σ P_leakage_beam + P_noise_floor).

    Returns: {source_label: sinr_db}
    """
    results: dict[str, float] = {}
    n_sources = len(scenario_sources)

    for i, active in enumerate(scenario_sources):
        target_key = active.label
        target_sig = propagation_result.get(target_key)
        if target_sig is None:
            continue

        # All other sources constitute interference
        interferer_sigs = [
            propagation_result[a.label]
            for j, a in enumerate(scenario_sources)
            if j != i and a.label in propagation_result
        ]

        # Build noise signal for covariance: interferers only, or noise floor proxy
        if interferer_sigs:
            noise_for_cov = np.sum(interferer_sigs, axis=0)
        else:
            noise_for_cov = np.random.default_rng(42).standard_normal(target_sig.shape) * 1e-3

        w = mvdr_weights(
            noise_signals=noise_for_cov,
            mic_positions=mic_positions,
            source_position=active.participant.position,
        )

        target_bf = apply_weights(w, target_sig)
        interferer_bfs = [apply_weights(w, isig) for isig in interferer_sigs]

        sinr = compute_sinr(target_bf, interferer_bfs)
        results[target_key] = sinr

    return results
