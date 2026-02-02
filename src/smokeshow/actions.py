"""Instrumented Playwright action wrappers."""

from opentelemetry.trace import StatusCode

from smokeshow.sensitive import redact_if_needed
from smokeshow.spans import action_span


class ActionInstrumentor:
    """Wraps a Playwright Page with OpenTelemetry-instrumented actions."""

    def __init__(self, page, tracer, parent_ctx):
        self._page = page
        self._tracer = tracer
        self._ctx = parent_ctx

    @property
    def page(self):
        """Raw Playwright Page for escape-hatch scenarios."""
        return self._page

    async def navigate(self, url):
        """Navigate to a URL with performance timing capture."""
        with action_span(
            self._tracer,
            self._ctx,
            "navigate",
            **{"test.action.target_url": url},
        ) as span:
            span.set_attribute("test.action.page_url", self._page.url)
            response = await self._page.goto(url, wait_until="domcontentloaded")
            if response:
                span.set_attribute(
                    "test.navigation.response_status", response.status
                )
            try:
                timing = await self._page.evaluate(
                    """() => {
                    const entries = performance.getEntriesByType('navigation');
                    if (entries.length === 0) return null;
                    const nav = entries[0];
                    return {
                        domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
                        loadEvent: nav.loadEventEnd - nav.startTime,
                        transferSize: nav.transferSize || 0,
                        domInteractive: nav.domInteractive - nav.startTime,
                    };
                }"""
                )
                if timing:
                    span.set_attribute(
                        "test.navigation.dom_content_loaded_ms",
                        timing["domContentLoaded"],
                    )
                    span.set_attribute(
                        "test.navigation.load_event_ms", timing["loadEvent"]
                    )
                    span.set_attribute(
                        "test.navigation.transfer_size_bytes",
                        timing["transferSize"],
                    )
                    span.set_attribute(
                        "test.navigation.dom_interactive_ms",
                        timing["domInteractive"],
                    )
            except Exception:
                pass  # navigation timing not available
            span.set_status(StatusCode.OK)

    async def click(self, selector):
        """Click an element."""
        with action_span(self._tracer, self._ctx, "click", selector) as span:
            span.set_attribute("test.action.page_url", self._page.url)
            await self._page.click(selector)
            span.set_status(StatusCode.OK)

    async def fill(self, selector, value, sensitive=False):
        """Fill a form field, with optional sensitive data redaction."""
        with action_span(self._tracer, self._ctx, "fill", selector) as span:
            span.set_attribute("test.action.page_url", self._page.url)
            redacted = redact_if_needed(value, selector, sensitive)
            span.set_attribute("test.action.input_value", redacted)
            await self._page.fill(selector, value)
            span.set_status(StatusCode.OK)

    async def assert_visible(self, selector):
        """Assert an element is visible."""
        with action_span(
            self._tracer, self._ctx, "assert_visible", selector
        ) as span:
            span.set_attribute("test.action.page_url", self._page.url)
            await self._page.wait_for_selector(selector, state="visible", timeout=5000)
            span.set_attribute("test.action.result", "success")
            span.set_status(StatusCode.OK)

    async def assert_text(self, selector, expected):
        """Assert an element contains expected text (case-insensitive)."""
        with action_span(
            self._tracer, self._ctx, "assert_text", selector
        ) as span:
            span.set_attribute("test.action.page_url", self._page.url)
            element = await self._page.wait_for_selector(
                selector, state="visible", timeout=5000
            )
            text = await element.text_content()
            if expected.lower() in text.lower():
                span.set_attribute("test.action.result", "success")
                span.set_status(StatusCode.OK)
            else:
                span.set_attribute("test.action.result", "failed")
                span.set_status(StatusCode.ERROR, f"Expected '{expected}' in '{text}'")
                raise AssertionError(f"Expected '{expected}' in '{text}'")

    async def assert_count(self, selector, expected_count):
        """Assert the number of elements matching a selector."""
        with action_span(
            self._tracer, self._ctx, "assert_count", selector
        ) as span:
            span.set_attribute("test.action.page_url", self._page.url)
            elements = await self._page.query_selector_all(selector)
            actual = len(elements)
            span.set_attribute(
                "test.action.result",
                "success" if actual == expected_count else "failed",
            )
            if actual == expected_count:
                span.set_status(StatusCode.OK)
            else:
                span.set_status(
                    StatusCode.ERROR,
                    f"Expected {expected_count} elements, got {actual}",
                )
                raise AssertionError(
                    f"Expected {expected_count} elements matching '{selector}', got {actual}"
                )

    async def assert_url(self, pattern):
        """Assert the current URL contains a pattern."""
        with action_span(self._tracer, self._ctx, "assert_url") as span:
            span.set_attribute("test.action.page_url", self._page.url)
            if pattern in self._page.url:
                span.set_attribute("test.action.result", "success")
                span.set_status(StatusCode.OK)
            else:
                span.set_attribute("test.action.result", "failed")
                span.set_status(
                    StatusCode.ERROR,
                    f"Expected '{pattern}' in URL '{self._page.url}'",
                )
                raise AssertionError(
                    f"Expected '{pattern}' in URL, got {self._page.url}"
                )
