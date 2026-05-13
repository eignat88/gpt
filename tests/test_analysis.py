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


if __name__ == "__main__":
    unittest.main()
