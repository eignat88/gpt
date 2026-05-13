"""Document classification helpers for exported X++/AOT artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .class_parser import SOURCE_METHOD_RE, extract_class_info, normalize_xpo_source


class DocumentKind(str, Enum):
    """Supported high-level document categories."""

    CLASS = "class"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DocumentClassification:
    """Classification result for a source document."""

    kind: DocumentKind
    name: str | None = None
    reason: str | None = None


def classify_document(source: str) -> DocumentClassification:
    """Classify raw exported text as an AOT document type."""
    normalized_source = normalize_xpo_source(source)
    class_info = extract_class_info(source)
    class_name = class_info.get("name")
    if class_name:
        return DocumentClassification(kind=DocumentKind.CLASS, name=class_name, reason="class metadata found")
    if SOURCE_METHOD_RE.search(normalized_source):
        return DocumentClassification(kind=DocumentKind.CLASS, reason="SOURCE method sections found")
    return DocumentClassification(kind=DocumentKind.UNKNOWN, reason="no supported AOT markers found")


__all__ = ["DocumentClassification", "DocumentKind", "classify_document"]
