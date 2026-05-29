import unittest

from app.services.parser_service import ParserService


class ParserServiceTest(unittest.TestCase):
    def test_parse_labeled_lot_exp_and_dom(self) -> None:
        parsed = ParserService().parse(["LOT: RN620", "EXP: 10 2026", "DOM: 10 2023"])

        self.assertEqual(parsed.lot_number, "RN620")
        self.assertEqual(parsed.expiration_date, "2026-10")
        self.assertEqual(parsed.manufacture_date, "2023-10")

    def test_parse_unlabeled_expiration_fallback_from_real_ocr_shape(self) -> None:
        parsed = ParserService().parse(["PPC : 139.00 DH", "Lot : CIX31", "07/25"])

        self.assertEqual(parsed.lot_number, "CIX31")
        self.assertEqual(parsed.expiration_date, "2025-07")
        self.assertIsNone(parsed.manufacture_date)

    def test_parse_split_label_and_value_columns_from_real_ocr_shape(self) -> None:
        parsed = ParserService().parse(
            ["LOT:", "EXP:", "10", "2026", "RN620", "DOM:", "10", "2023", "CLX", "C"]
        )

        self.assertEqual(parsed.lot_number, "RN620")
        self.assertEqual(parsed.expiration_date, "2026-10")
        self.assertEqual(parsed.manufacture_date, "2023-10")

    def test_parse_numeric_lot_after_split_label(self) -> None:
        parsed = ParserService().parse(["LOT", "251391", "EXP", "04 2028"])

        self.assertEqual(parsed.lot_number, "251391")
        self.assertEqual(parsed.expiration_date, "2028-04")

    def test_parse_lot_value_before_label(self) -> None:
        parsed = ParserService().parse(["2JV0951", "LOT:", "09-2025", "EXP:", "10-2022"])

        self.assertEqual(parsed.lot_number, "2JV0951")
        self.assertEqual(parsed.expiration_date, "2022-10")

    def test_parse_per_and_emp_as_expiration_labels(self) -> None:
        parsed = ParserService().parse(["K43598 05.24", "EMP 05.27"])

        self.assertEqual(parsed.expiration_date, "2027-05")

    def test_labeled_expiration_takes_precedence_over_unlabeled_date(self) -> None:
        parsed = ParserService().parse(["BATCH K8NGWAHVKJ", "EXP DATE 08-2025", "01/2024"])

        self.assertEqual(parsed.lot_number, "K8NGWAHVKJ")
        self.assertEqual(parsed.expiration_date, "2025-08")


if __name__ == "__main__":
    unittest.main()
