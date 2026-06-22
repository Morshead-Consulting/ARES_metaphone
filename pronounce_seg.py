#!/usr/bin/env python3
"""
pronounce_seg.py -- k-best pronunciation segmentation for military acronyms.

Converts a term such as ISTAR into its plausible spoken forms ("eye star",
"is tar", ...) by segmenting the letter string using dynamic programming.
See docs/pronounce_seg.md for algorithm details, cost constants, and guidance
on extending FAMILIAR_WORDS.

Public entry point: spoken_forms(term, k=4) -- called by altspell_gen.py.
"""

import heapq

# Canonical letter-sound table (imported by altspell_gen.py — edit here only).
# Known limitation: 'W' renders as the two-word string 'double you'. When this
# is passed to doublemetaphone() as part of a longer spoken form, the library
# drops the /juː/ phoneme ('you'), so W-bearing acronyms in spell-out position
# receive an incomplete phonetic key. In practice the current target lists
# contain no W-bearing acronyms, so impact is nil, but any future target with
# W in spell-out position should be verified manually.
LETTER_SOUNDS = {
    'A': 'ay', 'B': 'bee', 'C': 'see', 'D': 'dee', 'E': 'ee', 'F': 'eff',
    'G': 'gee', 'H': 'aitch', 'I': 'eye', 'J': 'jay', 'K': 'kay', 'L': 'el',
    'M': 'em', 'N': 'en', 'O': 'oh', 'P': 'pee', 'Q': 'cue', 'R': 'are',
    'S': 'ess', 'T': 'tee', 'U': 'you', 'V': 'vee', 'W': 'double you',
    'X': 'ex', 'Y': 'why', 'Z': 'zed',
}

VOWELS = set("aeiouy")

# Legal English syllable onsets (consonant clusters that may start a syllable)
ONSETS = {
    "", "b", "c", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p", "q",
    "r", "s", "t", "v", "w", "x", "y", "z",
    "bl", "br", "ch", "cl", "cr", "dr", "dw", "fl", "fr", "gl", "gr",
    "kl", "kn", "kr", "ph", "pl", "pr", "qu", "sc", "sh", "sk", "sl",
    "sm", "sn", "sp", "st", "sw", "th", "tr", "tw", "wh", "wr",
    "sch", "scr", "shr", "spl", "spr", "squ", "str", "thr",
}

# Legal English syllable codas (clusters that may end a syllable) -- pragmatic set
CODAS = {
    "", "b", "c", "d", "f", "g", "k", "l", "m", "n", "p", "r", "s", "t",
    "v", "x", "z",
    "ch", "ck", "ct", "ft", "ld", "lf", "lk", "lm", "lp", "lt", "mp",
    "nd", "ng", "nk", "nt", "pt", "rb", "rd", "rf", "rg", "rk", "rl",
    "rm", "rn", "rp", "rt", "sh", "sk", "sp", "st", "th", "ts", "gm",
    "lts", "mps", "nds", "nts", "rst", "sts",
}

# Small set of very common words used as "familiarity attractors".
# In the real tool this would be (a) this seed set plus (b) a frequency-
# filtered slice of the cached word list -- NOT the full 248k list, which
# would treat obscure words as attractors.
FAMILIAR_WORDS = {
    "star", "tar", "bat", "or", "for", "op", "case", "vac", "med", "sit",
    "rep", "sam", "at", "is", "an", "in", "on", "it", "car", "van", "arm",
    "air", "sea", "gun", "map", "net", "ops", "rad", "bar", "ban", "tab",
    "cat", "rat", "ram", "jam", "tan", "ten", "tin", "ton", "men", "man",
}


def _legal_consonant_run(run: str, leading: bool, trailing: bool) -> bool:
    """A consonant run is fine if it's a legal onset (leading), legal coda
    (trailing), or splittable into legal coda + legal onset (internal)."""
    if leading:
        return run in ONSETS
    if trailing:
        return run in CODAS
    return any(run[:i] in CODAS and run[i:] in ONSETS
               for i in range(len(run) + 1))


