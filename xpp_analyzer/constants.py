"""Common constants and patterns for X++ analysis."""

from __future__ import annotations

import re

# Regex patterns for method detection
METHOD_HEADER_RE = re.compile(
    r"(?m)^\s*(?!(?:if|while|for|switch|catch|using|else)\b)"
    r"[^\n;{}=]*?\b(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
)
SOURCE_METHOD_RE = re.compile(r"(?m)^\s*SOURCE\s+#(?P<name>[A-Za-z_]\w*)\s*$")
ENDSOURCE_RE = re.compile(r"(?m)^\s*ENDSOURCE\s*$")
PREPROCESSOR_LINE_RE = re.compile(r"(?m)^[^\S\n]*#.*(?:\n|$)")
LOCALMACRO_BLOCK_RE = re.compile(r"(?im)^\s*#localmacro\b[\s\S]*?^\s*#endmacro[^\n]*(?:\n|$)")

# Operation patterns
OPERATION_PATTERNS = {
    "while_select": re.compile(r"\bwhile\s+select\b", re.IGNORECASE),
    "select": re.compile(r"\bselect\b", re.IGNORECASE),
    "ttsBegin": re.compile(r"\bttsBegin\b", re.IGNORECASE),
    "update": re.compile(r"\bupdate\b", re.IGNORECASE),
    "insert": re.compile(r"\binsert\b", re.IGNORECASE),
    "delete": re.compile(r"\bdelete\b", re.IGNORECASE),
}

# Call and field patterns
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
FIELD_ACCESS_RE = re.compile(r"\b(?P<buffer>[A-Za-z_]\w*)\s*\.\s*(?P<field>[A-Za-z_]\w*)\b")

# Ignored call names
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

# Variable declaration pattern
VARIABLE_DECLARATION_RE = re.compile(r"^\s*(?P<type>[A-Za-z_]\w*)\s+(?P<names>[^;]+);\s*$")

# Control flow keywords
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

# Non-table types
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

# Select option keywords
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

# Field method names
FIELD_METHOD_NAMES = {"clear", "delete", "doupdate", "insert", "reread", "update", "validatewrite"}

# Method signature parsing
METHOD_SIGNATURE_RE = re.compile(
    r"^\s*"
    r"(?P<modifiers>(?:public|private|protected)(?:\s+static)?|static|client|server|display|edit)"
    r"(?:\s+(?P<qualifier>client|server|display|edit))*"
    r"\s+(?P<return_type>[A-Za-z_]\w*)"
    r"\s+(?P<name>[A-Za-z_]\w*)"
    r"\s*\((?P<parameters>[^;{}]*)\)\s*\{",
    re.IGNORECASE | re.MULTILINE,
)

# Access and signature modifiers
ACCESS_MODIFIERS = {"public", "private", "protected"}
SIGNATURE_MODIFIERS = ACCESS_MODIFIERS | {"static"}

# Invalid filename characters
INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')