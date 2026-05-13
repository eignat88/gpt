# X++ class analyzer

`xpp_analyzer.py` extracts methods from an exported X++ class, keeps each method source, finds database and transaction operations, detects method calls, builds an internal call graph/tree, and writes the result to JSON for further AI review.

## Usage

```bash
python xpp_analyzer.py path/to/MyClass.xpp -o analysis.json --ai-prompt ai-review.md
# or, as a package module:
python -m xpp_analyzer.cli path/to/MyClass.xpp -o analysis.json --ai-prompt ai-review.md

# analyze every .txt file in a folder, writing one JSON file per input file
python xpp_analyzer.py path/to/folder-with-txt-files
python xpp_analyzer.py path/to/folder-with-txt-files -o path/to/output-folder
```

Options:

- `input` — exported X++ class source file, or a folder containing `.txt` files to process sequentially.
- `-o, --output` — JSON output path for a single file, or output folder for a folder input; when omitted for a single file, the analyzer writes `<ClassName>.json` based on `class_info.name` (falling back to `xpp-analysis.json` if no class name is found). For a folder input, omitted `-o` writes JSON files back into the input folder.
- `--no-source` — omit full method bodies from JSON when you need a smaller artifact.
- `--ai-prompt` — additionally writes a Markdown prompt with embedded JSON that can be pasted into an AI tool. This option is available only for single-file analysis.

When `input` is a folder, only top-level `.txt` files are analyzed. Files are processed in sorted filename order. Each `.txt` file gets one JSON output file. If the class name cannot be found, the output filename falls back to the input `.txt` stem.

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

## Development check

```bash
python -m unittest discover -s tests
```
