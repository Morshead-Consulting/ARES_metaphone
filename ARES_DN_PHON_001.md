# Design Note — Phonetic-Edge ASR Correction

**ID:** ARES-DN-PHON-001
**Status:** Design note (informs the alternative-spelling map and the Phase 2 correction layer)
**Date:** 2026-06-06
**Related:** ARES-DDR-ASR-001 (ASR choice), Option B prototype v3, ARES context graph (Layer 4), Phase 2 analytical layer (Layer 5)
**Prompted by:** MedSpeak (Song et al., arXiv:2602.00981v2, Apr 2026) — knowledge-graph-aided ASR error correction for spoken medical QA.

---

## 1. Purpose

ARES currently handles military-vocabulary recognition with a hand-authored **alternative-spelling map** consumed by CTC-WS context-biasing at ASR time. This note describes how to (a) **generate** that map more systematically using phonetic algorithms rather than relying solely on hand-enumeration, and (b) extend the same phonetic information into the ARES context graph as **phonetic edges**, providing a citable, structured basis for the deferred Phase 2 semantic-correction layer.

The technique is adapted from MedSpeak, which encodes both semantic and phonetic relationships between medical terms in a knowledge graph and uses them to correct ASR confusions between phonetically similar terms (e.g. *hypertension* / *hypotension*, *chorioretinitis* / *chorioamnionitis*). The military-acronym problem is the direct analogue.

## 2. Two placements — keep them distinct

The single most important design decision is **where** phonetic correction runs. There are two placements, and they must not be conflated:

| | **Phase 1 — ASR-time (live)** | **Phase 2 — post-session (offline)** |
|---|---|---|
| Mechanism | CTC-WS context-biasing on the hybrid CTC head | LLM-plus-graph correction (Llama 3.1 + context graph) |
| Input | Alternative-spelling map (flat term list) | Retrieved phonetic + semantic graph edges |
| Latency | Inside the sub-10-second loop — must be cheap | No real-time constraint |
| Hardware | Single RTX 4090, shared with diarisation | Post-session batch on the same GPU |
| MedSpeak parallel | (MedSpeak does not do this) | This is essentially MedSpeak's method |

**MedSpeak's correction is entirely the right-hand column.** Its LLM correction pass ran on a cluster of 8× A100 80GB GPUs — wholly incompatible with the ARES live budget. Nothing from MedSpeak's runtime belongs in the Phase 1 hot path. What Phase 1 borrows is only the *method for generating phonetic candidates* (§3), not the LLM correction step.

## 3. Phase 1 — generating the alternative-spelling map

Rather than hand-enumerating every likely mis-recognition, generate candidates and have domain experts curate. The MedSpeak recipe:

1. **Double Metaphone** over each target term (scenario acronyms *and* the game-mechanical register) to produce phonetic keys and surface similar-sounding English words/phrases.
2. **Levenshtein distance** as a second filter — MedSpeak notes Double Metaphone *alone* produced excessive false positives, so the two are combined to tighten matching.
3. **Expert curation** — the wargame-experienced personnel keep the plausible confusions, discard the noise, and add real mis-recognitions the algorithms miss (the human step remains essential; this is an assist, not a replacement).
4. **Emit** the curated confusions into the CTC-WS context file in the existing `target_spelling1_spelling2_...` format.

This makes the alternative-spelling map more complete, less dependent on individual memory, and defensible as a rigorous deliverable rather than an ad-hoc list. The Sprint 3 live recordings still feed back the *actual* observed mis-recognitions, closing the loop.

**Cost:** small. Double Metaphone and Levenshtein are trivial, well-understood algorithms (e.g. `metaphone`, `python-Levenshtein`) with no provenance or licensing concern. The work is the curation, which the team is already doing by hand — this makes it faster and more thorough, not more expensive.

## 4. Phase 2 — phonetic edges in the context graph

For the deferred analytical layer, extend the ARES context graph with explicit **phonetic edges**, mirroring MedSpeak's KG:

- Nodes already exist for terms/entities in the semantic layer.
- Add edges tagged **`phonetic`** linking terms that are confusable by sound (generated as in §3).
- At post-session correction time, when a term is uncertain, retrieve its phonetic neighbours *and* its semantic neighbours, and present both to the LLM (Llama 3.1) so it can disambiguate using sound **and** meaning together — e.g. distinguishing two similar-sounding acronyms by which one fits the surrounding operational context.

This gives the Phase 2 correction layer a concrete, published architecture rather than a vague "post-session phonetic→acronym correction" placeholder. It also fits the existing ARES context-graph design: the phonetic edge is just another typed edge alongside the semantic relations, consistent with reserving "knowledge graph" for the semantic layer and "ARES context graph" for the whole.

## 5. Grounded expectations

MedSpeak's headline 93.4% is **answer-selection accuracy** on multiple-choice QA — not transcription accuracy, and not the ARES use case. The relevant figures are its **WER** results:

- Raw ASR (Whisper small, no correction): **7.72%**
- Fine-tuned LLM, no graph: **3.58%**
- Fine-tuned LLM + semantic/phonetic graph: **2.99%**

Two honest reads from this:
- The **graph contribution over fine-tuning alone is ~0.6 WER points** — real, consistent, but modest. The graph is a refinement, not the main event.
- **Most of MedSpeak's gain came from fine-tuning** the LLM, which ARES is *not* planning. So ARES should not expect MedSpeak-scale WER from the graph alone, and should not quote MedSpeak's numbers as if they were ARES's. They establish that the *approach* works, not what ARES will achieve.

## 6. Recommendations

1. **Phase 1, now:** adopt Double Metaphone + Levenshtein as a generation step for the alternative-spelling map, expert-curated. Low cost, improves a named deliverable.
2. **Phase 2, deferred:** specify phonetic edges in the context graph and LLM-plus-graph post-session correction, with MedSpeak as the reference architecture. Keep this firmly out of the live loop.
3. **Evidence discipline:** cite MedSpeak as concept-validation for graph-aided correction; quote its ~0.6-point graph-over-fine-tuning WER delta, never the 93% answer-accuracy headline.
4. **Verify before relying:** MedSpeak's results are self-reported on a synthetic benchmark and not independently checked here; treat as a strong supporting reference, not settled proof.

## 7. Caveats

- The §3 generation step is an **assist to expert curation**, not an automation of it — Double Metaphone's false-positive rate is the reason the human step stays.
- The term-graph **source** matters for provenance: MedSpeak used UMLS (NIH); ARES builds its own military lexicon, which sidesteps that dependency but should still be provenance-reviewed.
- The Phase 2 correction layer depends on the deferred Llama 3.1 / Graph RAG layer being funded; until then this is design intent, not committed capability.
