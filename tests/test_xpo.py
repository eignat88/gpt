import unittest

from xpp_analyzer import analyze_source, extract_class_info, normalize_xpo_source


class XpoTest(unittest.TestCase):
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
        self.assertEqual(extract_class_info(source), expected)
        self.assertEqual(extract_class_info(xpo_source), expected)

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


if __name__ == "__main__":
    unittest.main()
