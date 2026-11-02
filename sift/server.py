from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from .search import Searcher


def make_handler(searcher: Searcher, corpus_name: str):
    page = resources.files("sift").joinpath("static/index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def _send(self, status: int, body: bytes, content_type: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, status: int = 200) -> None:
            self._send(status, json.dumps(payload).encode())

        def do_GET(self) -> None:
            url = urlparse(self.path)
            params = parse_qs(url.query)
            q = params.get("q", [""])[0][:200]
            if url.path in ("/", "/index.html"):
                self._send(200, page, "text/html; charset=utf-8")
            elif url.path == "/api/search":
                try:
                    k = max(1, min(50, int(params.get("k", ["10"])[0])))
                except ValueError:
                    return self._json({"error": "k must be a number"}, 400)
                self._json(asdict(searcher.search(q, k)))
            elif url.path == "/api/suggest":
                self._json(searcher.suggest(q))
            elif url.path == "/api/stats":
                idx = searcher.index
                self._json({"corpus": corpus_name, "documents": len(idx), "terms": len(idx.postings)})
            else:
                self._json({"error": "not found"}, 404)

    return Handler


def serve(searcher: Searcher, corpus_name: str, port: int = 8000, host: str = "127.0.0.1") -> None:
    server = ThreadingHTTPServer((host, port), make_handler(searcher, corpus_name))
    server.daemon_threads = True
    print(f"Sift is searching {len(searcher.index):,} documents at http://localhost:{server.server_port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
