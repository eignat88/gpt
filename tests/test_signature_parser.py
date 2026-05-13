import unittest
from dataclasses import asdict

from xpp_analyzer import analyze_source, parse_method_signature


class SignatureParserTest(unittest.TestCase):
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
        self.assertEqual(asdict(parse_method_signature(source, "checkSalesIdRange")), signature)

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
        self.assertEqual(asdict(parse_method_signature(source, "run")), signature)

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
        self.assertEqual(asdict(parse_method_signature(source, "run")), signature)

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
        self.assertEqual(asdict(parse_method_signature(source, "doDisplay")), signature)


if __name__ == "__main__":
    unittest.main()
