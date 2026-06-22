# Alternative-spelling generator (`altspell_gen.py`)

## Purpose

`altspell_gen.py` is the main script. Given a list of military acronyms
(targets) and a source of English words (candidates), it finds the candidates
that sound like each target and writes them out in the format the ASR system
reads. See the [README](../README.md) for usage, flags, and quick-start
commands. This document covers the algorithm design and internal data shapes.

---

## Pipeline

```
targets.txt
    │
    ▼
[pronounce_seg]  spoken_forms(target)  →  "eye star", "is tar", …
    │
    ▼
[phonetic_keys]  doublemetaphone(rendering)  →  ["ASTR", "ASTR"]
    │
    ▼
[generate_confusions]  match every candidate rendering against every target
    │                  rendering; keep pairs within max_key_dist (phonetic)
    │                  and max_surface_dist (character)
    ▼
{target: [(cand, key_dist, surface_dist, via), …]}
    │
    ├─── --report  →  human-readable proposals list
    │
    └─── default   →  CTC-WS lines  target_cand1_cand2_…
```

---

## Matching algorithm

### Step 1 — Spoken forms (`term_forms`)

`term_forms(term, use_seg)` returns the list of `(rendering, phonetic_keys)`
pairs actually used for matching.

- For **acronym-like targets** (all-caps alphabetic, 2+ letters), when
  segmentation is on, the k-best spoken forms from `pronounce_seg` are used:
  ISTAR yields `[("eye star", ["ASTR"]), ("is tar", ["ASTR"]), ...]`.
- For **non-acronyms** (ordinary words, candidates), or when `--no-pronounce-seg`
  is set, the raw string is keyed: "psalm" yields `[("psalm", ["SLM"])]`.
- **Acronym-like candidates** (e.g. IUD in `--candidates`) go through the same
  segmentation, so IUD → "eye you dee" and is matched against targets on that
  basis. This is what allows cross-acronym confusion discovery.

If segmentation produces no phonetically keyable form, `term_forms` falls back
to the raw string. If the raw string also produces no key (empty string, symbols
only), the term is silently skipped — it can match nothing.

### Step 2 — Phonetic keying (`phonetic_keys`)

`phonetic_keys(term)` calls `doublemetaphone(term)` and returns both primary and
secondary codes, dropping any empty string the library returns. This means a
single rendering can produce up to two keys, and distance is taken as the minimum
across all pairings (see `_min_key_dist`). The secondary code handles common
spelling variations (e.g. the C/K ambiguity in CASEVAC).

### Step 3 — Matching (`generate_confusions`)

```python
results = generate_confusions(targets, candidates,
    max_key_dist=0,         # 0 = identical phonetic key; 1 = one phoneme off
    max_surface_dist=None,  # optional character-level cap
    max_per_target=15,      # cap per target
    use_seg=True)
```

Returns `{target: [(cand, key_dist, surface_dist, via), ...]}`.

Key design decisions:

- **Candidate forms are pre-computed once**, not per-target. This makes the
  inner loop O(T × C) comparisons of already-computed key lists rather than
  O(T × C) `doublemetaphone` calls.
- **`via`** records which pair of renderings produced the best match:
  `(target_rendering, candidate_rendering)`. Used in report mode to show the
  `via "eye star"` annotation. If neither rendering differs from its raw term,
  `via` is `None`.
- **`surface_dist`** is computed on the raw surface strings (`target.lower()`,
  `cand.lower()`), not on the renderings. It is a rough noise filter: a
  candidate that matches phonetically but differs wildly in length from the
  target is usually noise.
- **Ranking:** `(key_dist, -zipf(cand), surface_dist)`. Exact phonetic matches
  first, then most-common word first (the dominant Phase 1 curation criterion),
  then surface closeness as a tiebreaker. If `wordfreq` is not installed, `zipf`
  returns 0.0 for all words and the sort degrades to `(key_dist, surface_dist)`.

### Step 4 — Output

**Default (CTC-WS lines):** `emit_ctcws(results)` joins target and candidates
with underscores. One line per target that has at least one hit:

```
ISTAR_aster_astir_estray_…
```

**`--report` (proposals list):** `main()` formats a human-readable block per
target. The `via` and rendering-differs logic controls when the `via "…"` /
`~ "…"` annotations appear — they are suppressed when the rendering is identical
to the raw string, avoiding clutter for ordinary dictionary candidates.

---

## Candidate sources

The three sources are merged by `build_candidates()`. De-duplication is
case-insensitive (first-seen wins, original case preserved):

