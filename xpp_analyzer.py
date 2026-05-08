#!/usr/bin/env python3
"""Analyze X++ class methods and build a JSON call/operation tree.

The analyzer is intentionally dependency-free so it can be used in CI jobs,
local export pipelines, or before sending a compact summary to an AI reviewer.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

METHOD_HEADER_RE = re.compile(
    r"(?m)^\s*(?!(?:if|while|for|switch|catch|using|else)\b)"
    r"[^\n;{}=]*?\b(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
)
OPERATION_PATTERNS = {
    "while_select": re.compile(r"\bwhile\s+select\b", re.IGNORECASE),
    "select": re.compile(r"\bselect\b", re.IGNORECASE),
    "ttsBegin": re.compile(r"\bttsBegin\b", re.IGNORECASE),
    "update": re.compile(r"\bupdate\b", re.IGNORECASE),
    "insert": re.compile(r"\binsert\b", re.IGNORECASE),
    "delete": re.compile(r"\bdelete\b", re.IGNORECASE),
}
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
IGNORED_CALL_NAMES = {
    "if",
    "while",
    "for",
    "switch",
    "catch",
    "select",
    "exists",
    "join",
    "ttsbegin",
    "ttscommit",
    "ttsabort",
    "strfmt",
    "info",
    "warning",
    "error",
    "checkfailed",
}


@dataclass
class Operation:
    type: str
    line: int
    snippet: str


@dataclass
class MethodSource:
    name: str
    start: int
    end: int
    start_line: int
    end_line: int
    source: str
    clean_source: str
    operations: list[Operation] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    internal_calls: list[str] = field(default_factory=list)
    external_calls: list[str] = field(default_factory=list)


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


def mask_comments_and_strings(source: str) -> str:
    """Replace comments and strings with spaces while preserving offsets/newlines."""
    result: list[str] = []
    i = 0
    state = "code"
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""

        if state == "code":
            if ch == "/" and nxt == "/":
                result.extend("  ")
                i += 2
                state = "line_comment"
            elif ch == "/" and nxt == "*":
                result.extend("  ")
                i += 2
                state = "block_comment"
            elif ch in {'"', "'"}:
                result.append(" ")
                quote = ch
                i += 1
                state = f"string:{quote}"
            else:
                result.append(ch)
                i += 1
        elif state == "line_comment":
            if ch == "\n":
                result.append("\n")
                state = "code"
            else:
                result.append(" ")
            i += 1
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                result.extend("  ")
                i += 2
                state = "code"
            else:
                result.append("\n" if ch == "\n" else " ")
                i += 1
        else:
            quote = state.split(":", 1)[1]
            if ch == "\\" and nxt:
                result.extend("  ")
                i += 2
            elif ch == quote:
                result.append(" ")
                i += 1
                state = "code"
            else:
                result.append("\n" if ch == "\n" else " ")
                i += 1
    return "".join(result)


def line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def matching_brace(source: str, opening_brace: int) -> int:
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"No matching closing brace found for offset {opening_brace}")


def extract_methods(source: str) -> list[MethodSource]:
    clean = mask_comments_and_strings(source)
    methods: list[MethodSource] = []
    for match in METHOD_HEADER_RE.finditer(clean):
        name = match.group("name")
        opening = clean.find("{", match.start(), match.end())
        closing = matching_brace(clean, opening)
        method_source = source[match.start() : closing + 1]
        clean_method_source = clean[match.start() : closing + 1]
        methods.append(
            MethodSource(
                name=name,
                start=match.start(),
                end=closing + 1,
                start_line=line_number(source, match.start()),
                end_line=line_number(source, closing),
                source=method_source,
                clean_source=clean_method_source,
            )
        )
    return methods


def snippet_for(source: str, local_offset: int) -> str:
    line_start = source.rfind("\n", 0, local_offset) + 1
    line_end = source.find("\n", local_offset)
    if line_end == -1:
        line_end = len(source)
    return source[line_start:line_end].strip()


def find_operations(method: MethodSource) -> list[Operation]:
    operations: list[Operation] = []
    while_select_spans = [m.span() for m in OPERATION_PATTERNS["while_select"].finditer(method.clean_source)]

    def inside_while_select(position: int) -> bool:
        return any(start <= position < end for start, end in while_select_spans)

    for operation_type, pattern in OPERATION_PATTERNS.items():
        for match in pattern.finditer(method.clean_source):
            if operation_type == "select" and inside_while_select(match.start()):
                continue
            operations.append(
                Operation(
                    type=operation_type,
                    line=method.start_line + line_number(method.clean_source, match.start()) - 1,
                    snippet=snippet_for(method.source, match.start()),
                )
            )
    return sorted(operations, key=lambda item: (item.line, item.type))


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def find_calls(method: MethodSource) -> list[str]:
    names = []
    for match in CALL_RE.finditer(method.clean_source):
        name = match.group(1)
        if name.lower() not in IGNORED_CALL_NAMES and name != method.name:
            names.append(name)
    return unique_preserve_order(names)


def build_call_tree(method_name: str, graph: dict[str, list[str]], stack: tuple[str, ...] = ()) -> dict[str, Any]:
    if method_name in stack:
        return {"method": method_name, "recursive": True, "calls": []}
    return {
        "method": method_name,
        "recursive": False,
        "calls": [build_call_tree(child, graph, (*stack, method_name)) for child in graph.get(method_name, [])],
    }


def analyze_source(source: str, include_source: bool = True) -> dict[str, Any]:
    methods = extract_methods(source)
    method_names = {method.name.lower(): method.name for method in methods}

    for method in methods:
        method.operations = find_operations(method)
        method.calls = find_calls(method)
        method.internal_calls = [method_names[call.lower()] for call in method.calls if call.lower() in method_names]
        method.external_calls = [call for call in method.calls if call.lower() not in method_names]

    graph = {method.name: method.internal_calls for method in methods}
    called = {child for children in graph.values() for child in children}
    roots = [method.name for method in methods if method.name not in called] or [method.name for method in methods]

    return {
        "summary": {
            "method_count": len(methods),
            "operation_counts": {
                operation_type: sum(1 for method in methods for op in method.operations if op.type == operation_type)
                for operation_type in OPERATION_PATTERNS
            },
        },
        "methods": [
            {
                "name": method.name,
                "start_line": method.start_line,
                "end_line": method.end_line,
                "source": method.source if include_source else None,
                "operations": [op.__dict__ for op in method.operations],
                "calls": method.calls,
                "internal_calls": method.internal_calls,
                "external_calls": method.external_calls,
            }
            for method in methods
        ],
        "call_graph": graph,
        "call_tree": [build_call_tree(root, graph) for root in roots],
        "ai_analysis_prompt": (
            "Analyze this X++ class JSON. Focus on DB reads/writes, ttsBegin transaction boundaries, "
            "nested while select patterns, update/insert/delete risks, and risky method-call chains."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze X++ class methods and save a JSON call/operation tree.")
    parser.add_argument("input", type=Path, help="Path to an exported X++ class source file")
    parser.add_argument("-o", "--output", type=Path, default=Path("xpp-analysis.json"), help="JSON output path")
    parser.add_argument("--no-source", action="store_true", help="Do not include full method source in JSON")
    parser.add_argument("--ai-prompt", type=Path, help="Optional path for a ready-to-send AI prompt Markdown file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input.read_text(encoding="utf-8", errors="ignore")
    source = normalize_xpo_source(source)
    result = analyze_source(source, include_source=not args.no_source)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.ai_prompt:
        prompt = (
            f"{result['ai_analysis_prompt']}\n\n"
            "```json\n"
            f"{json.dumps(result, ensure_ascii=False, indent=2)}\n"
            "```\n"
        )
        args.ai_prompt.write_text(prompt, encoding="utf-8")


if __name__ == "__main__":
    main()
