"""Heuristic project-level technical object extraction for X++ text."""

from __future__ import annotations

import re

from .analyzer import (
    CONTROL_FLOW_KEYWORDS,
    IGNORED_CALL_NAMES,
    mask_comments_and_strings,
    unique_preserve_order,
)

TECHNICAL_OBJECT_KEYS = (
    "classes",
    "tables",
    "fields",
    "enums",
    "methods",
    "queries",
    "batch_jobs",
    "services",
)
TECHNICAL_OBJECT_PREFIXES = ("Invent", "WHS", "Sales", "Cust", "LFL")
QUERY_SUFFIXES = ("QueryBuilder",)
SERVICE_SUFFIXES = ("Service",)
BATCH_JOB_SUFFIXES = ("Controller", "Batch", "Job")
TABLE_SUFFIXES = ("Table", "Trans", "Line", "Header", "Jour", "Items")
ENUM_SUFFIXES = ("Enum",)

IDENTIFIER_RE = r"[A-Za-z_]\w*"
FIELD_ACCESS_RE = re.compile(rf"\b(?P<table>{IDENTIFIER_RE})\.(?P<field>{IDENTIFIER_RE})\b")
CLASS_METHOD_RE = re.compile(
    rf"\b(?P<class>{IDENTIFIER_RE})\s*(?P<separator>\.|::)\s*(?P<method>{IDENTIFIER_RE})\s*\("
)
METHOD_CALL_RE = re.compile(rf"\b(?P<method>{IDENTIFIER_RE})\s*\(")
IDENTIFIER_TOKEN_RE = re.compile(rf"\b{IDENTIFIER_RE}\b")
ENUM_REFERENCE_RE = re.compile(rf"\b(?P<enum>{IDENTIFIER_RE})\s*::\s*(?P<value>{IDENTIFIER_RE})\b")

_METHOD_EXCLUSIONS = {
    *CONTROL_FLOW_KEYWORDS,
    *IGNORED_CALL_NAMES,
    "new",
    "super",
}


def _empty_technical_objects() -> dict[str, list[str]]:
    return {key: [] for key in TECHNICAL_OBJECT_KEYS}


def _append_unique(target: list[str], value: str) -> None:
    if value and value.lower() not in {item.lower() for item in target}:
        target.append(value)


def _has_technical_prefix(identifier: str) -> bool:
    return identifier.startswith(TECHNICAL_OBJECT_PREFIXES)


def _has_camel_or_underscore_shape(identifier: str) -> bool:
    return "_" in identifier or bool(re.search(r"[a-z][A-Z]", identifier))


def _is_technical_identifier(identifier: str) -> bool:
    return _has_technical_prefix(identifier) and _has_camel_or_underscore_shape(identifier)


def _classify_identifier(identifier: str) -> str | None:
    if identifier.endswith(QUERY_SUFFIXES):
        return "queries"
    if identifier.endswith(SERVICE_SUFFIXES):
        return "services"
    if identifier.endswith(BATCH_JOB_SUFFIXES):
        return "batch_jobs"
    if identifier.endswith(ENUM_SUFFIXES):
        return "enums"
    if identifier.endswith(TABLE_SUFFIXES):
        return "tables"
    if _is_technical_identifier(identifier):
        return "classes"
    return None


def _normalize_field(table: str, field: str) -> str:
    return f"{table}.{field}"


def _dedupe_all(technical_objects: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: unique_preserve_order(technical_objects[key]) for key in TECHNICAL_OBJECT_KEYS}


def extract_technical_objects(text: str) -> dict[str, dict[str, list[str]]]:
    """Extract likely X++ technical objects from arbitrary project text.

    The extractor intentionally uses lightweight heuristics so it can process
    free-form project descriptions, snippets, and exported X++ source without a
    complete metadata model.
    """
    searchable_text = mask_comments_and_strings(text)
    technical_objects = _empty_technical_objects()

    field_table_identifiers: set[str] = set()
    for match in FIELD_ACCESS_RE.finditer(searchable_text):
        if re.match(r"\s*\(", searchable_text[match.end() :]):
            continue
        table = match.group("table")
        field = match.group("field")
        field_table_identifiers.add(table.lower())
        _append_unique(technical_objects["tables"], table)
        _append_unique(technical_objects["fields"], _normalize_field(table, field))

    for match in CLASS_METHOD_RE.finditer(searchable_text):
        method_name = match.group("method")
        if method_name.lower() in _METHOD_EXCLUSIONS:
            continue
        _append_unique(technical_objects["methods"], f"{match.group('class')}.{method_name}")

    for match in METHOD_CALL_RE.finditer(searchable_text):
        method_name = match.group("method")
        if method_name.lower() in _METHOD_EXCLUSIONS:
            continue
        prefix = searchable_text[max(0, match.start() - 2) : match.start()]
        if prefix.endswith(".") or prefix.endswith("::"):
            continue
        _append_unique(technical_objects["methods"], method_name)

    for match in ENUM_REFERENCE_RE.finditer(searchable_text):
        enum_name = match.group("enum")
        if enum_name.lower() not in _METHOD_EXCLUSIONS and enum_name.endswith(ENUM_SUFFIXES):
            _append_unique(technical_objects["enums"], enum_name)

    for match in IDENTIFIER_TOKEN_RE.finditer(searchable_text):
        identifier = match.group(0)
        if identifier.lower() in _METHOD_EXCLUSIONS:
            continue
        category = _classify_identifier(identifier)
        if category is None:
            continue
        if identifier.lower() in field_table_identifiers and category != "tables":
            continue
        _append_unique(technical_objects[category], identifier)

    return {"technical_objects": _dedupe_all(technical_objects)}
