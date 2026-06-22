# ARES alternative-spelling map generator

[![Tests](https://github.com/Morshead-Consulting/ARES_metaphone/actions/workflows/test.yml/badge.svg)](https://github.com/Morshead-Consulting/ARES_metaphone/actions/workflows/test.yml)

DN-PHON-001: generate candidate ASR confusions for military terms, for
expert curation into the CTC-WS context file.

The tool converts each military term into its spoken form before matching.
ISTAR becomes "eye star"; CBRN, which has no pronounceable cluster, is spelled
out letter-by-letter as "see bee are en". It then uses Double Metaphone and
Levenshtein distance to find English words that sound like those spoken forms.
This spoken-form approach is what makes the tool effective for letter-by-letter
acronyms (CBRN, IED, ATGM): matching on the raw spelling of those strings would
find nothing useful.

## Install (one-time)

Requires Python 3.12 (see `.python-version`).

With uv (recommended — locks exact versions via `uv.lock`):
```
uv sync
```

Or with plain pip:
```
pip install metaphone rapidfuzz
pip install wordfreq          # optional, enables common-word-first ranking
```

## Run tests

```
uv run pytest tests/ -v
```

The suite includes a **gold standard**: the real spoken pronunciation of each
target acronym (ISTAR -> "eye star", CBRN -> "see bee are en", ...) must appear
among the proposals, and the previously un-handled cases (CBRN, IED, ATGM) must
now match. See `tests/test_pronounce_seg.py`.

## Quick start

Run from the **project root** (the directory containing `altspell_gen.py`), not from inside `data\`:

```
uv run python altspell_gen.py --targets data\targets.txt --use-wordlist --max-key-dist 0 --max-per-target 10 --report
```

If you run from a subdirectory Python will report `can't open file '...\altspell_gen.py'` — always `cd` to the project root first.

## How pronunciation segmentation works

A familiar word embedded in an acronym attracts a hybrid pronunciation: the
`STAR` in ISTAR gives "eye-star", not "eye-ess-tee-ay-are". An acronym with no
pronounceable element (no vowel) is spelled out letter by letter: CBRN ->
"see-bee-are-en". The tool produces the **k-best** spoken forms per acronym
(it does not guess a single winner — eye-STAR vs iss-tar is a genuine
ambiguity the reviewer resolves), always including the full spell-out as a
fallback. Matching then runs on every spoken form, on both the target and any
acronym-like candidate (so IED can match IUD through their spoken forms).

This applies to anything `--targets` flags as an acronym (all-caps, 2-8
letters). Ordinary words are matched on their raw string as before. To turn
segmentation off entirely and revert to raw-string matching, use
`--no-pronounce-seg`.

## Candidate sources

You supply the **targets** (your hand-authored military terms). The generator
finds confusable candidates from any combination of three sources:

| Flag | Source | Network? |
|---|---|---|
| `--candidates FILE` | your own list, one word/phrase per line | no |
| `--use-spellouts` | letter spell-outs as candidates (largely superseded) | no |
| `--use-wordlist` | ~248k-word English list, cached after first download | first run only |

Combine freely. Your `--candidates` entries take priority on de-duplication.

> **Note:** `--use-spellouts` is retained only for pipeline verification.
> Spell-outs are now generated automatically on the *target* side by
> segmentation, so you no longer need them as candidates.

## Windows usage

From the **project root directory**, in Command Prompt:

```
uv run python altspell_gen.py --targets data\targets.txt --use-wordlist ^
    --max-key-dist 0 --max-per-target 8 --report
```

(`^` is the line-continuation in cmd; or just put it all on one line.)

First run with `--use-wordlist` downloads the word list to
`english_words_cache.txt` next to the script, then works offline forever.

## Air-gapped / no-network use

Supply your own word list and forbid network access:

```
python altspell_gen.py --targets data\targets.txt --wordlist-file mywords.txt ^
    --no-download --report
```

Segmentation, Double Metaphone and Levenshtein are all fully offline. Only the
optional first-time word-list download and the optional `wordfreq` package
touch the network; neither is required to run.

## Tuning

- `--max-key-dist 0` = identical phonetic key only (tighter, less noise).
  `1` = near-match (broader, more noise). Start at 0 with the word list.
- `--max-per-target 8` caps proposals per term — recommended with the word
  list, which otherwise returns dozens of obscure dictionary words.
- `--max-surface-dist N` drops candidates whose spelling is wildly different
  in length from the target. Useful for short spell-out keys (e.g. IED), whose
  coarse phonetic key can otherwise attract short high-frequency words.
- `--wordlist-min-len` / `--wordlist-max-len` bound dictionary word length
  (default 3-10). Acronyms rarely collide with very long words.
- `--no-pronounce-seg` reverts to pre-segmentation raw-string matching.

## Ranking

If `wordfreq` is installed, proposals are ranked **common-word-first** — the
criterion that actually decides curation (a recogniser is far likelier to emit
a common word than an obscure one), and the report shows a Zipf score per
candidate (z>=3.5 common, z<2 obscure, z=0 not a known word). Without
`wordfreq`, ranking falls back to phonetic- then surface-distance, unchanged.

## Output

### Flags

| Flag | Description |
|---|---|
| `--targets FILE` | file listing target military terms, one per line (required) |
| `--candidates FILE` | optional reviewer-supplied candidate list |
| `--use-wordlist` | match against the ~248k English word list |
| `--max-key-dist N` | phonetic distance threshold (0 = exact match, 1 = near) |
| `--max-per-target N` | cap on proposals returned per term |
| `--max-surface-dist N` | cap on character-level edit distance |
| `--report` | human-readable output instead of raw CTC-WS lines |
| `--output-dir DIR` | write output to a timestamped file in DIR instead of the terminal |
| `--no-pronounce-seg` | disable spoken-form conversion; match on raw spelling |
| `--no-download` | prevent any network access (air-gapped use) |

### Modes

**Without `--report`** (default): the tool prints raw `target_spelling1_spelling2_...`
lines to the terminal, ready to paste into the CTC-WS context file.

**With `--report`**: the tool prints a human-readable curation sheet. For each
target term it shows the spoken forms the tool derived, then a ranked list of
phonetically similar English words with phonetic and surface distances, a Zipf
frequency score (if `wordfreq` is installed), and a `via "..."` note showing
which spoken form produced the match. The reviewer reads this output and selects
which candidates are genuine plausible confusions — words the recogniser might
actually emit in place of the military term — discarding the rest. Accepted
candidates are added to `--candidates` for the next run or entered directly
into the CTC-WS context file.

By default `--report` prints to the terminal. To save the output to a file,
add `--output-dir results\` and the tool writes a timestamped file to that
directory instead.

## Expert curation

This tool is an assist to expert curation, not a replacement. The tool
proposes; the human keeps the plausible confusions, discards the noise, and
adds real mis-recognitions the algorithms miss. The Sprint 3 recordings feed
the actual observed errors back into `--candidates`, closing the loop.
