import unittest
from unittest.mock import patch, MagicMock
import json
import proto
from google.analytics.data_v1beta.types import Filter
from tap_ga4.client import Client


def _which_expr(filter_expression):
    """Return the name of the populated oneof field on a proto-plus FilterExpression."""
    return proto.Message.pb(filter_expression).WhichOneof("expr")


class TestClientAuthentication(unittest.TestCase):
    """Test Client initialization with different auth types."""

    @patch('tap_ga4.client.BetaAnalyticsDataClient')
    @patch('tap_ga4.client.Credentials')
    def test_oauth_client_creation(self, mock_credentials, mock_client_class):
        """Test that OAuth credentials are used correctly."""
        config = {
            'oauth_client_id': 'client-id',
            'oauth_client_secret': 'client-secret',
            'refresh_token': 'refresh-token',
        }

        mock_credentials_instance = MagicMock()
        mock_credentials.return_value = mock_credentials_instance

        client = Client(config, auth_type='oauth')

        mock_credentials.assert_called_once_with(
            None,
            refresh_token='refresh-token',
            token_uri='https://www.googleapis.com/oauth2/v4/token',
            client_id='client-id',
            client_secret='client-secret'
        )
        mock_client_class.assert_called_once_with(credentials=mock_credentials_instance)

    @patch('tap_ga4.client.BetaAnalyticsDataClient')
    def test_service_account_json_string_client_creation(self, mock_client_class):
        """Test that service account JSON string is used correctly."""
        sa_info = {'type': 'service_account', 'project_id': 'test-project'}
        config = {
            'service_account_json': json.dumps(sa_info),
        }

        Client(config, auth_type='service_account')

        mock_client_class.from_service_account_info.assert_called_once_with(sa_info)

    @patch('tap_ga4.client.BetaAnalyticsDataClient')
    def test_service_account_json_dict_client_creation(self, mock_client_class):
        """Test that service account JSON as dict is used correctly."""
        sa_info = {'type': 'service_account', 'project_id': 'test-project'}
        config = {
            'service_account_json': sa_info,
        }

        Client(config, auth_type='service_account')

        mock_client_class.from_service_account_info.assert_called_once_with(sa_info)

    @patch('tap_ga4.client.BetaAnalyticsDataClient')
    @patch('os.path.exists', return_value=True)
    def test_service_account_path_client_creation(self, mock_exists, mock_client_class):
        """Test that service account file path is used correctly."""
        config = {
            'service_account_json_path': '/path/to/sa.json',
        }

        Client(config, auth_type='service_account')

        mock_exists.assert_called_once_with('/path/to/sa.json')
        mock_client_class.from_service_account_file.assert_called_once_with(
            '/path/to/sa.json'
        )

    @patch('os.path.exists', return_value=False)
    def test_service_account_path_not_found_raises(self, mock_exists):
        """Test that missing service account file raises FileNotFoundError."""
        config = {
            'service_account_json_path': '/nonexistent/path.json',
        }

        with self.assertRaises(FileNotFoundError) as ctx:
            Client(config, auth_type='service_account')
        self.assertIn('/nonexistent/path.json', str(ctx.exception))

    def test_invalid_auth_type_raises(self):
        """Test that invalid auth_type raises ValueError."""
        config = {}
        with self.assertRaises(ValueError) as ctx:
            Client(config, auth_type='invalid')
        self.assertIn('Unknown auth_type', str(ctx.exception))

    def test_service_account_missing_credentials_raises(self):
        """Test that missing service account credentials raises ValueError."""
        config = {}
        with self.assertRaises(ValueError) as ctx:
            Client(config, auth_type='service_account')
        self.assertIn("'service_account_json' or 'service_account_json_path'",
                      str(ctx.exception))

    @patch('tap_ga4.client.BetaAnalyticsDataClient')
    @patch('tap_ga4.client.Credentials')
    def test_default_auth_type_is_oauth(self, mock_credentials, mock_client_class):
        """Test that default auth_type is oauth for backward compatibility."""
        config = {
            'oauth_client_id': 'client-id',
            'oauth_client_secret': 'client-secret',
            'refresh_token': 'refresh-token',
        }

        # Call without auth_type argument
        Client(config)

        # Should use OAuth credentials
        mock_credentials.assert_called_once()


def _oauth_config(**extra):
    config = {
        'oauth_client_id': 'client-id',
        'oauth_client_secret': 'client-secret',
        'refresh_token': 'refresh-token',
    }
    config.update(extra)
    return config


def _basic_report():
    return {
        "name": "some_report",
        "property_id": "1234567890",
        "dimensions": [],
        "metrics": [],
    }


