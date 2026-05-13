"""Analysis of X++ operations, variables, tables, fields, and calls."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from xpp_analyzer.models import MethodSource, MethodVariable, Operation
from xpp_analyzer.parser import extract_methods
from xpp_analyzer.text import line_number, snippet_for, unique_preserve_order
from xpp_analyzer.xpo import extract_class_info

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
FIELD_ACCESS_RE = re.compile(r"\b(?P<buffer>[A-Za-z_]\w*)\s*\.\s*(?P<field>[A-Za-z_]\w*)\b")
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
VARIABLE_DECLARATION_RE = re.compile(r"^\s*(?P<type>[A-Za-z_]\w*)\s+(?P<names>[^;]+);\s*$")
CONTROL_FLOW_KEYWORDS = {
    "break",
    "case",
    "catch",
    "continue",
    "default",
    "delete_from",
    "do",
    "else",
    "for",
    "if",
    "insert_recordset",
    "return",
    "select",
    "switch",
    "throw",
    "try",
    "ttsabort",
    "ttsbegin",
    "ttscommit",
    "update_recordset",
    "while",
}
NON_TABLE_TYPES = {
    "anytype",
    "boolean",
    "class",
    "container",
    "date",
    "datetime",
    "enum",
    "guid",
    "int",
    "int64",
    "list",
    "map",
    "object",
    "real",
    "set",
    "setenumerator",
    "str",
    "string",
    "time",
    "utcdatetime",
    "void",
}
SELECT_OPTION_KEYWORDS = {
    "crosscompany",
    "firstfast",
    "firstonly",
    "firstonly1",
    "firstonly10",
    "firstonly100",
    "firstonly1000",
    "forceindex",
    "forcenestedloop",
    "forceliterals",
    "forceplaceholders",
    "forceselectorder",
    "forupdate",
    "generateonly",
    "nofetch",
    "optimisticlock",
    "order",
    "pessimisticlock",
    "reverse",
    "validtimestate",
}
FIELD_METHOD_NAMES = {"clear", "delete", "doupdate", "insert", "reread", "update", "validatewrite"}


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


def method_body_start(method: MethodSource) -> int | None:
    """Return the offset just after the method signature opening brace."""
    for match in METHOD_HEADER_RE.finditer(method.clean_source):
        if method.signature and match.group("name") != method.signature.name:
            continue
        return match.end()
    return None


def parse_variable_declaration_line(line: str) -> list[MethodVariable]:
    """Parse a single X++ variable declaration line."""
    statement_end = line.find(";")
    if statement_end == -1:
        return []
    if "(" in line[:statement_end]:
        return []

    match = VARIABLE_DECLARATION_RE.match(line)
    if not match:
        return []

    variable_type = match.group("type")
    if variable_type.lower() in CONTROL_FLOW_KEYWORDS:
        return []

    variables: list[MethodVariable] = []
    for raw_name in match.group("names").split(","):
        name = raw_name.split("=", 1)[0].strip()
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            return []
        if name.lower() in CONTROL_FLOW_KEYWORDS:
            return []
        variables.append(MethodVariable(type=variable_type, name=name))
    return variables


def find_variables(method: MethodSource) -> list[MethodVariable]:
    """Find initial method-local variable declarations."""
    body_start = method_body_start(method)
    if body_start is None:
        return []

    variables: list[MethodVariable] = []
    for line in method.clean_source[body_start:].splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        declaration_variables = parse_variable_declaration_line(line)
        if not declaration_variables:
            break
        variables.extend(declaration_variables)
    return variables


def is_table_type(type_name: str) -> bool:
    """Return True when a variable type is likely an X++ table buffer."""
    return type_name.lower() not in NON_TABLE_TYPES and type_name.lower() not in CONTROL_FLOW_KEYWORDS


def table_variable_map(method: MethodSource) -> dict[str, str]:
    """Map local table-buffer variable names to their table types."""
    return {variable.name: variable.type for variable in method.variables if is_table_type(variable.type)}


def select_statement_segment(source: str, start: int) -> str:
    """Return a bounded select statement fragment starting just after the select keyword."""
    end_candidates = [
        position for position in (source.find(";", start), source.find("{", start)) if position != -1
    ]
    end = min(end_candidates) if end_candidates else min(len(source), start + 500)
    return source[start:end]


def select_buffer_names(method: MethodSource) -> list[str]:
    """Find table buffer identifiers used by select and while select statements."""
    buffers: list[str] = []
    for match in re.finditer(r"\b(?:while\s+)?select\b", method.clean_source, re.IGNORECASE):
        segment = select_statement_segment(method.clean_source, match.end())
        tokens = re.findall(r"\b[A-Za-z_]\w*\b", segment)
        lower_tokens = [token.lower() for token in tokens]

        if "from" in lower_tokens:
            from_index = lower_tokens.index("from")
            for token in tokens[from_index + 1 :]:
                if token.lower() not in SELECT_OPTION_KEYWORDS:
                    buffers.append(token)
                    break
            continue

        for token in tokens:
            lower_token = token.lower()
            if lower_token in SELECT_OPTION_KEYWORDS:
                continue
            if lower_token in {"where", "join", "exists", "notexists", "outer", "index", "by"}:
                break
            buffers.append(token)
            break
    return buffers


def find_tables(method: MethodSource) -> list[str]:
    """Find table names referenced by local table buffers and select statements."""
    table_variables = table_variable_map(method)
    tables: list[str] = [variable.type for variable in method.variables if variable.name in table_variables]

    for buffer in select_buffer_names(method):
        table_name = table_variables.get(buffer)
        if table_name:
            tables.append(table_name)
        elif is_table_type(buffer):
            tables.append(buffer)

    return unique_preserve_order(tables)


def find_fields(method: MethodSource, table_variables: dict[str, str]) -> list[str]:
    """Find field names accessed through known table-buffer variables."""
    table_buffer_names = {name.lower() for name in table_variables}
    excluded_field_names = {
        method.name.lower(),
        *IGNORED_CALL_NAMES,
        *FIELD_METHOD_NAMES,
        *(call.lower() for call in method.calls),
        *(call.lower() for call in method.internal_calls),
    }
    fields: list[str] = []

    for match in FIELD_ACCESS_RE.finditer(method.clean_source):
        buffer = match.group("buffer")
        field_name = match.group("field")
        if buffer.lower() not in table_buffer_names:
            continue
        if field_name.lower() in excluded_field_names:
            continue

        tail = method.clean_source[match.end() :]
        if re.match(r"\s*\(", tail):
            continue

        fields.append(field_name)
    return unique_preserve_order(fields)


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
    class_info = extract_class_info(source)
    methods = extract_methods(source)
    method_names = {method.name.lower(): method.name for method in methods}

    for method in methods:
        method.variables = find_variables(method)
        method.tables = find_tables(method)
        method.operations = find_operations(method)
        method.calls = find_calls(method)
        method.internal_calls = [method_names[call.lower()] for call in method.calls if call.lower() in method_names]
        method.external_calls = [call for call in method.calls if call.lower() not in method_names]
        method.fields = find_fields(method, table_variable_map(method))

    graph = {method.name: method.internal_calls for method in methods}
    called = {child for children in graph.values() for child in children}
    roots = [method.name for method in methods if method.name not in called] or [method.name for method in methods]

    return {
        "class_info": class_info,
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
                "signature": asdict(method.signature) if method.signature else None,
                "variables": [variable.__dict__ for variable in method.variables],
                "tables": method.tables,
                "fields": method.fields,
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
