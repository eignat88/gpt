"""Serialization helpers for typed X++ analyzer results."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import AnalysisResult
from .prompts import AI_ANALYSIS_PROMPT


def analysis_to_dict(result: AnalysisResult, include_source: bool = True) -> dict[str, Any]:
    """Convert a typed analysis result into the legacy JSON-ready dictionary."""
    return {
        "result_type": "class_xpp",
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
        "ai_analysis_prompt": AI_ANALYSIS_PROMPT,
    }
