#!/usr/bin/env python3
"""
altspell_gen.py  --  ARES alternative-spelling map generator (Phase 1)

Implements the DN-PHON-001 recipe:
  1. Double Metaphone phonetic key for each TARGET term and each CANDIDATE word.
  2. Match candidates whose phonetic key matches (or nearly matches) a target.
  3. Levenshtein distance as a second filter to drop excessive false positives.
  4. Emit `target_spelling1_spelling2_...` lines for the CTC-WS context file.

This is an ASSIST TO EXPERT CURATION, not a replacement. It proposes
confusions; the wargame-experienced reviewer keeps the plausible ones,
discards noise, and adds real mis-recognitions the algorithms miss.

Dependencies (both permissive-licensed, no provenance concern):
    pip install metaphone python-Levenshtein
"""

import argparse
import sys
from metaphone import doublemetaphone
import Levenshtein


def phonetic_keys(term: str):
    """Return the (primary, secondary) Double Metaphone codes, dropping blanks."""
    primary, secondary = doublemetaphone(term)
    return [k for k in (primary, secondary) if k]


def phonetic_match(a: str, b: str) -> bool:
    """True if any Double Metaphone key of a matches any key of b."""
    ka, kb = phonetic_keys(a), phonetic_keys(b)
    return any(x == y for x in ka for y in kb)


def key_edit_distance(a: str, b: str) -> int:
    """Smallest Levenshtein distance between any pair of phonetic keys."""
    ka, kb = phonetic_keys(a), phonetic_keys(b)
    if not ka or not kb:
        return 99
    return min(Levenshtein.distance(x, y) for x in ka for y in kb)


def generate_confusions(targets, candidates, max_key_dist=1, max_surface_dist=None):
    """
    For each target, find candidate words that are phonetically confusable.

    max_key_dist:     max Levenshtein distance between phonetic keys
                      (0 = identical phonetic key only; 1 = near match).
    max_surface_dist: optional cap on surface-string Levenshtein distance,
                      to suppress wildly different-length matches.
    """
    results = {}
    for target in targets:
        hits = []
        for cand in candidates:
            if cand.lower() == target.lower():
                continue
            kd = key_edit_distance(target, cand)
            if kd > max_key_dist:
                continue
            sd = Levenshtein.distance(target.lower(), cand.lower())
            if max_surface_dist is not None and sd > max_surface_dist:
                continue
            hits.append((cand, kd, sd))
        # closest phonetic match first, then closest surface match
        hits.sort(key=lambda h: (h[1], h[2]))
        if hits:
            results[target] = hits
    return results


def emit_ctcws(results):
    """Emit `target_spelling1_spelling2_...` lines for the CTC-WS context file."""
    lines = []
    for target, hits in results.items():
        spellings = [target] + [c for c, _, _ in hits]
        lines.append("_".join(spellings))
    return lines


def main():
    ap = argparse.ArgumentParser(description="ARES alt-spelling map generator")
    ap.add_argument("--targets", required=True,
                    help="file with one target military term per line")
    ap.add_argument("--candidates", required=True,
                    help="file with one candidate word per line (general "
                         "English + observed mis-recognitions)")
    ap.add_argument("--max-key-dist", type=int, default=1,
                    help="max Levenshtein distance between phonetic keys "
                         "(default 1)")
    ap.add_argument("--max-surface-dist", type=int, default=None,
                    help="optional cap on surface-string Levenshtein distance")
    ap.add_argument("--report", action="store_true",
                    help="print a human-readable curation report instead of "
                         "the raw CTC-WS lines")
    args = ap.parse_args()

    with open(args.targets) as f:
        targets = [ln.strip() for ln in f if ln.strip()]
    with open(args.candidates) as f:
        candidates = [ln.strip() for ln in f if ln.strip()]

    results = generate_confusions(
        targets, candidates,
        max_key_dist=args.max_key_dist,
        max_surface_dist=args.max_surface_dist,
    )

    if args.report:
        print("# Curation report  (keep / discard the proposals below)")
        print(f"# {len(targets)} targets, {len(candidates)} candidates, "
              f"max_key_dist={args.max_key_dist}\n")
        for target, hits in results.items():
            keys = ", ".join(phonetic_keys(target))
            print(f"{target}  [{keys}]")
            for cand, kd, sd in hits:
                print(f"    <- {cand:20s} key_dist={kd} surface_dist={sd}")
            print()
        missing = [t for t in targets if t not in results]
        if missing:
            print("# No candidates matched (add manually if needed):")
            print("#   " + ", ".join(missing))
    else:
        for line in emit_ctcws(results):
            print(line)


if __name__ == "__main__":
    main()
