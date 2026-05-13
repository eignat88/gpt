"""Helpers for XPO-exported source text."""

from __future__ import annotations

import re
from typing import Any

PREPROCESSOR_LINE_RE = re.compile(r"(?m)^[^\S\n]*#.*(?:\n|$)")
LOCALMACRO_BLOCK_RE = re.compile(r"(?im)^\s*#localmacro\b[\s\S]*?^\s*#endmacro[^\n]*(?:\n|$)")


def normalize_xpo_source(text: str) -> str:
    """Remove leading XPO export markers from source lines."""
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            lines.append(stripped[1:])
        else:
            lines.append(line)
    return "\n".join(lines)


def strip_xpo_value(value: str) -> str:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:].strip()
    if value.startswith("{") and value.endswith("}"):
        value = value[1:-1].strip()
    return value


def extract_properties(source: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    match = re.search(r"(?ims)^\s*#?PROPERTIES\s*$(?P<body>.*?)^\s*#?ENDPROPERTIES\s*$", source)
    if not match:
        return properties

    for line in match.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue

        property_match = re.match(r"#?\s*(?P<key>[A-Za-z_]\w*)\s+(?P<value>.+?)\s*$", line)
        if property_match:
            properties[property_match.group("key").lower()] = strip_xpo_value(property_match.group("value"))

    return properties


def extract_class_info(source: str) -> dict[str, Any]:
    """Extract class metadata from regular or XPO-prefixed X++ source."""
    normalized_source = normalize_xpo_source(source)
    searchable_source = f"{source}\n{normalized_source}"
    properties = extract_properties(searchable_source)

    extends_match = re.search(
        r"(?im)^\s*#?class\s+(?P<name>[A-Za-z_]\w*)(?:\s+extends\s+(?P<extends>[A-Za-z_]\w*))?\b",
        searchable_source,
    )
    version_match = re.search(
        r"(?im)#*define\s*\.\s*CurrentVersion\s*\(\s*(?P<version>\d+)\s*\)",
        searchable_source,
    )

    current_version = int(version_match.group("version")) if version_match else None

    return {
        "name": (
            properties.get("name")
            or properties.get("classname")
            or (extends_match.group("name") if extends_match else None)
        ),
        "extends": extends_match.group("extends") if extends_match else None,
        "origin": properties.get("origin"),
        "current_version": current_version,
    }


def remove_signature_preprocessor_source(source: str) -> str:
    """Remove X++ preprocessor-only lines and localmacro blocks before signature parsing."""
    source = LOCALMACRO_BLOCK_RE.sub("", source)
    return PREPROCESSOR_LINE_RE.sub("", source)
