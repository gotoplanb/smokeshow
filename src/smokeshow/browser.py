"""InstrumentedBrowser — top-level async context manager for instrumented E2E suites."""

import uuid
from datetime import datetime, timezone

import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import StatusCode
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider
from playwright.async_api import async_playwright

from smokeshow.config import SmokeshowConfig
from smokeshow.spans import get_git_info
from smokeshow.test_case import TestCase


class InstrumentedBrowser:
    """Async context manager that sets up OTEL + Playwright for a test suite.

    Usage::

        async with InstrumentedBrowser(
            service_name="my-e2e",
            suite_name="smoke",
        ) as browser:
            async with browser.test_case(name="login", case_id="TC-001") as test:
                await test.navigate("http://localhost:8080")
                await test.assert_visible("h1")
    """

    def __init__(self, *, service_name="", suite_name="", base_url="",
                 otlp_endpoint="", otlp_insecure=True, environment="",
                 trigger="", browser_type="", headless=True,
                 viewport_width=1280, viewport_height=720):
        self._config = SmokeshowConfig(
            service_name=service_name,
            suite_name=suite_name,
            base_url=base_url,
            otlp_endpoint=otlp_endpoint,
            otlp_insecure=otlp_insecure,
            environment=environment,
            trigger=trigger,
            browser_type=browser_type,
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        self._provider = None
        self._tracer = None
        self._suite_span = None
        self._suite_ctx = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._passed = 0
        self._failed = 0
        self._total = 0

    async def __aenter__(self):
        cfg = self._config

        # Set up OTEL
        resource = Resource.create({
            "service.name": cfg.service_name,
            "telemetry.sdk.name": "smokeshow",
            "deployment.environment": cfg.environment,
        })
        self._provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=cfg.otlp_endpoint, insecure=cfg.otlp_insecure
        )
        self._provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(self._provider)
        self._tracer = trace.get_tracer("smokeshow", "0.2.0")

        # Set up OTEL logging (emits error logs for failed test cases, correlated with traces)
        self._log_provider = LoggerProvider(resource=resource)
        log_exporter = OTLPLogExporter(
            endpoint=cfg.otlp_endpoint, insecure=cfg.otlp_insecure
        )
        self._log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        set_logger_provider(self._log_provider)
        handler = LoggingHandler(level=logging.ERROR, logger_provider=self._log_provider)
        self._logger = logging.getLogger("smokeshow.test_results")
        self._logger.addHandler(handler)
        self._logger.setLevel(logging.ERROR)

        # Build suite span attributes
        suite_id = str(uuid.uuid4())
        suite_attrs = {
            "test.suite.name": cfg.suite_name,
            "test.suite.id": suite_id,
            "test.run.trigger": cfg.trigger,
            "test.run.timestamp": datetime.now(timezone.utc).isoformat(),
            "test.target.base_url": cfg.base_url,
            "test.target.environment": cfg.environment,
            "test.browser.name": cfg.browser_type,
            "test.browser.headless": cfg.headless,
            "test.viewport.width": cfg.viewport_width,
            "test.viewport.height": cfg.viewport_height,
        }
        suite_attrs.update(get_git_info())

        self._suite_span = self._tracer.start_span(
            f"suite({cfg.suite_name})", attributes=suite_attrs
        )
        self._suite_ctx = trace.set_span_in_context(self._suite_span)

        # Launch Playwright
        self._playwright = await async_playwright().start()
        launcher = getattr(self._playwright, cfg.browser_type)
        self._browser = await launcher.launch(headless=cfg.headless)
        self._context = await self._browser.new_context(
            viewport={"width": cfg.viewport_width, "height": cfg.viewport_height}
        )
        self._page = await self._context.new_page()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Finalize suite span
        self._suite_span.set_attribute("test.suite.total_tests", self._total)
        self._suite_span.set_attribute("test.suite.passed", self._passed)
        self._suite_span.set_attribute("test.suite.failed", self._failed)
        if self._failed == 0:
            result = "passed"
        elif self._passed == 0:
            result = "failed"
        else:
            result = "partial"
        self._suite_span.set_attribute("test.suite.result", result)
        self._suite_span.end()

        # Close browser
        await self._browser.close()
        await self._playwright.stop()

        # Flush telemetry
        self._provider.force_flush()
        self._log_provider.force_flush()

        return False

    def test_case(self, *, name, case_id="", tags="", description=""):
        """Create a TestCase async context manager for a single test."""
        self._total += 1
        return TestCase(
            self._tracer,
            self._suite_ctx,
            self._page,
            self._record_result,
            logger=self._logger,
            suite_name=self._config.suite_name,
            name=name,
            case_id=case_id,
            tags=tags,
            description=description,
        )

    def _record_result(self, passed: bool):
        """Called by TestCase.__aexit__ to track pass/fail counts."""
        if passed:
            self._passed += 1
        else:
            self._failed += 1

    @property
    def passed(self):
        return self._passed

    @property
    def failed(self):
        return self._failed

    @property
    def total(self):
        return self._total
