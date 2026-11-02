import argparse
import html
import time
from pathlib import Path

from .corpus import build_folder, build_stdlib
from .index import InvertedIndex
from .search import Searcher


def load(args) -> tuple[InvertedIndex, str]:
    start = time.perf_counter()
    if getattr(args, "index", None):
        index, name = InvertedIndex.load(args.index), Path(args.index).name
    elif getattr(args, "folder", None):
        index, name = build_folder(args.folder), Path(args.folder).resolve().name
    else:
        index, name = build_stdlib(), "Python standard library"
    print(f"Indexed {len(index):,} documents from {name} in {time.perf_counter() - start:.1f}s")
    return index, name


def main() -> None:
    parser = argparse.ArgumentParser(prog="sift", description="Full-text search engine with BM25 ranking")
    sub = parser.add_subparsers(dest="command", required=True)

    def source_args(p):
        group = p.add_mutually_exclusive_group()
        group.add_argument("--folder", help="index .md/.txt/.rst/.py files in this folder (default: Python standard library)")
        group.add_argument("--index", help="load a saved index file")

    s = sub.add_parser("serve", help="run the search web app")
    source_args(s)
    s.add_argument("--port", type=int, default=8000)

    q = sub.add_parser("search", help="search from the terminal")
    source_args(q)
    q.add_argument("query")
    q.add_argument("-k", type=int, default=8)

    b = sub.add_parser("build", help="build an index and save it to a file")
    b.add_argument("--folder")
    b.add_argument("-o", "--output", default="sift-index.json.gz")

    args = parser.parse_args()
    if args.command == "build":
        index, _ = load(args)
        index.save(args.output)
        print(f"Saved to {args.output}")
        return

    index, name = load(args)
    searcher = Searcher(index)
    if args.command == "serve":
        from .server import serve

        serve(searcher, name, args.port)
        return

    results = searcher.search(args.query, args.k)
    print(f"\n{results.total:,} results in {results.took_ms:.1f} ms")
    if results.suggestion:
        print(f"Did you mean: {results.suggestion}")
    for i, hit in enumerate(results.hits, 1):
        snippet = html.unescape(hit.snippet.replace("<mark>", "\033[1;33m").replace("</mark>", "\033[0m"))
        print(f"\n{i}. {hit.title}  ({hit.score})\n   {hit.source}\n   {snippet}")
    print()


if __name__ == "__main__":
    main()
