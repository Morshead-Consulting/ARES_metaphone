# Producing a CTC-WS context file

## What you are making

A **CTC-WS context file** tells the ASR engine which English words to watch
for alongside each military acronym. When the engine hears something that
sounds like SITREP, it should also consider "strap", "strip", "strep", and
so on. This file delivers that list. The document below explains how to
produce it from a list of target acronyms.

---

## Pipeline overview

| Step | What happens | Who/what does it | Mandatory? |
|------|-------------|------------------|------------|
| 1 | Generate a human-readable proposals list | `altspell_gen.py --report` | Yes |
| 2 | Pre-tag proposals [KEEP] / [DISCARD] / [UNCERTAIN] | LLM (optional labour-saver) | No |
| 3 | Review proposals; keep, discard, add missed confusables | Expert reviewer | Yes |
| 4 | Generate the same proposals in CTC-WS format | `altspell_gen.py` (no `--report`) | Yes |
| 5 | Remove discarded candidates; load into ASR system | Expert reviewer | Yes |

Steps 1 and 4 run the same script with the same parameters; the only
difference is the output format. Step 1 produces a rich annotated file for
human review; Step 4 produces the machine-readable format the ASR system
reads. Steps 2 and 3 happen between them; Step 5 applies the Step 3
decisions to the Step 4 output.

---

## Step 1 — Generate the proposals list (mandatory)

**Input:** `data/targets.txt` — one military acronym per line (normalised to
uppercase automatically, so mixed-case entries are accepted)  
**Output:** `data/reports/targets_YYYYMMDD_HHMMSS_curation_report.txt`

```
uv run python altspell_gen.py --targets data/targets.txt --use-wordlist --max-key-dist 0 --max-per-target 15 --report --output-dir data/reports
```

The tool runs Double Metaphone phonetic matching against an English word
list and writes one block per target. The file is timestamped so successive
runs do not overwrite each other. The path is echoed to stderr.

Install `wordfreq` before running (`uv add wordfreq` or
`pip install wordfreq`). Without it the output still works, but the `zipf`
frequency scores — the single most useful signal when judging candidates —
will not appear.

### What the proposals list looks like

```
ISTAR  spoken as: "istar" | "is tar" | "eye star" | "eye ess tee ay are"
    <- aster                   key_dist=0 surface_dist=4 zipf=3.9  via "eye star"
    <- astir                   key_dist=0 surface_dist=4 zipf=2.1  via "eye star"
    <- estrepe                 key_dist=0 surface_dist=6 zipf=0.0  via "eye star"
```

| Field | Meaning |
|---|---|
| `spoken as:` | The pronunciations tested for this acronym. Word-like acronyms (ISTAR, SITREP) are tested as full words and in syllable splits; pure initialisms (CBRN, IED) fall back to their letter-by-letter spell-out ("see bee are en") |
| `candidate` | A word from the English word list whose phonetic key matched one of the target's spoken forms |
| `key_dist` | Levenshtein distance between the two Double Metaphone keys (0 = identical sound; 1 = one-phoneme near-match) |
| `surface_dist` | Levenshtein distance between the raw strings — a rough guide to how visually different they are |
| `zipf` | Word frequency (≥3.5 common; <2.0 obscure; 0 = not a recognised word) |
| `via "..."` | Which spoken form of the target produced the match, shown when it differs from the raw acronym |

Proposals are ranked: exact phonetic match first, then most-common word
first, then surface closeness. Each target is capped at 15 proposals
(`--max-per-target 15`).

---

## Step 2 — AI pre-annotation (optional)

A general-purpose LLM can pre-tag every candidate `[KEEP]` / `[DISCARD]` /
`[UNCERTAIN]` before you begin, clearing obvious noise quickly and letting
you focus on genuine judgement calls. This is a labour-saver for large
target lists; it is not a replacement for expert review.

This step is kept deliberately outside the tool. `altspell_gen.py` is
deterministic and offline; keeping AI assistance as a separate manual step
means the tool's output remains fully auditable.

**Record provenance.** Save the AI-tagged file alongside the original (e.g.
`..._curation_report_annotated.txt`) and note which model tagged it and who
reviewed it. "Machine-suggested, human-approved" is an honest and
defensible description.

### How to do it

1. Take the proposals list from Step 1.
2. Paste it into the LLM with the prompt below.
3. Save the returned annotated file.
4. **Review every tag before trusting it** — especially `[KEEP]` tags,
   since a false keep pollutes the final context file.

### Suggested prompt

