# Playwright OpenTelemetry Instrumentation Framework — Spec

## Project Name

`smokeshow`

## Overview

A Python library that wraps Playwright test execution with OpenTelemetry instrumentation, producing traces, metrics, and logs that describe the end-to-end test run itself — not the service under test. The telemetry models the **test session as a trace**, with individual user actions as spans. This gives us observability into E2E test behavior, timing, and reliability using the same Grafana stack we'd use for production services.

The local telemetry pipeline uses **Grafana Alloy** as the OTEL collector, running in Docker Desktop alongside the test runner on the developer's local machine. The developer will handle all Grafana/Tempo/Loki/Prometheus/Mimir configuration — this spec covers everything up to and including OTLP export to Alloy.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Developer's Local Machine                          │
│                                                     │
│  ┌───────────────┐       OTLP (gRPC :4317)         │
│  │  pytest +      │  ──────────────────────────►    │
│  │  playwright +  │                                 │
│  │  playwright-   │       ┌──────────────────┐      │
│  │  otel          │       │  Grafana Alloy   │      │
│  └───────────────┘       │  (Docker Desktop) │      │
│                           │                  │      │
│                           │  → Tempo (traces)│      │
│                           │  → Loki (logs)   │      │
│                           │  → Prometheus/   │      │
│                           │    Mimir(metrics)│      │
│                           └──────────────────┘      │
└─────────────────────────────────────────────────────┘
```

## Trace Structure / Span Hierarchy

The key design decision: **one trace = one test session or one test suite run**. This is NOT the typical "one trace per HTTP request" model. A trace represents a complete user journey through the application under test.

### Three-level hierarchy

```
trace: "regression-run-<uuid>"                          ← root span (suite level)
  └─ span: test("checkout-flow")                        ← test-case span
  │    └─ span: navigate("https://example.com/shop")    ← action span
  │    └─ span: click("button#add-to-cart")             ← action span
  │    └─ span: fill("input#email", "test@test.com")    ← action span
  │    └─ span: click("button#submit")                  ← action span
  │    └─ span: assert(visible, "div.confirmation")     ← action span
  └─ span: test("user-registration")                    ← test-case span
  │    └─ span: navigate("https://example.com/signup")
  │    └─ span: fill("input#username", "newuser")
  │    └─ ...
