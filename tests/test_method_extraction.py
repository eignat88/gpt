import unittest

from xpp_analyzer import analyze_source, extract_methods
from tests.fixtures import XPO_SAMPLE


class MethodExtractionTest(unittest.TestCase):
    def test_xpo_sections_do_not_extract_control_flow_or_identifiers_as_methods(self):
        result = analyze_source(XPO_SAMPLE)

        names = [method["name"] for method in result["methods"]]
        self.assertEqual(result["summary"]["method_count"], 2)
        self.assertEqual(names, ["run", "helper"])
        self.assertFalse({"if", "while", "switch", "case", "name", "SalesIdRange"} & set(names))

        extracted_names = [method.name for method in extract_methods(XPO_SAMPLE)]
        self.assertEqual(extracted_names, names)

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

        extracted_names = {method.name for method in extract_methods(source)}
        self.assertEqual(extracted_names, names)


if __name__ == "__main__":
    unittest.main()