```
You are helping pre-annotate a proposals list for an automatic speech
recognition (ASR) project. Each TARGET is a military acronym. Beneath it
are candidate English words the ASR engine might output INSTEAD of the
acronym because they sound similar. A human reviewer will check your work
afterwards; your job is a consistent first-pass draft, not the final
decision.

For every candidate line, append exactly one tag and a short rationale:

  [KEEP]       a real, reasonably common English word (or legitimate
               variant) that an ASR engine could plausibly emit for the
               spoken acronym
  [DISCARD]    not a plausible ASR output — e.g. a non-word, a very
               obscure or technical term, a proper noun, an archaic
               spelling, a foreign word, or a "spellout artefact" (a match
               via the letter-by-letter spoken form rather than a real word)
  [UNCERTAIN]  plausible only under a condition the reviewer must confirm
               (e.g. depends on whether an abbreviation is in local use)

Rationale style — keep it terse (2-6 words), consistent, and drawn from
this vocabulary where it fits:
  "very common word, plausible ASR slip" / "common word, plausible"
  "real English word, plausible" / "legitimate variant of <word>"
  "non-word" / "too obscure" / "proper noun" / "archaic, unlikely ASR output"
  "<field> term, too obscure" (e.g. chemistry, botanical, maths)
  "spellout artefact, not an ASR output"
  "redundant if <other candidate> kept"
  "sounds too different"

Rules:
  - Judge plausibility by how the ACRONYM is spoken (shown in the
    "spoken as:" line), not by spelling. Use the zipf score as the main
    commonness signal: zipf >= 3.5 is common, < 2 is obscure, 0 means not
    a known word (almost always [DISCARD]).
  - Tag EVERY candidate. Do not add, remove, reorder or re-rank lines.
  - Preserve the original layout exactly; only append the tag + rationale.
  - Where a whole target block is weak or empty (common for pure initialisms
    such as CBRN, IED, ATGM), add a note:
    "# MANUAL NEEDED: add real mis-recognitions from recorded audio."
  - Do not invent candidates the report does not contain.

Output the annotated report only. Here is the report:

<paste the proposals list here>
```

**What the LLM cannot do:** it has no access to your operational
vocabulary, your unit's communication habits, or real recordings. Treat the
AI pass as a way to clear obvious noise; the final call on every candidate
is yours.

---

## Step 3 — Expert review (mandatory)

Work through the proposals list (or its AI-annotated version) and for each
candidate ask: **could an ASR engine plausibly output this word instead of
the acronym in a military-comms context?**

**Keep** a candidate if:
- It sounds like the acronym when spoken aloud, AND
- It is a word an ASR language model might plausibly predict (high `zipf`
  is the main signal).

**Discard** a candidate if:
- `zipf` is near 0 — not a word an ASR engine would emit.
- It matched only via the spell-out fallback and is not a realistic
  mis-recognition. Word-like acronyms (e.g. CASEVAC) occasionally produce
  artefacts such as "sisyphus" `via "see ay ess ee vee ay see"` — discard
  these on sight.
- It is phonetically close but operationally implausible.

**Add** any real mis-recognitions from your recordings that the algorithm
did not surface. The algorithm gives a useful starting set even for pure
initialisms, but observed errors from real audio are the ground truth and
must be included.

> **Short-acronym caution:** SAM, IED and similar short acronyms have
> coarse phonetic keys that attract many short common words. Lean heavily on
> `zipf` and operational judgement. Consider re-running with
> `--max-surface-dist` to trim the noise if needed.

---

## Step 4 — Generate the CTC-WS draft (mandatory)

**Input:** `data/targets.txt` (same file as Step 1)  
**Output:** `data/reports/targets_YYYYMMDD_HHMMSS_ctcws.txt`

Run the same command as Step 1, omitting `--report`:

```
uv run python altspell_gen.py --targets data/targets.txt --use-wordlist --max-key-dist 0 --max-per-target 15 --output-dir data/reports
```

This produces the same candidates as Step 1 in the format the ASR system
reads — one line per target, acronym and candidates joined by underscores:

```
TARGET_spelling1_spelling2_...
```

For example:

```
ISTAR_astare_aster_astir_astor_astr_astur_ester_ostara_uster_wister_asteer_astore_astray_astre_auster
ORBAT_orbate_orbit_orbed_orbite_orbity_orpit_airboat_arabit_arbith_arbota_arbute_erept_erupt_jarbot_aerobate
CASEVAC_zyzzyvas_sisyphus_zizyphus
SITREP_strep_satrap_strap_streep_strip_strop_estrepe_satrapy_stirp_stirrup_stripe_strype_stripy_stroup_strub
SAM_saim_same_samh_saum_seam_sem_siam_sim_sym_soam_sum_swam_asem_assam_ism
```

This file is a **draft**. It contains all algorithm proposals including
ones you will discard in Step 5. The variation in candidate counts is
expected: targets with a distinctive phonetic key produce few proposals;
short acronyms produce many.

---

## Step 5 — Edit the draft and load into the ASR system (mandatory)

Open the `_ctcws.txt` draft from Step 4 alongside your reviewed proposals
list from Step 3. For each line:

- Delete any candidate you marked `[DISCARD]`.
- Add any real mis-recognitions you identified in Step 3 that are not
  already present.

The result is the **CTC-WS context file** — the deliverable. Paste the
edited lines into the context file the ASR system reads at inference time,
replacing or extending any existing hand-authored entries.
