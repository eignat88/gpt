import json
import tempfile
import unittest
from pathlib import Path

from xpp_analyzer.cli import main


class CliTest(unittest.TestCase):
    def test_directory_input_processes_txt_files_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            input_dir.mkdir()
            (input_dir / "b.txt").write_text(
                """
class SecondClass
{
}
SOURCE #run
public void run()
{
}
ENDSOURCE
""",
                encoding="utf-8",
            )
            (input_dir / "a.txt").write_text(
                """
class FirstClass
{
}
SOURCE #run
public void run()
{
}
ENDSOURCE
""",
                encoding="utf-8",
            )
            (input_dir / "ignored.xpp").write_text("class Ignored {}", encoding="utf-8")

            main([str(input_dir), "-o", str(output_dir), "--no-source"])

            self.assertEqual(sorted(path.name for path in output_dir.iterdir()), ["FirstClass.json", "SecondClass.json"])
            first = json.loads((output_dir / "FirstClass.json").read_text(encoding="utf-8"))
            self.assertEqual(first["class_info"]["name"], "FirstClass")
            self.assertIsNone(first["methods"][0]["source"])

    def test_directory_input_falls_back_to_txt_file_name_when_class_name_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            input_dir.mkdir()
            (input_dir / "no class.txt").write_text(
                """
SOURCE #run
public void run()
{
}
ENDSOURCE
""",
                encoding="utf-8",
            )

            main([str(input_dir)])

            self.assertTrue((input_dir / "no class.json").exists())


if __name__ == "__main__":
    unittest.main()
