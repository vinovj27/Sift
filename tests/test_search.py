import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from sift import InvertedIndex, Searcher, build_folder, build_stdlib, parse
from sift.server import make_handler
from sift.text import stem, tokens


def corpus() -> InvertedIndex:
    idx = InvertedIndex()
    idx.add("Brewing coffee", "a.md", "Coffee beans are ground and brewed with hot water. Coffee coffee coffee.")
    idx.add("Green tea", "b.md", "Tea leaves are steeped in hot water. Some people add milk to black tea.")
    idx.add("Cold brew", "c.md", "Cold brew coffee steeps ground beans in cold water for twelve hours.")
    idx.add("Water filters", "d.md", "Filtered water improves the taste of both coffee and tea.")
    for i in range(6):
        idx.add(f"Note {i}", f"n{i}.md", "Unrelated text about gardening, tomatoes and soil.")
    return idx


class TextTests(unittest.TestCase):
    def test_stemming_groups_word_forms(self):
        self.assertEqual(stem("parsing"), stem("parsed"))
        self.assertEqual(stem("parses"), stem("parse"))
        self.assertEqual(stem("files"), stem("file"))
        self.assertEqual(stem("creation"), stem("create"))
        self.assertEqual(stem("class"), "class")

    def test_tokens_split_identifiers_and_drop_stopwords(self):
        self.assertEqual(tokens("ThreadPoolExecutor"), [stem("thread"), stem("pool"), stem("executor")])
        self.assertEqual(tokens("read_file"), [stem("read"), stem("file")])
        self.assertNotIn("the", tokens("the cat"))


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.s = Searcher(corpus())

    def titles(self, q):
        return [h.title for h in self.s.search(q).hits]

    def test_term_frequency_and_title_boost_rank_first(self):
        self.assertEqual(self.titles("coffee")[0], "Brewing coffee")

    def test_rare_terms_outweigh_common_ones(self):
        self.assertEqual(self.titles("water milk")[0], "Green tea")

    def test_phrase_requires_adjacent_words(self):
        self.assertEqual(self.titles('"cold brew"'), ["Cold brew"])
        self.assertEqual(self.titles('"brew cold"'), [])

    def test_required_and_excluded_terms(self):
        self.assertEqual(set(self.titles("+coffee tea")), {"Brewing coffee", "Cold brew", "Water filters"})
        self.assertNotIn("Water filters", self.titles("coffee -filtered"))

    def test_stemmed_queries_match_other_forms(self):
        self.assertIn("Cold brew", self.titles("steeping"))

    def test_snippet_highlights_and_escapes(self):
        idx = InvertedIndex()
        idx.add("x", "x", "Use <script> tags carefully with coffee")
        snip = Searcher(idx).search("coffee").hits[0].snippet
        self.assertIn("<mark>coffee</mark>", snip)
        self.assertIn("&lt;script&gt;", snip)

    def test_did_you_mean_only_for_unknown_words(self):
        self.assertEqual(self.s.search("cofee").suggestion, "coffee")
        self.assertIsNone(self.s.search("coffee").suggestion)

    def test_autocomplete_ranks_by_frequency(self):
        self.assertEqual(self.s.suggest("co")[0], "coffee")
        self.assertEqual(self.s.suggest("x"), [])

    def test_query_parser(self):
        q = parse('+socket "thread pool" -ftp timeout')
        self.assertEqual(q.required, ["socket"])
        self.assertEqual(q.phrases, [["thread", "pool"]])
        self.assertEqual(q.excluded, ["ftp"])
        self.assertEqual(parse('unbalanced "quote').terms, tokens("unbalanced quote"))

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "idx.json.gz"
            self.s.index.save(path)
            loaded = Searcher(InvertedIndex.load(path))
            self.assertEqual([h.title for h in loaded.search("coffee").hits], self.titles("coffee"))


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Searcher(build_stdlib())

    def test_stdlib_corpus_answers_real_questions(self):
        self.assertGreater(len(self.s.index), 1000)
        top = [h.title for h in self.s.search("serialize object to json", 5).hits]
        self.assertTrue(any(t.startswith("json.dump") for t in top), top)
        top = [h.title for h in self.s.search("parse command line arguments", 5).hits]
        self.assertTrue(any(t.startswith(("argparse", "getopt")) for t in top), top)

    def test_search_is_fast(self):
        self.assertLess(self.s.search("http server request handler").took_ms, 100)

    def test_folder_indexing(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "notes.md").write_text("# Kafka notes\nConsumer groups rebalance partitions.")
            (Path(tmp) / "tool.py").write_text('"""Rotate log files nightly."""\n')
            s = Searcher(build_folder(tmp))
            self.assertEqual(s.search("rebalance").hits[0].title, "Kafka notes")
            self.assertEqual(s.search("rotate logs").hits[0].title, "tool")


class ApiTests(unittest.TestCase):
    def test_http_api(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Searcher(corpus()), "test"))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            def get(path):
                with urllib.request.urlopen(base + path) as resp:
                    return json.loads(resp.read())

            r = get("/api/search?q=cold%20brew")
            self.assertEqual(r["hits"][0]["title"], "Cold brew")
            self.assertEqual(get("/api/suggest?q=co")[0], "coffee")
            self.assertEqual(get("/api/stats")["documents"], 10)
            with urllib.request.urlopen(base + "/") as resp:
                self.assertIn(b"<title>Sift</title>", resp.read())
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
