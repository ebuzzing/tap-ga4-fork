import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from google.analytics.data_v1beta.types import (Dimension, DimensionValue, Metric,
                                                ResponseMetaData, Row, RunReportResponse)
from tap_ga4.sync import (REPORT_METADATA_MARKER, build_report_metadata, count_other_rows,
                          sync_report)

REPORT = {"id": "report_id",
          "name": "report_name",
          "property_id": "123456789",
          "account_id": "123456",
          "dimensions": [Dimension(name="dateHour"), Dimension(name="pagePath")],
          "metrics": [Metric(name="sessions")]}


def make_response(dimension_rows, data_loss=False, row_count=None):
    return RunReportResponse(
        rows=[Row(dimension_values=[DimensionValue(value=v) for v in values])
              for values in dimension_rows],
        row_count=len(dimension_rows) if row_count is None else row_count,
        metadata=ResponseMetaData(data_loss_from_other_row=data_loss,
                                  time_zone="Europe/Paris",
                                  currency_code="EUR"))


class TestCountOtherRows(unittest.TestCase):
    def test_counts_rows_with_any_other_dimension(self):
        response = make_response([["2026090100", "/a"],
                                  ["2026090100", "(other)"],
                                  ["(other)", "(other)"]])
        self.assertEqual(2, count_other_rows(response))

    def test_no_rows(self):
        self.assertEqual(0, count_other_rows(make_response([])))


class TestReportMetadata(unittest.TestCase):
    def test_flag_false(self):
        metadata = build_report_metadata(REPORT, "2026-09-01", "2026-09-01", 0,
                                         make_response([["2026090100", "/a"]]))
        self.assertEqual({"stream": "report_name",
                          "tap_stream_id": "report_id",
                          "property_id": "123456789",
                          "start_date": "2026-09-01",
                          "end_date": "2026-09-01",
                          "page": 0,
                          "dimensions": ["dateHour", "pagePath"],
                          "metrics": ["sessions"],
                          "data_loss_from_other_row": False,
                          "row_count": 1,
                          "page_rows": 1,
                          "other_rows": 0,
                          "time_zone": "Europe/Paris",
                          "currency_code": "EUR"}, metadata)

    def test_flag_true_without_other_row(self):
        # GA4 sets the flag from the aggregated table, even when a filter dropped `(other)`.
        metadata = build_report_metadata(REPORT, "2026-09-01", "2026-09-01", 0,
                                         make_response([["2026090100", "/a"]], data_loss=True))
        self.assertTrue(metadata["data_loss_from_other_row"])
        self.assertEqual(0, metadata["other_rows"])

    def test_zero_rows(self):
        metadata = build_report_metadata(REPORT, "2026-09-01", "2026-09-01", 0, make_response([]))
        self.assertFalse(metadata["data_loss_from_other_row"])
        self.assertEqual(0, metadata["row_count"])
        self.assertEqual(0, metadata["page_rows"])


class TestSyncReportLogsMetadata(unittest.TestCase):
    def run_sync(self, pages_per_window):
        client = MagicMock()
        client.get_report.side_effect = [iter(pages) for pages in pages_per_window]
        events = []
        with patch("tap_ga4.sync.LOGGER") as logger, \
                patch("tap_ga4.sync.row_to_record", return_value={}), \
                patch("tap_ga4.sync.transform_datetimes", side_effect=lambda _, rec: rec), \
                patch("tap_ga4.sync.Transformer"), \
                patch("tap_ga4.sync.singer.write_record",
                      side_effect=lambda *_, **__: events.append("record")), \
                patch("tap_ga4.sync.singer.write_state"):
            logger.info.side_effect = lambda fmt, *args: events.append(fmt % args)
            sync_report(client, {}, REPORT, datetime(2026, 9, 1), datetime(2026, 9, 2), 1, {})
        markers = [json.loads(e.split(" ", 1)[1]) for e in events
                   if e.startswith(REPORT_METADATA_MARKER + " ")]
        return events, markers

    def test_one_line_per_response_before_its_records(self):
        events, markers = self.run_sync([
            [make_response([["2026090100", "/a"]], row_count=2),
             make_response([["2026090101", "(other)"]], data_loss=True, row_count=2)],
            [make_response([["2026090200", "/b"]])],
        ])
        self.assertEqual([(0, False, 0), (1, True, 1), (0, False, 0)],
                         [(m["page"], m["data_loss_from_other_row"], m["other_rows"]) for m in markers])
        self.assertEqual(["2026-09-01", "2026-09-01", "2026-09-02"], [m["start_date"] for m in markers])
        kinds = ["marker" if e.startswith(REPORT_METADATA_MARKER) else e for e in events
                 if e == "record" or e.startswith(REPORT_METADATA_MARKER)]
        self.assertEqual(["marker", "record", "marker", "record", "marker", "record"], kinds)

    def test_logged_before_record_writing_fails(self):
        client = MagicMock()
        client.get_report.return_value = iter([make_response([["(other)", "(other)"]], data_loss=True)])
        with patch("tap_ga4.sync.LOGGER") as logger, \
                patch("tap_ga4.sync.row_to_record", side_effect=ValueError("schema mismatch")):
            with self.assertRaises(ValueError):
                sync_report(client, {}, REPORT, datetime(2026, 9, 1), datetime(2026, 9, 1), 1, {})
        logged = [call.args[2] for call in logger.info.call_args_list
                  if call.args[1:2] == (REPORT_METADATA_MARKER,)]
        self.assertEqual(1, len(logged))
        self.assertTrue(json.loads(logged[0])["data_loss_from_other_row"])

    def test_logged_when_window_has_no_rows(self):
        _, markers = self.run_sync([[make_response([])], [make_response([])]])
        self.assertEqual(2, len(markers))
        self.assertEqual([0, 0], [m["row_count"] for m in markers])


if __name__ == "__main__":
    unittest.main()
