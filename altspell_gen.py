#!/usr/bin/env python3
r"""
altspell_gen.py  --  ARES alternative-spelling map generator (Phase 2)

Implements the DN-PHON-001 recipe, extended with PRONUNCIATION SEGMENTATION:
  0. Each acronym target is segmented into its plausible spoken forms via
     pronounce_seg.py (familiar embedded words attract hybrid pronunciation:
     ISTAR -> "eye star"; no pronounceable element forces letter-by-letter:
     CBRN -> "see bee are en"). Matching operates on what is SAID, not on
     the raw letter string. Disable with --no-pronounce-seg.
  1. Double Metaphone phonetic key for each spoken form and each CANDIDATE
     word (acronym-like candidates, e.g. IUD, get spoken forms too).
  2. Match candidates whose phonetic key matches (or nearly matches) any
     spoken form of a target.
  3. Levenshtein distance as a second filter to drop excessive false positives.
  4. Emit `target_spelling1_spelling2_...` lines for the CTC-WS context file.

This is an ASSIST TO EXPERT CURATION, not a replacement. It proposes
confusions; the wargame-experienced reviewer keeps the plausible ones,
discards noise, and adds real mis-recognitions the algorithms miss.

CANDIDATE SOURCES (merged automatically; all optional, combine freely):
  --candidates FILE   your own list, one word/phrase per line
  --use-spellouts     add letter spell-outs of each target as candidates
                      (largely superseded by segmentation; kept for
                      pipeline verification)
  --use-wordlist      a general English word list. Downloaded once to a
                      local cache, then used offline forever after. Or
                      point --wordlist-file at a list you supply yourself
                      (no network needed).

Dependencies (both permissive-licensed, no provenance concern):
    pip install metaphone python-Levenshtein

WINDOWS NOTE: paths with backslashes work fine, e.g.
    python altspell_gen.py --targets targets.txt --use-wordlist --report
The cache file lives next to this script by default.
"""

import argparse
import os
import sys
import urllib.request
from metaphone import doublemetaphone
import Levenshtein

from pronounce_seg import spoken_forms

# Optional: word-frequency ranking. Phase 1 curation showed the dominant
# keep/discard criterion is whether the candidate is a common word an ASR
# language model would plausibly emit. If `wordfreq` is installed, hits
# are ranked common-first and the report shows a Zipf score (z>=3.5 common,
# z<2 obscure, z=0 not a known word). Without it, behaviour is unchanged.
# NOTE for Sprint 1 legal review: wordfreq code is MIT, but its bundled
# frequency data aggregates sources under CC licences -- a DEV-TIME ranking
# aid only; it ships nothing into the delivered system.
try:
    from wordfreq import zipf_frequency as _zipf

    def zipf(word: str) -> float:
        return _zipf(word, "en")
except ImportError:
    def zipf(word: str) -> float:
        return 0.0
    _zipf = None


# --- Candidate source: letter spell-outs -----------------------------------

LETTER_SOUNDS = {
    'A': 'ay', 'B': 'bee', 'C': 'see', 'D': 'dee', 'E': 'ee', 'F': 'eff',
    'G': 'gee', 'H': 'aitch', 'I': 'eye', 'J': 'jay', 'K': 'kay', 'L': 'el',
    'M': 'em', 'N': 'en', 'O': 'oh', 'P': 'pee', 'Q': 'cue', 'R': 'are',
    'S': 'ess', 'T': 'tee', 'U': 'you', 'V': 'vee', 'W': 'double you',
    'X': 'ex', 'Y': 'why', 'Z': 'zed',
}


def spell_out(acronym: str) -> str:
    """Render an acronym as its spoken letter sequence (UK 'zed' for Z)."""
    return " ".join(LETTER_SOUNDS.get(c.upper(), c)
                    for c in acronym if c.isalpha())


# --- Candidate source: downloadable English word list ----------------------

# dwyl/english-words: a public-domain plain word list on GitHub (raw host is
# on the ARES network allowlist). Downloaded once, then cached locally.
WORDLIST_URL = (
    "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
)


def default_cache_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "english_words_cache.txt")


def load_wordlist(cache_path: str, allow_download: bool, min_len: int,
                  max_len: int):
    """
    Load the English word list, downloading to cache on first use.

    Returns a list of words filtered by length (most useful confusions are
    short; very long dictionary words rarely collide with acronyms).
    """
    if not os.path.exists(cache_path):
        if not allow_download:
            sys.exit(
                f"Word list cache not found at {cache_path} and download is "
                f"disabled.\nEither run once with network access, or supply "
                f"your own list via --wordlist-file."
            )
        sys.stderr.write(f"Downloading word list to cache: {cache_path}\n")
        try:
            urllib.request.urlretrieve(WORDLIST_URL, cache_path)
        except Exception as e:
            sys.exit(
                f"Download failed ({e}).\nOn an air-gapped machine, supply a "
                f"word list yourself with --wordlist-file PATH."
            )

    with open(cache_path, encoding="utf-8", errors="ignore") as f:
        words = [w.strip() for w in f if w.strip()]
    return [w for w in words if min_len <= len(w) <= max_len]


