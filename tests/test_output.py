import unittest
from pathlib import Path

from xpp_analyzer import analyze_source, output_path_for_result, safe_filename


class OutputTest(unittest.TestCase):
    def test_default_output_uses_class_name_when_output_is_omitted(self):
        source = """
class LFL_SCSPickingWaveRun
{
    public void run()
    {
    }
}
"""

        result = analyze_source(source)

        self.assertEqual(output_path_for_result(result), Path("LFL_SCSPickingWaveRun.json"))

    def test_safe_filename_replaces_invalid_characters(self):
        self.assertEqual(safe_filename(' Demo:Class<>"/\\|?* .'), "Demo_Class_")

    def test_output_path_uses_explicit_output_when_provided(self):
        result = {"class_info": {"name": "Demo"}}

        self.assertEqual(output_path_for_result(result, Path("custom/result.json")), Path("custom/result.json"))

    def test_output_path_falls_back_when_class_name_is_missing(self):
        result = {"class_info": {"name": None}}

        self.assertEqual(output_path_for_result(result), Path("xpp-analysis.json"))

    def test_class_xpp_output_keeps_legacy_fields_and_document_type(self):
        result = analyze_source(
            """
class DemoClass
{
}
SOURCE #run
public void run()
{
}
ENDSOURCE
"""
        )

        self.assertEqual(result["document_type"], "class_xpp")
        self.assertEqual(
            set(result),
            {
                "document_type",
                "class_info",
                "summary",
                "methods",
                "call_graph",
                "call_tree",
                "recommended_breakpoints",
                "debug_route",
                "debug_strategy",
                "ai_analysis_prompt",
            },
        )
        self.assertEqual(result["class_info"]["name"], "DemoClass")
        self.assertEqual(result["methods"][0]["name"], "run")
        self.assertEqual(result["summary"]["debug_points_count"], 1)
        self.assertEqual(result["recommended_breakpoints"][0]["id"], "BP001")
        self.assertEqual(result["recommended_breakpoints"][0]["kind"], "method_entry")
        self.assertEqual(result["debug_strategy"]["recommended_order"], ["BP001"])

    def test_project_document_output_has_stable_json_schema(self):
        result = analyze_source(
            """
# Project: Warehouse wave automation
Module: SCM
Owner: Operations

## Business requirements
- BR-1: Create picking waves automatically.

## Technical objects
- Class: LFL_SCSPickingWaveRun
- Table: WMSPickingRoute

## Algorithms
- Validate input ranges before creating waves.

## Dependencies
- Batch framework must be available.

## Risks
- Duplicate wave creation if retries are not idempotent.
""",
            source_file="docs/wave.md",
        )

        self.assertEqual(
            list(result),
            [
                "document_type",
                "source_file",
                "project",
                "business_requirements",
                "technical_objects",
                "algorithms",
                "dependencies",
                "risks",
                "matches_with_code",
            ],
        )
        self.assertEqual(result["document_type"], "project_document")
        self.assertEqual(result["source_file"], "docs/wave.md")
        self.assertEqual(result["project"]["name"], "Warehouse wave automation")
        self.assertEqual(result["project"]["module"], "SCM")
        self.assertEqual(result["project"]["owner"], "Operations")
        self.assertEqual(result["business_requirements"][0]["id"], "BR-1")
        self.assertEqual(result["technical_objects"]["classes"], ["LFL_SCSPickingWaveRun"])
        self.assertEqual(result["technical_objects"]["tables"], ["WMSPickingRoute"])
        self.assertEqual(result["matches_with_code"][0]["object_name"], "LFL_SCSPickingWaveRun")

    def test_mixed_document_contains_project_schema_and_nested_xpp_analysis(self):
        result = analyze_source(
            """
# Project: Mixed wave document

## Business requirements
- BR-2: Run validation before updating table SalesTable.

SOURCE #run
public void run()
{
    SalesTable salesTable;
    salesTable.update();
}
ENDSOURCE
"""
        )

        self.assertEqual(result["document_type"], "mixed_document")
        self.assertIn("xpp_analysis", result)
        self.assertEqual(result["xpp_analysis"]["document_type"], "class_xpp")
        self.assertEqual(result["xpp_analysis"]["summary"]["method_count"], 1)
        self.assertEqual(result["technical_objects"]["tables"], ["SalesTable"])


if __name__ == "__main__":
    unittest.main()
