"""Tests for span helpers and VCS metadata."""

import subprocess
import pytest
from unittest.mock import patch

from opentelemetry import trace

from smokeshow.spans import get_git_info, action_span


class TestGetGitInfo:
    def test_returns_sha_and_branch(self):
        info = get_git_info()
        # We're in a git repo, so both should be present
        assert "vcs.commit.sha" in info
        assert len(info["vcs.commit.sha"]) == 40  # full SHA
        assert "vcs.branch" in info

    def test_handles_no_git(self):
        with patch("smokeshow.spans.subprocess.check_output", side_effect=FileNotFoundError):
            info = get_git_info()
        assert info == {}


class TestActionSpan:
    def test_span_with_selector(self, otel_setup):
        tracer, exporter = otel_setup
        root = tracer.start_span("root")
        ctx = trace.set_span_in_context(root)

        with action_span(tracer, ctx, "click", "button#submit") as span:
            pass
        root.end()

        spans = exporter.get_finished_spans()
        action = [s for s in spans if s.name == "click(button#submit)"][0]
        assert action.attributes["test.action.type"] == "click"
        assert action.attributes["test.action.selector"] == "button#submit"

    def test_span_without_selector(self, otel_setup):
        tracer, exporter = otel_setup
        root = tracer.start_span("root")
        ctx = trace.set_span_in_context(root)

        with action_span(tracer, ctx, "navigate", target_url="http://example.com") as span:
            pass
        root.end()

        spans = exporter.get_finished_spans()
        action = [s for s in spans if s.name == "navigate"][0]
        assert action.attributes["test.action.type"] == "navigate"
        assert action.attributes["target_url"] == "http://example.com"

    def test_extra_attrs_included(self, otel_setup):
        tracer, exporter = otel_setup
        root = tracer.start_span("root")
        ctx = trace.set_span_in_context(root)

        with action_span(tracer, ctx, "fill", "input#email", custom_key="custom_val"):
            pass
        root.end()

        spans = exporter.get_finished_spans()
        action = [s for s in spans if s.name == "fill(input#email)"][0]
        assert action.attributes["custom_key"] == "custom_val"
