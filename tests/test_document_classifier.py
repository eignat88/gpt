import unittest

from xpp_analyzer.document_classifier import classify_document


class DocumentClassifierTest(unittest.TestCase):
    def test_classifies_aot_class_export_as_class_xpp(self):
        text = """
***Element: CLS
CLASS #SalesFormLetter_Invoice
METHODS
SOURCE #run
public void run()
{
}
ENDSOURCE
"""

        self.assertEqual(classify_document(text), "class_xpp")

    def test_classifies_project_description_by_task_and_sections(self):
        text = """
DAX-11253 Автоматизация проверки заказов

Цели
Сократить ручную обработку ошибок.

Алгоритм
1. Найти документы с расхождениями.
2. Создать уведомление для ответственного.

Бизнес-процесс
Пользователь SUP подтверждает результат обработки.
"""

        self.assertEqual(classify_document(text), "project_description")

    def test_classifies_document_with_code_and_specification_as_mixed(self):
        text = """
DAX-11253 Требования к доработке класса

***Element: CLS
CLASS #CustInvoicePost
METHODS
SOURCE #validate
public boolean validate()
{
    return true;
}
ENDSOURCE
"""

        self.assertEqual(classify_document(text), "mixed_document")

    def test_methods_word_in_prose_is_not_enough_for_xpp(self):
        text = "The requirements describe methods for FD 42 without an AOT export."

        self.assertEqual(classify_document(text), "project_description")

    def test_plain_text_without_explicit_markers_defaults_to_project_description(self):
        text = "Нужно описать поведение формы и согласовать детали с пользователем."

        self.assertEqual(classify_document(text), "project_description")

    def test_source_marker_alone_is_enough_for_xpp_boundary_case(self):
        text = "SOURCE #pack\npublic container pack()\n{\n}\nENDSOURCE\n"

        self.assertEqual(classify_document(text), "class_xpp")


if __name__ == "__main__":
    unittest.main()
