# ADR 0003: Test Data And Environment Strategy

## Status

Accepted

## Context

The current test suites depend on a mix of seeded application data, locally configured service endpoints, and environment-specific runtime dependencies.

The repository already establishes:

- functional test configuration through `tests/e2e/TestConfig.py`
- environment-driven settings such as `database_url`, `api_url`, and `redis_url`
- a local test env file at `tests/.test.env`
- E2E tests that verify persisted database state
- performance tests that depend on realistic product data already being present

As testing expands across functional and performance layers, we need a clear strategy for test data and environment assumptions.

## Decision

We will use environment-driven configuration and stable seeded baseline data as the default testing strategy for this repository.

We will distinguish between:

1. Read-oriented tests that rely on existing seeded data.
2. Write-oriented tests that create their own disposable data when needed.
3. Environment-specific dependencies that must be explicit rather than inferred.

## Data Strategy

### Seeded Baseline Data

Seeded baseline data is the preferred default for:

- product browsing tests
- search and filter coverage
- pagination and sorting checks
- any flow that benefits from a predictable catalog already existing

This is especially important for performance tests, where repeated setup inside each task adds noise and instability.

### Disposable Generated Data

Generated data is preferred for flows that mutate state, such as:

- product creation
- product updates
- order creation used for lifecycle transitions

These tests should create only the data they need and should not assume exclusive ownership of long-lived shared records unless that is guaranteed by the environment.

### Safety Boundary

Read-heavy performance scenarios are safe to run broadly because they mostly depend on seeded state.

Write-heavy or lifecycle-mutating scenarios require more care and should only be used in environments where repeated state mutation is acceptable.

## Environment Strategy

Tests should obtain configuration from explicit environment variables or the existing settings loader rather than from hardcoded URLs or implicit local assumptions.

The current baseline contract includes:

- API URL
- database URL
- Redis URL

This keeps local, PR, and later deployed-environment execution aligned around the same configuration model.

## By Test Type

### Unit Tests

Unit and integration-style tests may create and control their own local data because they run in a tighter in-process environment and validate focused behaviors.

### End-To-End Functional Tests

E2E tests may rely on seeded data for lookup flows, but should create their own records when validating write paths or lifecycle state transitions.

Where they verify persistence, they should treat the database as part of the test contract, not as a hidden implementation detail.

### Performance Tests

Performance tests should prefer seeded data for repeated read scenarios.

When performance tests need write behavior, they should:

- keep write traffic limited
- create only the minimum necessary test data
- avoid assumptions that make repeated runs collide or degrade the environment

## What We Are Avoiding

We are intentionally avoiding:

- hardcoded local-only endpoints in test code
- performance tests that require expensive per-task setup
- fragile assumptions that search and filter queries always return data unless the seed set guarantees it
- broad mutation of shared records without explicit environmental safety

## Consequences

### Positive

- Product read tests stay stable and easy to run repeatedly.
- Environment setup remains explicit and portable.
- Functional and performance tests can share the same baseline data model without becoming tightly coupled.

### Tradeoffs

- Seeded data creates some dependency on fixture quality and freshness.
- Write-heavy tests require more care to avoid collisions and state pollution.
- Different environments may still need different levels of data preparation, even with the same configuration pattern.

## Current Scope

At the time of this ADR:

- functional tests already use environment-driven configuration
- product-focused performance tests already assume baseline product data exists
- order and mutation-heavy performance flows are still being added and should follow this strategy

## Follow-Up

- Document the expected local test environment more explicitly if the current setup becomes harder to bootstrap.
- Keep seed data sufficient for browse, search, sort, and filter scenarios.
- Add helper utilities for generated test data where write-path tests start repeating setup logic.