def pronounceable(chunk: str) -> bool:
    """True if `chunk` could plausibly be read aloud as a word in English:
    contains a vowel, and every consonant cluster is phonotactically legal."""
    s = chunk.lower()
    if not s.isalpha() or not any(c in VOWELS for c in s):
        return False
    # walk the string splitting into consonant runs and vowel runs
    runs, i = [], 0
    while i < len(s):
        j = i
        is_vowel = s[i] in VOWELS
        while j < len(s) and (s[j] in VOWELS) == is_vowel:
            j += 1
        runs.append((is_vowel, s[i:j]))
        i = j
    for idx, (is_vowel, run) in enumerate(runs):
        if is_vowel:
            continue
        if not _legal_consonant_run(run, leading=(idx == 0),
                                    trailing=(idx == len(runs) - 1)):
            return False
    return True


# --- segment costs ----------------------------------------------------------

LETTER_COST = 1.0          # one spelled-out letter
CHUNK_BASE = 0.65          # pronounceable but not a familiar word
FAMILIAR_BASE = 0.45       # familiar word: the attractor discount
LEN_DISCOUNT = 0.04        # mild preference for longer chunks (maximal munch)


def segment_cost(seg: str, familiar: set) -> float | None:
    """Cost of treating `seg` as one segment, or None if not allowed."""
    if len(seg) == 1:
        return LETTER_COST
    if not pronounceable(seg):
        return None
    base = FAMILIAR_BASE if seg.lower() in familiar else CHUNK_BASE
    return max(0.2, base - LEN_DISCOUNT * (len(seg) - 2))


def k_best_segmentations(term: str, k: int = 3, familiar: set = None):
    """k-best DP over the letter string. Returns [(cost, [segments])],
    cheapest first. Each segment is the original substring."""
    if familiar is None:
        familiar = FAMILIAR_WORDS
    t = "".join(c for c in term if c.isalpha())
    n = len(t)
    best = [[] for _ in range(n + 1)]   # best[i] = list of (cost, segs) up to i
    best[0] = [(0.0, [])]
    for i in range(1, n + 1):
        cands = []
        for j in range(max(0, i - 8), i):
            seg = t[j:i]
            c = segment_cost(seg, familiar)
            if c is None:
                continue
            for prev_cost, prev_segs in best[j]:
                cands.append((prev_cost + c, prev_segs + [seg]))
        best[i] = heapq.nsmallest(k, cands, key=lambda x: x[0])
    return best[n]


def render(segments: list) -> str:
    """Spoken form: spelled letters via LETTER_SOUNDS, chunks as themselves."""
    out = []
    for seg in segments:
        if len(seg) == 1:
            out.append(LETTER_SOUNDS.get(seg.upper(), seg.lower()))
        else:
            out.append(seg.lower())
    return " ".join(out)


def spoken_forms(term: str, k: int = 4) -> list:
    """De-duplicated spoken renderings of the k-best segmentations,
    cheapest first, ALWAYS including the full letter-by-letter spell-out
    as a fallback. Spell-out is how letter-initialisms (IED, CBRN) are
    actually spoken, and the DP can underrank it for vowel-led acronyms
    that look spuriously word-like (\"ied\"). Guaranteeing it costs one
    extra proposal per target; curation discards it where unused.
    This is what altspell_gen.py should key on."""
    seen, forms = set(), []
    for cost, segs in k_best_segmentations(term, k=k):
        r = render(segs)
        if r not in seen:
            seen.add(r)
            forms.append((cost, segs, r))
    letters = [c for c in term if c.isalpha()]
    spellout = render(letters)
    if spellout not in seen:
        forms.append((float(len(letters)), letters, spellout))
    return forms


if __name__ == "__main__":
    targets = ["ISTAR", "ORBAT", "CASEVAC", "CBRN", "OPFOR",
               "SITREP", "MEDEVAC", "SAM", "IED", "ATGM"]
    for t in targets:
        print(t)
        for cost, segs, r in spoken_forms(t):
            print(f"    {cost:5.2f}  {'+'.join(segs):20s} -> \"{r}\"")
        print()
