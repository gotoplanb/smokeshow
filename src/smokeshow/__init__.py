"""smokeshow — OpenTelemetry instrumentation for Playwright E2E tests."""

from smokeshow.browser import InstrumentedBrowser
from smokeshow.config import SmokeshowConfig

__all__ = ["InstrumentedBrowser", "SmokeshowConfig"]
