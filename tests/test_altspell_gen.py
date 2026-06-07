import pytest

from altspell_gen import (
    emit_ctcws,
    generate_confusions,
    key_edit_distance,
    load_wordlist,
    phonetic_keys,
    spell_out,
)


# ---------------------------------------------------------------------------
# spell_out
# ---------------------------------------------------------------------------

def test_spell_out_basic_acronym():
    assert spell_out("IED") == "eye ee dee"

def test_spell_out_uk_zed():
    assert spell_out("Z") == "zed"

def test_spell_out_ignores_non_alpha():
    assert spell_out("I.E.D") == "eye ee dee"

def test_spell_out_empty():
    assert spell_out("") == ""


# ---------------------------------------------------------------------------
# phonetic_keys
# ---------------------------------------------------------------------------

def test_phonetic_keys_returns_nonempty_list():
    keys = phonetic_keys("SAM")
    assert len(keys) > 0

def test_phonetic_keys_no_blank_strings():
    keys = phonetic_keys("SAM")
    assert all(k for k in keys)

def test_phonetic_keys_empty_string_returns_empty():
    assert phonetic_keys("") == []


# ---------------------------------------------------------------------------
# key_edit_distance
# ---------------------------------------------------------------------------

def test_key_edit_distance_same_word_is_zero():
    assert key_edit_distance("SAM", "SAM") == 0

def test_key_edit_distance_known_confusable_pair():
    # "psalm" and "SAM" share a near-identical phonetic key; should match
    # within the default max_key_dist=1 window
    assert key_edit_distance("SAM", "psalm") <= 1

def test_key_edit_distance_no_phonetic_key_returns_sentinel():
    # Empty string produces no phonetic key — sentinel value 99
    assert key_edit_distance("", "SAM") == 99

def test_key_edit_distance_unrelated_words_above_threshold():
    assert key_edit_distance("ISTAR", "cat") > 1


# ---------------------------------------------------------------------------
# generate_confusions
# ---------------------------------------------------------------------------

def test_generate_confusions_excludes_self():
    results = generate_confusions(["SAM"], ["SAM", "psalm"], max_key_dist=1)
    hits = results.get("SAM", [])
    assert all(c.lower() != "sam" for c, _, _ in hits)

def test_generate_confusions_finds_known_confusable():
    results = generate_confusions(["SAM"], ["psalm"], max_key_dist=1)
    assert "SAM" in results

def test_generate_confusions_max_per_target_caps_results():
    candidates = ["psalm", "salmon", "slim", "slime", "samba"]
    results = generate_confusions(["SAM"], candidates, max_key_dist=2, max_per_target=2)
    assert len(results.get("SAM", [])) <= 2

def test_generate_confusions_max_surface_dist_filters():
    # "psalm" surface dist from "SAM" is 2; cap at 1 should exclude it
    results = generate_confusions(
        ["SAM"], ["psalm"], max_key_dist=1, max_surface_dist=1
    )
    hits = results.get("SAM", [])
    assert all(sd <= 1 for _, _, sd in hits)

def test_generate_confusions_no_match_absent_from_results():
    results = generate_confusions(["XYZZY"], ["cat", "dog"], max_key_dist=0)
    assert "XYZZY" not in results

def test_generate_confusions_sorted_by_key_dist_then_surface_dist():
    candidates = ["psalm", "slim", "samba"]
    results = generate_confusions(["SAM"], candidates, max_key_dist=2)
    hits = results.get("SAM", [])
    if len(hits) >= 2:
        for i in range(len(hits) - 1):
            assert (hits[i][1], hits[i][2]) <= (hits[i + 1][1], hits[i + 1][2])


# ---------------------------------------------------------------------------
# emit_ctcws
# ---------------------------------------------------------------------------

def test_emit_ctcws_single_hit():
    results = {"SAM": [("psalm", 0, 1)]}
    assert emit_ctcws(results) == ["SAM_psalm"]

def test_emit_ctcws_multiple_hits():
    results = {"SAM": [("psalm", 0, 1), ("samba", 1, 2)]}
    assert emit_ctcws(results) == ["SAM_psalm_samba"]

def test_emit_ctcws_empty_input():
    assert emit_ctcws({}) == []


# ---------------------------------------------------------------------------
# load_wordlist
# ---------------------------------------------------------------------------

def test_load_wordlist_includes_words_within_bounds(tmp_path):
    wl = tmp_path / "words.txt"
    wl.write_text("hi\ncat\nfoo\nelephant\n", encoding="utf-8")
    result = load_wordlist(str(wl), allow_download=False, min_len=3, max_len=4)
    assert "cat" in result
    assert "foo" in result

def test_load_wordlist_excludes_words_too_short(tmp_path):
    wl = tmp_path / "words.txt"
    wl.write_text("hi\ncat\n", encoding="utf-8")
    result = load_wordlist(str(wl), allow_download=False, min_len=3, max_len=10)
    assert "hi" not in result

def test_load_wordlist_excludes_words_too_long(tmp_path):
    wl = tmp_path / "words.txt"
    wl.write_text("cat\nelephant\n", encoding="utf-8")
    result = load_wordlist(str(wl), allow_download=False, min_len=3, max_len=4)
    assert "elephant" not in result

def test_load_wordlist_missing_cache_no_download_exits(tmp_path):
    missing = str(tmp_path / "missing.txt")
    with pytest.raises(SystemExit):
        load_wordlist(missing, allow_download=False, min_len=3, max_len=10)