@patch('tap_ga4.client.BetaAnalyticsDataClient')
@patch('tap_ga4.client.Credentials')
class TestLandingPageFilter(unittest.TestCase):
    """Test the landing_page_plus_query_string_regexes filter plumbing."""

    def test_no_regexes_no_filter(self, _mock_credentials, _mock_client_class):
        client = Client(_oauth_config())
        self.assertIsNone(client._landing_page_filter)

    def test_single_regex_is_flat_expression(self, _mock_credentials, _mock_client_class):
        pattern = "^/foo/.*"
        client = Client(_oauth_config(landing_page_plus_query_string_regexes=[pattern]))

        fe = client._landing_page_filter
        self.assertIsNotNone(fe)
        # Flat filter — not wrapped in or_group
        self.assertEqual(_which_expr(fe), "filter")
        self.assertEqual(fe.filter.field_name, "landingPagePlusQueryString")
        self.assertEqual(fe.filter.string_filter.value, pattern)
        self.assertEqual(
            fe.filter.string_filter.match_type,
            Filter.StringFilter.MatchType.FULL_REGEXP,
        )

    def test_multiple_regexes_or_grouped(self, _mock_credentials, _mock_client_class):
        patterns = ["^/foo/.*", "bar", "baz.*qux"]
        client = Client(_oauth_config(landing_page_plus_query_string_regexes=patterns))

        fe = client._landing_page_filter
        self.assertEqual(_which_expr(fe), "or_group")
        self.assertEqual(len(fe.or_group.expressions), 3)
        for child, expected in zip(fe.or_group.expressions, patterns):
            self.assertEqual(child.filter.field_name, "landingPagePlusQueryString")
            self.assertEqual(child.filter.string_filter.value, expected)
            self.assertEqual(
                child.filter.string_filter.match_type,
                Filter.StringFilter.MatchType.FULL_REGEXP,
            )

    def test_get_report_passes_landing_page_filter(self, _mock_credentials, _mock_client_class):
        client = Client(_oauth_config(landing_page_plus_query_string_regexes=["^/foo/.*"]))
        client._make_request = MagicMock(return_value=MagicMock(
            row_count=0,
            property_quota=MagicMock(tokens_per_hour=MagicMock(consumed=0)),
        ))

        list(client.get_report(_basic_report(), "2024-01-01", "2024-01-02"))

        sent_request = client._make_request.call_args[0][0]
        # No hardcoded filter for "some_report" → outgoing filter is the landing-page one directly
        self.assertEqual(_which_expr(sent_request.dimension_filter), "filter")
        self.assertEqual(
            sent_request.dimension_filter.filter.field_name,
            "landingPagePlusQueryString",
        )

    def test_get_report_combines_with_hardcoded_filter(self, _mock_credentials, _mock_client_class):
        client = Client(_oauth_config(landing_page_plus_query_string_regexes=["^/foo/.*"]))
        client._make_request = MagicMock(return_value=MagicMock(
            row_count=0,
            property_quota=MagicMock(tokens_per_hour=MagicMock(consumed=0)),
        ))

        report = _basic_report()
        report["name"] = "conversions_report"
        list(client.get_report(report, "2024-01-01", "2024-01-02"))

        sent_request = client._make_request.call_args[0][0]
        fe = sent_request.dimension_filter
        self.assertEqual(_which_expr(fe), "and_group")
        self.assertEqual(len(fe.and_group.expressions), 2)

        first, second = fe.and_group.expressions
        # First is the hardcoded conversions filter
        self.assertEqual(first.filter.field_name, "isKeyEvent")
        self.assertEqual(first.filter.string_filter.value, "true")
        # Second is the landing-page regex
        self.assertEqual(second.filter.field_name, "landingPagePlusQueryString")
        self.assertEqual(second.filter.string_filter.value, "^/foo/.*")

    def test_get_report_no_filters_sends_empty_filter(self, _mock_credentials, _mock_client_class):
        client = Client(_oauth_config())
        client._make_request = MagicMock(return_value=MagicMock(
            row_count=0,
            property_quota=MagicMock(tokens_per_hour=MagicMock(consumed=0)),
        ))

        list(client.get_report(_basic_report(), "2024-01-01", "2024-01-02"))

        sent_request = client._make_request.call_args[0][0]
        # When no filter is provided, the proto default is an empty FilterExpression
        self.assertIsNone(_which_expr(sent_request.dimension_filter))

    def test_get_report_hardcoded_only_when_no_landing_page(self, _mock_credentials, _mock_client_class):
        client = Client(_oauth_config())
        client._make_request = MagicMock(return_value=MagicMock(
            row_count=0,
            property_quota=MagicMock(tokens_per_hour=MagicMock(consumed=0)),
        ))

        report = _basic_report()
        report["name"] = "in_app_purchases"
        list(client.get_report(report, "2024-01-01", "2024-01-02"))

        sent_request = client._make_request.call_args[0][0]
        fe = sent_request.dimension_filter
        # Just the hardcoded filter, no and_group wrapping
        self.assertEqual(_which_expr(fe), "filter")
        self.assertEqual(fe.filter.field_name, "eventName")
        self.assertEqual(fe.filter.string_filter.value, "in_app_purchase")
