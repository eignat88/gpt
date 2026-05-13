"""Command-line interface for the X++ analyzer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from xpp_analyzer import analyze_source, normalize_xpo_source, output_path_for_result, safe_filename
from xpp_analyzer.linker import build_code_index, link_project_to_code

DEFAULT_BATCH_INPUT_PATTERN = "*.txt"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze X++ class methods and save a JSON call/operation tree.")
    parser.add_argument("input", type=Path, help="Path to an exported X++ class source file or a folder with .txt files")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="JSON output path for a file input, or output folder for a folder input",
    )
    parser.add_argument("--no-source", action="store_true", help="Do not include full method source in JSON")
    parser.add_argument("--ai-prompt", type=Path, help="Optional path for a ready-to-send AI prompt Markdown file")
    return parser.parse_args(argv)


def txt_files_in_directory(input_dir: Path) -> list[Path]:
    """Return .txt files in a directory in a deterministic processing order."""
    return sorted(path for path in input_dir.glob(DEFAULT_BATCH_INPUT_PATTERN) if path.is_file())


def result_output_path_for_input(result: dict[str, Any], source_path: Path, output_dir: Path) -> Path:
    """Build a batch output path, falling back to the input file stem when a class name is absent."""
    if not isinstance(result.get("class_info"), dict):
        source_stem = safe_filename(source_path.stem) or "xpp-analysis"
        return output_dir / f"{source_stem}.json"

    candidate = output_path_for_result(result)
    if candidate.name == "xpp-analysis.json":
        source_stem = safe_filename(source_path.stem) or "xpp-analysis"
        candidate = Path(f"{source_stem}.json")
    return output_dir / candidate.name


def analyze_or_load_batch_result(source_path: Path, *, include_source: bool) -> dict[str, Any]:
    """Analyze an X++ source file or load an existing project/mixed JSON result."""
    source = source_path.read_text(encoding="utf-8", errors="ignore")
    try:
        loaded_result = json.loads(source)
    except json.JSONDecodeError:
        loaded_result = None

    if isinstance(loaded_result, dict) and (
        loaded_result.get("technical_objects")
        or loaded_result.get("result_type") in {"project", "mixed"}
        or loaded_result.get("type") in {"project", "mixed"}
    ):
        return loaded_result

    return analyze_source(normalize_xpo_source(source), include_source=include_source)


def unique_output_path(path: Path, used_paths: set[Path]) -> Path:
    """Avoid overwriting files when several inputs resolve to the same output name."""
    if path not in used_paths and not path.exists():
        used_paths.add(path)
        return path

    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if candidate not in used_paths and not candidate.exists():
            used_paths.add(candidate)
            return candidate
        index += 1


def write_analysis_result(
    source_path: Path,
    output_path: Path,
    *,
    include_source: bool,
    ai_prompt_path: Path | None = None,
) -> None:
    source = source_path.read_text(encoding="utf-8", errors="ignore")
    source = normalize_xpo_source(source)
    result = analyze_source(source, include_source=include_source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if ai_prompt_path:
        prompt = (
            f"{result['ai_analysis_prompt']}\n\n"
            "```json\n"
            f"{json.dumps(result, ensure_ascii=False, indent=2)}\n"
            "```\n"
        )
        ai_prompt_path.parent.mkdir(parents=True, exist_ok=True)
        ai_prompt_path.write_text(prompt, encoding="utf-8")


def analyze_single_file(args: argparse.Namespace) -> None:
    output_path = args.output
    if output_path is None:
        source = args.input.read_text(encoding="utf-8", errors="ignore")
        result = analyze_source(normalize_xpo_source(source), include_source=not args.no_source)
        output_path = output_path_for_result(result)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        if args.ai_prompt:
            prompt = (
                f"{result['ai_analysis_prompt']}\n\n"
                "```json\n"
                f"{json.dumps(result, ensure_ascii=False, indent=2)}\n"
                "```\n"
            )
            args.ai_prompt.parent.mkdir(parents=True, exist_ok=True)
            args.ai_prompt.write_text(prompt, encoding="utf-8")
        return

    write_analysis_result(args.input, output_path, include_source=not args.no_source, ai_prompt_path=args.ai_prompt)


def analyze_directory(args: argparse.Namespace) -> None:
    if args.ai_prompt:
        raise SystemExit("--ai-prompt can only be used when analyzing a single file")

    input_files = txt_files_in_directory(args.input)
    if not input_files:
        raise SystemExit(f"No .txt files found in {args.input}")

    output_dir = args.output or args.input
    if output_dir.exists() and not output_dir.is_dir():
        raise SystemExit("When input is a folder, --output must be a folder too")
    output_dir.mkdir(parents=True, exist_ok=True)

    analyzed_results: list[tuple[Path, dict[str, Any]]] = []
    for source_path in input_files:
        result = analyze_or_load_batch_result(source_path, include_source=not args.no_source)
        analyzed_results.append((source_path, result))

    code_index = build_code_index([result for _, result in analyzed_results])

    used_paths: set[Path] = set()
    for source_path, result in analyzed_results:
        if (
            result.get("technical_objects")
            or result.get("result_type") in {"project", "mixed"}
            or result.get("type") in {"project", "mixed"}
        ):
            result = link_project_to_code(result, code_index)
        output_path = unique_output_path(result_output_path_for_input(result, source_path, output_dir), used_paths)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.input.is_dir():
        analyze_directory(args)
        return

    analyze_single_file(args)


if __name__ == "__main__":
    main()
