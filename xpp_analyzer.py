#!/usr/bin/env python3
"""Compatibility entrypoint for the X++ analyzer."""

from __future__ import annotations

from xpp_analyzer import *  # noqa: F403
from xpp_analyzer import main


if __name__ == "__main__":
    main()
