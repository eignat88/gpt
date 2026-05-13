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


if __name__ == "__main__":
    unittest.main()
