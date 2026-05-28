# ADR 0002: Performance Testing Approach

## Status

Accepted

## Context

This repository now includes Locust-based performance testing under `tests/perf`.

The current implementation establishes:

- a central Locust entrypoint in `tests/perf/locustfile.py`
- shared helpers in `tests/perf/base_user.py` and `tests/perf/commons.py`
- a product-focused performance user in `tests/perf/users/product_browsing.py`
- order-focused performance users in `tests/perf/users/orders_actions.py` and `tests/perf/users/order_journeys.py`
- a custom load shape in `tests/perf/load_profiles/ramp_up_sustain_ramp_down.py`
- local report configuration through `tests/perf/locust.local.conf`
- GitHub Actions execution against the EC2 Kubernetes environment through `perf-k8s.yml`

We needed a performance testing approach that is:

- simple to run locally and in headless automation
- realistic enough to model actual API usage
- maintainable as coverage grows beyond product reads
- explicit about the kinds of performance tests that matter most for this service

## Decision

We will use Locust as the primary performance testing framework for this repository.

We will prioritize the following kinds of performance tests:

1. Read-heavy API traffic for product browsing workflows.
2. End-to-end user journeys that chain multiple API calls together.
3. Order creation and lifecycle workflows that reflect meaningful business traffic.
4. A small smoke-level performance suite that can be used during deployment validation.

We will prefer custom Locust `LoadTestShape` classes over relying only on ad hoc CLI user and spawn-rate inputs when modeling sustained load patterns.

## What We Are Optimizing For

The performance suite is intended to answer practical questions such as:

- Can the API handle realistic browsing traffic?
- Can key user journeys complete successfully under concurrent load?
- Do order-related write paths remain healthy when mixed with read traffic?
- Can we run a repeatable smoke or baseline load after deployment?

The suite is not intended to become a second functional test suite with deep business-rule validation.

## Priorities

### 1. Product Read Traffic First

Product listing and product detail traffic are expected to be the most frequent and the safest starting point for load testing.

These scenarios are prioritized because they:

- represent common user behavior
- are easier to scale safely
- create fast feedback while the Locust harness is still evolving
- help validate pagination, sorting, filtering, and search behavior under load

### 2. End-To-End Journeys Over Isolated Endpoints Alone

Single-endpoint tests are useful, but they do not fully represent real usage. We therefore prefer journey-style scenarios that chain calls together, such as:

- list products, choose a product, fetch product details
- list products, create an order, fetch the created order
- create an order, progress through supported lifecycle states, verify state changes

This gives better signal about:

- cache and database behavior across related calls
- API consistency across state transitions
- realistic request mixes rather than isolated hot loops

### 3. Order Flows As The Main Write Path

When write traffic is added, order APIs take priority over general product mutation.

Order flows better reflect the business value of the system and are more useful than synthetic high-volume writes to administrative product endpoints.

Product create, update, and delete performance tests are considered lower priority and should only be run where test data mutation is safe.

### 4. Lightweight Assertions

Assertions in Locust scenarios should remain intentionally light:

- expected HTTP status codes
- response body parses as JSON
- required fields exist
- IDs and immediate state transitions are consistent

We avoid deep assertions that make load tests brittle or turn them into functional regression suites.

## Why Custom Load Shapes Are Preferred

We prefer custom `LoadTestShape` classes, especially for steady load modeling, because they provide:

- repeatable test behavior in both UI and headless runs
- version-controlled load definitions
- clearer intent than manually entering values in the UI every time
- easier reuse for smoke, baseline, and stress runs

The initial preferred pattern is a ramp-up, sustain, ramp-down profile because it reflects a realistic progression:

- gradually introduce traffic
- hold a stable concurrency level long enough to observe system behavior
- reduce load in a controlled way

This is a better default for this project than one-off constant or manually tuned runs.

## Structural Conventions

We will keep the performance test layout organized by responsibility:

- `tests/perf/locustfile.py`: central Locust entrypoint
- `tests/perf/base_user.py`: shared base user and request helpers
- `tests/perf/commons.py`: common utilities and wait strategies
- `tests/perf/load_profiles/`: custom load shapes
- `tests/perf/users/`: user behavior modules grouped by scenario type

As coverage grows, we prefer splitting user behavior into focused files such as:

- product browsing
- order checkout
- order fulfillment
- smoke traffic

## Reporting

Performance runs should generate timestamped local reports so results can be inspected immediately and later published if needed.

For normal local usage, we prefer routing runs through the central Locust config and entrypoint rather than running individual user files directly.

Automated EC2 Kubernetes performance runs publish Locust HTML artifacts to GitHub Pages. The latest report pointer and run-specific report links are treated as portfolio-facing evidence for baseline behavior.

For the current baseline workflow, Locust request failures do not fail the GitHub Actions job if the report is generated. This is intentional for now: the report should preserve visible evidence about system limits, bottlenecks, and failure rates instead of hiding them behind a green-only threshold.

## Consequences

### Positive

- Performance scenarios stay close to real API usage.
- Load profiles become explicit and reproducible.
- The suite remains maintainable as more workflows are added.
- Local and automated runs can share the same testing model.

### Tradeoffs

- Writing custom shapes and reusable helpers requires more upfront structure than quick one-off Locust scripts.
- Journey-style tests require more care around test data, chaining, and environment safety.
- Some assertions must stay intentionally shallow to keep the suite stable under load.

## Current Scope

At the time of this ADR:

- product browsing coverage exists
- order action and order journey coverage exists
- one custom ramp-up, sustain, ramp-down shape exists
- EC2 Kubernetes performance workflow publishes Locust reports to GitHub Pages

## Follow-Up

- Add a mixed traffic run combining browsing and order behavior.
- Document standard smoke, baseline, and stretch runs.
- Define future pass/fail thresholds after enough baseline data exists.
