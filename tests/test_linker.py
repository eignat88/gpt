import unittest

from xpp_analyzer.linker import build_code_index, link_project_to_code


class LinkerTest(unittest.TestCase):
    def test_links_inventupd_reservation_project_to_code(self):
        class_result = {
            "result_type": "class_xpp",
            "class_info": {"name": "InventUpd_Reservation", "extends": "InventUpd"},
            "methods": [
                {
                    "name": "updateReserveMore",
                    "tables": ["InventTrans", "InventDim"],
                    "fields": ["StatusIssue", "InventDimId"],
                },
                {
                    "name": "updateReserveLess",
                    "tables": ["InventTrans"],
                    "fields": ["StatusIssue"],
                },
            ],
        }
        project_result = {
            "result_type": "project",
            "technical_objects": {"classes": ["InventUpd_Reservation"]},
            "description": (
                "Проект меняет резервирование в InventTrans: метод updateReserveMore "
                "проверяет StatusIssue и InventDimId."
            ),
        }

        code_index = build_code_index([class_result, {"result_type": "project"}])
        linked_result = link_project_to_code(project_result, code_index)

        self.assertEqual(list(code_index["classes"]), ["InventUpd_Reservation"])
        self.assertEqual(linked_result["matches_with_code"]["classes"][0]["name"], "InventUpd_Reservation")
        self.assertEqual(
            linked_result["matches_with_code"]["classes"][0]["match_reason"],
            "Точное совпадение с technical_objects.classes",
        )
        self.assertEqual(linked_result["matches_with_code"]["tables"][0]["name"], "InventTrans")
        self.assertEqual(
            linked_result["matches_with_code"]["tables"][0]["match_reason"],
            "Упоминается в проектном описании",
        )
        self.assertEqual(
            [match["name"] for match in linked_result["matches_with_code"]["fields"]],
            ["StatusIssue", "InventDimId"],
        )
        self.assertEqual(linked_result["matches_with_code"]["methods"][0]["name"], "updateReserveMore")
        self.assertEqual(
            linked_result["matches_with_code"]["methods"][0]["match_reason"],
            "Упоминается в проектном описании",
        )

    def test_class_match_is_case_sensitive_exact_match(self):
        code_index = build_code_index(
            [
                {
                    "result_type": "class_xpp",
                    "class_info": {"name": "InventUpd_Reservation"},
                    "methods": [],
                }
            ]
        )
        linked_result = link_project_to_code(
            {
                "technical_objects": {"classes": ["inventupd_reservation"]},
                "description": "InventUpd_Reservation",
            },
            code_index,
        )

        self.assertEqual(linked_result["matches_with_code"]["classes"], [])


if __name__ == "__main__":
    unittest.main()
