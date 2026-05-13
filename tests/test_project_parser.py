import unittest

from xpp_analyzer import extract_technical_objects


class ProjectParserTest(unittest.TestCase):
    def test_extracts_requested_technical_object_examples(self):
        text = """
        InventUpd_Reservation calls reserveNow().
        WHSInventBatchReserveQueryBuilder builds InventBatch.ALK_EcMarkCodeApplied filters.
        LFL_SCSPickingWaveItems should be treated as a technical object candidate.
        """

        result = extract_technical_objects(text)
        technical_objects = result["technical_objects"]

        self.assertEqual(technical_objects["classes"], ["InventUpd_Reservation"])
        self.assertEqual(technical_objects["queries"], ["WHSInventBatchReserveQueryBuilder"])
        self.assertEqual(technical_objects["tables"], ["InventBatch", "LFL_SCSPickingWaveItems"])
        self.assertEqual(technical_objects["fields"], ["InventBatch.ALK_EcMarkCodeApplied"])
        self.assertIn("reserveNow", technical_objects["methods"])

    def test_extracts_methods_services_batch_jobs_enums_and_preserves_order(self):
        text = """
        SalesPostingService::runOperation();
        SalesPostingService.runOperation();
        CustInvoiceController.startOperation();
        processLine();
        processLine();
        SalesStatusEnum::Invoiced;
        """

        result = extract_technical_objects(text)["technical_objects"]

        self.assertEqual(result["services"], ["SalesPostingService"])
        self.assertEqual(result["batch_jobs"], ["CustInvoiceController"])
        self.assertEqual(result["enums"], ["SalesStatusEnum"])
        self.assertEqual(
            result["methods"],
            ["SalesPostingService.runOperation", "CustInvoiceController.startOperation", "processLine"],
        )


if __name__ == "__main__":
    unittest.main()
