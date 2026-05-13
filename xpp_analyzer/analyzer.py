#!/usr/bin/env python3
"""Analyze X++ class methods and build a JSON call/operation tree.

The analyzer is intentionally dependency-free so it can be used in CI jobs,
local export pipelines, or before sending a compact summary to an AI reviewer.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

METHOD_HEADER_RE = re.compile(
    r"(?m)^\s*(?!(?:if|while|for|switch|catch|using|else)\b)"
    r"[^\n;{}=]*?\b(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
)
SOURCE_METHOD_RE = re.compile(r"(?m)^\s*SOURCE\s+#(?P<name>[A-Za-z_]\w*)\s*$")
ENDSOURCE_RE = re.compile(r"(?m)^\s*ENDSOURCE\s*$")
PREPROCESSOR_LINE_RE = re.compile(r"(?m)^[^\S\n]*#.*(?:\n|$)")
LOCALMACRO_BLOCK_RE = re.compile(r"(?im)^\s*#localmacro\b[\s\S]*?^\s*#endmacro[^\n]*(?:\n|$)")
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


@dataclass
class Operation:
    type: str
    line: int
    snippet: str


@dataclass
class MethodVariable:
    type: str
    name: str


@dataclass
class MethodParameter:
    name: str
    type: str | None
    default: str | None


@dataclass
class MethodSignature:
    access: str | None
    static: bool
    return_type: str | None
    name: str
    parameters: list[MethodParameter]


@dataclass
class MethodSource:
    name: str
    start: int
    end: int
    start_line: int
    end_line: int
    source: str
    clean_source: str
    signature: MethodSignature | None = None
    variables: list[MethodVariable] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
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



METHOD_SIGNATURE_RE = re.compile(
    r"^\s*"
    r"(?P<modifiers>(?:public|private|protected)(?:\s+static)?|static|client|server|display|edit)"
    r"(?:\s+(?P<qualifier>client|server|display|edit))*"
    r"\s+(?P<return_type>[A-Za-z_]\w*)"
    r"\s+(?P<name>[A-Za-z_]\w*)"
    r"\s*\((?P<parameters>[^;{}]*)\)\s*\{",
    re.IGNORECASE | re.MULTILINE,
)
ACCESS_MODIFIERS = {"public", "private", "protected"}
SIGNATURE_MODIFIERS = ACCESS_MODIFIERS | {"static"}


def split_parameters(parameters: str) -> list[str]:
    """Split parameter text by commas while preserving simple quoted defaults."""
    result: list[str] = []
    start = 0
    quote: str | None = None
    depth = 0
    index = 0
    while index < len(parameters):
        char = parameters[index]
        if quote:
            if char == "\\" and index + 1 < len(parameters):
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            result.append(parameters[start:index].strip())
            start = index + 1
        index += 1

    tail = parameters[start:].strip()
    if tail:
        result.append(tail)
    return result


def split_default(parameter: str) -> tuple[str, str | None]:
    quote: str | None = None
    depth = 0
    index = 0
    while index < len(parameter):
        char = parameter[index]
        if quote:
            if char == "\\" and index + 1 < len(parameter):
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]" and depth > 0:
            depth -= 1
        elif char == "=" and depth == 0:
            return parameter[:index].strip(), parameter[index + 1 :].strip() or None
        index += 1
    return parameter.strip(), None


def parse_parameter(parameter: str) -> MethodParameter:
    declaration, default = split_default(parameter)
    parts = declaration.split()
    if not parts:
        return MethodParameter(name="", type=None, default=default)
    if len(parts) == 1:
        return MethodParameter(name=parts[0], type=None, default=default)
    return MethodParameter(name=parts[-1], type=" ".join(parts[:-1]), default=default)


def remove_signature_preprocessor_source(source: str) -> str:
    """Remove X++ preprocessor-only lines and localmacro blocks before signature parsing."""
    source = LOCALMACRO_BLOCK_RE.sub("", source)
    return PREPROCESSOR_LINE_RE.sub("", source)


def preprocess_signature_source(method_source: str) -> str:
    """Prepare a SOURCE section for method-signature regex parsing."""
    source_body = SOURCE_METHOD_RE.sub("", method_source, count=1)
    source_body = source_body.replace("\r\n", "\n").replace("\r", "\n")
    source_body = mask_comments_and_strings(source_body)
    return remove_signature_preprocessor_source(source_body)


def parse_method_signature(method_source: str, fallback_name: str) -> MethodSignature:
    """Parse the first X++ method declaration inside a SOURCE section."""
    source_body = preprocess_signature_source(method_source)
    match = METHOD_SIGNATURE_RE.search(source_body)
    if not match:
        return MethodSignature(access=None, static=False, return_type=None, name=fallback_name, parameters=[])

    name = match.group("name") or fallback_name
    modifier_tokens = match.group("modifiers").split()
    access = next((token.lower() for token in modifier_tokens if token.lower() in ACCESS_MODIFIERS), None)
    static = any(token.lower() == "static" for token in modifier_tokens)
    return_type = match.group("return_type")

    unmasked_source_body = SOURCE_METHOD_RE.sub("", method_source, count=1)
    unmasked_source_body = unmasked_source_body.replace("\r\n", "\n").replace("\r", "\n")
    unmasked_source_body = remove_signature_preprocessor_source(unmasked_source_body)
    parameters_text = unmasked_source_body[match.start("parameters") : match.end("parameters")]
    parameters = [parse_parameter(parameter) for parameter in split_parameters(parameters_text.strip())]
    return MethodSignature(access=access, static=static, return_type=return_type, name=name, parameters=parameters)


def extract_methods(source: str) -> list[MethodSource]:
    methods: list[MethodSource] = []
    for start_match in SOURCE_METHOD_RE.finditer(source):
        end_match = ENDSOURCE_RE.search(source, start_match.end())
        if not end_match:
            continue

        start = start_match.start()
        end = section_end_offset(source, end_match.end())
        method_source = source[start:end]
        fallback_name = start_match.group("name")
        signature = parse_method_signature(method_source, fallback_name)
        methods.append(
            MethodSource(
                name=signature.name if signature else fallback_name,
                start=start,
                end=end,
                start_line=line_number(source, start),
                end_line=line_number(source, end_match.start()),
                source=method_source,
                clean_source=mask_comments_and_strings(method_source),
                signature=signature,
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
        "result_type": "class_xpp",
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
