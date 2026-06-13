"""
optimise.py — ARES-SIM-001
Simple sweep over candidate mic placements (spec Step 6 / §2.4.2).

Enumerates placements from poc_room.yaml, runs each through all 3 scenarios,
and ranks by the robust figure of merit: 5th-percentile minimum-speaker SINR.

Stage 4 local fine-tuning is explicitly excluded from the PoC scope (spec §Step 6).
"""

from __future__ import annotations

import numpy as np

from ares_sim.behaviour_model import Scenario, build_scenarios, build_participants
from ares_sim.propagation import run_propagation
from ares_sim.beamform_eval import evaluate_scenario, compute_placement_fom


def run_sweep(
    room_cfg: dict,
    participants_cfg: list[dict],
    placements: list[dict],
    seed: int = 42,
) -> list[dict]:
    """
    Run the placement sweep and return ranked results.

    Parameters
    ----------
    room_cfg         : dict from poc_room.yaml room section
    participants_cfg : list of seat dicts (position, team, label, id)
    placements       : list of placement dicts from poc_room.yaml mic_placements

    Returns
    -------
    List of result dicts sorted by p5_sinr descending.  Each dict:
      id, description, pattern, fom (mean/min/p5), per_scenario breakdown.
    """
    import random
    rng_seed = random.Random(seed)

    participants = build_participants(participants_cfg, rng_seed)
    scenarios    = build_scenarios(participants)

    results = []

    for placement in placements:
        mic_positions = [list(p) for p in placement["positions"]]
        mic_pattern   = placement["pattern"]

        scenario_sinrs: list[float] = []
        scenario_breakdown: list[dict] = []

        for scenario in scenarios:
            prop = run_propagation(
                room_cfg=room_cfg,
                mic_positions=mic_positions,
                mic_pattern=mic_pattern,
                scenario=scenario,
                duration_s=0.5,
                seed=seed,
            )

            sinr_map = evaluate_scenario(
                propagation_result=prop,
                mic_positions=mic_positions,
                scenario_sources=scenario.sources,
            )

            # Minimum-speaker SINR for this scenario (binding constraint)
            if sinr_map:
                min_sinr = min(sinr_map.values())
                scenario_sinrs.append(min_sinr)
                scenario_breakdown.append({
                    "scenario": scenario.label,
                    "per_source_sinr": {k: round(v, 2) for k, v in sinr_map.items()},
                    "min_sinr": round(min_sinr, 2),
                })

        fom = compute_placement_fom(scenario_sinrs)
        results.append({
            "id":          placement["id"],
            "description": placement["description"],
            "pattern":     mic_pattern,
            "fom":         {k: round(v, 2) for k, v in fom.items()},
            "breakdown":   scenario_breakdown,
        })

    # Rank by p5_sinr descending (robust design objective)
    results.sort(key=lambda r: r["fom"]["p5_sinr"], reverse=True)
    return results
