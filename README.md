# tap-ga4

A [Singer](https://singer.io) tap for extracting data from the
[Google Analytics 4 Data API v1](https://developers.google.com/analytics/devguides/reporting/data/v1).

- Pulls report data from a single GA4 property.
- Supports a set of premade reports plus user-defined reports via
  `report_definitions`.
- Supports OAuth and service-account authentication.
- Supports incremental replication keyed off `date`.
- Supports catalog-driven per-field regex filtering pushed down to the GA4 API.

---

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

The CLI entry point is `tap-ga4`.

---

## Configuration

The tap takes a JSON config file. Required keys:

| Key           | Description                                                    |
| ------------- | -------------------------------------------------------------- |
| `start_date`  | UTC ISO-8601 (e.g. `"2024-01-01T00:00:00Z"`) — earliest date to extract. |
| `property_id` | GA4 property ID (numeric string).                              |
| `account_id`  | GA4 account ID (numeric string).                               |

Pick **one** authentication method:

**OAuth** (all three keys required):

- `oauth_client_id`
- `oauth_client_secret`
- `refresh_token`

**Service account** (exactly one of):

- `service_account_json` — the full service-account JSON (object or JSON string).
- `service_account_json_path` — filesystem path to the JSON key file.

Mixing the two methods raises a configuration error.

Optional keys:

| Key                     | Default | Description |
| ----------------------- | ------- | ----------- |
| `end_date`              | now (UTC) | Last date to extract. |
| `conversion_window`     | `90`    | Days re-synced behind the bookmark to capture late-arriving data. |
| `request_window_size`   | `7`     | Days per GA4 API request. |
| `report_definitions`    | `[]`    | List of `{name, id, dimensions, metrics}` for custom reports. May be a JSON string. |

Minimal example (`config.json`):

```json
{
  "start_date": "2024-01-01T00:00:00Z",
  "property_id": "123456789",
  "account_id": "987654321",
  "oauth_client_id": "...",
  "oauth_client_secret": "...",
  "refresh_token": "..."
}
```

---

## Run

**1. Discover** — write the catalog to stdout:

```bash
tap-ga4 --config config.json --discover > catalog.json
```

**2. Select streams/fields** — in `catalog.json`, set `"selected": true` on the
stream metadata (breadcrumb `[]`) and on any non-automatic field metadata you
want to sync. Premade reports come with sensible `selected-by-default` flags.

**3. Sync**:

```bash
tap-ga4 --config config.json --catalog catalog.json [--state state.json] > out.jsonl
```

The tap writes a state message after each report-date chunk; pipe it back in
via `--state state.json` to resume incrementally.

---

## Per-field regex filtering (catalog-driven)

Each dimension in the generated `catalog.json` carries a
`tap-ga4.field-filter-regexes` metadata entry (default `[]`). Populate it with
one or more GA4 `FULL_REGEXP` patterns and the tap pushes the filter down to
the GA4 Data API — only matching rows are fetched.

Example dimension metadata entry:

```json
{
  "breadcrumb": ["properties", "landing_page_plus_query_string"],
  "metadata": {
    "behavior": "DIMENSION",
    "tap-ga4.api-field-names": "landingPagePlusQueryString",
    "tap-ga4.field-filter-regexes": ["^/foo/.*", "/bar/"]
  }
}
```

Combining rules:

- Multiple regexes on the **same** dimension are OR-combined.
- Filters on **different** dimensions are AND-combined.
- For premade reports with a built-in filter (`conversions_report`,
  `in_app_purchases`), the catalog filter is AND-combined with the built-in one.

Only dimensions support filtering; entries on metrics are ignored. Filtering
applies only to dimensions actually selected for sync.

---

## Report metadata log line

For every RunReport response (one page of a date window), the tap logs one
single-line JSON entry to stderr, prefixed with the marker
`GA4_REPORT_METADATA`, before writing that page's records. It is emitted
whether or not GA4 reported data loss, and before record writing so it still
reaches the consumer when writing fails (with the discovered catalog, a
`(other)` `dateHour` does not match the `date-time` schema and aborts the
tap). stdout (the Singer stream) is unchanged; records are always forwarded as
GA4 returned them.

```
INFO GA4_REPORT_METADATA {"stream":"report_name","tap_stream_id":"report_id","property_id":"123456789","start_date":"2026-09-01","end_date":"2026-09-01","page":0,"dimensions":["dateHour","pagePath"],"metrics":["sessions"],"data_loss_from_other_row":true,"row_count":1234,"page_rows":1234,"other_rows":1,"time_zone":"Europe/Paris","currency_code":"EUR"}
```

- `data_loss_from_other_row`: GA4's `ResponseMetaData.dataLossFromOtherRow`,
  i.e. some rows were aggregated into `(other)` because of high-cardinality
  dimensions. GA4 sets it regardless of filters and limits, so it can be true
  with `other_rows: 0`.
- `page`: 0-based page index within the date window.
- `row_count`: GA4's total row count for the window; `page_rows`: rows in this
  response.
- `other_rows`: rows in this response with any dimension value `(other)`.

The marker and field names are a contract for downstream consumers; keep them
stable.

---

## Tests

Unit tests (offline):

```bash
python -m unittest discover -s tests/unittests -t tests/unittests
```

The top-level `tests/` directory contains Stitch `tap_tester` integration tests
that require live GA4 credentials and the `tap_tester` framework; they are not
runnable without that environment.

---

Copyright &copy; 2022 Stitch
