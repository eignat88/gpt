"""Recommended breakpoint discovery for analyzed X++ methods."""

from __future__ import annotations

import re

from .models import DebugPoint, MethodSource, Operation

ENTRY_POINT_METHODS = {"main", "construct", "new", "run", "process", "execute", "init", "update", "create", "post"}
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
OPERATION_KIND_PRIORITY = {
    "ttsBegin": ("transaction_start", "critical"),
    "ttsCommit": ("transaction_commit", "critical"),
    "select": ("data_read", "medium"),
    "while_select": ("data_read", "medium"),
    "update": ("data_change", "critical"),
    "insert": ("data_change", "critical"),
    "delete": ("data_change", "critical"),
    "doUpdate": ("data_change", "critical"),
    "update_recordset": ("data_change", "critical"),
    "insert_recordset": ("data_change", "critical"),
    "delete_from": ("data_change", "critical"),
    "throw": ("error_point", "high"),
    "error": ("error_point", "high"),
    "warning": ("error_point", "high"),
    "checkFailed": ("error_point", "high"),
}


def _entry_snippet(method: MethodSource) -> str:
    for line in method.source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.lower().startswith("source #"):
            return stripped
    return method.name


def _point(
    *,
    method: str,
    line: int,
    kind: str,
    priority: str,
    reason: str,
    snippet: str,
    what_to_check: str,
) -> DebugPoint:
    return DebugPoint(
        id="",
        method=method,
        line=line,
        kind=kind,
        priority=priority,
        reason=reason,
        snippet=snippet,
        what_to_check=what_to_check,
    )


def _operation_point(method: MethodSource, operation: Operation) -> DebugPoint | None:
    mapping = OPERATION_KIND_PRIORITY.get(operation.type)
    if mapping is None:
        return None

    kind, priority = mapping
    checks = {
        "transaction_start": "Verify transaction scope, nested tts levels, and all exits before commit/abort.",
        "transaction_commit": "Verify data was validated before commit and exceptions cannot leave partial state.",
        "data_read": "Inspect selected filters, joins, forUpdate usage, locking, and expected cardinality.",
        "data_change": "Validate changed table buffers, write conditions, side effects, and transaction coverage.",
        "error_point": "Check whether the error path is expected, user-safe, and leaves data in a consistent state.",
    }
    reasons = {
        "transaction_start": f"{operation.type} starts a transaction boundary.",
        "transaction_commit": f"{operation.type} commits a transaction boundary.",
        "data_read": f"{operation.type} reads data that may drive branching or updates.",
        "data_change": f"{operation.type} changes persisted data.",
        "error_point": f"{operation.type} can interrupt or alter the execution path.",
    }
    return _point(
        method=method.name,
        line=operation.line,
        kind=kind,
        priority=priority,
        reason=reasons[kind],
        snippet=operation.snippet,
        what_to_check=checks[kind],
    )


def _internal_call_points(method: MethodSource) -> list[DebugPoint]:
    points: list[DebugPoint] = []
    for call in method.internal_calls:
        pattern = re.compile(rf"\b{re.escape(call)}\s*\(", re.IGNORECASE)
        for match in pattern.finditer(method.clean_source):
            line = method.start_line + method.clean_source.count("\n", 0, match.start())
            line_start = method.source.rfind("\n", 0, match.start()) + 1
            line_end = method.source.find("\n", match.start())
            if line_end == -1:
                line_end = len(method.source)
            points.append(
                _point(
                    method=method.name,
                    line=line,
                    kind="internal_call",
                    priority="low",
                    reason=f"Calls internal method {call}.",
                    snippet=method.source[line_start:line_end].strip(),
                    what_to_check="Step into the internal method if inputs or side effects influence this scenario.",
                )
            )
    return points


def find_debug_points(methods: list[MethodSource]) -> list[DebugPoint]:
    """Build sorted recommended breakpoint points from analyzed methods."""
    points: list[DebugPoint] = []

    for method in methods:
        if method.name.lower() in ENTRY_POINT_METHODS:
            points.append(
                _point(
                    method=method.name,
                    line=method.start_line,
                    kind="entry_point",
                    priority="high",
                    reason=f"{method.name} is a common execution entry point.",
                    snippet=_entry_snippet(method),
                    what_to_check="Confirm incoming parameters, object state, and the first branch taken by execution.",
                )
            )

        for operation in method.operations:
            point = _operation_point(method, operation)
            if point is not None:
                points.append(point)

        points.extend(_internal_call_points(method))

    points.sort(key=lambda point: (point.line, PRIORITY_ORDER.get(point.priority, 99), point.kind))
    for index, point in enumerate(points, start=1):
        point.id = f"BP{index:03d}"
    return points
