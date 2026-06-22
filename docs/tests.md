# Test suite

## Running

```
uv run pytest tests/ -v
```

All tests run offline. `wordfreq` is optional — the suite does not depend on it
(the one sort-order test that would be sensitive to it zeroes out `zipf` via
monkeypatch; see below).

---

## Structure

| File | What it tests |
|---|---|
| `tests/test_pronounce_seg.py` | Gold-standard pronunciations, phonotactics, and the Phase 1 → Phase 2 integration story |
| `tests/test_altspell_gen.py` | Unit tests for every public function in `altspell_gen.py` |

---

## `test_pronounce_seg.py`

### Gold standard

The `GOLD` dictionary encodes how each target acronym is **actually spoken** in
British military usage:

```python
GOLD = {
    "ISTAR":   "eye star",      # hybrid: letter + familiar-word attractor
    "ORBAT":   "orbat",         # fully pronounceable
    "SITREP":  "sitrep",
    "CASEVAC": "casevac",
    "MEDEVAC": "medevac",
    "SAM":     "sam",
    "OPFOR":   "opfor",
    "CBRN":    "see bee are en", # pure initialism — no pronounceable element
    "IED":     "eye ee dee",
    "ATGM":    "ay tee gee em",
}
```

`test_gold_pronunciation_is_proposed` (parametrised over every entry) asserts
that the real pronunciation appears somewhere in `spoken_forms(acronym)`. The
segmenter is allowed to propose other forms alongside it — the tool proposes,
the expert curates — but the truth must be on the list.

**If this test fails:** the cost model or `FAMILIAR_WORDS` no longer ranks the
real pronunciation among the k-best segmentations. Check whether a recent change
to cost constants or the familiar-words set has underranked the expected form.

**If the real pronunciation changes** (e.g. a new operational convention for an
acronym): update `GOLD`. The gold standard records consensus military usage, not
an algorithmic output, so it should only change when human authority says so.

**To add a new target:** add it to `GOLD` with its correct spoken form, then
run the tests. If the gold test fails immediately, the segmenter is not finding
the right form — investigate cost constants or add the key word to
`FAMILIAR_WORDS` in `pronounce_seg.py`.

### Strictness tests

`test_cbrn_yields_only_the_spellout` is the strictest single test in the suite:
it asserts that `spoken_forms("CBRN")` returns **exactly one form** — the
letter-by-letter spell-out. Any other output would mean the phonotactic filter
is passing illegal consonant clusters. CBRN has no vowel at all; no segment of
it can pass `pronounceable()`.

`test_full_spellout_always_present` asserts the spell-out guarantee holds for
both a hybrid acronym (ISTAR) and a pure initialism (IED). This is the fallback
that ensures initialisms are matched on how they are actually said.

### Phonotactics unit tests

Two parametrised tests exercise `pronounceable()` directly:

- Legal chunks (`"star"`, `"orbat"`, `"vac"`, ...): the phonotactic filter must
  accept these.
- Illegal chunks (`"cbrn"`, `"tgm"`, `"bd"`, ...): the filter must reject these.
  Failures here would mean illegal consonant clusters are being accepted as chunk
  segments, producing nonsense spoken forms.

### Acronym detection

`test_acronym_detection` checks `looks_like_acronym()` for true positives (CBRN,
IED) and false positives that must be excluded: a lowercase word ("cassava"), a
single letter ("A"), and an alphanumeric token ("C2").

`test_non_acronyms_key_on_raw_string` confirms that a dictionary word passed
through `term_forms()` is keyed as its raw string, not segmented.

### Phase 1 failure regression tests

These four tests encode the failures that motivated Phase 2, and must continue
to pass:

| Test | What it verifies |
|---|---|
| `test_cbrn_matches_seaborne_at_distance_zero` | Matching on the spoken form "see bee are en" finds "seaborne" at key_dist=0, the primary Phase 2 win for pure initialisms |
| `test_cbrn_no_longer_hits_caburn_at_distance_zero` | The Phase 1 false positive ("caburn" from raw-string keying of "CBRN") is gone with segmentation on |
| `test_ied_matches_iud_via_spoken_forms` | Cross-acronym matching: IED and IUD both get spoken forms and match through them |
| `test_no_pronounce_seg_reverts_to_phase1_behaviour` | With `use_seg=False`, the old "caburn" false positive returns — confirming the escape hatch (`--no-pronounce-seg`) genuinely reverts behaviour |

`test_report_records_which_rendering_matched` checks that the `via` field in the
`generate_confusions` output records the correct rendering pair — this is what
drives the `via "see bee are en"` annotation in the proposals report.

---

## `test_altspell_gen.py`

### `spell_out`

Three boundary cases: basic acronym, UK "zed" (not "zee"), non-alphabetic
characters (dots in "I.E.D" must be stripped), and empty string.

### `phonetic_keys`

Checks the contract: a non-empty list for a real word; no blank strings in the
list; empty list for an empty string. Does not pin exact key values (those are
the library's responsibility).

### `key_edit_distance`

Four cases: identical word → 0; a known near-homophone pair (SAM / psalm) within
distance 1; empty string → sentinel 99; unrelated words above threshold.

### `generate_confusions`

| Test | What it pins |
|---|---|
| `test_generate_confusions_excludes_self` | A target must not appear as its own candidate |
| `test_generate_confusions_finds_known_confusable` | "psalm" must be found for SAM at max_key_dist=1 |
| `test_generate_confusions_max_per_target_caps_results` | `max_per_target=2` must cap the hit list |
| `test_generate_confusions_max_surface_dist_filters` | `max_surface_dist=1` must exclude "psalm" (surface_dist=2 from "SAM") |
| `test_generate_confusions_no_match_absent_from_results` | A target with no hits must be absent from the results dict (not present with an empty list) |
| `test_generate_confusions_sorted_by_key_dist_then_surface_dist` | Hits must be ordered `(key_dist, surface_dist)` ascending |

The sort-order test uses `monkeypatch.setattr(altspell_gen, "zipf", lambda word: 0.0)`.
Without this, the actual sort key is `(key_dist, -zipf(cand), surface_dist)`, and
the order would depend on whether `wordfreq` is installed and on word frequencies
that can change between releases. Zeroing `zipf` makes the test environment-independent
without changing any production behaviour.

### `emit_ctcws`

Single hit, multiple hits, empty input, and an end-to-end integration test that
chains a real `generate_confusions` call into `emit_ctcws` and checks the output
line starts with `SAM_` and contains "psalm". The integration test also validates
that the 4-tuple shape `(cand, key_dist, surface_dist, via)` from
`generate_confusions` is what `emit_ctcws` receives in production.

The unit tests supply `None` as the `via` element in their fixture tuples
(`("psalm", 0, 1, None)`) because `emit_ctcws` only accesses `h[0]` (the
candidate string). This is pinned so that a future change to the tuple shape
that breaks `emit_ctcws` would be caught here.

### `load_wordlist`

Four tests using `tmp_path`:

- Words within the length bounds are included.
- Words shorter than `min_len` are excluded.
- Words longer than `max_len` are excluded.
- Missing cache file with `allow_download=False` exits (`SystemExit`).

These tests supply a local file path; no network calls are made.
