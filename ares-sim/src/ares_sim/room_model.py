"""
room_model.py — ARES-SIM-001
Wraps pyroomacoustics ShoeBox for the PoC acoustic simulation.

Limitation: scalar absorption coefficient (per-surface modelling deferred to Sprint 2).
"""

import numpy as np
import pyroomacoustics as pra


def build_room(
    dimensions: list[float],
    absorption: float,
    mic_positions: list[list[float]],
    source_positions: list[list[float]],
    sample_rate: int = 16000,
    max_order: int = 12,
    seed: int = 42,
) -> pra.ShoeBox:
    """
    Return a configured pyroomacoustics ShoeBox with mics and sources placed.

    Parameters
    ----------
    dimensions      : [length, width, height] in metres
    absorption      : scalar wall absorption coefficient in [0, 1]
    mic_positions   : list of [x, y, z] mic coordinates
    source_positions: list of [x, y, z] source coordinates
    sample_rate     : Hz (default 16000 to match ARES ASR pipeline)
    max_order       : image-source reflection order (spec §2.1 default 12)
    seed            : numpy RNG seed for reproducibility
    """
    np.random.seed(seed)

    materials = pra.Material(absorption)
    room = pra.ShoeBox(
        dimensions,
        fs=sample_rate,
        materials=materials,
        max_order=max_order,
    )

    # Add microphone array (all mics in one array)
    mic_array = np.array(mic_positions).T  # shape (3, n_mics)
    room.add_microphone(mic_array)

    # Add sources (each source gets a unit-impulse signal; real signals applied later)
    for pos in source_positions:
        room.add_source(pos, signal=np.zeros(1))

    return room


def compute_rirs(room: pra.ShoeBox) -> list[np.ndarray]:
    """
    Compute room impulse responses and return per-source RIR matrix.

    Returns list of length n_sources; each element is ndarray (n_mics, n_samples).
    """
    room.compute_rir()
    n_mics    = room.mic_array.R.shape[1]
    n_sources = len(room.sources)

    rirs = []
    for src_idx in range(n_sources):
        per_mic = [room.rir[mic_idx][src_idx] for mic_idx in range(n_mics)]
        max_len = max(len(h) for h in per_mic)
        padded  = np.zeros((n_mics, max_len))
        for mic_idx, h in enumerate(per_mic):
            padded[mic_idx, : len(h)] = h
        rirs.append(padded)

    return rirs
