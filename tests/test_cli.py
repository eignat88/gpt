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

    def test_directory_input_enriches_project_results_after_code_index_is_built(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            input_dir.mkdir()
            (input_dir / "code.txt").write_text(
                """
class InventUpd_Reservation
{
}
SOURCE #updateReserveMore
public void updateReserveMore()
{
    InventTrans inventTrans;

    inventTrans.StatusIssue = StatusIssue::ReservPhysical;
}
ENDSOURCE
""",
                encoding="utf-8",
            )
            (input_dir / "project.txt").write_text(
                json.dumps(
                    {
                        "result_type": "project",
                        "technical_objects": {"classes": ["InventUpd_Reservation"]},
                        "description": "Доработка InventTrans в методе updateReserveMore по полю StatusIssue.",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            main([str(input_dir), "-o", str(output_dir), "--no-source"])

            project = json.loads((output_dir / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project["matches_with_code"]["classes"][0]["name"], "InventUpd_Reservation")
            self.assertEqual(project["matches_with_code"]["tables"][0]["name"], "InventTrans")
            self.assertEqual(project["matches_with_code"]["fields"][0]["name"], "StatusIssue")
            self.assertEqual(project["matches_with_code"]["methods"][0]["name"], "updateReserveMore")


if __name__ == "__main__":
    unittest.main()
