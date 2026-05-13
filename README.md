# X++ class analyzer

`xpp_analyzer.py` extracts methods from an exported X++ class, keeps each method source, finds database and transaction operations, detects method calls, builds an internal call graph/tree, and writes the result to JSON for further AI review.

## Usage

```bash
python xpp_analyzer.py path/to/MyClass.xpp -o analysis.json --ai-prompt ai-review.md
python xpp_analyzer.py path/to/dir
python xpp_analyzer.py path/to/dir -o path/to/results
```

Options:

- `input` — exported X++ class source file or a directory containing exported sources. Batch directory mode recursively scans `*.txt` and `*.xpo` files.
- `-o, --output` — for file input, this is the JSON output path; when omitted, the analyzer writes `<ClassName>.json` based on `class_info.name` (falling back to `xpp-analysis.json` if no class name is found). For directory input, this is the output directory; when omitted, each JSON file is written next to its source file with a `.json` suffix. When provided for directory input, the analyzer preserves the input directory's relative structure under the output directory.
- `--no-source` — omit full method bodies from JSON when you need a smaller artifact.
- `--ai-prompt` — additionally writes a Markdown prompt with embedded JSON that can be pasted into an AI tool. This option is ignored with a warning in directory mode.

Directory mode prints one `Processed: <path>` line per successful `*.txt` or `*.xpo` file, continues after per-file errors, and ends with a summary:

```text
Total files: N
Processed: M
Errors: K
```

## JSON contents

The generated JSON includes:

1. all parsed class methods with line ranges;
2. optional full method source;
3. occurrences of `select`, `while select`, `ttsBegin`, `update`, `insert`, and `delete` with line numbers and snippets;
4. detected calls to other methods;
5. for each method:
   - `"tables"` — tables found in variable declarations and `select` statements;
   - `"fields"` — fields found in `where` clauses, `update` statements, assignments, and dot-member accesses;
6. internal method call graph and tree;
7. a short AI analysis prompt describing what to review.

Example method-level table and field data:

```json
{
  "tables": ["LFL_SCSPickingWaveLine"],
  "fields": ["PickingWaveId", "SalesId", "RecId"]
}
```

Local methods and standard functions should not be included in `"fields"`.

## Python API

`analyze_model(source)` returns a typed `AnalysisResult` for tests and programmatic consumers that do not need the JSON serialization layer. The compatible `analyze_source(source, include_source=True)` facade still returns the existing JSON-ready dictionary.

## Development check

```bash
python -m unittest discover -s tests
```
