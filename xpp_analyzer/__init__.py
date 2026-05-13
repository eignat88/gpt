"""Public API for the X++ analyzer package."""

from __future__ import annotations

from xpp_analyzer.analysis import (
    analyze_source,
    build_call_tree,
    find_calls,
    find_fields,
    find_operations,
    find_tables,
    find_variables,
)
from xpp_analyzer.cli import output_path_for_result, safe_filename
from xpp_analyzer.models import MethodParameter, MethodSignature, MethodSource, MethodVariable, Operation
from xpp_analyzer.parser import (
    extract_methods,
    parse_method_signature,
    parse_parameter,
    split_default,
    split_parameters,
)
from xpp_analyzer.text import (
    line_number,
    mask_comments_and_strings,
    matching_brace,
    section_end_offset,
    snippet_for,
    unique_preserve_order,
)
from xpp_analyzer.xpo import extract_class_info, extract_properties, normalize_xpo_source, strip_xpo_value

__all__ = [
    "Operation",
    "MethodVariable",
    "MethodParameter",
    "MethodSignature",
    "MethodSource",
    "normalize_xpo_source",
    "strip_xpo_value",
    "extract_properties",
    "extract_class_info",
    "mask_comments_and_strings",
    "line_number",
    "matching_brace",
    "section_end_offset",
    "snippet_for",
    "unique_preserve_order",
    "split_parameters",
    "split_default",
    "parse_parameter",
    "parse_method_signature",
    "extract_methods",
    "find_operations",
    "find_variables",
    "find_tables",
    "find_fields",
    "find_calls",
    "build_call_tree",
    "analyze_source",
    "safe_filename",
    "output_path_for_result",
]
