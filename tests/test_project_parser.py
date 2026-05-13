import unittest

from xpp_analyzer.project_parser import analyze_project_description


class ProjectParserTest(unittest.TestCase):
    def test_analyzes_russian_functional_design_document(self):
        text = """
# DAX-11253 Автоматизация закрытия заявок

Цель:
Сократить ручную обработку заявок после подтверждения поставки.

Проблема
Операторы вручную сверяют статус поставки и забывают закрывать часть заявок.

Бизнес-процесс
1. Менеджер подтверждает поставку в AX.
2. Система проверяет связанные строки заявки.

Ограничения
- Не менять существующие статусы архивных заявок.

Ожидаемый результат
Заявка автоматически закрывается после подтверждения всех строк поставки.

Риски
- Некорректное закрытие частично поставленных заявок.
- Повторный запуск пакетного задания.

Зависимости
- Справочник статусов заявок.
- Batch-задание синхронизации поставок.

Алгоритм
1. Найти заявки со статусом "Поставка подтверждена".
2. Проверить, что все строки поставлены.
3. Установить статус "Закрыта" и записать дату закрытия.

Требования
- Закрывать только заявки по проекту DAX-11253.
- Логировать идентификатор заявки и пользователя.
"""

        result = analyze_project_description(text, source_file="fd/DAX-11253.md")

        self.assertEqual(result["project"]["code"], "DAX-11253")
        self.assertEqual(result["project"]["title"], "Автоматизация закрытия заявок")
        self.assertEqual(result["project"]["source_file"], "fd/DAX-11253.md")
        self.assertIn("Сократить ручную обработку", result["sections"]["goal"])
        self.assertIn("Операторы вручную", result["sections"]["problem"])
        self.assertIn("Менеджер подтверждает", result["sections"]["business_process"])
        self.assertIn("Не менять существующие", result["sections"]["constraints"])
        self.assertIn("автоматически закрывается", result["sections"]["expected_result"])
        self.assertEqual(
            result["business_requirements"],
            [
                "Закрывать только заявки по проекту DAX-11253",
                "Логировать идентификатор заявки и пользователя",
            ],
        )
        self.assertEqual(
            result["algorithms"],
            [
                "Найти заявки со статусом \"Поставка подтверждена\"",
                "Проверить, что все строки поставлены",
                "Установить статус \"Закрыта\" и записать дату закрытия",
            ],
        )
        self.assertEqual(
            result["dependencies"],
            ["Справочник статусов заявок", "Batch-задание синхронизации поставок"],
        )
        self.assertEqual(
            result["risks"],
            ["Некорректное закрытие частично поставленных заявок", "Повторный запуск пакетного задания"],
        )

    def test_extracts_fd_and_sup_codes_and_title_next_to_code(self):
        fd_result = analyze_project_description("FD-CRM-42: Интеграция с CRM\n\nRequirements:\n- Send customer updates")
        sup_result = analyze_project_description("Project code: SUP-77\nTitle: Исправление остатков")

        self.assertEqual(fd_result["project"]["code"], "FD-CRM-42")
        self.assertEqual(fd_result["project"]["title"], "Интеграция с CRM")
        self.assertEqual(fd_result["business_requirements"], ["Send customer updates"])
        self.assertEqual(sup_result["project"]["code"], "SUP-77")
        self.assertEqual(sup_result["project"]["title"], "Исправление остатков")


if __name__ == "__main__":
    unittest.main()
