# ADR 0005: Test Reporting Strategy

## Status

Accepted

## Context

The repository already has two distinct reporting styles in place:

- functional E2E tests attach rich request, response, assertion, and DB evidence through Allure helpers in `tests/e2e/reporting.py`
- performance tests generate timestamped local Locust report artifacts through `tests/perf/config.py`

The repository also already runs meaningful validation on commit and push boundaries, including:

- formatting and hygiene hooks
- secret and env-file protection
- Kubernetes kustomize validation
- Alembic head validation
- Docker image build verification

We need a reporting strategy that explains what evidence each test layer should produce and how PR-time validation should be treated.

## Decision

We will use layer-appropriate reporting rather than forcing all tests into a single reporting format.

Specifically:

1. Functional E2E tests will continue to prefer rich diagnostic reporting.
2. Performance tests will continue to prefer lightweight timestamped run artifacts.
3. PR-time validation checks will be treated as first-class quality signals and should be visible in the development workflow even when they do not produce the same style of artifact as test suites.

## Functional Test Reporting

Functional E2E tests should capture enough evidence to make failures easy to understand without rerunning immediately.

The current preferred pattern includes:

- request payloads
- response payloads
- curl equivalents for API calls
- DB query evidence
- assertion context

This is appropriate because functional failures often require detailed correctness debugging, not just pass or fail output.

## Performance Test Reporting

Performance tests should generate timestamped local artifacts under the configured report root.

The current preferred outputs are:

- HTML report
- CSV stats output
- JSON stats output

These are appropriate because performance runs are evaluated through trends, request distributions, throughput, and latency summaries rather than deep per-request debugging.

## PR Validation As A Reporting Signal

Every PR already benefits from in-depth repository checks beyond basic unit assertions.

The current validation path includes repository-level checks such as:

- formatting and file hygiene
- secret and env-file protection
- kustomize build validation
- Alembic single-head validation
- Docker build verification

These checks should be treated as part of the test evidence for a change, even when they do not emit Allure-style reports or Locust artifacts.

In practice, that means PRs should communicate:

- which functional tests were run
- which performance runs were executed, if relevant
- whether the repository-level validation path passed

This is the best place to record the deeper PR validation expectation because it governs how testing results are surfaced to reviewers.

## Separation By Purpose

We do not need one reporting format for every testing style.

Instead:

- functional reporting should optimize for diagnosis
- performance reporting should optimize for run-level metrics
- PR validation reporting should optimize for reviewer confidence and release safety

## Storage And Scope

Generated test artifacts should be treated as build or run outputs unless explicitly needed in version control.

That includes:

- Allure outputs
- generated HTML reports
- CSV and JSON run artifacts
- local temporary planning or scratch files

The repository should continue to prefer keeping these outputs out of normal commits.

## Consequences

### Positive

- Each test layer can report in the format that fits its purpose.
- Reviewers get stronger evidence than a bare test-pass summary.
- Existing Allure and Locust reporting work can evolve without being flattened into one toolchain.

### Tradeoffs

- Test evidence is distributed across more than one format.
- Some PR validation signals live in hook output rather than in a standalone artifact bundle.
- Reviewers need a small amount of context to interpret different reporting styles.

## Current Scope

At the time of this ADR:

- functional E2E reporting is already helper-driven and evidence-rich
- performance reporting is already timestamped and file-based
- commit and push hooks already enforce meaningful repo-level validation on every PR workflow

## Follow-Up

- Keep PR descriptions explicit about what testing and validation ran.
- Expand report publishing only when there is a concrete consumer for stored results.
- Avoid adding a second reporting pattern when an existing helper or artifact style already fits the need.