# --- Core algorithm --------------------------------------------------------

def phonetic_keys(term: str):
    """Return the (primary, secondary) Double Metaphone codes, dropping blanks."""
    primary, secondary = doublemetaphone(term)
    return [k for k in (primary, secondary) if k]


def looks_like_acronym(term: str) -> bool:
    """Heuristic: an all-caps alphabetic token of 2-8 letters is treated as
    an acronym and matched via its spoken forms rather than its raw string."""
    return term.isalpha() and term.isupper() and 2 <= len(term) <= 8


def term_forms(term: str, use_seg: bool = True):
    """
    The list of (rendering, phonetic_keys) actually used for matching.

    For acronyms (when segmentation is enabled) these are the k-best
    pronounceability segmentations from pronounce_seg -- e.g. ISTAR yields
    "istar", "is tar", "eye star", "eye ess tee ay are" -- so matching
    operates on what is SAID, not on the letter string. CBRN, having no
    pronounceable element, yields only its spell-out "see bee are en",
    which is precisely why its old false hits (caburn, caprine, ...)
    disappear. Non-acronyms key on the raw string, as before.
    """
    forms = []
    if use_seg and looks_like_acronym(term):
        for _cost, _segs, rendering in spoken_forms(term):
            keys = phonetic_keys(rendering)
            if keys:
                forms.append((rendering, keys))
    if not forms:
        keys = phonetic_keys(term)
        if keys:
            forms.append((term, keys))
    return forms


def _min_key_dist(keys_a, keys_b) -> int:
    return min(Levenshtein.distance(x, y) for x in keys_a for y in keys_b)


def key_edit_distance(a: str, b: str) -> int:
    """Return the minimum phonetic-key edit distance between two surface strings.
    Returns 99 if either string produces no phonetic key."""
    keys_a, keys_b = phonetic_keys(a), phonetic_keys(b)
    if not keys_a or not keys_b:
        return 99
    return _min_key_dist(keys_a, keys_b)


def generate_confusions(targets, candidates, max_key_dist=1,
                        max_surface_dist=None, max_per_target=None,
                        use_seg=True):
    """
    For each target, find candidate words that are phonetically confusable.

    Matching compares every spoken form of the target against every spoken
    form of the candidate (candidates that look like acronyms, e.g. IUD,
    get the same treatment) and keeps the best distance, recording WHICH
    pair of renderings matched so the curation report can show it.

    max_key_dist:     max Levenshtein distance between phonetic keys
                      (0 = identical phonetic key only; 1 = near match).
    max_surface_dist: optional cap on surface-string Levenshtein distance.
    max_per_target:   optional cap on number of proposals per target
                      (useful when --use-wordlist returns many hits).
    use_seg:          False reverts to raw-string keying (pre-DN-PHON-001
                      Phase 2 behaviour).

    Returns {target: [(candidate, key_dist, surface_dist, (t_rend, c_rend)), ...]}
    """
    # Pre-compute candidate forms once: O(candidates), not O(targets x candidates).
    cand_entries = []
    for cand in candidates:
        forms = term_forms(cand, use_seg)
        if forms:
            cand_entries.append((cand, forms))

    results = {}
    for target in targets:
        tforms = term_forms(target, use_seg)
        if not tforms:
            continue
        hits = []
        for cand, cforms in cand_entries:
            if cand.lower() == target.lower():
                continue
            best, via = 99, None
            for t_rend, t_keys in tforms:
                for c_rend, c_keys in cforms:
                    d = _min_key_dist(t_keys, c_keys)
                    if d < best:
                        best, via = d, (t_rend, c_rend)
            if best > max_key_dist:
                continue
            sd = Levenshtein.distance(target.lower(), cand.lower())
            if max_surface_dist is not None and sd > max_surface_dist:
                continue
            hits.append((cand, best, sd, via))
        # Rank: exact phonetic match first, then COMMON words first (the
        # Phase 1 curation criterion, automated), then surface closeness.
        hits.sort(key=lambda h: (h[1], -zipf(h[0]), h[2]))
        if max_per_target is not None:
            hits = hits[:max_per_target]
        if hits:
            results[target] = hits
    return results


def emit_ctcws(results):
    """Emit `target_spelling1_spelling2_...` lines for the CTC-WS context file."""
    lines = []
    for target, hits in results.items():
        spellings = [target] + [h[0] for h in hits]
        lines.append("_".join(spellings))
    return lines


