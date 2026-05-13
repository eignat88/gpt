"""Utilities for extracting structured metadata from project descriptions."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PROJECT_CODE_RE = re.compile(r"\b(?:DAX|FD|SUP)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "goal": ("цель", "цели", "goal", "goals", "objective", "objectives", "purpose"),
    "problem": ("проблема", "проблемы", "problem", "problems", "issue", "issues"),
    "business_process": (
        "бизнес-процесс",
        "бизнес процесс",
        "бизнес-процессы",
        "бизнес процессы",
        "business process",
        "business processes",
    ),
    "constraints": (
        "ограничение",
        "ограничения",
        "constraint",
        "constraints",
        "restriction",
        "restrictions",
        "limitations",
    ),
    "expected_result": (
        "ожидаемый результат",
        "ожидаемые результаты",
        "результат",
        "expected result",
        "expected results",
        "outcome",
        "outcomes",
    ),
    "risks": ("риски", "риск", "risk", "risks"),
    "dependencies": (
        "зависимости",
        "зависимость",
        "dependency",
        "dependencies",
        "depends on",
    ),
    "algorithms": (
        "алгоритм",
        "алгоритмы",
        "алгоритм работы",
        "algorithm",
        "algorithms",
        "flow",
        "logic",
    ),
    "requirements": (
        "требования",
        "требование",
        "бизнес-требования",
        "бизнес требования",
        "business requirements",
        "requirement",
        "requirements",
    ),
}

_SECTION_BY_ALIAS = {
    alias: canonical
    for canonical, aliases in _SECTION_ALIASES.items()
    for alias in aliases
}

_TITLE_LABEL_RE = re.compile(r"^(?:название|тема|заголовок|title|name)\s*[:\-–—]\s*", re.IGNORECASE)
_CODE_LABEL_RE = re.compile(
    r"^(?:код\s+проекта|project\s+code|проект|номер|задача|тикет|project|code|ticket)\s*[:\-–—]?\s*",
    re.IGNORECASE,
)
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")


def analyze_project_description(text: str, source_file: str | None = None) -> dict:
    """Analyze a free-form project description and return structured metadata.

    The parser is intentionally heuristic-based: project descriptions often mix
    Markdown, numbered lists, plain text labels, and Russian/English headings.
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    lines = text.splitlines()
    project_code = _extract_project_code(text)
    sections = _extract_sections(lines)

    result: dict[str, Any] = {
        "project": {
            "code": project_code,
            "title": _extract_title(lines, project_code, source_file),
            "source_file": source_file,
        },
        "sections": sections,
        "business_requirements": _items_from_sections(sections, "requirements"),
        "algorithms": _items_from_sections(sections, "algorithms"),
        "dependencies": _items_from_sections(sections, "dependencies"),
        "risks": _items_from_sections(sections, "risks"),
    }
    return result


def _extract_project_code(text: str) -> str | None:
    match = PROJECT_CODE_RE.search(text)
    return match.group(0).upper() if match else None


def _extract_title(lines: list[str], project_code: str | None, source_file: str | None) -> str | None:
    significant = [(index, _clean_line(line)) for index, line in enumerate(lines) if _clean_line(line)]

    for _, line in significant:
        heading = _heading_text(line)
        if heading:
            title = _title_candidate(heading, project_code)
            if title:
                return title

    for _, line in significant:
        label_match = _TITLE_LABEL_RE.match(line)
        if label_match:
            title = _title_candidate(line[label_match.end() :], project_code)
            if title:
                return title

    if project_code:
        for index, line in significant:
            if PROJECT_CODE_RE.search(line):
                title = _title_candidate(line, project_code)
                if title:
                    return title

                for nearby_index in (index + 1, index - 1):
                    if 0 <= nearby_index < len(lines):
                        nearby = _title_candidate(_clean_line(lines[nearby_index]), project_code)
                        if nearby:
                            return nearby

    for _, line in significant:
        title = _title_candidate(line, project_code)
        if title:
            return title

    if source_file:
        stem = Path(source_file).stem.strip()
        return stem or None
    return None


def _extract_sections(lines: list[str]) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        heading = _section_heading(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    return {name: _normalize_block(content) for name, content in sections.items()}


def _items_from_sections(sections: dict[str, str], *names: str) -> list[str]:
    items: list[str] = []
    for name in names:
        section_text = sections.get(name, "")
        items.extend(_split_items(section_text))
    return _unique_non_empty(items)


def _split_items(section_text: str) -> list[str]:
    items: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            items.append(_clean_item(" ".join(paragraph)))
            paragraph.clear()

    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            continue

        bullet = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)(.+)$", line)
        if bullet:
            flush_paragraph()
            items.append(_clean_item(bullet.group(1)))
        else:
            paragraph.append(line)

    flush_paragraph()
    return [item for item in items if item]


def _section_heading(line: str) -> str | None:
    text = _clean_line(line)
    if not text:
        return None

    heading = _heading_text(text)
    if heading is None:
        heading = text

    heading = heading.strip().strip(":：").strip()
    heading = re.sub(r"^\d+(?:\.\d+)*[.)]?\s+", "", heading)
    heading = heading.strip("*_").strip()

    if ":" in heading:
        before_colon, after_colon = heading.split(":", 1)
        if after_colon.strip():
            return None
        heading = before_colon

    normalized = _normalize_heading(heading)
    return _SECTION_BY_ALIAS.get(normalized)


def _heading_text(line: str) -> str | None:
    match = _MARKDOWN_HEADING_RE.match(line)
    if match:
        return match.group(1).strip()

    bold = re.match(r"^\s*\*\*(.+?)\*\*\s*:??\s*$", line)
    if bold:
        return bold.group(1).strip()

    return None


def _title_candidate(line: str, project_code: str | None) -> str | None:
    title = _clean_line(line)
    title = _heading_text(title) or title
    title = _TITLE_LABEL_RE.sub("", title).strip()
    title = _CODE_LABEL_RE.sub("", title).strip()
    title = PROJECT_CODE_RE.sub("", title).strip() if project_code else title
    title = title.strip("-–—:|. ").strip()

    if not title or _section_heading(title):
        return None
    if len(title) < 3:
        return None
    return title


def _clean_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = _LIST_MARKER_RE.sub("", cleaned).strip()
    cleaned = cleaned.strip("` ").strip()
    return cleaned


def _clean_item(item: str) -> str:
    return item.strip().strip(";,. ").strip()


def _normalize_block(lines: Iterable[str]) -> str:
    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def _normalize_heading(heading: str) -> str:
    normalized = heading.casefold().replace("ё", "е")
    normalized = re.sub(r"[\t\s\-_]+", " ", normalized)
    normalized = re.sub(r"[^0-9a-zа-я ]+", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _unique_non_empty(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _clean_item(item)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result
