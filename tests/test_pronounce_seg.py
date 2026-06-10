"""
Gold-standard tests for DN-PHON-001 Phase 2: pronunciation segmentation.

The gold standard encodes how these military acronyms are ACTUALLY spoken
in British military usage. The segmenter must propose the real spoken form
among its candidates (it may propose others too -- the tool proposes,
the expert curates -- but the truth must be on the list).
"""

import pytest

from pronounce_seg import pronounceable, spoken_forms
from altspell_gen import generate_confusions, looks_like_acronym, term_forms


# --- gold standard: real pronunciations ------------------------------------

GOLD = {
    # hybrid: spelled letter + familiar word attractor
    "ISTAR":   "eye star",
    # pronounced as words (fully pronounceable / clipped compounds)
    "ORBAT":   "orbat",
    "OPFOR":   "opfor",
    "SITREP":  "sitrep",
    "CASEVAC": "casevac",
    "MEDEVAC": "medevac",
    "SAM":     "sam",
    # letter-by-letter initialisms (no pronounceable element, or convention)
    "CBRN":    "see bee are en",
    "IED":     "eye ee dee",
    "ATGM":    "ay tee gee em",
}


@pytest.mark.parametrize("acronym,expected", sorted(GOLD.items()))
def test_gold_pronunciation_is_proposed(acronym, expected):
    renderings = [r for _, _, r in spoken_forms(acronym)]
    assert expected in renderings, (
        f"{acronym}: real pronunciation {expected!r} missing from "
        f"proposals {renderings}"
    )


def test_cbrn_yields_only_the_spellout():
    """CBRN has no vowel, hence no pronounceable segment: the cost model
    must force the full spell-out with no word-like alternatives."""
    renderings = [r for _, _, r in spoken_forms("CBRN")]
    assert renderings == ["see bee are en"]


def test_full_spellout_always_present():
    """The letter-by-letter fallback is guaranteed for every acronym."""
    assert "eye ess tee ay are" in [r for _, _, r in spoken_forms("ISTAR")]
    assert "eye ee dee" in [r for _, _, r in spoken_forms("IED")]


# --- phonotactics unit tests ------------------------------------------------

@pytest.mark.parametrize("chunk", ["star", "tar", "bat", "rep", "vac", "orbat"])
def test_pronounceable_accepts_legal_chunks(chunk):
    assert pronounceable(chunk)


@pytest.mark.parametrize("chunk", ["cbrn", "tgm", "bd", "x", "kk"])
def test_pronounceable_rejects_illegal_chunks(chunk):
    assert not pronounceable(chunk)


# --- acronym detection -------------------------------------------------------

def test_acronym_detection():
    assert looks_like_acronym("CBRN")
    assert looks_like_acronym("IED")
    assert not looks_like_acronym("cassava")   # lowercase dictionary word
    assert not looks_like_acronym("A")          # too short
    assert not looks_like_acronym("C2")         # non-alphabetic


def test_non_acronyms_key_on_raw_string():
    forms = term_forms("cassava")
    assert len(forms) == 1 and forms[0][0] == "cassava"


# --- integration: the Phase 1 failures are now solved ------------------------

def test_cbrn_matches_seaborne_at_distance_zero():
    """Phase 1 found nothing usable for CBRN (all 15 hits discarded,
    'MANUAL NEEDED'). Matching on the spoken form must surface 'seaborne'
    as an exact phonetic-key match."""
    results = generate_confusions(["CBRN"], ["seaborne"], max_key_dist=0)
    assert "CBRN" in results
    cand, kd, _sd, _via = results["CBRN"][0]
    assert cand == "seaborne" and kd == 0


def test_cbrn_no_longer_hits_caburn_at_distance_zero():
    """Phase 1's false positives came from keying CBRN as if it were a
    word. With segmentation, 'caburn' must NOT match at distance 0."""
    results = generate_confusions(["CBRN"], ["caburn"], max_key_dist=0)
    assert "CBRN" not in results


def test_ied_matches_iud_via_spoken_forms():
    """Both sides are acronyms: IED and IUD must match through their
    spoken renderings."""
    results = generate_confusions(["IED"], ["IUD"], max_key_dist=0)
    assert "IED" in results
    assert results["IED"][0][0] == "IUD"


def test_no_pronounce_seg_reverts_to_phase1_behaviour():
    """The escape hatch: with use_seg=False, CBRN keys as a raw string
    and the old 'caburn' false positive returns."""
    results = generate_confusions(["CBRN"], ["caburn"], max_key_dist=0,
                                  use_seg=False)
    assert "CBRN" in results


def test_report_records_which_rendering_matched():
    results = generate_confusions(["CBRN"], ["seaborne"], max_key_dist=0)
    _cand, _kd, _sd, via = results["CBRN"][0]
    t_rend, c_rend = via
    assert t_rend == "see bee are en"
    assert c_rend == "seaborne"
