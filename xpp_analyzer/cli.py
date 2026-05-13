"""Command-line interface for the X++ analyzer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import analyze_source
from .output import output_path_for_result
from .xpo import normalize_xpo_source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze X++ class methods and save a JSON call/operation tree.")
    parser.add_argument("input", type=Path, help="Path to an exported X++ class source file")
    parser.add_argument("-o", "--output", type=Path, default=None, help="JSON output path")
    parser.add_argument("--no-source", action="store_true", help="Do not include full method source in JSON")
    parser.add_argument("--ai-prompt", type=Path, help="Optional path for a ready-to-send AI prompt Markdown file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input.read_text(encoding="utf-8", errors="ignore")
    source = normalize_xpo_source(source)
    result = analyze_source(source, include_source=not args.no_source)
    output_path = output_path_for_result(result, args.output)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.ai_prompt:
        prompt = (
            f"{result['ai_analysis_prompt']}\n\n"
            "```json\n"
            f"{json.dumps(result, ensure_ascii=False, indent=2)}\n"
            "```\n"
        )
        args.ai_prompt.write_text(prompt, encoding="utf-8")
