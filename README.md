# ARES alternative-spelling map generator

Phase 1 of DN-PHON-001: generate candidate ASR confusions for military terms
using Double Metaphone + Levenshtein, for expert curation into the CTC-WS
context file.

## Install (one-time)

```
pip install metaphone python-Levenshtein
```

## Candidate sources

You supply the **targets** (your hand-authored military terms). The generator
finds confusable candidates from any combination of three sources:

| Flag | Source | Network? |
|---|---|---|
| `--candidates FILE` | your own list, one word/phrase per line | no |
| `--use-spellouts` | auto letter spell-outs, e.g. `IED -> "eye ee dee"` | no |
| `--use-wordlist` | ~248k-word English list, cached after first download | first run only |

Combine freely. Your `--candidates` entries take priority on de-duplication.

## Windows usage (your machine)

From `C:\Users\rftwo\Documents\ARES_metaphone`, in Command Prompt:

```
python altspell_gen.py --targets targets.txt --use-spellouts --use-wordlist ^
    --max-key-dist 0 --max-per-target 8 --report
```

(`^` is the line-continuation in cmd; or just put it all on one line.)

First run with `--use-wordlist` downloads the word list to
`english_words_cache.txt` next to the script, then works offline forever.

## Air-gapped / no-network use

Supply your own word list and forbid network access:

```
python altspell_gen.py --targets targets.txt --wordlist-file mywords.txt ^
    --no-download --report
```

Or just use `--use-spellouts` and `--candidates`, which never touch the network.

## Tuning

- `--max-key-dist 0` = identical phonetic key only (tighter, less noise).
  `1` = near-match (broader, more noise). Start at 0 with the word list.
- `--max-per-target 8` caps proposals per term — recommended with the word
  list, which otherwise returns dozens of obscure dictionary words.
- `--max-surface-dist N` drops candidates whose spelling is wildly different
  in length from the target.
- `--wordlist-min-len` / `--wordlist-max-len` bound dictionary word length
  (default 3-10). Acronyms rarely collide with very long words.

## Two output modes

- `--report` : human-readable curation sheet (target, phonetic key, ranked
  proposals with distances). This is what the wargame-experienced reviewer
  marks up. Also makes good bid evidence.
- default : raw `target_spelling1_spelling2_...` lines for the CTC-WS file.

## Remember

This is an **assist to expert curation, not a replacement**. The tool
proposes; the human keeps the plausible confusions, discards the noise, and
adds real mis-recognitions the algorithms miss. The Sprint 3 recordings feed
the actual observed errors back into `--candidates`, closing the loop.
```
