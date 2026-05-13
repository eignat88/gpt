#!/usr/bin/env python3
"""Compatibility facade for legacy analysis imports.

Historically this module duplicated the analyzer implementation and also
exposed output-path helpers.  The parser now lives in
:mod:`xpp_analyzer.class_parser`; output helpers remain in
:mod:`xpp_analyzer.output`.  Both are re-exported here to avoid breaking older
callers.
"""

from __future__ import annotations

from .class_parser import *  # noqa: F403
from .class_parser import __all__ as _CLASS_PARSER_ALL
from .output import output_path_for_result, safe_filename

__all__ = [*_CLASS_PARSER_ALL, "output_path_for_result", "safe_filename"]
