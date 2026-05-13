"""Public API for the X++ analyzer."""

from __future__ import annotations

from .analysis import analyze_model, analyze_source, normalize_xpo_source, output_path_for_result, safe_filename
from .cli import main
from .models import AnalysisResult, MethodParameter, MethodSignature, MethodSource, MethodVariable, Operation
from .serialization import analysis_to_dict


__all__ = [
    "AnalysisResult",
    "MethodParameter",
    "MethodSignature",
    "MethodSource",
    "MethodVariable",
    "Operation",
    "analysis_to_dict",
    "analyze_model",
    "analyze_source",
    "main",
    "normalize_xpo_source",
    "output_path_for_result",
    "safe_filename",
]
