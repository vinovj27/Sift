# Sift

A full-text search engine built from scratch in Python: positional inverted index, BM25 ranking, phrase and boolean queries, typo correction, autocomplete and an instant-search web UI. Standard library only.

Out of the box it indexes the **Python standard library's own documentation** — about 4,000 modules, classes and functions, read with `ast` so no library code runs — so you can try it with nothing to download. Point it at any folder to search your own notes or code.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen) ![Tests](https://img.shields.io/badge/tests-16%20passing-brightgreen)

```
$ python -m sift search "serialize object to json"
Indexed 3,930 documents from Python standard library in 2.1s

652 results in 3.7 ms

1. json.dump(obj, fp)  (13.546)
   Serialize ``obj`` as a JSON formatted stream to ``fp`` …
```

## Features

| Feature | How |
|---|---|
| **Ranking** | Okapi BM25 (k1 = 1.2, b = 0.75) with title matches weighted 3× |
| **Phrases** | `"thread pool"` matches only adjacent words, using token positions |
| **Boolean** | `+socket` must appear, `-ftp` must not |
| **Stemming** | A light suffix stripper, so *parse*, *parsing* and *parsed* match each other |
| **Code-aware tokens** | `ThreadPoolExecutor` and `read_file` are split into searchable words |
| **Typo correction** | "Did you mean" via bounded Levenshtein distance over the vocabulary, ranked by frequency |
| **Autocomplete** | Prefix lookup by binary search over the sorted vocabulary |
| **Snippets** | The best window of text with matches highlighted and HTML-escaped |
| **Persistence** | `sift build` saves a gzipped index file; `--index` loads it |

Queries over the standard-library corpus return in 1–5 ms.

## Run it

Python 3.10 or newer, no installs needed.

```bash
python -m sift serve                          # web UI at http://localhost:8000
python -m sift search '"thread pool"'         # search from the terminal
python -m sift search "subprocesss timout"    # → Did you mean: subprocess timeout
python -m sift serve --folder ~/notes         # search your own .md/.txt/.rst/.py files
python -m sift build --folder ~/notes -o notes.json.gz
python -m unittest discover -s tests          # run the tests
```

Or install the `sift` command with `pip install .`.

## How it works

```
documents ─▶ tokenize (split identifiers, lowercase, drop stopwords, stem)
          ─▶ inverted index   term → { doc id → [positions] }
query     ─▶ parse (+required, -excluded, "phrases")
          ─▶ candidate set from postings ─▶ filter phrases/required/excluded
          ─▶ BM25 score ─▶ top k ─▶ highlighted snippets
```

Title tokens sit at positions 0…n and body tokens start at 1000, so a phrase can never match across the title and body boundary, and title hits can be weighted separately.

## Layout

```
sift/
├── text.py      tokenizer and stemmer
├── index.py     positional inverted index, save/load
├── search.py    query parser, BM25, phrases, snippets, did-you-mean, autocomplete
├── corpus.py    standard-library and folder indexers
├── server.py    JSON API + web UI
└── static/index.html
tests/           ranking, parsing, stemming, corpus quality and HTTP API tests
```

## Next steps

- Store postings in a compressed on-disk format (delta + varint) instead of rebuilding on load
- Proximity scoring so query words close together rank higher
- A web crawler that respects robots.txt to index sites
