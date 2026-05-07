import unittest

from converters.php_converter import format_as_php_array, parse_sql_content


class PhpConverterTest(unittest.TestCase):
    def test_parse_sql_content_preserves_rows_after_html_entity_semicolon(self):
        sql = '''
        INSERT INTO `organization` (`id`, `name`, `parent_id`, `supervisor`, `deleted_by`, `deleted_at`) VALUES
            (21, "CORPORATE ACCOUNTS SUPPORT", 2, NULL, NULL, NULL),
            (23, "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION", 2, NULL, NULL, NULL),
            (24, "E-COMMERCE", 2, NULL, NULL, NULL);
        '''

        data, table_columns = parse_sql_content(sql)

        self.assertEqual(
            ["id", "name", "parent_id", "supervisor", "deleted_by", "deleted_at"],
            table_columns["organization"],
        )
        self.assertEqual(3, len(data["organization"]))
        self.assertEqual(
            "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION",
            data["organization"][1]["name"],
        )
        self.assertEqual("E-COMMERCE", data["organization"][2]["name"])

    def test_format_as_php_array_keeps_nulls_and_numbers(self):
        data = {
            "organization": [
                {
                    "id": "23",
                    "name": "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION",
                    "parent_id": "2",
                    "deleted_at": "null",
                }
            ]
        }

        php = format_as_php_array(data)

        self.assertIn("'id' => '23'", php)
        self.assertIn("'name' => 'CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION'", php)
        self.assertIn("'deleted_at' => null", php)


if __name__ == "__main__":
    unittest.main()
