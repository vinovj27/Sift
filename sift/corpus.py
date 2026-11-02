from __future__ import annotations

import ast
import sysconfig
from pathlib import Path
from typing import Iterator

from .index import InvertedIndex

SKIP_DIRS = {"test", "tests", "idlelib", "lib2to3", "site-packages", "dist-packages", "__pycache__", "ensurepip", "turtledemo"}
TEXT_SUFFIXES = {".md", ".txt", ".rst"}


def stdlib_root() -> Path:
    return Path(sysconfig.get_paths()["stdlib"])


def _module_name(root: Path, file: Path) -> str:
    parts = list(file.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def python_docs(root: Path, module_prefix: str = "") -> Iterator[tuple[str, str, str]]:
    """Yield (title, source, text) for each documented module, class and public function.

    Source files are parsed with `ast`, never imported, so no module code runs.
    """
    for file in sorted(root.rglob("*.py")):
        if SKIP_DIRS.intersection(file.relative_to(root).parts) or file.name.startswith("_") and file.name != "__init__.py":
            continue
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError, OSError):
            continue
        module = module_prefix + _module_name(root, file)
        if not module or any(p.startswith("_") for p in module.split(".")):
            continue
        source = str(file)
        doc = ast.get_docstring(tree)
        if doc:
            yield module, source, doc
        for node in tree.body:
            yield from _node_docs(node, module, source)


def _node_docs(node: ast.AST, prefix: str, source: str) -> Iterator[tuple[str, str, str]]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name.startswith("_"):
        return
    name = f"{prefix}.{node.name}"
    doc = ast.get_docstring(node)
    if doc and len(doc) > 20:
        signature = ""
        if not isinstance(node, ast.ClassDef):
            signature = f"({', '.join(a.arg for a in node.args.args if a.arg != 'self')})"
        yield name + signature, f"{source}:{node.lineno}", doc
    if isinstance(node, ast.ClassDef):
        for child in node.body:
            yield from _node_docs(child, name, source)


def text_docs(root: Path) -> Iterator[tuple[str, str, str]]:
    for file in sorted(root.rglob("*")):
        if file.suffix.lower() in TEXT_SUFFIXES and file.is_file() and not SKIP_DIRS.intersection(file.parts):
            text = file.read_text(encoding="utf-8", errors="replace")
            first = next((line.strip("# ").strip() for line in text.splitlines() if line.strip()), file.stem)
            yield first[:120], str(file), text


def build_stdlib() -> InvertedIndex:
    index = InvertedIndex()
    for title, source, text in python_docs(stdlib_root()):
        index.add(title, source, text)
    return index


def build_folder(folder: str | Path) -> InvertedIndex:
    root = Path(folder).resolve()
    index = InvertedIndex()
    for title, source, text in text_docs(root):
        index.add(title, source, text)
    for title, source, text in python_docs(root):
        index.add(title, source, text)
    return index
