# DN-PHON-001 Phase 2 — Pronunciation segmentation

## Insight

Familiar pronunciations embedded within an acronym attract the whole
pronunciation toward a hybrid form: ISTAR contains the familiar word STAR,
so it is spoken "eye-STAR", not "eye-ess-tee-ay-are". CBRN contains no
pronounceable element (no vowel), so it is spelled out letter by letter.
Phase 1 keyed every target as if it were an ordinary word, which is why
CBRN, IED and ATGM produced nothing usable ("MANUAL NEEDED" in the Phase 1
curation report). Matching must operate on what is SAID, not on the letter
string.

## What changed

1. **New module `pronounce_seg.py`** — k-best dynamic-programming
   segmentation of each acronym into spelled letters and pronounceable
   chunks. Pronounceability = contains a vowel and all consonant clusters
   are legal English onsets/codas; familiar dictionary words get a cost
   discount (the attractor). The full letter-by-letter spell-out is always
   included as a fallback. Several segmentations are returned, not one:
   eye-STAR vs iss-tar is genuinely ambiguous and resolving it is a
   curation decision.

2. **`altspell_gen.py` matches on spoken forms** — every spoken form of
   the target is compared against every spoken form of the candidate
   (acronym-like candidates such as IUD get the same treatment). The
   report records *which* renderings matched (`via "see bee are en"`).
   Candidate phonetic keys are now precomputed once (faster than Phase 1).
   `--no-pronounce-seg` reverts to Phase 1 behaviour. `--use-spellouts`
   is retained but largely superseded.

3. **Optional frequency ranking** — Phase 1 curation showed the dominant
   keep/discard criterion was "is this a common word an ASR would
   plausibly emit". If `wordfreq` is installed, hits are ranked
   common-first and the report shows a Zipf score; without it, behaviour
   is unchanged. *Licence note for Sprint 1 review: wordfreq code is MIT
   but its frequency data aggregates CC-licensed sources — dev-time
   ranking aid only, nothing ships in the delivered system.*

4. **Gold-standard tests** (`tests/test_pronounce_seg.py`, 30 tests) —
   the real pronunciation of all ten targets must appear among the
   proposals; CBRN must yield only its spell-out; the Phase 1 failures
   (CBRN→seaborne, IED→IUD) must now match at key-distance 0 and the
   Phase 1 false positive (CBRN→caburn) must not.

## Results vs Phase 1 (same word list, max_key_dist=0)

| Target | Phase 1 | Phase 2 |
|---|---|---|
| CBRN | 15 hits, all discarded, "MANUAL NEEDED" | sabrina, siberian, soprano, seaborne, spurn — plausible confusions of "see bee are en" |
| IED | only IUD kept (accidental) | idea, yet, add (+ IUD via spoken forms) |
| ATGM | only atm kept | outcome via "at gee em" (+ atm) |
| ISTAR | aster, astir, ester | + easter, oyster, esther (via word-form keying), ranked common-first |

## Known limitations (state honestly in the bid)

- No silent-e, schwa-reduction ("MED-uh-vac") or stress modelling;
  Double Metaphone's coarseness absorbs most of this.
- DM keys for very short spell-outs are coarse: IED's key matches some
  short high-frequency words (out, what). Mitigate with
  `--max-surface-dist` or curation; observed Sprint 3 errors remain the
  ground truth.
- The familiar-word seed list should grow to a frequency-filtered slice
  of the cached word list plus military vocabulary.

## Doc updates needed

- README: replace the `--use-spellouts` quick-start with plain
  `--use-wordlist` runs; document `--no-pronounce-seg`; add `wordfreq`
  as an optional dev dependency; note the spoken-forms line and `via`
  annotation in the report format.
- CURATION_HOWTO: the report now shows `spoken as:` per target, a Zipf
  column (if wordfreq installed), and `via` annotations explaining
  rendering-level matches (including occasional spell-out-fallback noise
  for word-like acronyms, e.g. CASEVAC's "sisyphus" — discard on sight).
