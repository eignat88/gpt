import unittest

from xpp_analyzer import analyze_source
from tests.fixtures import XPO_SAMPLE


class AnalysisTest(unittest.TestCase):
    def test_extracts_xpo_source_sections_operations_and_tree(self):
        result = analyze_source(XPO_SAMPLE)

        self.assertEqual(result["summary"]["method_count"], 2)
        self.assertEqual(result["summary"]["operation_counts"]["select"], 1)
        self.assertEqual(result["summary"]["operation_counts"]["while_select"], 1)
        self.assertEqual(result["summary"]["operation_counts"]["ttsBegin"], 1)
        self.assertEqual(result["summary"]["operation_counts"]["update"], 1)
        self.assertEqual(result["summary"]["operation_counts"]["insert"], 1)
        self.assertEqual(result["summary"]["operation_counts"]["delete"], 1)
        self.assertEqual(result["call_graph"], {"run": ["helper"], "helper": []})
        self.assertEqual(result["call_tree"][0]["method"], "run")
        self.assertEqual(result["call_tree"][0]["calls"][0]["method"], "helper")

    def test_extracts_initial_method_variables(self):
        source = """
SOURCE #checkSalesIdRange
protected boolean checkSalesIdRange()
{
    SetEnumerator se;
    LFL_SCSPickingWaveLine waveLine;
    boolean ret;
    container data;

    ret = true;
    return ret;
}
ENDSOURCE
"""

        result = analyze_source(source)

        self.assertEqual(
            result["methods"][0]["variables"],
            [
                {"type": "SetEnumerator", "name": "se"},
                {"type": "LFL_SCSPickingWaveLine", "name": "waveLine"},
                {"type": "boolean", "name": "ret"},
                {"type": "container", "name": "data"},
            ],
        )

    def test_extracts_multiple_variables_of_same_type(self):
        source = """
SOURCE #run
public void run()
{
    CustTable custTable, custTable2;

    custTable = CustTable::find("001");
}
ENDSOURCE
"""

        result = analyze_source(source)

        self.assertEqual(
            result["methods"][0]["variables"],
            [
                {"type": "CustTable", "name": "custTable"},
                {"type": "CustTable", "name": "custTable2"},
            ],
        )

    def test_method_call_at_start_of_body_is_not_variable(self):
        source = """
SOURCE #run
public void run()
{
    init();
}
ENDSOURCE
"""

        result = analyze_source(source)

        self.assertEqual(result["methods"][0]["variables"], [])

    def test_extracts_tables_and_fields_for_check_sales_id_range(self):
        source = """
SOURCE #checkSalesIdRange
protected boolean checkSalesIdRange()
{
    SetEnumerator se;
    LFL_SCSPickingWaveLine waveLine;
    boolean ret;

    while select forUpdate waveLine
        where waveLine.PickingWaveId == this.parmPickingWaveId()
           && waveLine.SalesId == salesId
    {
        if (waveLine.RecId)
        {
            waveLine.update();
        }
    }

    return ret;
}
ENDSOURCE
"""

        result = analyze_source(source)
        method = result["methods"][0]

        self.assertEqual(method["tables"], ["LFL_SCSPickingWaveLine"])
        self.assertEqual(method["fields"], ["PickingWaveId", "SalesId", "RecId"])

    def test_table_and_field_extraction_filters_non_tables_and_buffer_methods(self):
        source = """
SOURCE #run
public void run()
{
    CustTable custTable;
    SalesTable salesTable;
    boolean ret;
    SetEnumerator se;

    select firstOnly AccountNum from custTable
        where custTable.AccountNum == "001";
    while select forUpdate salesTable
        where salesTable.CustAccount == custTable.AccountNum
    {
        salesTable.SalesId = "SO-001";
        salesTable.update();
        custTable.insert();
    }
}
ENDSOURCE
"""

        result = analyze_source(source)
        method = result["methods"][0]

        self.assertEqual(method["tables"], ["CustTable", "SalesTable"])
        self.assertEqual(method["fields"], ["AccountNum", "CustAccount", "SalesId"])
        self.assertNotIn("update", method["fields"])
        self.assertNotIn("insert", method["fields"])


