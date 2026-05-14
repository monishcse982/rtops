## Summary

- Add a Locust-based performance test scaffold for product browsing, with local report output and a parameterized ramp-up/sustain/ramp-down load profile.

## What changed

- Added a `tests/perf/` Locust scaffold with:
  - a shared `BaseApiUser` helper for request/JSON validation
  - a `ProductBrowsingUser` scenario that lists products and fetches product details
  - a `RampUpSustainRampDown` custom load shape
- Added Locust startup/config hooks to:
  - create a timestamped local report directory per run
  - write HTML, CSV, and JSON Locust artifacts into that directory
  - expose custom ramp/sustain/ramp-down inputs to Locust
- Added `tests/perf/locust.local.conf` as the local entrypoint
- Added `make locust` and `make locust-headless` commands for local UI and headless runs
- Added `locust` to the dev dependency group and refreshed `uv.lock`
- Updated `.gitignore` for generated report output

## Testing

- `python3 -m py_compile tests/perf/base_user.py tests/perf/commons.py tests/perf/config.py tests/perf/locustfile.py tests/perf/load_profiles/__init__.py tests/perf/load_profiles/ramp_up_sustain_ramp_down.py tests/perf/users/product_browsing.py`
- `uv run python3 - <<'PY' ... load_locustfile('tests/perf/locustfile.py') ... PY` to verify Locust discovers `ProductBrowsingUser` and `RampUpSustainRampDown`
- `uv lock`

## Risk

- Low to medium. This adds new tooling and a new local run path, but it does not change application runtime behavior.

## Notes for reviewer

- Run Locust through `tests/perf/locust.local.conf` so the report hooks load and a timestamped report directory is created.
- The current product scenario assumes a seeded product catalog is available at the configured API host.
