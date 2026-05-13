"""Low-level text utilities used by the X++ analyzer."""

from __future__ import annotations

from typing import Iterable


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


def section_end_offset(source: str, endsource_end: int) -> int:
    """Return an offset that includes the whole ENDSOURCE line."""
    if endsource_end < len(source) and source[endsource_end] == "\r":
        endsource_end += 1
    if endsource_end < len(source) and source[endsource_end] == "\n":
        endsource_end += 1
    return endsource_end


def snippet_for(source: str, local_offset: int) -> str:
    line_start = source.rfind("\n", 0, local_offset) + 1
    line_end = source.find("\n", local_offset)
    if line_end == -1:
        line_end = len(source)
    return source[line_start:line_end].strip()


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
