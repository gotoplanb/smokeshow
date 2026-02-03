"""TestCase async context manager — wraps a single test case with OTEL spans."""

import logging

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from smokeshow.actions import ActionInstrumentor
from smokeshow.spans import action_span


class TestCase:
    """Async context manager for a single test case.

    Creates a test-case span as a child of the suite span. Delegates
    instrumented actions to ActionInstrumentor.
    """

    def __init__(self, tracer, suite_ctx, page, record_result_fn, *, logger=None, suite_name="", name, case_id="", tags="", description=""):
        self._tracer = tracer
        self._suite_ctx = suite_ctx
        self._page = page
        self._record_result = record_result_fn
        self._logger = logger
        self._suite_name = suite_name
        self._name = name
        self._case_id = case_id
        self._tags = tags
        self._description = description
        self._case_span = None
        self._case_ctx = None
        self._actions = None

    async def __aenter__(self):
        attrs = {
            "test.case.name": self._name,
        }
        if self._case_id:
            attrs["test.case.id"] = self._case_id
        if self._tags:
            attrs["test.case.tags"] = self._tags
        if self._description:
            attrs["test.case.description"] = self._description

        self._case_span = self._tracer.start_span(
            f'test("{self._name}")',
            context=self._suite_ctx,
            attributes=attrs,
        )
        self._case_ctx = trace.set_span_in_context(self._case_span)
        self._actions = ActionInstrumentor(self._page, self._tracer, self._case_ctx)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self._case_span.set_attribute("test.case.result", "failed")
            self._case_span.set_attribute("test.case.failure_reason", str(exc_val))
            self._case_span.set_attribute("test.case.failure_url", self._page.url)
            self._case_span.set_status(StatusCode.ERROR, str(exc_val))
            self._case_span.record_exception(exc_val)
            self._record_result(False)

            # Emit error log correlated with the trace via active span context
            if self._logger:
                trace_id = format(self._case_span.get_span_context().trace_id, "032x")
                span_id = format(self._case_span.get_span_context().span_id, "016x")
                case_label = self._case_id or self._name
                self._logger.error(
                    "Test case FAILED: %s [%s] — %s (url=%s, trace_id=%s, span_id=%s)",
                    case_label, self._suite_name, exc_val, self._page.url, trace_id, span_id,
                )
        else:
            self._case_span.set_attribute("test.case.result", "passed")
            self._case_span.set_status(StatusCode.OK)
            self._record_result(True)
        self._case_span.end()
        return False  # Do NOT suppress exceptions

    # --- Delegate instrumented actions ---

    async def navigate(self, url):
        await self._actions.navigate(url)

    async def click(self, selector):
        await self._actions.click(selector)

    async def fill(self, selector, value, sensitive=False):
        await self._actions.fill(selector, value, sensitive)

    async def assert_visible(self, selector):
        await self._actions.assert_visible(selector)

    async def assert_text(self, selector, expected):
        await self._actions.assert_text(selector, expected)

    async def assert_count(self, selector, expected_count):
        await self._actions.assert_count(selector, expected_count)

    async def assert_url(self, pattern):
        await self._actions.assert_url(pattern)

    # --- Escape hatches ---

    @property
    def page(self):
        """Raw Playwright Page for actions not covered by the instrumented API."""
        return self._page

    def set_attribute(self, key, value):
        """Set a custom attribute on the test case span (e.g. arc.* domain attrs)."""
        self._case_span.set_attribute(key, value)

    def action_span(self, action_type, selector=None, **extra_attrs):
        """Create a raw action span for custom instrumented blocks."""
        return action_span(self._tracer, self._case_ctx, action_type, selector, **extra_attrs)
