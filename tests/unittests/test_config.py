import unittest
from tap_ga4 import maybe_parse_report_definitions, maybe_parse_landing_page_regexes


class TestMaybeParseReportDefinitions(unittest.TestCase):
    config_with_list = {'report_definitions':
                        [{'name': 'report1', 'id': 'id1'},
                         {'name': 'report2', 'id': 'id2'}],
                        'start_date': '2024-02-24T00:00:00Z',}

    config_with_string = {'report_definitions':
                          "[{\"name\":\"report1\",\"id\":\"id1\"},{\"name\":\"report2\",\"id\":\"id2\"}]",
                          'start_date': '2024-02-24T00:00:00Z',}

    config_without_report_definitions = {'start_date': '2024-02-24T00:00:00Z'}

    config_with_bad_type = {'report_definitions':
                            12345,
                            'start_date': '2024-02-24T00:00:00Z',}

    def test_with_list(self):
        """Test that config with report_definitions of type list remains unchanged"""
        self.assertIsInstance(self.config_with_list["report_definitions"], list)
        maybe_parse_report_definitions(self.config_with_list)
        self.assertIsInstance(self.config_with_list["report_definitions"], list)
        self.assertEqual(self.config_with_list["start_date"], '2024-02-24T00:00:00Z')

    def test_with_string(self):
        """Test that config with report_definitions of type string is converted to type list"""
        self.assertIsInstance(self.config_with_string["report_definitions"], str)
        maybe_parse_report_definitions(self.config_with_string)
        self.assertIsInstance(self.config_with_string["report_definitions"], list)
        self.assertEqual(self.config_with_string["start_date"], '2024-02-24T00:00:00Z')
        self.assertEqual(self.config_with_string, self.config_with_list)

    def test_without_report_definitions(self):
        """Test that config without report_definitions does not break"""
        assert "report_definitions" not in self.config_without_report_definitions
        maybe_parse_report_definitions(self.config_without_report_definitions)
        assert "report_definitions" not in self.config_without_report_definitions
        self.assertEqual(self.config_without_report_definitions["start_date"], '2024-02-24T00:00:00Z')

    def test_with_bad_type(self):
        """Test that config with report_definitions with unexpected type is unchanged by the function"""
        self.assertIsInstance(self.config_with_bad_type["report_definitions"], int)
        maybe_parse_report_definitions(self.config_with_bad_type)
        self.assertIsInstance(self.config_with_bad_type["report_definitions"], int)
        self.assertEqual(self.config_with_bad_type["start_date"], '2024-02-24T00:00:00Z')


class TestMaybeParseLandingPageRegexes(unittest.TestCase):
    def test_absent(self):
        """Config without the key is left untouched."""
        config = {'start_date': '2024-02-24T00:00:00Z'}
        maybe_parse_landing_page_regexes(config)
        self.assertNotIn("landing_page_plus_query_string_regexes", config)

    def test_with_list(self):
        """A list of strings is left as-is."""
        config = {"landing_page_plus_query_string_regexes": ["^/foo/.*", "bar"]}
        maybe_parse_landing_page_regexes(config)
        self.assertEqual(config["landing_page_plus_query_string_regexes"], ["^/foo/.*", "bar"])

    def test_with_string(self):
        """A JSON-encoded string is parsed into a list."""
        config = {"landing_page_plus_query_string_regexes": '["^/foo/.*", "bar"]'}
        maybe_parse_landing_page_regexes(config)
        self.assertEqual(config["landing_page_plus_query_string_regexes"], ["^/foo/.*", "bar"])

    def test_with_empty_list(self):
        """An empty list is accepted."""
        config = {"landing_page_plus_query_string_regexes": []}
        maybe_parse_landing_page_regexes(config)
        self.assertEqual(config["landing_page_plus_query_string_regexes"], [])

    def test_with_non_string_entries_raises(self):
        config = {"landing_page_plus_query_string_regexes": ["ok", 123]}
        with self.assertRaises(ValueError):
            maybe_parse_landing_page_regexes(config)

    def test_with_non_list_raises(self):
        config = {"landing_page_plus_query_string_regexes": 12345}
        with self.assertRaises(ValueError):
            maybe_parse_landing_page_regexes(config)

    def test_with_malformed_json_string_raises(self):
        config = {"landing_page_plus_query_string_regexes": '["unterminated'}
        with self.assertRaises(ValueError):
            maybe_parse_landing_page_regexes(config)
