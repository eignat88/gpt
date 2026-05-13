"""Link project-analysis results to analyzed X++ code results."""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable
from typing import Any

PROJECT_DESCRIPTION_MATCH_REASON = "Упоминается в проектном описании"
CLASS_TECHNICAL_OBJECT_MATCH_REASON = "Точное совпадение с technical_objects.classes"
DESCRIPTION_TEXT_KEYS = {
    "description",
    "project_description",
    "business_description",
    "technical_description",
    "functional_description",
    "overview",
    "summary",
    "details",
}


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _object_name(value: Any) -> str | None:
    """Return a technical-object name from either a string or a small mapping."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        name_keys = (
            "name",
            "class",
            "class_name",
            "table",
            "table_name",
            "field",
            "field_name",
            "method",
            "method_name",
        )
        for key in name_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def _technical_object_names(project_result: dict[str, Any], key: str) -> list[str]:
    technical_objects = project_result.get("technical_objects")
    if not isinstance(technical_objects, dict):
        return []

    values = technical_objects.get(key, [])
    if isinstance(values, (str, dict)):
        values = [values]
    if not isinstance(values, list):
        return []

    return _unique_preserve_order(name for value in values if (name := _object_name(value)))


def _description_text(value: Any, *, current_key: str | None = None, in_description: bool = False) -> str:
    """Collect likely human-written project description text for mention matching."""
    is_description = in_description or current_key in DESCRIPTION_TEXT_KEYS
    if isinstance(value, str):
        return value if is_description else ""
    if isinstance(value, list):
        return "\n".join(
            _description_text(item, current_key=current_key, in_description=is_description)
            for item in value
        )
    if isinstance(value, dict):
        chunks: list[str] = []
        for key, item in value.items():
            if key in {"matches_with_code", "ai_analysis_prompt"}:
                continue
            chunks.append(_description_text(item, current_key=key, in_description=is_description))
        return "\n".join(chunk for chunk in chunks if chunk)
    return ""


def _is_mentioned(text: str, name: str) -> bool:
    if not text or not name:
        return False
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text, re.IGNORECASE) is not None


def _is_class_xpp_result(result: dict[str, Any]) -> bool:
    result_kind = (
        result.get("result_type") or result.get("type") or result.get("kind") or result.get("analysis_type")
    )
    if isinstance(result_kind, str) and result_kind.lower() == "class_xpp":
        return True
    return isinstance(result.get("class_info"), dict) and isinstance(result.get("methods"), list)


def _append_reference(index_section: dict[str, Any], name: str, reference: dict[str, Any]) -> None:
    entry = index_section.setdefault(name, {"name": name, "references": []})
    entry["references"].append(reference)


def build_code_index(results: list[dict]) -> dict:
    """Build an index of classes, methods, tables, and fields from class_xpp results."""
    code_index: dict[str, Any] = {
        "classes": {},
        "methods": {},
        "tables": {},
        "fields": {},
    }

    for result in results:
        if not isinstance(result, dict) or not _is_class_xpp_result(result):
            continue

        class_info = result.get("class_info") if isinstance(result.get("class_info"), dict) else {}
        class_name = class_info.get("name")
        if not isinstance(class_name, str) or not class_name:
            continue

        code_index["classes"][class_name] = {
            "name": class_name,
            "class_info": class_info,
            "result": result,
        }

        methods = result.get("methods", [])
        if not isinstance(methods, list):
            continue

        for method in methods:
            if not isinstance(method, dict):
                continue
            method_name = method.get("name")
            if isinstance(method_name, str) and method_name:
                _append_reference(
                    code_index["methods"],
                    method_name,
                    {"class_name": class_name, "method_name": method_name, "method": method},
                )

            for table_name in method.get("tables", []) if isinstance(method.get("tables"), list) else []:
                if isinstance(table_name, str) and table_name:
                    _append_reference(
                        code_index["tables"],
                        table_name,
                        {"class_name": class_name, "method_name": method_name, "method": method},
                    )

            for field_name in method.get("fields", []) if isinstance(method.get("fields"), list) else []:
                if isinstance(field_name, str) and field_name:
                    _append_reference(
                        code_index["fields"],
                        field_name,
                        {"class_name": class_name, "method_name": method_name, "method": method},
                    )

    return code_index


def _code_match(name: str, entry: dict[str, Any], reason: str) -> dict[str, Any]:
    match = {"name": name, "match_reason": reason}
    if "class_info" in entry:
        match["class_info"] = entry["class_info"]
    if "references" in entry:
        match["references"] = entry["references"]
    return match


def link_project_to_code(project_result: dict, code_index: dict) -> dict:
    """Return a project/mixed result enriched with matches to the code index."""
    linked_result = copy.deepcopy(project_result)
    description_text = _description_text(linked_result)

    matches_with_code: dict[str, list[dict[str, Any]]] = {
        "classes": [],
        "tables": [],
        "fields": [],
        "methods": [],
    }

    for class_name in _technical_object_names(linked_result, "classes"):
        class_entry = code_index.get("classes", {}).get(class_name)
        if class_entry:
            matches_with_code["classes"].append(
                _code_match(class_name, class_entry, CLASS_TECHNICAL_OBJECT_MATCH_REASON)
            )

    for section in ("tables", "fields", "methods"):
        for name, entry in code_index.get(section, {}).items():
            if _is_mentioned(description_text, name):
                matches_with_code[section].append(_code_match(name, entry, PROJECT_DESCRIPTION_MATCH_REASON))

    linked_result["matches_with_code"] = matches_with_code
    return linked_result
