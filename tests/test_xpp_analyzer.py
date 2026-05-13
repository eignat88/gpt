import unittest

from xpp_analyzer import analyze_source


class AnalyzerFacadeTest(unittest.TestCase):
    def test_public_analyze_source_facade_remains_backward_compatible(self):
        source = """
SOURCE #run
public void run()
{
}
ENDSOURCE
"""

        result = analyze_source(source)

        self.assertEqual(result["summary"]["method_count"], 1)
        self.assertEqual(result["methods"][0]["name"], "run")


if __name__ == "__main__":
    unittest.main()
