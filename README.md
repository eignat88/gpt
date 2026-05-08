# X++ class analyzer

`xpp_analyzer.py` extracts methods from an exported X++ class, keeps each method source, finds database and transaction operations, detects method calls, builds an internal call graph/tree, and writes the result to JSON for further AI review.

## Usage

```bash
python xpp_analyzer.py path/to/MyClass.xpp -o analysis.json --ai-prompt ai-review.md
```

Options:

- `input` — exported X++ class source file.
- `-o, --output` — JSON output path; defaults to `xpp-analysis.json`.
- `--no-source` — omit full method bodies from JSON when you need a smaller artifact.
- `--ai-prompt` — additionally writes a Markdown prompt with embedded JSON that can be pasted into an AI tool.

## JSON contents

The generated JSON includes:

1. all parsed class methods with line ranges;
2. optional full method source;
3. occurrences of `select`, `while select`, `ttsBegin`, `update`, `insert`, and `delete` with line numbers and snippets;
4. detected calls to other methods;
5. internal method call graph and tree;
6. a short AI analysis prompt describing what to review.

## Development check

```bash
python -m unittest discover -s tests
```
