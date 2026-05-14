"""Serialization helpers for typed X++ analyzer results."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import AnalysisResult
from .prompts import AI_ANALYSIS_PROMPT


def analysis_to_dict(result: AnalysisResult, include_source: bool = True) -> dict[str, Any]:
    """Convert a typed analysis result into the legacy JSON-ready dictionary."""
    return {
        "document_type": "class_xpp",
        "class_info": result.class_info,
        "summary": result.summary,
        "methods": [
            {
                "name": method.name,
                "start_line": method.start_line,
                "end_line": method.end_line,
                "source": method.source if include_source else None,
                "signature": asdict(method.signature) if method.signature else None,
                "variables": [asdict(variable) for variable in method.variables],
                "tables": method.tables,
                "fields": method.fields,
                "operations": [asdict(operation) for operation in method.operations],
                "calls": method.calls,
                "internal_calls": method.internal_calls,
                "external_calls": method.external_calls,
            }
            for method in result.methods
        ],
        "call_graph": result.call_graph,
        "call_tree": result.call_tree,
        "recommended_breakpoints": [asdict(point) for point in result.debug_points],
        "debug_strategy": {
            "summary": "Start with entry points, transaction boundaries, data changes, and error paths before stepping into lower-risk calls.",
            "entry_points": [point.method for point in result.debug_points if point.kind == "entry_point"],
            "recommended_order": [point.id for point in result.debug_points],
        },
        "ai_analysis_prompt": AI_ANALYSIS_PROMPT,
    }
