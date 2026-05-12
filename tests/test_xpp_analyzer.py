import unittest
from pathlib import Path

from xpp_analyzer import analyze_source, normalize_xpo_source, output_path_for_result


XPO_SAMPLE = """
Exportfile for AOT version 1.0 or later
Formatversion: 1

***Element: CLS

; Microsoft Dynamics AX Class: Demo unloaded
; --------------------------------------------------------------------------------
  CLSVERSION 1

SOURCE #run
public void run()
{
    if (SalesIdRange)
    {
        while (name)
        {
            switch (SalesIdRange)
            {
                case 1:
                    this.helper(SalesIdRange);
                    break;
            }
        }
    }

    select firstOnly custTable;
    other.doWork();
}
ENDSOURCE
SOURCE #helper
private void helper(SalesIdRange _salesIdRange)
{
    ttsBegin;
    while select forUpdate salesTable
    {
        salesTable.update();
    }
    tableBuffer.insert();
    tableBuffer.delete();
}
ENDSOURCE
"""


class AnalyzerTest(unittest.TestCase):
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

    def test_xpo_sections_do_not_extract_control_flow_or_identifiers_as_methods(self):
        result = analyze_source(XPO_SAMPLE)

        names = [method["name"] for method in result["methods"]]
        self.assertEqual(result["summary"]["method_count"], 2)
        self.assertEqual(names, ["run", "helper"])
        self.assertFalse({"if", "while", "switch", "case", "name", "SalesIdRange"} & set(names))

    def test_normalizes_xpo_method_markers_before_analysis(self):
        xpo_source = """
class Demo
{
    #SOURCE #run
    #public void run()
    #{
    #}
    #ENDSOURCE
}
"""

        result = analyze_source(normalize_xpo_source(xpo_source))

        self.assertEqual(result["summary"]["method_count"], 1)
        self.assertEqual(result["methods"][0]["name"], "run")

    def test_extracts_class_info_from_lfl_scspickingwaverun(self):
        source = """
PROPERTIES
  Name                #LFL_SCSPickingWaveRun
  Origin              #{local}
ENDPROPERTIES

class LFL_SCSPickingWaveRun extends RunBaseBatch
{
    #define.CurrentVersion(4)

    public void run()
    {
    }
}
"""

        result = analyze_source(source)

        expected = {
            "name": "LFL_SCSPickingWaveRun",
            "extends": "RunBaseBatch",
            "origin": "local",
            "current_version": 4,
        }
        self.assertEqual(result["class_info"], expected)

        xpo_source = """
#PROPERTIES
#  Name                #LFL_SCSPickingWaveRun
#  Origin              #{local}
#ENDPROPERTIES
#
#class LFL_SCSPickingWaveRun extends RunBaseBatch
#{
#    ##define.CurrentVersion(4)
#}
"""

        self.assertEqual(analyze_source(xpo_source)["class_info"], expected)

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

    def test_lfl_scspickingwaverun_acceptance_does_not_extract_body_tokens_as_methods(self):
        source = """
SOURCE #run
class LFL_SCSPickingWaveRun
{
    public void run()
    {
        if (SalesIdRange)
        {
            while (name)
            {
                switch (SalesIdRange)
                {
                    case 1:
                        break;
                }
            }
        }
    }
}
ENDSOURCE
"""

        result = analyze_source(source, include_source=False)
        names = {method["name"] for method in result["methods"]}

        self.assertEqual(result["summary"]["method_count"], 1)
        self.assertNotIn("if", names)
        self.assertNotIn("while", names)
        self.assertNotIn("switch", names)
        self.assertNotIn("name", names)
        self.assertNotIn("SalesIdRange", names)

    def test_xpo_source_marker_uses_signature_name_when_different(self):
        source = """
SOURCE #SalesIdRange
public Object dialog()
{
}
ENDSOURCE
"""

        result = analyze_source(source)

        self.assertEqual(result["methods"][0]["name"], "dialog")
        self.assertEqual(result["methods"][0]["signature"]["name"], "dialog")
        self.assertEqual(result["summary"]["method_count"], 1)

    def test_extracts_method_signature_metadata(self):
        source = """
SOURCE #checkSalesIdRange
protected boolean checkSalesIdRange()
{
}
ENDSOURCE
"""

        result = analyze_source(source)
        signature = result["methods"][0]["signature"]

        self.assertEqual(signature["access"], "protected")
        self.assertFalse(signature["static"])
        self.assertEqual(signature["return_type"], "boolean")
        self.assertEqual(signature["name"], "checkSalesIdRange")
        self.assertEqual(signature["parameters"], [])

    def test_extracts_check_sales_id_range_table_fields_from_buffer_references(self):
        source = """
SOURCE #checkSalesIdRange
protected boolean checkSalesIdRange()
{
    LFL_SCSPickingWaveLine waveLine;
    boolean ret;

    select firstOnly waveLine
        where waveLine.PickingWaveId == this.parmPickingWaveId()
           && waveLine.SalesId == salesTable.SalesId;

    ret = waveLine.RecId != 0;
    if (waveLine.SalesId)
    {
        waveLine.update();
        this.helper();
        strFmt("%1", waveLine.SalesId);
    }

    return ret;
}
ENDSOURCE
"""

        result = analyze_source(source)
        method = result["methods"][0]

        self.assertEqual(method["tables"], ["LFL_SCSPickingWaveLine"])
        self.assertEqual(method["fields"], ["PickingWaveId", "SalesId", "RecId"])
        self.assertNotIn("update", method["fields"])
        self.assertNotIn("helper", method["fields"])
        self.assertNotIn("strFmt", method["fields"])

    def test_extracts_static_method_signature_parameters_and_defaults(self):
        source = """
SOURCE #run
public static void run(SalesId _salesId = "001")
{
}
ENDSOURCE
"""

        result = analyze_source(source)
        signature = result["methods"][0]["signature"]

        self.assertEqual(signature["access"], "public")
        self.assertTrue(signature["static"])
        self.assertEqual(signature["return_type"], "void")
        self.assertEqual(signature["name"], "run")
        self.assertEqual(
            signature["parameters"],
            [{"name": "_salesId", "type": "SalesId", "default": '"001"'}],
        )

    def test_ignores_macros_directives_and_comments_before_method_signatures(self):
        cases = [
            (
                "run",
                """
SOURCE #run
#define.Test("1")
public void run()
{ }
ENDSOURCE
""",
                {"access": "public", "static": False, "return_type": "void", "name": "run"},
            ),
            (
                "pack",
                """
SOURCE #pack
#localmacro.Test
#endmacro
public static container pack()
{ }
ENDSOURCE
""",
                {"access": "public", "static": True, "return_type": "container", "name": "pack"},
            ),
            (
                "validate",
                """
SOURCE #validate
// comment
protected boolean validate()
{ }
ENDSOURCE
""",
                {"access": "protected", "static": False, "return_type": "boolean", "name": "validate"},
            ),
            (
                "execute",
                """
SOURCE #execute
/* block comment */
private server void execute()
{ }
ENDSOURCE
""",
                {"access": "private", "static": False, "return_type": "void", "name": "execute"},
            ),
        ]

        for expected_name, source, expected_signature in cases:
            with self.subTest(method=expected_name):
                result = analyze_source(source)
                methods = result["methods"]
                signature = methods[0]["signature"]

                self.assertEqual(result["summary"]["method_count"], 1)
                self.assertEqual(methods[0]["name"], expected_name)
                self.assertEqual(signature["access"], expected_signature["access"])
                self.assertEqual(signature["static"], expected_signature["static"])
                self.assertEqual(signature["return_type"], expected_signature["return_type"])
                self.assertEqual(signature["name"], expected_signature["name"])

        sales_id_range_source = """
SOURCE #SalesIdRange
#define.SalesIdRange("SalesIdRange")
public Object dialog()
{ }
ENDSOURCE
"""

        result = analyze_source(sales_id_range_source)
        method_names = [method["name"] for method in result["methods"]]

        self.assertEqual(result["summary"]["method_count"], 1)
        self.assertEqual(method_names, ["dialog"])
        self.assertNotIn("SalesIdRange", method_names)

    def test_signature_parser_ignores_preprocessor_and_comments_before_method(self):
        source = """
SOURCE #run
#define.Fake(public void wrongDefine() {)
#localmacro.FakeMethod
public void wrongMacro()
{
}
#endmacro
// public void wrongLineComment()
// {
// }
/*
public void wrongBlockComment()
{
}
*/
protected static boolean run(int _count = 1)
{
}
ENDSOURCE
"""

        result = analyze_source(source)
        signature = result["methods"][0]["signature"]

        self.assertEqual(signature["access"], "protected")
        self.assertTrue(signature["static"])
        self.assertEqual(signature["return_type"], "boolean")
        self.assertEqual(signature["name"], "run")
        self.assertEqual(signature["parameters"], [{"name": "_count", "type": "int", "default": "1"}])

    def test_signature_parser_supports_entry_tokens_and_requires_return_type(self):
        source = """
SOURCE #doDisplay
if (ready)
{
}
public static server str doDisplay(str _value)
{
}
ENDSOURCE
"""

        result = analyze_source(source)
        signature = result["methods"][0]["signature"]

        self.assertEqual(signature["access"], "public")
        self.assertTrue(signature["static"])
        self.assertEqual(signature["return_type"], "str")
        self.assertEqual(signature["name"], "doDisplay")
        self.assertEqual(signature["parameters"], [{"name": "_value", "type": "str", "default": None}])

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


if __name__ == "__main__":
    unittest.main()