class DebugPointsTest(unittest.TestCase):
    def test_recommends_breakpoints_for_operations_and_calls(self):
        source = """
SOURCE #run
public void run()
{
    CustTable custTable;

    ttsBegin;
    select firstOnly custTable;
    helper();
    custTable.update();
    warning("Check customer");
    ttsCommit;
}
ENDSOURCE
SOURCE #helper
private void helper()
{
    throw error("Failed");
}
ENDSOURCE
"""

        result = analyze_source(source)
        kinds = [point["kind"] for point in result["recommended_breakpoints"]]

        self.assertEqual(result["summary"]["debug_points_count"], len(result["recommended_breakpoints"]))
        self.assertEqual(result["recommended_breakpoints"][0]["id"], "BP001")
        self.assertIn("method_entry", kinds)
        self.assertIn("transaction_start", kinds)
        self.assertIn("transaction_commit", kinds)
        self.assertIn("data_read", kinds)
        self.assertIn("data_change", kinds)
        self.assertNotIn("entry_point", kinds)
        self.assertIn("error_point", kinds)
        self.assertIn("debug_route", result)


    def test_debug_points_are_filtered_deduplicated_and_russian(self):
        source = """
SOURCE #main
public static void main(Args _args)
{
    DemoClass demo = DemoClass::construct();
    demo.initFromArgs(_args);
    demo.run();
}
ENDSOURCE
SOURCE #run
// comment before signature must not be selected
public void run()
{
    BatchHeader batchHeader;

    ttsBegin;
    BatchHeader::construct(this.parmCurrentBatch().BatchJobId);
    this.checkWaveStatus();
    this.caption();
    this.pack();
    this.unpack();
    throw error(strFmt("Волна %1 не существует", pickingWaveId));
    ttsCommit;
}
ENDSOURCE
SOURCE #checkWaveStatus
private void checkWaveStatus()
{
    ret = checkFailed("Invalid");
}
ENDSOURCE
SOURCE #parmCurrentBatch
public Batch parmCurrentBatch()
{
    return currentBatch;
}
ENDSOURCE
SOURCE #caption
public str caption()
{
    return "Demo";
}
ENDSOURCE
SOURCE #pack
public container pack()
{
    return conNull();
}
ENDSOURCE
SOURCE #unpack
public boolean unpack(container _packedClass)
{
    return true;
}
ENDSOURCE
"""

        result = analyze_source(source)
        breakpoints = result["recommended_breakpoints"]
        kinds = [point["kind"] for point in breakpoints]
        snippets = [point["snippet"] for point in breakpoints]

        self.assertNotIn("entry_point", kinds)
        self.assertTrue(all(isinstance(point["what_to_check"], list) for point in breakpoints))
        self.assertEqual(
            sum(1 for point in breakpoints if point["kind"] == "error_point" and "throw error" in point["snippet"]),
            1,
        )
        self.assertNotIn("BatchHeader::construct", [point["snippet"] for point in breakpoints if point["kind"] == "internal_call"])
        run_method = next(method for method in result["methods"] if method["name"] == "run")
        self.assertIn("BatchHeader::construct", run_method["external_calls"])
        self.assertNotIn("construct", run_method["internal_calls"])
        self.assertIn("business_call", kinds)
        self.assertFalse(any("caption" in snippet or "pack" in snippet or "unpack" in snippet for snippet in snippets))

        run_entry = next(point for point in breakpoints if point["method"] == "run" and point["kind"] == "method_entry")
        self.assertEqual(run_entry["snippet"], "public void run()")
        self.assertFalse(run_entry["snippet"].startswith("//"))

        summary = result["summary"]["breakpoints_summary"]
        self.assertEqual(summary["total_recommended"], len(breakpoints))
        self.assertEqual(sum(summary["by_priority"].values()), len(breakpoints))
        self.assertEqual(sum(summary["by_kind"].values()), len(breakpoints))
        self.assertGreaterEqual(summary["filtered_low_priority_count"], 3)
        self.assertGreaterEqual(summary["deduplicated_count"], 1)

        route_methods = [step["method"] for step in result["debug_route"]]
        self.assertIn("main", route_methods)
        self.assertIn("run", route_methods)
        self.assertTrue(any(step["method"] == "run" and step["kind"] == "business_call" for step in result["debug_route"]))

    def test_runbasebatch_entry_methods_are_recommended(self):
        source = """
class DemoBatch extends runbasebatch
{
}
SOURCE #main
public static void main(Args _args)
{
    DemoBatch batch = DemoBatch::construct();
    batch.initFromArgs(_args);
    batch.run();
}
ENDSOURCE
SOURCE #construct
public static DemoBatch construct()
{
    return new DemoBatch();
}
ENDSOURCE
SOURCE #initFromArgs
public void initFromArgs(Args _args)
{
}
ENDSOURCE
SOURCE #run
public void run()
{
}
ENDSOURCE
"""

        result = analyze_source(source)
        method_entry_points = [
            point
            for point in result["recommended_breakpoints"]
            if point["kind"] == "method_entry"
        ]

        self.assertEqual(result["class_info"]["extends"], "runbasebatch")
        self.assertGreaterEqual(len(method_entry_points), 4)
        self.assertTrue(
            {"main", "construct", "initFromArgs", "run"}.issubset(
                {point["method"] for point in method_entry_points}
            )
        )

    def test_debug_points_respect_total_limit(self):
        sections = []
        for method_index in range(8):
            body = "\n".join(f'    throw error("Failed {method_index}-{index}");' for index in range(10))
            sections.append(
                f"""
SOURCE #process{method_index}
public void process{method_index}()
{{
{body}
}}
ENDSOURCE
"""
            )
        source = "\n".join(sections)

        result = analyze_source(source)

        self.assertLessEqual(len(result["recommended_breakpoints"]), 50)
        self.assertEqual(result["summary"]["breakpoints_summary"]["total_recommended"], 50)


if __name__ == "__main__":
    unittest.main()
