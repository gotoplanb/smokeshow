"""Configuration for smokeshow instrumented browser."""

import os
from dataclasses import dataclass, field


@dataclass
class SmokeshowConfig:
    """Configuration for an instrumented browser session.

    Constructor arguments take precedence over environment variables.
    """

    service_name: str = ""
    suite_name: str = ""
    base_url: str = ""
    otlp_endpoint: str = ""
    otlp_insecure: bool = True
    environment: str = ""
    trigger: str = ""
    browser_type: str = ""
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720

    def __post_init__(self):
        # Apply env var defaults for fields left at their zero-value
        if not self.service_name:
            self.service_name = os.environ.get("OTEL_SERVICE_NAME", "playwright-otel")
        if not self.otlp_endpoint:
            self.otlp_endpoint = os.environ.get(
                "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
            )
        if not self.environment:
            self.environment = os.environ.get(
                "PLAYWRIGHT_OTEL_ENVIRONMENT", "development"
            )
        if not self.trigger:
            self.trigger = os.environ.get("PLAYWRIGHT_OTEL_TRIGGER", "manual")
        if not self.browser_type:
            self.browser_type = os.environ.get("PLAYWRIGHT_OTEL_BROWSER", "chromium")
        headless_env = os.environ.get("PLAYWRIGHT_OTEL_HEADLESS")
        if headless_env is not None and self.headless is True:
            self.headless = headless_env.lower() not in ("false", "0", "no")

    @classmethod
    def from_env(cls, **overrides):
        """Create config primarily from environment variables, with optional overrides."""
        return cls(**overrides)
