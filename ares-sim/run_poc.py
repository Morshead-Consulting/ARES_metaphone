#!/usr/bin/env python3
"""
run_poc.py — ARES Capture Simulation PoC entry point
ARES-SIM-001 v1.0

Usage:
    python run_poc.py                      # print ranked table to stdout
    python run_poc.py --csv results.csv    # also save CSV
    python run_poc.py --room other.yaml    # alternate room config

Loads scenarios/poc_room.yaml, runs the placement sweep, and prints a
justification table ranked by 5th-percentile minimum-speaker SINR.

PoC success criterion (spec §7.1): directional placement must achieve
measurably higher robust SINR than omni baseline on simultaneous-speech
and low-energy-background scenarios.
"""

import argparse
import csv
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ares_sim.optimise import run_sweep


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def print_table(results: list[dict]) -> None:
    header = (
        f"{'Rank':<5} {'Placement':<35} {'Pattern':<15} "
        f"{'P5 SINR (dB)':<14} {'Min SINR (dB)':<14} {'Mean SINR (dB)':<14}"
    )
    sep = "-" * len(header)
    print()
    print("=" * len(header))
    print("ARES Capture Simulation — Placement Ranking")
    print("Ranked by 5th-percentile minimum-speaker SINR (robust design objective)")
    print("=" * len(header))
    print(header)
    print(sep)

    for rank, r in enumerate(results, 1):
        fom = r["fom"]
        print(
            f"{rank:<5} {r['description'][:34]:<35} {r['pattern']:<15} "
            f"{fom['p5_sinr']:<14.2f} {fom['min_sinr']:<14.2f} {fom['mean_sinr']:<14.2f}"
        )

    print(sep)
    print()
    print("Per-scenario breakdown:")
    print()
    for r in results:
        print(f"  {r['description']} [{r['pattern']}]")
        for bd in r["breakdown"]:
            src_detail = "  ".join(
                f"{k}={v:.1f} dB" for k, v in bd["per_source_sinr"].items()
            )
            print(f"    {bd['scenario']}")
            print(f"      sources: {src_detail}")
            print(f"      min SINR: {bd['min_sinr']:.2f} dB")
        print()


def save_csv(results: list[dict], path: Path) -> None:
    rows = []
    for rank, r in enumerate(results, 1):
        for bd in r["breakdown"]:
            rows.append({
                "rank":        rank,
                "placement_id": r["id"],
                "description": r["description"],
                "pattern":     r["pattern"],
                "p5_sinr":     r["fom"]["p5_sinr"],
                "min_sinr":    r["fom"]["min_sinr"],
                "mean_sinr":   r["fom"]["mean_sinr"],
                "scenario":    bd["scenario"],
                "scenario_min_sinr": bd["min_sinr"],
            })
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Results saved to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ARES Capture Simulation PoC — placement sweep"
    )
    parser.add_argument(
        "--room", default="scenarios/poc_room.yaml",
        help="Path to room YAML config"
    )
    parser.add_argument(
        "--csv", default=None, metavar="PATH",
        help="Save results to CSV"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)"
    )
    args = parser.parse_args()

    room_yaml_path = Path(args.room)
    if not room_yaml_path.exists():
        print(f"ERROR: room config not found: {room_yaml_path}", file=sys.stderr)
        sys.exit(1)

    cfg = load_yaml(room_yaml_path)

    print(f"Loading room: {room_yaml_path}")
    print(f"  Dimensions:  {cfg['room']['dimensions']} m")
    print(f"  Absorption:  {cfg['room']['absorption']}")
    print(f"  Participants: {len(cfg['seats'])}")
    print(f"  Placements:  {len(cfg['mic_placements'])}")
    print(f"  Seed:        {args.seed}")
    print()
    print("Running simulation sweep... (this may take a minute)")

    results = run_sweep(
        room_cfg=cfg["room"],
        participants_cfg=cfg["seats"],
        placements=cfg["mic_placements"],
        seed=args.seed,
    )

    print_table(results)

    if args.csv:
        save_csv(results, Path(args.csv))


if __name__ == "__main__":
    main()
