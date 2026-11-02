from __future__ import annotations

import re

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)

STOPWORDS = frozenset("""
a an and are as at be but by for from has have if in into is it its of on or such that the their then there
these they this to was were will with which who whom this those than so not no can may might should would
""".split())

_SUFFIXES = (
    ("ational", "ate"), ("tional", "tion"), ("ization", "ize"), ("fulness", "ful"), ("iveness", "ive"),
    ("ousness", "ous"), ("ations", "ate"), ("ation", "ate"), ("ements", ""), ("ement", ""), ("ments", ""),
    ("ment", ""), ("ingly", ""), ("edly", ""), ("ings", ""), ("ing", ""), ("ies", "y"), ("ied", "y"),
    ("sses", "ss"), ("ers", ""), ("er", ""), ("ed", ""), ("ly", ""), ("es", ""), ("s", ""),
)


def stem(word: str) -> str:
    """A light suffix-stripping stemmer: maps 'parse', 'parsing', 'parsed' and 'parses' to 'pars'."""
    if len(word) <= 3 or word.isdigit():
        return word
    for suffix, repl in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) + len(repl) >= 3:
            if suffix == "s" and word.endswith(("ss", "us", "is")):
                continue
            word = word[: -len(suffix)] + repl
            break
    if len(word) >= 4 and word.endswith("e") and not word.endswith("ee"):
        word = word[:-1]
    return word


def tokens(text: str) -> list[str]:
    """Lowercase word tokens, splitting snake_case and camelCase identifiers into parts."""
    out = []
    for raw in TOKEN.findall(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)):
        word = raw.lower()
        if word not in STOPWORDS:
            out.append(stem(word))
    return out


def words(text: str) -> list[str]:
    return [w.lower() for w in TOKEN.findall(text)]
