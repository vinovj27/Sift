from __future__ import annotations

import html
import re
import shlex
import time
from dataclasses import dataclass, field

from .index import InvertedIndex
from .text import stem, tokens, words

K1 = 1.2
B = 0.75


@dataclass
class Query:
    terms: list[str] = field(default_factory=list)
    required: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    phrases: list[list[str]] = field(default_factory=list)
    raw_words: list[str] = field(default_factory=list)


@dataclass
class Hit:
    doc_id: int
    title: str
    source: str
    score: float
    snippet: str


@dataclass
class Results:
    query: str
    hits: list[Hit]
    total: int
    took_ms: float
    suggestion: str | None = None


def parse(q: str) -> Query:
    """Supports plain terms, +required, -excluded and "quoted phrases"."""
    try:
        parts = shlex.split(q)
    except ValueError:
        parts = q.replace('"', " ").split()
    query = Query()
    for raw in parts:
        if " " in raw:
            phrase = tokens(raw)
            if phrase:
                query.phrases.append(phrase)
                query.terms.extend(phrase)
                query.raw_words.extend(words(raw))
            continue
        bucket = query.terms
        if raw.startswith("+"):
            raw, bucket = raw[1:], query.required
        elif raw.startswith("-"):
            raw, bucket = raw[1:], query.excluded
        terms = tokens(raw)
        bucket.extend(terms)
        if bucket is query.required:
            query.terms.extend(terms)
        if bucket is not query.excluded:
            query.raw_words.extend(words(raw))
    return query


class Searcher:
    def __init__(self, index: InvertedIndex) -> None:
        self.index = index

    def search(self, q: str, k: int = 10) -> Results:
        start = time.perf_counter()
        query = parse(q)
        idx = self.index
        candidates: set[int] = set()
        for term in query.terms:
            candidates.update(idx.postings.get(term, {}))
        for term in query.required:
            candidates &= set(idx.postings.get(term, {}))
        for phrase in query.phrases:
            candidates = {d for d in candidates if self._has_phrase(phrase, d)}
        for term in query.excluded:
            candidates -= set(idx.postings.get(term, {}))

        avg = idx.avg_length or 1.0
        scored = []
        for doc_id in candidates:
            norm = K1 * (1 - B + B * idx.lengths[doc_id] / avg)
            score = 0.0
            for term in set(query.terms):
                tf = idx.weighted_tf(term, doc_id)
                if tf:
                    score += idx.idf(term) * tf * (K1 + 1) / (tf + norm)
            score *= 1 + 0.5 * len(query.phrases)
            scored.append((score, doc_id))
        scored.sort(key=lambda s: (-s[0], s[1]))

        hits = [Hit(d, idx.docs[d].title, idx.docs[d].source, round(s, 3), self.snippet(d, query))
                for s, d in scored[:k]]
        suggestion = self.did_you_mean(query)
        return Results(q, hits, len(scored), (time.perf_counter() - start) * 1000, suggestion)

    def suggest(self, prefix: str, limit: int = 8) -> list[str]:
        prefix = prefix.lower().strip()
        if len(prefix) < 2:
            return []
        matches = self.index.with_prefix(prefix)
        return sorted(matches, key=lambda w: -self.index.surface[w])[:limit]

    def did_you_mean(self, query: Query) -> str | None:
        fixed, changed = [], False
        for word in query.raw_words:
            if self.index.doc_freq(stem(word)) > 0 or len(word) < 4:
                fixed.append(word)
                continue
            best = self._closest(word)
            if best:
                fixed.append(best)
                changed = True
            else:
                fixed.append(word)
        return " ".join(fixed) if changed else None

    def _closest(self, word: str) -> str | None:
        best, best_key = None, None
        surface = self.index.surface
        for cand in self.index.vocabulary:
            if abs(len(cand) - len(word)) > 2 or cand[0] != word[0] or surface[cand] < 3:
                continue
            dist = _edit_distance(word, cand, limit=2)
            if dist <= 2:
                key = (dist, -surface[cand])
                if best_key is None or key < best_key:
                    best, best_key = cand, key
        return best

    def _has_phrase(self, phrase: list[str], doc_id: int) -> bool:
        lists = [self.index.postings.get(t, {}).get(doc_id) for t in phrase]
        if not all(lists):
            return False
        rest = [set(p) for p in lists[1:]]
        return any(all(start + i + 1 in rest[i] for i in range(len(rest))) for start in lists[0])

    def snippet(self, doc_id: int, query: Query, width: int = 220) -> str:
        text = " ".join(self.index.docs[doc_id].text.split())
        stems = set(query.terms)
        matches = [m for m in re.finditer(r"[^\W_]+", text) if stem(m.group().lower()) in stems]
        start = max(0, matches[0].start() - 60) if matches else 0
        if start:
            start = text.find(" ", start) + 1
        window = text[start:start + width]
        out, last = [], 0
        for m in re.finditer(r"[^\W_]+", window):
            if stem(m.group().lower()) in stems:
                out.append(html.escape(window[last:m.start()]))
                out.append(f"<mark>{html.escape(m.group())}</mark>")
                last = m.end()
        out.append(html.escape(window[last:]))
        prefix = "…" if start else ""
        suffix = "…" if start + width < len(text) else ""
        return prefix + "".join(out) + suffix


def _edit_distance(a: str, b: str, limit: int) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


__all__ = ["Hit", "Query", "Results", "Searcher", "parse"]
