# AGENTS.md

Guidance for Codex and other AI coding agents working in this repository.

## Start Here

- Inspect the current files before advising or editing. Do not rely only on earlier conversation state.
- Check `git status --short` before and after edits. Preserve user changes and do not revert unrelated work.
- Use the repo's existing patterns first. Keep changes narrow and avoid unrelated refactors.
- Use `uv` for Python commands and dependency workflows.
- Prefer raw commands first when the user asks how to run something. Makefile targets are useful, but they should not hide the underlying command when the user is learning.
- If the user says they want to write or learn the code themselves, guide step by step instead of taking over implementation.

## Commands

Common local checks:

```sh
uv run pytest tests/unit -q
uv run pytest tests/e2e -q -s
uv run pre-commit run --all-files
```

For syntax/import checks on perf files:

```sh
uv run python3 -m py_compile tests/perf/locustfile.py tests/perf/users/product_browsing.py tests/perf/load_profiles/load_profiles.py
```

When changing dependencies, update the lockfile:

```sh
uv lock
```

## E2E Tests

- E2E tests live under `tests/e2e`.
- Keep API base URL, database URL, and service endpoints configurable through environment variables or existing test config helpers.
- Allure output and generated reports should stay out of commits unless explicitly requested.
- If pre-commit reformats or edits generated files, re-check `git status`, re-stage the changed files, then commit.

## Locust Perf Tests

- Use `tests/perf/locustfile.py` as the central Locust entrypoint for normal runs. Running a user file directly can bypass shared config, shape classes, and report setup.
- Use stable request names so Locust metrics aggregate cleanly:
  - Good: `name="GET /api/products/{id}"`
  - Avoid: embedding random IDs, prices, pages, or query values in the request name.
- Include the HTTP method in Locust request names when endpoints share paths across methods.
- Keep performance tests focused on user journeys and API-level sanity. Do not turn Locust scenarios into deep functional or database validation suites.
- Prefer plain Python assertions over `.should` unless the assertion library is explicitly imported and verified. `response.status_code` is an `int`.
- If a base Locust user class has no tasks, mark it with `abstract = True`.
- Prefer simple wait-time callables such as `between(...)` or constants that resolve directly to callables. Do not assume a `.value` attribute exists.
- Use `catch_response=True` through shared helpers when adding response validation, so failures appear in Locust metrics instead of only as task exceptions.
- Do not assert that search or filter responses always contain items unless the fixture data guarantees it. Empty search results can be a valid API response.
- Verify product payload fields from schemas and routers before asserting on them. Previous work found that assumptions like `in_stock` can be wrong.
- Normalize numeric payload values before comparing them. Prices may arrive as strings, so convert with `Decimal` or another deliberate parser before sorting or range assertions.

Example local UI run:

```sh
uv run locust --config tests/perf/locust.local.conf --host http://localhost:8000
```

Example headless run:

```sh
uv run locust --config tests/perf/locust.local.conf --host http://localhost:8000 --headless -u 10 -r 2 -t 1m
```

## Load Profiles

- Custom Locust load shapes should live under `tests/perf/load_profiles`.
- Keep one well-named shape per behavior unless there is a clear reason to split further.
- For ramp-up, sustain, and ramp-down profiles, make the stage inputs explicit and validate them early.
- In the Locust UI, when a shape class is selected, user count and spawn rate may be controlled by the shape instead of the UI inputs. Make that clear when explaining runs.

## Reports

- Store local Locust reports in a timestamped folder under `reports/locust/local/<timestamp>/`.
- Prefer configuring report output through the central Locust config or entrypoint instead of asking users to remember long `--html` and CSV flags.
- Generated reports are build/test artifacts. Do not commit them unless the user explicitly asks.

## Lessons From Previous Work

Things to do better:

- Validate actual API behavior before writing assertions for filters, sorting, and field names.
- Avoid dynamic Locust request names that fragment the report.
- Keep load-test assertions lightweight and stable under changing seed data.
- Explain raw commands directly before adding Makefile convenience wrappers.
- Verify Locust discovery and UI behavior after adding user classes or shape classes.
- When pushing or raising a PR, refresh the current branch, status, and diff instead of assuming prior state.

Patterns the user accepted:

- Locust scenarios organized under `tests/perf/users`.
- Shared perf helpers/base user to reduce repeated `catch_response=True` boilerplate.
- A central `tests/perf/locustfile.py` for normal Locust runs.
- A custom `RampUpSustainRampDown` shape for controlled load profiles.
- Timestamped local report output for later publishing.
- Stable, method-prefixed request names that correlate with the API collection.
- Plain Python `assert` for simple checks.

Corrections to preserve:

- The user wants to learn Locust by writing it directly, so guide incrementally when asked.
- `har2locust` is not the preferred path for this repo right now.
- Do not overcomplicate local run ergonomics. If a raw command solves the problem, give the raw command.
- Do not assume enum-style `.value` access for wait strategies.
- Do not assume product search/filter results are non-empty.
- Do not assume product response fields without checking schemas.

## Before Push Or PR

- Only use `feat/` as default, `doc/` for documentation publishing, `fix/` for bug fixes as branch prefixes.
- Run the narrowest relevant tests first, then broader checks if the change affects shared behavior.
- For Locust changes, at minimum verify Python compilation and Locust file discovery.
- Review `git diff --stat` and `git diff` before staging.
- Stage only intentional files.
- Push the current branch only after confirming the commit contains the intended changes.
