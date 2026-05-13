"""Method and signature parsing for X++ SOURCE sections."""

from __future__ import annotations

import re

from xpp_analyzer.models import MethodParameter, MethodSignature, MethodSource
from xpp_analyzer.text import line_number, mask_comments_and_strings, section_end_offset

METHOD_SIGNATURE_RE = re.compile(
    r"^\s*"
    r"(?P<modifiers>(?:public|private|protected)(?:\s+static)?|static|client|server|display|edit)"
    r"(?:\s+(?P<qualifier>client|server|display|edit))*"
    r"\s+(?P<return_type>[A-Za-z_]\w*)"
    r"\s+(?P<name>[A-Za-z_]\w*)"
    r"\s*\((?P<parameters>[^;{}]*)\)\s*\{",
    re.IGNORECASE | re.MULTILINE,
)
SOURCE_METHOD_RE = re.compile(r"(?m)^\s*SOURCE\s+#(?P<name>[A-Za-z_]\w*)\s*$")
ENDSOURCE_RE = re.compile(r"(?m)^\s*ENDSOURCE\s*$")
PREPROCESSOR_LINE_RE = re.compile(r"(?m)^[^\S\n]*#.*(?:\n|$)")
LOCALMACRO_BLOCK_RE = re.compile(r"(?im)^\s*#localmacro\b[\s\S]*?^\s*#endmacro[^\n]*(?:\n|$)")
ACCESS_MODIFIERS = {"public", "private", "protected"}


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
