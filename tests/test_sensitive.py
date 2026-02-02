"""Tests for sensitive data redaction."""

import pytest
from smokeshow.sensitive import is_sensitive_selector, redact_if_needed, REDACTED


class TestIsSensitiveSelector:
    @pytest.mark.parametrize(
        "selector",
        [
            "input#password",
            "input[name='card-number']",
            "#cvv",
            "input.ssn-field",
            "#credit-card",
            "input#secret-key",
            "input[name='token']",
            "INPUT#PASSWORD",  # case insensitive
        ],
    )
    def test_sensitive_selectors_detected(self, selector):
        assert is_sensitive_selector(selector) is True

    @pytest.mark.parametrize(
        "selector",
        [
            "input#email",
            "input[name='username']",
            "#first-name",
            "button.submit",
            "h1",
        ],
    )
    def test_non_sensitive_selectors(self, selector):
        assert is_sensitive_selector(selector) is False


class TestRedactIfNeeded:
    def test_explicit_sensitive_flag(self):
        assert redact_if_needed("my-value", "input#email", sensitive=True) == REDACTED

    def test_auto_detect_from_selector(self):
        assert redact_if_needed("secret123", "input#password") == REDACTED

    def test_not_sensitive(self):
        assert redact_if_needed("hello", "input#email") == "hello"

    def test_auto_detect_overrides_default(self):
        # Even without explicit sensitive=True, password selector triggers redaction
        assert redact_if_needed("pass123", "input#password", sensitive=False) == REDACTED