# --- CLI -------------------------------------------------------------------

def build_candidates(args, targets):
    """Assemble the candidate pool from every selected source, de-duplicated."""
    pool = {}  # lowercase key -> original-case value (first seen wins)

    def add(word):
        k = word.lower()
        if k not in pool:
            pool[k] = word

    if args.candidates:
        with open(args.candidates, encoding="utf-8") as f:
            for ln in f:
                if ln.strip():
                    add(ln.strip())

    if args.use_spellouts:
        for t in targets:
            so = spell_out(t)
            if so:
                add(so)

    if args.use_wordlist:
        cache = args.wordlist_file or default_cache_path()
        allow_download = args.wordlist_file is None and not args.no_download
        for w in load_wordlist(cache, allow_download,
                               args.wordlist_min_len, args.wordlist_max_len):
            add(w)

    return list(pool.values())


def main():
    ap = argparse.ArgumentParser(description="ARES alt-spelling map generator")
    ap.add_argument("--targets", required=True,
                    help="file with one target military term per line")

    src = ap.add_argument_group("candidate sources (combine any)")
    src.add_argument("--candidates",
                     help="your own candidate file, one word/phrase per line")
    src.add_argument("--use-spellouts", action="store_true",
                     help="add letter spell-outs of each target as CANDIDATES "
                          "(largely superseded: spell-outs are now generated "
                          "automatically on the target side by pronunciation "
                          "segmentation; kept for pipeline-verification use)")
    src.add_argument("--use-wordlist", action="store_true",
                     help="include a general English word list (cached)")
    src.add_argument("--wordlist-file",
                     help="use this word list file instead of downloading "
                          "(air-gapped use)")
    src.add_argument("--no-download", action="store_true",
                     help="never reach the network; fail if cache is missing")
    src.add_argument("--wordlist-min-len", type=int, default=3,
                     help="ignore dictionary words shorter than this (default 3)")
    src.add_argument("--wordlist-max-len", type=int, default=10,
                     help="ignore dictionary words longer than this (default 10)")

    filt = ap.add_argument_group("matching filters")
    filt.add_argument("--max-key-dist", type=int, default=1,
                      help="max Levenshtein distance between phonetic keys "
                           "(default 1)")
    filt.add_argument("--max-surface-dist", type=int, default=None,
                      help="optional cap on surface-string Levenshtein distance")
    filt.add_argument("--max-per-target", type=int, default=None,
                      help="cap proposals per target (recommended with "
                           "--use-wordlist, e.g. 15)")
    filt.add_argument("--no-pronounce-seg", action="store_true",
                      help="disable pronunciation segmentation and match on "
                           "raw strings (pre-Phase-2 behaviour)")

    ap.add_argument("--report", action="store_true",
                    help="human-readable curation report instead of raw lines")
    args = ap.parse_args()

    if not (args.candidates or args.use_spellouts or args.use_wordlist):
        ap.error("choose at least one candidate source: --candidates, "
                 "--use-spellouts, and/or --use-wordlist")

    with open(args.targets, encoding="utf-8") as f:
        targets = [ln.strip() for ln in f if ln.strip()]

    candidates = build_candidates(args, targets)
    n_sources = sum(bool(x) for x in
                    [args.candidates, args.use_spellouts, args.use_wordlist])
    sys.stderr.write(f"Candidate pool: {len(candidates)} words "
                     f"from {n_sources} source(s)\n")

    use_seg = not args.no_pronounce_seg
    results = generate_confusions(
        targets, candidates,
        max_key_dist=args.max_key_dist,
        max_surface_dist=args.max_surface_dist,
        max_per_target=args.max_per_target,
        use_seg=use_seg,
    )

    if args.report:
        print("# Curation report  (keep / discard the proposals below)")
        print(f"# {len(targets)} targets, {len(candidates)} candidates, "
              f"max_key_dist={args.max_key_dist}, "
              f"pronounce_seg={'on' if use_seg else 'off'}\n")
        for target, hits in results.items():
            forms = term_forms(target, use_seg)
            spoken = " | ".join(f'"{r}"' for r, _ in forms)
            print(f"{target}  spoken as: {spoken}")
            for cand, kd, sd, via in hits:
                note = ""
                if via is not None:
                    t_rend, c_rend = via
                    parts = []
                    if t_rend.lower() != target.lower():
                        parts.append(f'via "{t_rend}"')
                    if c_rend.lower() != cand.lower():
                        parts.append(f'~ "{c_rend}"')
                    if parts:
                        note = "  " + " ".join(parts)
                freq = f" zipf={zipf(cand):.1f}" if _zipf else ""
                print(f"    <- {cand:24s} key_dist={kd} "
                      f"surface_dist={sd}{freq}{note}")
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
