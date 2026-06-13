"""
tests/test_modules.py — ARES-SIM-001 sanity tests
Run with: python -m pytest tests/
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── room_model ────────────────────────────────────────────────────────────────

def test_room_model_rir_shape():
    from ares_sim.room_model import build_room, compute_rirs
    room = build_room(
        dimensions=[6.0, 5.0, 3.0],
        absorption=0.3,
        mic_positions=[[3.0, 2.5, 2.9]],
        source_positions=[[2.0, 2.0, 1.2]],
    )
    rirs = compute_rirs(room)
    assert len(rirs) == 1
    assert rirs[0].shape[0] == 1
    assert rirs[0].shape[1] > 0


def test_room_model_multi_mic_multi_source():
    from ares_sim.room_model import build_room, compute_rirs
    room = build_room(
        dimensions=[8.0, 6.0, 3.0],
        absorption=0.3,
        mic_positions=[[3.5, 2.5, 2.9], [4.5, 2.5, 2.9]],
        source_positions=[[2.0, 1.5, 1.2], [4.0, 4.5, 1.2]],
    )
    rirs = compute_rirs(room)
    assert len(rirs) == 2          # one RIR matrix per source
    assert rirs[0].shape[0] == 2  # two mics


# ── mic_model ─────────────────────────────────────────────────────────────────

def test_omni_flat_gain():
    from ares_sim.mic_model import omni_gain
    angles = np.linspace(0, np.pi, 20)
    assert np.allclose(omni_gain(angles), 1.0)


def test_hypercardioid_front_rear():
    from ares_sim.mic_model import hypercardioid_gain
    assert hypercardioid_gain(0.0) == pytest.approx(1.0, abs=1e-6)
    # rear gain = 0.25 (0° phase) — hypercardioid pattern has rear lobe
    assert hypercardioid_gain(np.pi) == pytest.approx(0.5, abs=0.05)


def test_hypercardioid_null_depth():
    from ares_sim.mic_model import hypercardioid_gain
    angles = np.linspace(0, np.pi, 1000)
    assert np.min(hypercardioid_gain(angles)) < 0.1


def test_apply_directivity_on_vs_off_axis():
    from ares_sim.mic_model import apply_directivity
    p_on  = apply_directivity(1.0, [0, 0, 1], [0, 0, 1], "hypercardioid")
    p_off = apply_directivity(1.0, [1, 0, 0], [0, 0, 1], "hypercardioid")
    assert p_on > p_off


# ── behaviour_model ───────────────────────────────────────────────────────────

def test_build_participants():
    import random
    from ares_sim.behaviour_model import build_participants
    seats = [
        {"id": "s1", "position": [2.0, 1.5, 1.2], "label": "A", "team": "blue"},
        {"id": "s2", "position": [4.0, 1.5, 1.2], "label": "B", "team": "red"},
    ]
    participants = build_participants(seats, random.Random(0))
    assert len(participants) == 2
    assert participants[0].team_id == "team_blue"
    assert participants[0].position == [2.0, 1.5, 1.2]


def test_build_scenarios_count():
    import random
    from ares_sim.behaviour_model import build_participants, build_scenarios, ScenarioType
    seats = [
        {"id": f"s{i}", "position": [float(i)*2, 1.5, 1.2], "label": f"P{i}", "team": "blue"}
        for i in range(3)
    ]
    participants = build_participants(seats, random.Random(0))
    scenarios = build_scenarios(participants)
    types = {s.type for s in scenarios}
    assert ScenarioType.EXPECTED_SEATED     in types
    assert ScenarioType.SIMULTANEOUS_SPEECH in types
    assert ScenarioType.LOW_ENERGY_BG       in types


# ── beamform_eval ─────────────────────────────────────────────────────────────

def test_sinr_no_interferer():
    from ares_sim.beamform_eval import compute_sinr
    target = np.ones(1000)
    sinr = compute_sinr(target, [])
    assert sinr > 30.0  # high SINR with no interferer


def test_sinr_strong_interferer():
    from ares_sim.beamform_eval import compute_sinr
    target    = np.ones(1000) * 0.01
    interferer = np.ones(1000)
    sinr = compute_sinr(target, [interferer])
    assert sinr < 0.0  # negative SINR when interferer dominates


def test_placement_fom_keys():
    from ares_sim.beamform_eval import compute_placement_fom
    fom = compute_placement_fom([10.0, 5.0, -2.0, 8.0])
    assert "mean_sinr" in fom
    assert "min_sinr"  in fom
    assert "p5_sinr"   in fom
    assert fom["min_sinr"] <= fom["p5_sinr"] <= fom["mean_sinr"]
