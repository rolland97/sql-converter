import unittest

from converters.insert_parser import parse_insert_statements


class InsertParserTest(unittest.TestCase):
    def test_parses_semicolon_and_comma_inside_double_quoted_value(self):
        sql = '''
        INSERT INTO `organization` (`id`, `name`, `parent_id`, `supervisor`, `deleted_by`, `deleted_at`) VALUES
            (21, "CORPORATE ACCOUNTS SUPPORT", 2, NULL, NULL, NULL),
            (23, "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION", 2, NULL, NULL, NULL),
            (24, "E-COMMERCE", 2, NULL, NULL, NULL);
        '''

        parsed = parse_insert_statements(sql)

        self.assertEqual(["organization"], list(parsed.keys()))
        self.assertEqual(
            ["id", "name", "parent_id", "supervisor", "deleted_by", "deleted_at"],
            parsed["organization"]["columns"],
        )
        self.assertEqual(3, len(parsed["organization"]["rows"]))
        self.assertEqual(
            "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION",
            parsed["organization"]["rows"][1][1],
        )
        self.assertEqual("E-COMMERCE", parsed["organization"]["rows"][2][1])

    def test_parses_semicolon_inside_single_quoted_value(self):
        sql = "INSERT INTO `notes` (`id`, `body`) VALUES (1, 'first; still same value'), (2, 'next');"

        parsed = parse_insert_statements(sql)

        self.assertEqual(2, len(parsed["notes"]["rows"]))
        self.assertEqual("first; still same value", parsed["notes"]["rows"][0][1])
        self.assertEqual("next", parsed["notes"]["rows"][1][1])

    def test_parses_parentheses_and_escaped_quotes_inside_values(self):
        sql = r"INSERT INTO `items` (`id`, `name`, `amount`) VALUES (1, 'Lab (Asia) O\\'Brien', -12.50);"

        parsed = parse_insert_statements(sql)

        self.assertEqual("Lab (Asia) O'Brien", parsed["items"]["rows"][0][1])
        self.assertEqual("-12.50", parsed["items"]["rows"][0][2])

    def test_raises_when_no_insert_exists(self):
        with self.assertRaisesRegex(Exception, "No INSERT statements found"):
            parse_insert_statements("CREATE TABLE `users` (`id` int);")


if __name__ == "__main__":
    unittest.main()
