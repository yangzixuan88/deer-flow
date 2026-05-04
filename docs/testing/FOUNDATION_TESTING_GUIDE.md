# Foundation Testing Guide

This guide freezes the R241-15F test organization policy. It is a testing
contract only: it does not change production runtime logic, Gateway routing,
audit JSONL behavior, action queues, or safety boundaries.

## CI Stage Matrix

### Stage 1: Smoke

Goal: minimal health checks for imports, registries, markers, and RootGuard style
wrappers.

Command:

```powershell
python -m pytest -m smoke -v
```

Target: less than 60 seconds.

### Stage 2: Fast Unit + Fast Integration

Goal: default local developer regression. This stage excludes slow tests and
includes pure units, formatters, validators, projection helpers, and fast CLI
helpers.

Command:

```powershell
python -m pytest backend/app/foundation backend/app/audit -m "not slow" -v
```

### Stage 3: Safety

Goal: run safety boundaries independently. The safety lane must remain available
even when tests are also slow or integration tests.

Command:

```powershell
python -m pytest backend/app/foundation backend/app/audit -m "no_network or no_runtime_write or no_secret" -v
```

### Stage 4: Slow Integration

Goal: real boundary tests, real repository scans, real aggregate diagnostics,
append/query/trend smoke tests, and Feishu preview smoke tests. These must not
pollute the fast lane.

Command:

```powershell
python -m pytest backend/app/foundation backend/app/audit -m slow -v
```

### Stage 5: Full Regression

Goal: pre-release or large-change regression across foundation surfaces.

Command:

```powershell
python -m pytest backend/app/foundation backend/app/audit backend/app/nightly backend/app/rtcm backend/app/prompt backend/app/tool_runtime backend/app/mode backend/app/gateway backend/app/asset backend/app/memory backend/app/m11 -v
```

## Marker Usage Policy

### `smoke`

Use for minimal import, registry, root health, and command-shape checks. Do not
use for deep scans, real aggregate diagnostics, or report generation. It may be
combined with `unit`, `integration`, and safety markers. It may run in fast lane.

### `unit`

Use for pure validators, formatters, classifiers, and schema builders. Do not
use for real repository scans, CLI aggregate calls, or report writes. It may be
combined with safety markers. It should run in fast lane.

### `integration`

Use for cross-module helpers, CLI wrappers, projections, and query helpers. Do
not use it as a replacement for simple unit tests. It may combine with `slow`
when the integration path is expensive.

### `slow`

Use for real repository scans, real aggregate diagnostics, real CLI smoke tests,
and sample/report artifact generation. Do not use for pure validators, small
formatters, or schema-only tests. It is excluded from the fast lane.

### `full`

Use for full regression-only coverage groups. Do not use it to hide missing
`slow` or safety markers. It is not part of the default fast lane.

### `no_network`

Use for tests proving no webhook or network calls happen. Do not use for tests
that require real network access; real network access is forbidden in this
foundation safety suite. This marker must not be deleted.

### `no_runtime_write`

Use for tests proving no runtime, governance, action queue, memory, asset,
prompt, RTCM, or trend state writes happen. Append-only writer tests must use
tmp_path or explicit dry-run boundaries. This marker must not be deleted.

### `no_secret`

Use for tests proving no token, secret, webhook URL, full prompt, full memory, or
full RTCM body is output. Tests must never read real secrets. This marker must
not be deleted.

## Synthetic Fixture Policy

Use synthetic fixtures when the test only validates:

- formatter structure
- payload schema
- projection aggregation shape
- report or sample JSON shape
- path validation
- audit_record field existence
- repeated aggregate diagnostics that do not validate real repository state

Synthetic fixtures must preserve asserted schema, safety flags, and tmp_path
write boundaries.

## Real Boundary Keep Rules

Keep real boundary tests for:

- RootGuard
- append-only audit JSONL invariant
- audit query real JSONL read smoke
- trend CLI guard line count
- no network / no webhook / no secret / no runtime write safety checks
- Feishu preview and pre-send validator real CLI smoke
- at least one real repository scan slow smoke
- Gateway smoke

## Forbidden Synthetic Replacement

Do not syntheticize:

- safety redline tests
- real boundary invariants
- user confirmation, webhook policy, and secret redaction critical paths
- audit JSONL append-only line count verification
- runtime write detection

## New Test Contribution Checklist

Every new test must answer:

1. Is this unit / integration / slow / safety / full?
2. Does it read the real repository?
3. Does it scan many files?
4. Does it generate sample/report artifacts?
5. Does it call CLI aggregate diagnostics?
6. Does it involve network/webhook/secret/runtime write boundaries?
7. Can it use a synthetic fixture?
8. Must it keep a real boundary?
9. Does it need `no_network`, `no_runtime_write`, or `no_secret`?
10. Will it pollute the fast lane?

## Report Path Policy

The primary report path is:

```text
migration_reports/foundation_audit/
```

If `backend/migration_reports/foundation_audit/` exists, report it as a path
inconsistency. Do not migrate, delete, or rewrite it in test policy work.

## Runtime Baselines And Thresholds

R241-15E baseline:

- foundation fast: 11.33s
- audit fast: 2.37s
- slow suite: 6.84s
- safety suite: 1.07s
- collect-only: 2.86s

Future regression thresholds:

- foundation fast greater than 30s: warning
- foundation fast greater than 60s: blocker
- audit fast greater than 15s: warning
- slow suite greater than 60s: warning
- safety suite greater than 10s: warning
- collect-only greater than 10s: warning

## Prohibited Changes

Do not delete tests, skip safety tests, xfail safety tests, lower safety
coverage, call network/webhooks, write runtime state, overwrite audit JSONL,
write action queues, or execute auto-fix as part of test organization work.