```

If only a single test is being run (not a suite), collapse to two levels: the test-case span becomes the root.

### Span Attributes

#### Root span (suite level)

| Attribute | Type | Description |
|-----------|------|-------------|
| `test.suite.name` | string | Name of the test suite |
| `test.suite.id` | string | UUID for this specific run |
| `test.run.trigger` | string | What initiated this run: `manual`, `ci`, `scheduled`, `smokeharvest` |
| `test.run.timestamp` | string | ISO 8601 start time |
| `test.target.base_url` | string | Base URL of the application under test |
| `test.target.environment` | string | `local`, `staging`, `production`, etc. |
| `test.browser.name` | string | `chromium`, `firefox`, `webkit` |
| `test.browser.headless` | bool | Whether browser ran headless |
| `test.viewport.width` | int | Viewport width in pixels |
| `test.viewport.height` | int | Viewport height in pixels |
| `test.suite.total_tests` | int | Total number of tests in the suite (set at end) |
| `test.suite.passed` | int | Count of passed tests (set at end) |
| `test.suite.failed` | int | Count of failed tests (set at end) |
| `test.suite.result` | string | `passed`, `failed`, `partial` |
| `vcs.commit.sha` | string | Git commit SHA if available (optional) |
| `vcs.branch` | string | Git branch name if available (optional) |

#### Test-case span

| Attribute | Type | Description |
|-----------|------|-------------|
| `test.case.name` | string | Human-readable test name |
| `test.case.id` | string | Stable identifier for this test case (for tracking across runs) |
| `test.case.description` | string | Optional longer description |
| `test.case.tags` | string[] | Tags/categories: `smoke`, `regression`, `checkout`, etc. |
| `test.case.result` | string | `passed`, `failed`, `skipped`, `error` |
| `test.case.failure_reason` | string | Error message if failed |
| `test.case.retry_count` | int | Number of retries attempted |
| `test.case.priority` | string | `critical`, `high`, `medium`, `low` (optional) |

#### Action span

| Attribute | Type | Description |
|-----------|------|-------------|
| `test.action.type` | string | `navigate`, `click`, `fill`, `select`, `hover`, `wait`, `assert`, `screenshot`, `keyboard`, `scroll` |
| `test.action.selector` | string | CSS selector or Playwright locator used |
| `test.action.target_url` | string | URL for navigate actions |
| `test.action.input_value` | string | Value for fill/select actions (REDACT sensitive fields — see below) |
| `test.action.page_url` | string | Current page URL when action was performed |
| `test.action.result` | string | `success`, `failed`, `timeout` |
| `test.action.error` | string | Error message if action failed |
| `test.action.screenshot_path` | string | Local path to screenshot if one was taken (especially on failure) |
| `test.action.wait_ms` | float | Time spent waiting for element/condition before acting |
| `test.action.duration_ms` | float | Total duration of the action |

#### Navigation-specific attributes (on `navigate` action spans)

| Attribute | Type | Description |
|-----------|------|-------------|
| `test.navigation.dom_content_loaded_ms` | float | DOMContentLoaded timing |
| `test.navigation.load_event_ms` | float | Load event timing |
| `test.navigation.response_status` | int | HTTP status code of the page |
| `test.navigation.transfer_size_bytes` | int | Total transfer size if available |

## Metrics

Export via OTEL Metrics SDK using OTLP exporter to Alloy.

| Metric Name | Type | Description |
|-------------|------|-------------|
| `test.run.duration_seconds` | Histogram | Duration of complete test suite runs |
| `test.case.duration_seconds` | Histogram | Duration per test case, with labels: `test_name`, `result`, `environment` |
| `test.action.duration_seconds` | Histogram | Duration per action, with labels: `action_type`, `result` |
| `test.case.result_total` | Counter | Count of test results, with labels: `test_name`, `result` (`passed`/`failed`/`skipped`) |
| `test.navigation.load_time_seconds` | Histogram | Page load times, with label: `url_path` (strip query params) |
| `test.assertion.result_total` | Counter | Assertion pass/fail counts, with labels: `test_name`, `assertion_type` |
| `test.flaky.retry_total` | Counter | Retry attempts, with label: `test_name` |

## Logs

Structured logs via Python `logging` module bridged to OTEL using `opentelemetry-sdk` log bridge. Logs are correlated to the active trace/span context automatically.

### Log events to emit

- **Test suite start/end**: INFO level, includes suite name, environment, total results
- **Test case start/end**: INFO level, includes test name, result, duration
- **Action performed**: DEBUG level, includes action type, selector, result, duration
- **Action failure**: WARNING level, includes error details, screenshot path if captured
- **Test case failure**: ERROR level, includes full error/exception, stack trace, screenshot path
- **Navigation timing**: DEBUG level, includes page load metrics
- **Assertion details**: DEBUG level for passes, WARNING for failures

### Log format

All log records should include these fields as structured attributes (not baked into the message string):

- `test.suite.name`
- `test.case.name` (when in test context)
- `test.action.type` (when in action context)
- `trace_id` and `span_id` (automatic via OTEL context)

## Python API Design

### Core wrapper class

```python
from playwright_otel import InstrumentedBrowser

