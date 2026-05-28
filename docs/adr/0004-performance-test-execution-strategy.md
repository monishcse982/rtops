# ADR 0004: Performance Test Execution Strategy

## Status

Accepted

## Context

The repository now includes a Locust-based performance test harness with:

- a central entrypoint in `tests/perf/locustfile.py`
- a local config file in `tests/perf/locust.local.conf`
- shared helpers and base user abstractions under `tests/perf`
- a custom load shape under `tests/perf/load_profiles`
- timestamped local report output configured from `tests/perf/config.py`

We also discussed two intended usage modes:

- headless runs for repeatable automated validation
- UI-driven runs for on-demand exploratory load testing
- GitHub Actions runs against the EC2 Kubernetes environment for reportable baselines

We need a consistent execution strategy so local use, future automation, and shape-based load modeling all stay aligned.

## Decision

We will treat the central Locust entrypoint and config as the standard way to run performance tests.

We will support two primary execution modes:

1. Local interactive runs through the Locust UI
2. Headless scripted runs for repeatable validation
3. GitHub Actions runs against the deployed EC2 Kubernetes environment

We will prefer custom `LoadTestShape` classes for meaningful load patterns and use direct `-u`, `-r`, and `-t` CLI inputs mainly for smoke runs and debugging.

## Standard Entry Point

Normal performance execution should route through:

- `tests/perf/locustfile.py`
- `tests/perf/locust.local.conf`

Running an individual user module directly is acceptable for quick debugging, but it is not the preferred long-term execution path because it can bypass shared config, reporting defaults, and shape registration.

## Execution Modes

### UI Mode

UI mode is preferred when:

- developing or debugging Locust users
- inspecting user classes and custom shapes interactively
- running exploratory or manual on-demand tests

### Headless Mode

Headless mode is preferred when:

- running a repeatable smoke or baseline test
- validating a deployed environment
- capturing report artifacts for later review

### GitHub Actions Mode

GitHub Actions mode is preferred when:

- running a visible portfolio/demo baseline
- publishing Locust reports to GitHub Pages
- validating the deployed EC2 Kubernetes environment from outside the cluster
- preserving run-specific links in the workflow summary

## Load Profile Strategy

The default preferred profile is a custom ramp-up, sustain, ramp-down shape.

This is preferred because it:

- reflects a more realistic load pattern than a flat one-off run
- is version-controlled in code
- makes UI and headless execution behave consistently

Simple CLI concurrency settings are still useful for:

- one-user smoke validation
- debugging a newly added user
- quickly checking whether a scenario runs at all

## Execution Order

When adding or debugging performance scenarios, the preferred sequence is:

1. Run the scenario in a very small local smoke configuration.
2. Run the scenario in UI mode for quick inspection and shape selection.
3. Run a headless baseline test with the shared config.
4. Run a mixed-traffic test after individual user types are stable.

This keeps debugging cheap before higher-concurrency runs.

## Scope Boundary

Performance execution should prioritize:

- read-heavy product browsing traffic
- meaningful journey-style flows
- limited, deliberate write-path coverage

It should avoid:

- turning every endpoint into a heavy load target by default
- mutating shared state aggressively without environmental safety
- deep functional verification during load

## Post-Deploy Use

The intended operational direction already discussed is:

- headless performance checks after the environment is already deployed
- UI-driven Locust runs available for on-demand manual testing

The deployed cluster remains the system under test. The performance suite is run from GitHub Actions through a tunnel to the EC2-hosted Kubernetes API service rather than as an in-cluster Kubernetes Job.

The current EC2 Kubernetes workflow uses a small explicit smoke/baseline shape. It sets the Locust error exit code to zero so the workflow can publish the report even when the baseline exposes service failures. Threshold-based failure gates should be added only after baseline behavior is understood.

## Consequences

### Positive

- Local and automated execution share the same core path.
- Load shapes remain explicit and reproducible.
- Debugging and operational usage can coexist without separate test harnesses.

### Tradeoffs

- The standard path is slightly more structured than running ad hoc user files.
- Custom shapes require some extra code and documentation.
- Write-path performance scenarios still need careful environmental judgment.

## Current Scope

At the time of this ADR:

- performance users exist for product browsing, order actions, and order journeys
- one custom load shape exists
- timestamped local report output is already configured
- UI and headless usage are both supported locally
- EC2 Kubernetes performance workflow publishes Locust reports to GitHub Pages

## Follow-Up

- Add mixed-traffic execution that combines browsing and order flows.
- Document standard smoke, baseline, and stretch runs more explicitly if the suite grows.
- Add explicit quality gates for performance only after enough baseline data is available.
