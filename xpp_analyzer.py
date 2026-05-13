#!/usr/bin/env python3
"""Compatibility wrapper for the :mod:`xpp_analyzer` package."""

from __future__ import annotations

from xpp_analyzer import *  # noqa: F403
from xpp_analyzer.cli import main


if __name__ == "__main__":
    main()
