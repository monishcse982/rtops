# ADR 0001: Functional Testing Approach

## Status

Accepted

## Context

This repository already contains functional test coverage under `tests/unit` and `tests/e2e`.

The current functional test structure establishes:

- unit and integration-style tests under `tests/unit`
- API-level end-to-end tests under `tests/e2e`
- shared E2E reporting helpers and assertions
- direct verification of persisted database state where it materially supports the API contract

We needed a testing approach that is:

- clear about the purpose of each test layer
- practical for evolving API workflows
- strong on contract and state validation
- separate from performance testing concerns

## Decision

We will use a layered functional testing approach with two main categories:

1. Unit and integration-style tests in `tests/unit`
2. End-to-end API and persistence validation in `tests/e2e`

We will prioritize functional tests that validate business behavior, state transitions, persistence, and event side effects over shallow endpoint-only checks.

## What We Are Optimizing For

The functional suite is intended to answer practical questions such as:

- Does the API behave correctly for expected and invalid inputs?
- Are business rules enforced correctly?
- Are persistence side effects written correctly?
- Are outbox and event-related side effects created when expected?
- Do order lifecycle transitions behave correctly across API and database layers?

The suite is not intended to be a load-testing framework or a replacement for production-like traffic simulation.

## Test Layers

### 1. Unit And Integration-Style Tests

Tests in `tests/unit` are used to validate focused behavior close to the application code.

These tests are prioritized for:

- pricing logic
- order creation and outbox behavior
- event handling
- seed-data assumptions
- request and response behavior that can be validated quickly in-process

They should remain fast, focused, and easy to diagnose.

### 2. End-To-End API Tests

Tests in `tests/e2e` validate complete user-visible workflows through the API, with database verification where it adds real confidence.

These tests are prioritized for:

- product API coverage
- order API workflows
- health and smoke behavior
- persistence correctness after API calls
- outbox event creation for relevant workflows

They should model realistic API usage and verify the most important externally observable behaviors.

## Priorities

### 1. Business-Critical Flows First

Functional coverage should prioritize the flows that matter most to the service:

- product retrieval and mutation behavior
- order creation
- order lifecycle transitions
- pricing and totals
- outbox event persistence and publication-related behavior

### 2. State Validation Matters

For this system, it is not enough to only assert HTTP status codes and response payloads.

Where appropriate, functional tests should also validate:

- persisted database records
- related child records such as line items
- outbox event rows
- state transitions across multiple requests

This is especially important because the application is event-driven and stateful.

### 3. Negative Cases Are First-Class Coverage

Functional tests should explicitly cover invalid requests and failure conditions, such as:

- nonexistent products
- invalid order states
- malformed or empty payloads
- invalid update or transition attempts

These cases are important because they often reveal contract drift or state-management bugs earlier than success-path tests.

### 4. Functional Tests May Be Deeper Than Perf Tests

Unlike Locust scenarios, functional tests are allowed and expected to perform stronger validation.

That includes:

- exact response semantics
- detailed field checks
- persisted state checks
- outbox payload verification
- header and request-ID behavior

## Separation From Performance Tests

Functional tests and performance tests serve different purposes and should stay intentionally distinct.

Functional tests should:

- validate correctness deeply
- inspect database and event side effects
- use richer assertions

Performance tests should:

- validate lightweight API sanity under load
- avoid deep persistence inspection
- keep scenarios stable and cheap to execute

This separation keeps each suite reliable and easier to maintain.

## Structural Conventions

We will keep the functional test layout organized by scope:

- `tests/unit`: focused logic and integration-style verification
- `tests/e2e`: API workflows and persistence validation
- shared helpers should be reused when they improve consistency and reduce repetition

Functional helpers should prefer:

- clear assertion wrappers
- reusable request builders when workflows repeat
- query helpers for common verification patterns

## Reporting

Functional E2E tests may produce richer reporting artifacts because correctness debugging often benefits from request, response, and persistence evidence.

Where reporting helpers already exist, extend them rather than introducing a second style.

## Consequences

### Positive

- The suite can validate both application logic and externally visible workflows.
- Database and outbox verification improve confidence in a stateful event-driven system.
- Unit and E2E layers remain easier to reason about when their roles are explicit.

### Tradeoffs

- End-to-end tests are heavier and slower than unit tests.
- Persistence verification requires more setup and maintenance.
- Richer assertions make functional tests more coupled to intended behavior, which is useful but can require careful updates when contracts evolve.

## Current Scope

At the time of this ADR:

- unit tests cover pricing, order integration behavior, event handlers, and seed-data-related behavior
- E2E tests cover product, order, and health workflows
- persistence and outbox verification are already important parts of the functional testing style

## Follow-Up

- Add more invalid-input and state-transition negative tests.
- Expand product API functional coverage where mutation paths are important.
- Continue improving reusable helpers for API requests and DB verification.
- Keep functional documentation separate from performance-testing guidance.
