from __future__ import annotations

import bisect
import gzip
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from .text import tokens, words

TITLE_GAP = 1000
TITLE_WEIGHT = 3


@dataclass(frozen=True)
class Document:
    id: int
    title: str
    source: str
    text: str


class InvertedIndex:
    """Positional inverted index: term -> {doc id -> sorted token positions}.

    Title tokens occupy positions [0, title_len); body tokens start at TITLE_GAP,
    so phrases never match across the title/body boundary.
    """

    def __init__(self) -> None:
        self.docs: list[Document] = []
        self.postings: dict[str, dict[int, list[int]]] = defaultdict(dict)
        self.lengths: list[int] = []
        self.title_lengths: list[int] = []
        self.surface: Counter[str] = Counter()
        self._vocab: list[str] | None = None

    def add(self, title: str, source: str, text: str) -> Document:
        doc = Document(len(self.docs), title, source, text)
        title_terms, body_terms = tokens(title), tokens(text)
        for pos, term in enumerate(title_terms):
            self.postings[term].setdefault(doc.id, []).append(pos)
        for pos, term in enumerate(body_terms, start=TITLE_GAP):
            self.postings[term].setdefault(doc.id, []).append(pos)
        self.docs.append(doc)
        self.lengths.append(len(body_terms) + TITLE_WEIGHT * len(title_terms))
        self.title_lengths.append(len(title_terms))
        self.surface.update(set(w for w in words(title + " " + text) if len(w) > 2 and not w.isdigit()))
        self._vocab = None
        return doc

    def __len__(self) -> int:
        return len(self.docs)

    @property
    def avg_length(self) -> float:
        return sum(self.lengths) / len(self.lengths) if self.lengths else 0.0

    @property
    def vocabulary(self) -> list[str]:
        if self._vocab is None:
            self._vocab = sorted(self.surface)
        return self._vocab

    def doc_freq(self, term: str) -> int:
        return len(self.postings.get(term, ()))

    def idf(self, term: str) -> float:
        n, df = len(self.docs), self.doc_freq(term)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def weighted_tf(self, term: str, doc_id: int) -> int:
        positions = self.postings.get(term, {}).get(doc_id, ())
        title_hits = bisect.bisect_left(positions, TITLE_GAP)
        return len(positions) - title_hits + TITLE_WEIGHT * title_hits

    def with_prefix(self, prefix: str) -> list[str]:
        vocab = self.vocabulary
        start = bisect.bisect_left(vocab, prefix)
        end = bisect.bisect_left(vocab, prefix + "￿")
        return vocab[start:end]

    def save(self, path: str | Path) -> None:
        payload = {"version": 1, "docs": [asdict(d) for d in self.docs]}
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh)

    @classmethod
    def load(cls, path: str | Path) -> "InvertedIndex":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        index = cls()
        for d in payload["docs"]:
            index.add(d["title"], d["source"], d["text"])
        return index
