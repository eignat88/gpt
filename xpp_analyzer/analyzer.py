#!/usr/bin/env python3
"""Compatibility facade for the X++ class parser.

The parsing implementation lives in :mod:`xpp_analyzer.class_parser`.  This
module is intentionally kept as a re-export layer so existing imports from
``xpp_analyzer.analyzer`` continue to work.
"""

from __future__ import annotations

from .class_parser import *  # noqa: F403
from .class_parser import __all__ as _CLASS_PARSER_ALL

__all__ = list(_CLASS_PARSER_ALL)
