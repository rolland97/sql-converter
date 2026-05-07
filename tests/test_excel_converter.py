import unittest

from converters.excel_converter import parse_sql_insert_statements


class ExcelConverterTest(unittest.TestCase):
    def test_parse_sql_insert_statements_preserves_rows_after_html_entity_semicolon(self):
        sql = '''
        INSERT INTO `organization` (`id`, `name`, `parent_id`, `supervisor`, `deleted_by`, `deleted_at`) VALUES
            (21, "CORPORATE ACCOUNTS SUPPORT", 2, NULL, NULL, NULL),
            (23, "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION", 2, NULL, NULL, NULL),
            (24, "E-COMMERCE", 2, NULL, NULL, NULL);
        '''

        data = parse_sql_insert_statements(sql)

        self.assertEqual(
            ["id", "name", "parent_id", "supervisor", "deleted_by", "deleted_at"],
            data["organization"]["columns"],
        )
        self.assertEqual(3, len(data["organization"]["rows"]))
        self.assertEqual(
            "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION",
            data["organization"]["rows"][1][1],
        )
        self.assertEqual("E-COMMERCE", data["organization"]["rows"][2][1])

    def test_parse_sql_insert_statements_converts_excel_value_types(self):
        sql = "INSERT INTO `metrics` (`id`, `amount`, `deleted_at`) VALUES (7, -12.50, NULL);"

        data = parse_sql_insert_statements(sql)

        self.assertEqual(7, data["metrics"]["rows"][0][0])
        self.assertEqual(-12.50, data["metrics"]["rows"][0][1])
        self.assertIsNone(data["metrics"]["rows"][0][2])


if __name__ == "__main__":
    unittest.main()