# Context manager handles trace lifecycle
async with InstrumentedBrowser(
    # OTEL configuration
    service_name="my-e2e-tests",
    otlp_endpoint="http://localhost:4317",  # Alloy gRPC endpoint

    # Test metadata
    suite_name="checkout-regression",
    environment="staging",
    trigger="manual",
    base_url="https://staging.example.com",

    # Playwright options
    browser_type="chromium",  # chromium | firefox | webkit
    headless=True,
    viewport={"width": 1280, "height": 720},
) as browser:

    # Each test case is a context manager that creates a child span
    async with browser.test_case(
        name="checkout-flow",
        case_id="TC-CHECKOUT-001",
        tags=["smoke", "checkout", "critical"],
        description="Verify user can complete checkout with credit card",
    ) as test:
        # Instrumented actions — each creates a grandchild span
        await test.navigate("https://staging.example.com/products")
        await test.click("button.add-to-cart")
        await test.click("a.checkout")
        await test.fill("input#email", "test@example.com")
        await test.fill("input#card-number", "4111111111111111", sensitive=True)
        await test.click("button#submit-order")
        await test.assert_visible("div.order-confirmation")

    async with browser.test_case(name="user-registration", case_id="TC-REG-001") as test:
        await test.navigate("https://staging.example.com/signup")
        # ... more actions
```

### Key API methods on `test` (the test case context)

These wrap Playwright's Page methods and add span instrumentation:

- `navigate(url)` — wraps `page.goto()`, captures navigation timing
- `click(selector)` — wraps `page.click()` or `locator.click()`
- `fill(selector, value, sensitive=False)` — wraps `page.fill()`, redacts value if `sensitive=True`
- `select(selector, value)` — wraps `page.select_option()`
- `hover(selector)` — wraps `page.hover()`
- `press(selector, key)` — wraps keyboard actions
- `scroll(selector_or_direction)` — wraps scroll actions
- `wait_for(selector, state="visible", timeout=30000)` — wraps `page.wait_for_selector()`
- `assert_visible(selector)` — asserts element is visible
- `assert_text(selector, expected_text)` — asserts element contains text
- `assert_url(expected_url_pattern)` — asserts current URL matches
- `assert_count(selector, expected_count)` — asserts number of matching elements
- `screenshot(name=None)` — takes screenshot, stores path in span attribute
- `page` — property that exposes the raw Playwright Page for escape-hatch scenarios (actions on raw page are NOT instrumented)

### Configuration via environment variables

Support configuration through env vars for CI/Docker use:

| Env Var | Default | Description |
|---------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Alloy gRPC endpoint |
| `OTEL_SERVICE_NAME` | `playwright-otel` | Service name in telemetry |
| `PLAYWRIGHT_OTEL_ENVIRONMENT` | `local` | Target environment tag |
| `PLAYWRIGHT_OTEL_HEADLESS` | `true` | Run headless |
| `PLAYWRIGHT_OTEL_BROWSER` | `chromium` | Browser type |
| `PLAYWRIGHT_OTEL_SCREENSHOT_DIR` | `./screenshots` | Where to store failure screenshots |
| `PLAYWRIGHT_OTEL_SCREENSHOT_ON_FAILURE` | `true` | Auto-screenshot on action/assertion failure |

### pytest integration (optional but recommended)

Provide a pytest plugin so existing Playwright tests can be instrumented with minimal changes:

```python
# conftest.py
import pytest
from playwright_otel.pytest_plugin import otel_browser

@pytest.fixture
async def instrumented_page(otel_browser):
    """Provides an instrumented test case context."""
    async with otel_browser.test_case(
        name=request.node.name,
        case_id=request.node.nodeid,
    ) as test:
        yield test
```

```python
# test_checkout.py
async def test_checkout_flow(instrumented_page):
    test = instrumented_page
    await test.navigate("/products")
    await test.click("button.add-to-cart")
    await test.assert_visible("div.cart-summary")
