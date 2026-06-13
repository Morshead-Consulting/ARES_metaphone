"""
behaviour_model.py — ARES-SIM-001
Participant and scenario generation for the acoustic simulation PoC.

Reuses identity/activity structure from generate_dataset.py (ARES-PROTO-001 P1):
  - team_id: blue | red | umpire | observer
  - role_id / hierarchy_level (lower = more senior = higher activity weight)
  - zone_id

Extends those fields with spatial and acoustic attributes that do NOT exist
in generate_dataset.py and are required by the acoustic simulation:
  - position [x, y, z] in metres
  - energy_db: nominal speech level at 1 m (primary ~65 dB, quiet ~50 dB)
  - activity_weight: relative speaking probability

Scenarios implemented (spec §3.3, three required for PoC):
  EXPECTED_SEATED       — design case, one speaker at a time
  SIMULTANEOUS_SPEECH   — two speakers active, stresses separation
  LOW_ENERGY_BACKGROUND — quiet side-remark alongside primary speech
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ScenarioType(Enum):
    EXPECTED_SEATED     = "expected_seated"
    SIMULTANEOUS_SPEECH = "simultaneous_speech"
    LOW_ENERGY_BG       = "low_energy_background"


@dataclass
class Participant:
    """
    Single acoustic simulation participant.

    Identity/activity fields aligned with generate_dataset.py player records.
    Spatial/acoustic fields are simulation-specific extensions.
    """
    # Identity — mirrors generate_dataset.py fields
    id:              str
    name:            str
    team_id:         str   # blue | red | umpire | observer
    role_id:         str
    hierarchy_level: int   # lower = more senior
    zone_id:         str

    # Spatial (simulation-specific — not in generate_dataset.py)
    position:        list[float]  # [x, y, z] metres; z≈1.2 m seated mouth height

    # Acoustic (simulation-specific)
    energy_db:       float = 65.0   # nominal speech level at 1 m (dB SPL)
    activity_weight: float = 1.0    # relative speaking probability


@dataclass
class ActiveSource:
    """One active sound source for a scenario instance."""
    participant: Participant
    energy_db:   float       # may differ from participant nominal (e.g. quiet remark)
    label:       str = "target"  # "target" | "interferer" | "background"


@dataclass
class Scenario:
    """One simulation scenario: a set of simultaneously active sources."""
    type:    ScenarioType
    sources: list[ActiveSource]
    label:   str = ""


def build_participants(seat_configs: list[dict], rng: random.Random) -> list[Participant]:
    """
    Construct Participant objects from seat configuration dicts (poc_room.yaml seats).

    seat_configs: list of dicts with keys id, position, label, team
    """
    team_hierarchy = {"blue": 0, "red": 0, "umpire": 5, "observer": 10}

    participants = []
    for i, seat in enumerate(seat_configs):
        team = seat["team"]
        p = Participant(
            id=seat["id"],
            name=seat["label"],
            team_id=f"team_{team}",
            role_id=f"role_{team}_{i:02d}",
            hierarchy_level=team_hierarchy.get(team, 10) + i,
            zone_id=f"zone_{team[0]}",
            position=list(seat["position"]),
            energy_db=65.0,
            activity_weight=max(1.0, 5.0 - team_hierarchy.get(team, 10)),
        )
        participants.append(p)

    return participants


def build_scenarios(participants: list[Participant]) -> list[Scenario]:
    """
    Build the three PoC scenarios from a participant list (spec §3.3).
    """
    # Use the first two participants as primary speakers
    primary   = participants[0]
    secondary = participants[1] if len(participants) > 1 else participants[0]

    scenarios = [
        # 1. Expected seated: single primary speaker
        Scenario(
            type=ScenarioType.EXPECTED_SEATED,
            label="Expected seated (single speaker)",
            sources=[
                ActiveSource(primary, energy_db=65.0, label="target"),
            ],
        ),

        # 2. Simultaneous speech: two active speakers
        Scenario(
            type=ScenarioType.SIMULTANEOUS_SPEECH,
            label="Simultaneous speech (two speakers)",
            sources=[
                ActiveSource(primary,   energy_db=65.0, label="target"),
                ActiveSource(secondary, energy_db=65.0, label="interferer"),
            ],
        ),

        # 3. Low-energy background: primary + quiet side remark from a third seat
        Scenario(
            type=ScenarioType.LOW_ENERGY_BG,
            label="Low-energy background (quiet remark)",
            sources=[
                ActiveSource(primary,   energy_db=65.0, label="target"),
                # quiet remark: 50 dB, 15 dB below primary (spec §3.3)
                ActiveSource(
                    participants[2] if len(participants) > 2 else secondary,
                    energy_db=50.0,
                    label="background",
                ),
            ],
        ),
    ]

    return scenarios
