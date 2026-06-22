# Pronunciation segmentation (`pronounce_seg.py`)

## Purpose

`pronounce_seg.py` converts a military acronym into the set of plausible spoken
forms used for phonetic matching in `altspell_gen.py`. It is the only part of
the pipeline that needs to change when the spoken-form model is updated.

---

## The problem it solves

Raw phonetic matching on the acronym string (the Phase 1 approach) fails in two
opposite ways:

- **Pronounceable acronyms** such as ISTAR are spoken "eye-STAR", not
  "eye-ess-tee-ay-are". Matching on the raw string "ISTAR" misses legitimate
  confusables and finds irrelevant near-homophones.
- **Pure initialisms** such as CBRN are spelled out letter-by-letter as
  "see-bee-are-en". The raw string "CBRN" is never spoken; matching on it
  found noise (e.g. "caburn") rather than real confusables (e.g. "seaborne").

Phase 2 fixes both by matching on what is actually *said*, not on what is
written.

---

## The insight

A familiar word embedded in an acronym attracts the pronunciation of surrounding
letters toward a hybrid form. ISTAR contains "STAR", so it is spoken "eye-STAR"
— the familiar word pulls the "IST" cluster into a single chunk rather than three
spelled letters. The more familiar and the longer the embedded word, the stronger
the pull.

---

## How it works

### Segmentation

The module runs a k-best dynamic-programming segmentation of the acronym letter
string. Each position in the string is filled by one of two segment types:

| Type | Description | Example | Base cost |
|------|-------------|---------|-----------|
| LETTER | Single spelled-out letter via `LETTER_SOUNDS` | `I` → "eye" | 1.0 (fixed) |
| CHUNK (unfamiliar) | A pronounceable substring | `ist` → "ist" | 0.65 |
| CHUNK (familiar word) | A word in `FAMILIAR_WORDS` | `star` → "star" | 0.45 |

A length discount of 0.04 per character beyond 2 is subtracted from chunk costs
(floored at 0.20). This gives a mild preference for longer chunks — "star" as
one familiar segment (cost 0.45 − 0.08 = 0.37) beats "s" + "tar" (0.65 + 0.61 =
1.26), because longer chunks imply fewer spelled-out letters. Segments are capped
at 8 characters.

### k-best output

The DP returns the k cheapest *distinct* segmentations, not just one.
"eye-STAR" vs "iss-tar" are both plausible — spoken ambiguity is real — so the
tool proposes both and the expert curates. The default is k=4.

### Spell-out guarantee

The full letter-by-letter spell-out is always appended to the output regardless
of what the DP produces. This ensures:

- Pure initialisms (CBRN, IED, ATGM) are always matched on how they are
  actually spoken.
- Vowel-led acronyms that look word-like (e.g. "ied") cannot have the spell-out
  silently underranked by the DP.

### Phonotactic filter (`pronounceable`)

Before a substring is eligible as a CHUNK segment, `pronounceable()` checks it
passes basic English phonotactics:

- It must contain at least one vowel (Y counts as a vowel).
- Every consonant cluster must be either a legal English onset, a legal coda, or
  splittable into a legal coda + legal onset (for internal clusters).

This is what prevents CBRN being segmented as a word: "cbrn", "cbr", and "brn"
all fail the vowel test, so the DP finds no pronounceable segments and the output
is the spell-out only.

---

## Example output

Run the module directly to see segmentations for the standard target list:

```
uv run python pronounce_seg.py
```

```
ISTAR
  0.49  I+STAR               -> "eye star"
  0.65  IS+TAR               -> "is tar"
  1.00  I+S+TAR              -> "eye ess tar"
  1.45  I+S+T+A+R            -> "eye ess tee ay are"

CBRN
  4.00  C+B+R+N              -> "see bee are en"

SITREP
  0.53  SIT+REP              -> "sit rep"
  0.89  SIT+R+E+P            -> "sit are ee pee"
  1.08  S+IT+REP             -> "ess it rep"
  1.45  S+I+T+R+E+P          -> "ess eye tee are ee pee"
```

---

## Data structures

### `LETTER_SOUNDS`

Maps each uppercase letter to its spoken name (UK conventions: "zed" not "zee",
"aitch" not "haitch"). This is the canonical copy — `altspell_gen.py` imports it
from here. Edit only in this file.

### `FAMILIAR_WORDS`

A curated set of short common English words that act as pronunciation attractors.
It is intentionally small: using the full 248k word list as attractors would make
obscure dictionary words attractors, producing implausible segmentations.

**To add an attractor:** add the word (lowercase) to `FAMILIAR_WORDS`. Only add
words that are genuinely common, appear as substrings in real target acronyms,
and where the attractor reflects observed spoken usage.

### `ONSETS` / `CODAS`

Sets of legal English consonant clusters at syllable boundaries. They cover the
most common English patterns. Extend if a target domain uses loanwords with
unusual clusters (e.g. Slavic names, technical terms).

### Cost constants

| Constant | Value | Meaning |
|---|---|---|
| `LETTER_COST` | 1.0 | Cost of spelling out one letter |
| `CHUNK_BASE` | 0.65 | Base cost of a pronounceable but unfamiliar chunk |
| `FAMILIAR_BASE` | 0.45 | Base cost of a familiar-word chunk (the attractor discount) |
| `LEN_DISCOUNT` | 0.04 | Per-character discount beyond 2 chars (maximal munch) |

---

## Public API

Only `spoken_forms()` is called by `altspell_gen.py`. The other functions are
internal but are tested directly.

| Function | Signature | Returns |
|---|---|---|
| `spoken_forms` | `(term, k=4)` | `[(cost, segs, rendering), ...]` — de-duplicated spoken forms, cheapest first, spell-out always included |
| `k_best_segmentations` | `(term, k=3, familiar=None)` | `[(cost, [segs]), ...]` — raw DP output, no spell-out guarantee |
| `render` | `(segments)` | `str` — space-separated spoken string from a segment list |
| `pronounceable` | `(chunk)` | `bool` — True if chunk has a vowel and legal consonant clusters |

`spoken_forms` returns 3-tuples: cost (float), segments (list of substrings),
rendering (space-separated spoken string e.g. `"eye star"`). The rendering is
what `altspell_gen.py` passes to `doublemetaphone`.

---

## Known limitations

**W letter name.** The letter W is represented as the two-word string
"double you". When this is passed to `doublemetaphone()` as part of a longer
spoken form, the library drops the /juː/ phoneme, giving W the same phonetic key
as the word "double". Any acronym with W in a spell-out position should be
verified manually. The current target list contains no such acronyms.

**Segment length cap.** The DP considers segments of up to 8 characters.
Acronym substrings longer than 8 characters cannot be treated as a single chunk.
No common military acronym has a pronounceable substring exceeding this length.
