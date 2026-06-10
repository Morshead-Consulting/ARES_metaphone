# ARES alternative-spelling map generator

[![Tests](https://github.com/Morshead-Consulting/ARES_metaphone/actions/workflows/test.yml/badge.svg)](https://github.com/Morshead-Consulting/ARES_metaphone/actions/workflows/test.yml)

DN-PHON-001: generate candidate ASR confusions for military terms, for
expert curation into the CTC-WS context file.

Each acronym is first segmented into how it is actually **spoken** — ISTAR
as "eye star", CBRN spelled out as "see bee are en" — then Double Metaphone
+ Levenshtein find English words that sound like those spoken forms. Matching
on speech rather than spelling is what lets the tool handle letter-by-letter
acronyms (CBRN, IED, ATGM) that keying the raw string cannot.

## Install (one-time)

Requires Python 3.12 (see `.python-version`).

With uv (recommended — locks exact versions via `uv.lock`):
```
uv sync
```

Or with plain pip:
```
pip install metaphone python-Levenshtein
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

```
python altspell_gen.py --targets data\targets.txt --use-wordlist --max-key-dist 0 --max-per-target 10 --report
```

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

From the project directory, in Command Prompt:

```
python altspell_gen.py --targets data\targets.txt --use-wordlist ^
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

> **Licence note (Sprint 1 review):** `wordfreq` code is MIT, but its bundled
> frequency *data* aggregates several CC-licensed sources. It is a **dev-time
> ranking aid only** — nothing from it ships in the delivered system.

## Two output modes

- `--report` : human-readable curation sheet. Each target shows its spoken
  forms, then ranked proposals with phonetic/surface distances, a Zipf score
  (if `wordfreq` is present), and a `via "..."` note showing which spoken form
  produced the match. This is what the wargame-experienced reviewer marks up,
  and it makes good bid evidence.
- default : raw `target_spelling1_spelling2_...` lines for the CTC-WS file.

## Remember

This is an **assist to expert curation, not a replacement**. The tool
proposes; the human keeps the plausible confusions, discards the noise, and
adds real mis-recognitions the algorithms miss. The Sprint 3 recordings feed
the actual observed errors back into `--candidates`, closing the loop.
