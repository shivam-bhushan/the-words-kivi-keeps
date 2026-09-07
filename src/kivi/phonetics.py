"""Phonetic matching for personal-term candidates.

We cluster surface forms by a phonetic code (metaphone) so that "Aditya" and
"Aaditya" -- or "Kiwi" and "Kivi" -- land in the same candidate cluster even
though ASR/formatting never produces identical spellings. Levenshtein distance
is used as a second gate so that phonetic collisions between unrelated short
words don't merge into one memory.
"""
import re

import jellyfish
from wordfreq import zipf_frequency

from kivi.config import COMMON_WORD_ZIPF_THRESHOLD, PHONETIC_MAX_EDIT_DISTANCE

TOKEN_RE = re.compile(r"[A-Za-z']+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def tokenize_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Tokens plus (start, end) character offsets, for span-exact replacement."""
    return [(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(text)]


def phonetic_key(word: str) -> str:
    return jellyfish.metaphone(word)


def surface_distance(a: str, b: str) -> int:
    return jellyfish.levenshtein_distance(a.lower(), b.lower())


def is_phonetic_match(a: str, b: str) -> bool:
    """True if two surface forms plausibly belong to the same spoken word.

    Exact metaphone match is not enough on its own: metaphone assigns different
    codes to kiwi/kivi (KW/KF), aditya/aaditya (ATTY/TTY) -- the exact pairs
    this system exists to cluster. So we also accept a near-miss metaphone
    (edit distance 1 between codes) when the surfaces share a first letter and
    are themselves within edit distance 1.
    """
    if a.lower() == b.lower():
        return True
    ka, kb = phonetic_key(a), phonetic_key(b)
    if ka == kb:
        return surface_distance(a, b) <= PHONETIC_MAX_EDIT_DISTANCE
    if jellyfish.levenshtein_distance(ka, kb) <= 1 and a[0].lower() == b[0].lower():
        return surface_distance(a, b) <= 1
    return False


def commonness(word: str) -> float:
    """Zipf frequency of word in general English (~1 rare .. ~7 extremely common)."""
    return zipf_frequency(word.lower(), "en")


def is_common_english_word(word: str) -> bool:
    return commonness(word) >= COMMON_WORD_ZIPF_THRESHOLD


def is_candidate_token(word: str, *, is_sentence_start: bool) -> bool:
    """Heuristic for 'this token might be a personal term worth remembering'.

    Candidates are: capitalized tokens not at sentence-start (proper-noun-like),
    or capitalized sentence-start tokens that are also rare in general English
    (catches names/products that happen to open a sentence).
    """
    if not word or not word[0].isalpha():
        return False
    if len(word) < 2:
        return False
    is_capitalized = word[0].isupper()
    if not is_capitalized:
        return False
    if not is_sentence_start:
        return True
    return not is_common_english_word(word)
