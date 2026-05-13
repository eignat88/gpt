"""Project-level parsing helpers for collections of X++/AOT files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .class_parser import analyze_source, normalize_xpo_source
from .document_classifier import DocumentClassification, classify_document

DEFAULT_SOURCE_PATTERNS = ("*.xpo", "*.txt", "*.xpp")


@dataclass(frozen=True)
class ParsedDocument:
    """Parsed source file and its analyzer result."""

    path: Path
    classification: DocumentClassification
    analysis: dict


def iter_source_files(root: Path, patterns: Iterable[str] = DEFAULT_SOURCE_PATTERNS) -> list[Path]:
    """Return source files below ``root`` in deterministic order."""
    if root.is_file():
        return [root]

    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in root.rglob(pattern) if path.is_file())
    return sorted(files)


def parse_project(root: Path, *, include_source: bool = True) -> list[ParsedDocument]:
    """Analyze all supported source files under ``root``."""
    documents: list[ParsedDocument] = []
    for path in iter_source_files(root):
        source = path.read_text(encoding="utf-8", errors="ignore")
        normalized_source = normalize_xpo_source(source)
        documents.append(
            ParsedDocument(
                path=path,
                classification=classify_document(source),
                analysis=analyze_source(normalized_source, include_source=include_source),
            )
        )
    return documents


__all__ = ["DEFAULT_SOURCE_PATTERNS", "ParsedDocument", "iter_source_files", "parse_project"]
