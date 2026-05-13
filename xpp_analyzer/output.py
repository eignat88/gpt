"""Output path and filename helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def safe_filename(name: str) -> str:
    """Return a filesystem-safe filename stem derived from a class name."""
    return INVALID_FILENAME_CHARS_RE.sub("_", name).strip(" .")


def output_path_for_result(result: dict[str, Any], explicit_output: Path | None = None) -> Path:
    if explicit_output is not None:
        return explicit_output

    class_name = result["class_info"]["name"]
    if class_name:
        filename = safe_filename(class_name)
        if filename:
            return Path(f"{filename}.json")

    return Path("xpp-analysis.json")
