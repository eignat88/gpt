"""Heuristic classifier for X++ exports and project-description documents."""

from __future__ import annotations

import re

CLASS_XPP = "class_xpp"
PROJECT_DESCRIPTION = "project_description"
MIXED_DOCUMENT = "mixed_document"

# Strong AOT/XPO export markers that are unlikely to appear in prose.
AOT_MARKER_PATTERNS = (
    re.compile(r"(?im)^\s*\*\*\*Element:\s*CLS\b"),
    re.compile(r"(?im)^\s*CLASS\s+#\S+"),
    re.compile(r"(?im)^\s*SOURCE\s+#\S+"),
)

# METHODS is a weaker marker because it can also be an ordinary word in
# requirements. Treat it as an AOT marker only when it appears as a section line.
METHODS_SECTION_RE = re.compile(r"(?im)^\s*METHODS\s*$")

PROJECT_MARKER_PATTERNS = (
    # Work-item identifiers and support/document families common in project specs.
    re.compile(r"(?i)\bDAX-\d+\b"),
    re.compile(r"\b(?:FD|SUP)(?:[-_\s]?\d+)?\b"),
    # Requirement/specification headings in Russian and English.
    re.compile(
        r"(?im)^\s*(?:#+\s*)?"
        r"(?:требован(?:ие|ия)|функциональн(?:ое|ые)\s+требован(?:ие|ия)|requirements?)\b"
    ),
    re.compile(r"(?im)^\s*(?:#+\s*)?(?:цель|цели|goals?|objectives?)\b"),
    re.compile(r"(?im)^\s*(?:#+\s*)?(?:алгоритм|алгоритмы|algorithm)s?\b"),
    re.compile(
        r"(?im)^\s*(?:#+\s*)?(?:бизнес[-\s]?процесс(?:ы)?|business\s+process(?:es)?)\b"
    ),
    re.compile(
        r"(?im)^\s*(?:#+\s*)?(?:постановка|описание\s+проекта|project\s+description)\b"
    ),
)


def _has_xpp_markers(text: str) -> bool:
    return any(pattern.search(text) for pattern in AOT_MARKER_PATTERNS) or bool(
        METHODS_SECTION_RE.search(text)
    )


def _has_project_description_markers(text: str) -> bool:
    return any(pattern.search(text) for pattern in PROJECT_MARKER_PATTERNS)


def classify_document(text: str) -> str:
    """Classify a document as X++ source export, project prose, or a mixture.

    The classifier intentionally uses transparent markers instead of trying to
    parse the entire document. If both X++/AOT export markers and project
    description markers are present, the document is considered mixed.
    Documents without explicit X++ markers are treated as project descriptions,
    which keeps plain text and weakly marked specifications in the prose bucket.
    """
    has_xpp_markers = _has_xpp_markers(text)
    has_project_markers = _has_project_description_markers(text)

    if has_xpp_markers and has_project_markers:
        return MIXED_DOCUMENT
    if has_xpp_markers:
        return CLASS_XPP
    return PROJECT_DESCRIPTION