```

The plugin should:
- Auto-create a root suite span for the entire pytest session
- Auto-populate `test.case.name` from the pytest test function name
- Auto-populate `test.case.id` from `request.node.nodeid`
- Auto-set `test.case.result` based on test outcome
- Auto-capture screenshots on failure if configured
- Respect all env var configuration

## Sensitive Data Handling

- When `sensitive=True` is passed to `fill()`, the `test.action.input_value` attribute must be set to `[REDACTED]`
- Auto-detect and redact common sensitive field selectors: anything matching `password`, `card`, `cvv`, `ssn`, `credit`, `secret`, `token` in the selector string
- Never log raw sensitive values at any log level

## Error Handling

- Action failures should NOT crash the test runner by default. Catch exceptions, record them on the span (`span.set_status(ERROR)`, `span.record_exception(e)`), and re-raise so the test framework can handle pass/fail
- Timeout failures should record the configured timeout in the span attributes
- If OTEL export fails (Alloy is down), log a warning locally but do NOT fail the tests — telemetry is observability, not correctness
- Use `span.set_status(StatusCode.ERROR, "description")` on failure, `StatusCode.OK` on success

## Dependencies

### Python packages

```
playwright
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp-proto-grpc
opentelemetry-instrumentation  # base instrumentation utilities
pytest                          # for the plugin
pytest-playwright               # for Playwright pytest integration
pytest-asyncio                  # async test support
```

### Infrastructure (developer handles setup, but document expectations)

- **Grafana Alloy** running in Docker Desktop, accepting OTLP gRPC on port `4317`
- Developer configures Alloy to forward traces → Tempo, metrics → Prometheus/Mimir, logs → Loki
- This project does NOT include Alloy/Grafana configuration — that's the developer's domain

## Project Structure

```
playwright-otel/
├── pyproject.toml
├── README.md
├── src/
│   └── playwright_otel/
│       ├── __init__.py              # Public API exports
│       ├── browser.py               # InstrumentedBrowser class
│       ├── test_case.py             # TestCase context manager
│       ├── actions.py               # Instrumented action wrappers
│       ├── spans.py                 # Span creation, attribute helpers
│       ├── metrics.py               # Metric instrument definitions
│       ├── logging_bridge.py        # OTEL log bridge setup
│       ├── config.py                # Env var and constructor config
│       ├── sensitive.py             # Redaction logic
│       └── pytest_plugin.py         # pytest plugin (entry point registered in pyproject.toml)
├── tests/
│   ├── conftest.py
│   ├── test_browser.py              # Unit tests for InstrumentedBrowser
│   ├── test_actions.py              # Unit tests for action wrappers
│   ├── test_spans.py                # Unit tests for span attributes
│   ├── test_sensitive.py            # Unit tests for redaction
│   ├── test_metrics.py              # Unit tests for metric recording
│   ├── test_config.py               # Unit tests for config/env parsing
│   └── test_pytest_plugin.py        # Tests for pytest integration
└── examples/
    ├── basic_usage.py               # Minimal example
    ├── full_suite.py                 # Multi-test suite example
    └── pytest_example/
        ├── conftest.py
        └── test_example.py
```

## Testing Strategy

- **Unit tests** for all modules. Mock Playwright and OTEL SDK internals — we're testing that the right spans/attributes/metrics are created, not that Playwright clicks buttons.
- Use `opentelemetry-sdk`'s `InMemorySpanExporter` and `InMemoryMetricReader` for assertions in tests.
- Test that sensitive data redaction works correctly.
- Test that OTEL export failure doesn't crash the test runner.
- Test span hierarchy (suite → case → action) is correct.
- Test that all attributes from the tables above are set correctly.
- **Integration test** (in `examples/`): one runnable example that hits `https://example.com` and produces real telemetry to a local Alloy instance. This is manual/smoke-test level, not automated CI.

## Out of Scope (for now)

- Alloy / Grafana / Tempo / Loki / Prometheus configuration and docker-compose
- Video recording of test runs
- Distributed tracing across the browser → backend (that's a different problem — we're tracing the test runner, not the service)
- Parallel test execution (start with sequential; parallel can be added later with per-worker trace context)
- Visual regression / screenshot diffing
- Test case management UI (the whole point is that trace backends replace this)

## Implementation Notes

- Use `async/await` throughout — Playwright's async API is preferred
- The library should work with Playwright's sync API too, but async is the primary target. If supporting both adds significant complexity, go async-only.
- Use `opentelemetry.context` to propagate trace context through the test hierarchy
- Use `opentelemetry.trace.get_tracer(__name__)` for tracer acquisition
- Set `service.name` resource attribute from config
- Add `telemetry.sdk.name: playwright-otel` as a resource attribute for easy filtering in Grafana
