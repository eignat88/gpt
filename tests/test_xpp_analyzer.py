import unittest

from xpp_analyzer import analyze_source, normalize_xpo_source


SAMPLE = """
class Demo
{
    public void run()
    {
        select firstOnly custTable;
        this.helper();
        other.doWork();
    }

    private void helper()
    {
        ttsBegin;
        while select forUpdate salesTable
        {
            salesTable.update();
        }
        tableBuffer.insert();
        tableBuffer.delete();
    }
}
"""


class AnalyzerTest(unittest.TestCase):
    def test_extracts_methods_operations_and_tree(self):
        result = analyze_source(SAMPLE)

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

    def test_normalizes_xpo_method_markers_before_analysis(self):
        xpo_source = """
class Demo
{
    #public void run()
    #{
    #}
}
"""

        result = analyze_source(normalize_xpo_source(xpo_source))

        self.assertEqual(result["summary"]["method_count"], 1)
        self.assertEqual(result["methods"][0]["name"], "run")



if __name__ == "__main__":
    unittest.main()
