import unittest

from xpp_analyzer import analyze_source, normalize_xpo_source


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


if __name__ == "__main__":
    unittest.main()