| Flag | What it adds |
|---|---|
| `--candidates FILE` | Your hand-curated list. Takes priority in de-dup because it is processed first. |
| `--use-spellouts` | Adds the letter spell-out of each target as a candidate. Largely superseded by segmentation on the target side — retained for pipeline verification only. |
| `--use-wordlist` | The ~248k dwyl/english-words list, filtered to `[--wordlist-min-len, --wordlist-max-len]` (default 3–10). Downloaded once, then used offline. |

`--use-wordlist` is the main source in production use. The others are for
supplementing with observed mis-recognitions or for offline/air-gapped contexts.

---

## Word list caching

On first use with `--use-wordlist`, the list is downloaded from GitHub to
`english_words_cache.txt` next to the script. Subsequent runs use the local
copy with no network access.

The download uses an **atomic write**: `tempfile.mkstemp()` in the same
directory, then `shutil.move()`. This prevents a partial download (e.g. from an
interrupted network request) from being silently used as the cache on the next
run. If the download fails, the temp file is deleted before the process exits.

To supply your own list (air-gapped use): `--wordlist-file mywords.txt
--no-download`. The file must be one word per line.

---

## Optional dependency: `wordfreq`

If `wordfreq` is installed (`uv add wordfreq`), hits are ranked common-word-first
and the `--report` output shows a Zipf score per candidate:

- z ≥ 3.5: very common ("star", "sat")
- z 2–3.5: moderately common
- z < 2: obscure
- z = 0: not a recognised English word

Without `wordfreq`, the `zipf()` function returns 0.0 for all words; ranking
falls back to `(key_dist, surface_dist)` and no Zipf column appears in the
report. All other behaviour is unchanged.

`wordfreq` is a ranking aid only. Its frequency data is CC-licensed and is not
embedded in any deliverable; it is a dev-time dependency.

---

## Tuning

| Parameter | Recommended start | Effect |
|---|---|---|
| `--max-key-dist 0` | Yes, with `--use-wordlist` | Exact phonetic key match only. Tighter, less noise. Use 1 to catch one-phoneme near-matches (broader but noisier). |
| `--max-per-target 15` | Yes, with `--use-wordlist` | Caps the proposal count per target. The word list can return dozens of obscure entries for short initialisms; 15 is a useful starting cap. |
| `--max-surface-dist N` | Optional | Drops candidates whose surface string differs from the target by more than N characters. Useful for short initialisms like IED whose coarse phonetic key attracts many short high-frequency words. |
| `--wordlist-min-len 3` | Default | Excludes very short words that cause noise for short initialisms. Raise if needed. |
| `--wordlist-max-len 10` | Default | Excludes very long dictionary words that rarely collide with acronym pronunciations. Lower to reduce volume. |
| `--no-pronounce-seg` | Debugging only | Reverts to raw-string keying. Use to verify that segmentation is improving results, not degrading them. |

---

## Internal functions reference

| Function | Purpose |
|---|---|
| `term_forms(term, use_seg)` | Returns `[(rendering, [keys]), ...]` for matching. The only function that bridges pronounce_seg and the phonetic algorithm. |
| `phonetic_keys(term)` | Returns `[primary, secondary]` Double Metaphone codes (non-empty only). |
| `_min_key_dist(keys_a, keys_b)` | Minimum Levenshtein distance across all pairs of phonetic keys. |
| `key_edit_distance(a, b)` | Public wrapper around `_min_key_dist`; returns 99 if either term has no phonetic key. Used directly in tests. |
| `generate_confusions(...)` | Core matching loop. Returns the `{target: [(cand, key_dist, surface_dist, via), ...]}` dict. |
| `emit_ctcws(results)` | Formats the results dict as CTC-WS lines. |
| `build_candidates(args, targets)` | Merges and de-duplicates all candidate sources. |
| `spell_out(acronym)` | Renders an acronym as a space-separated letter sequence ("IED" → "eye ee dee"). Used by `--use-spellouts`. |
| `load_wordlist(cache_path, ...)` | Downloads (atomically) or reads the English word list. |
| `looks_like_acronym(term)` | Heuristic: all-caps alphabetic, 2+ letters. Controls whether segmentation is applied to a term. |

---

## Data shapes

**`generate_confusions` return value:**

```python
{
    "ISTAR": [
        ("aster",  0, 4, ("eye star", "aster")),   # (cand, key_dist, surface_dist, via)
        ("astir",  0, 4, ("eye star", "astir")),
        ("estray", 0, 5, ("eye star", "estray")),
        ...
    ],
    "CBRN": [
        ("seaborne", 0, 6, ("see bee are en", "seaborne")),
        ...
    ],
}
```

`via` is `(target_rendering, candidate_rendering)` — the pair that produced the
best match — or `None` if the rendering was identical to the raw term.

**`emit_ctcws` output:**

```
ISTAR_aster_astir_estray_…
CBRN_seaborne_…
```
