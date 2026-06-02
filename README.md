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
