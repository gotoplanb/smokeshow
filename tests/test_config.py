"""Tests for SmokeshowConfig."""

import os
import pytest
from smokeshow.config import SmokeshowConfig


class TestDefaults:
    def test_default_values(self, monkeypatch):
        # Clear env vars that might interfere
        for var in [
            "OTEL_SERVICE_NAME",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "PLAYWRIGHT_OTEL_ENVIRONMENT",
            "PLAYWRIGHT_OTEL_TRIGGER",
            "PLAYWRIGHT_OTEL_BROWSER",
            "PLAYWRIGHT_OTEL_HEADLESS",
        ]:
            monkeypatch.delenv(var, raising=False)

        cfg = SmokeshowConfig()
        assert cfg.service_name == "playwright-otel"
        assert cfg.otlp_endpoint == "http://localhost:4317"
        assert cfg.environment == "development"
        assert cfg.trigger == "manual"
        assert cfg.browser_type == "chromium"
        assert cfg.headless is True
        assert cfg.viewport_width == 1280
        assert cfg.viewport_height == 720

    def test_constructor_overrides(self, monkeypatch):
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
        cfg = SmokeshowConfig(
            service_name="my-service",
            otlp_endpoint="http://alloy:4317",
            environment="staging",
        )
        assert cfg.service_name == "my-service"
        assert cfg.otlp_endpoint == "http://alloy:4317"
        assert cfg.environment == "staging"


class TestEnvVars:
    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "env-service")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://env:4317")
        monkeypatch.setenv("PLAYWRIGHT_OTEL_ENVIRONMENT", "production")
        monkeypatch.setenv("PLAYWRIGHT_OTEL_TRIGGER", "ci")
        monkeypatch.setenv("PLAYWRIGHT_OTEL_BROWSER", "firefox")

        cfg = SmokeshowConfig()
        assert cfg.service_name == "env-service"
        assert cfg.otlp_endpoint == "http://env:4317"
        assert cfg.environment == "production"
        assert cfg.trigger == "ci"
        assert cfg.browser_type == "firefox"

    def test_constructor_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "env-service")
        cfg = SmokeshowConfig(service_name="explicit-service")
        assert cfg.service_name == "explicit-service"

    def test_headless_env_false(self, monkeypatch):
        monkeypatch.setenv("PLAYWRIGHT_OTEL_HEADLESS", "false")
        cfg = SmokeshowConfig()
        assert cfg.headless is False

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "env-svc")
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        cfg = SmokeshowConfig.from_env(suite_name="my-suite")
        assert cfg.service_name == "env-svc"
        assert cfg.suite_name == "my-suite"
