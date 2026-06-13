"""
mic_model.py — ARES-SIM-001
Microphone directivity patterns for the PoC.

Two patterns implemented:
  omni          — omnidirectional (current baseline)
  hypercardioid — ~12 dB side-null rejection (high-leverage option, spec §2.2)

Interface: gain_fn(theta_rad) -> scalar in [0, 1]
  theta_rad is the angle between the mic look direction and the incoming signal.

The interface is generic so cardioid/shotgun patterns can be added later
without refactoring callers.
"""

import numpy as np


def omni_gain(theta_rad: float | np.ndarray) -> float | np.ndarray:
    """Omnidirectional: constant unit gain regardless of angle."""
    return np.ones_like(np.asarray(theta_rad, dtype=float))


def hypercardioid_gain(theta_rad: float | np.ndarray) -> float | np.ndarray:
    """
    Hypercardioid polar pattern: G(θ) = |0.25 + 0.75·cos(θ)|

    Maximum gain at θ=0 (on-axis), deep nulls at θ≈109.5°, rear lobe ≈0.25.
    Provides ~12 dB rejection of signals arriving from the sides (spec §2.2).
    """
    theta = np.asarray(theta_rad, dtype=float)
    return np.abs(0.25 + 0.75 * np.cos(theta))


# Registry — add new patterns here; callers resolve by string name.
PATTERNS: dict[str, callable] = {
    "omni":           omni_gain,
    "hypercardioid":  hypercardioid_gain,
}


def get_pattern(name: str) -> callable:
    if name not in PATTERNS:
        raise ValueError(f"Unknown mic pattern '{name}'. Available: {list(PATTERNS)}")
    return PATTERNS[name]


def apply_directivity(
    signal_power: float,
    source_vec: np.ndarray,
    look_direction: np.ndarray,
    pattern_name: str,
) -> float:
    """
    Apply directivity gain to a signal arriving from source_vec relative to mic.

    source_vec      : 3-element vector from mic to source
    look_direction  : 3-element unit vector of mic pointing direction
    pattern_name    : "omni" | "hypercardioid"

    Returns attenuated signal power.
    """
    src = np.asarray(source_vec, dtype=float)
    look = np.asarray(look_direction, dtype=float)

    norm_src  = np.linalg.norm(src)
    norm_look = np.linalg.norm(look)

    if norm_src < 1e-9 or norm_look < 1e-9:
        theta = 0.0
    else:
        cos_theta = np.clip(np.dot(src, look) / (norm_src * norm_look), -1.0, 1.0)
        theta = np.arccos(cos_theta)

    gain = get_pattern(pattern_name)(theta)
    return float(signal_power * gain ** 2)
