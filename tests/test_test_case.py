"""Tests for TestCase context manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from smokeshow.test_case import TestCase


@pytest.fixture
def test_case_setup(otel_setup, mock_page):
    tracer, exporter = otel_setup
    root = tracer.start_span("suite-root")
    ctx = trace.set_span_in_context(root)
    record_fn = MagicMock()
    tc = TestCase(
        tracer, ctx, mock_page, record_fn,
        name="test-login",
        case_id="TC-001",
        tags="smoke,auth",
        description="Test user login",
    )
    return tc, exporter, root, record_fn


class TestSuccessPath:
    @pytest.mark.asyncio
    async def test_passed_result(self, test_case_setup):
        tc, exporter, root, record_fn = test_case_setup
        async with tc as t:
            await t.navigate("http://localhost:8080/")
        root.end()

        spans = exporter.get_finished_spans()
        case_span = [s for s in spans if 'test("test-login")' in s.name][0]
        assert case_span.attributes["test.case.name"] == "test-login"
        assert case_span.attributes["test.case.id"] == "TC-001"
        assert case_span.attributes["test.case.tags"] == "smoke,auth"
        assert case_span.attributes["test.case.result"] == "passed"
        assert case_span.status.status_code == StatusCode.OK
        record_fn.assert_called_once_with(True)


class TestFailurePath:
    @pytest.mark.asyncio
    async def test_failed_result(self, test_case_setup, mock_page):
        tc, exporter, root, record_fn = test_case_setup
        type(mock_page).url = PropertyMock(return_value="http://localhost:8080/fail")

        with pytest.raises(RuntimeError, match="boom"):
            async with tc as t:
                raise RuntimeError("boom")
        root.end()

        spans = exporter.get_finished_spans()
        case_span = [s for s in spans if 'test("test-login")' in s.name][0]
        assert case_span.attributes["test.case.result"] == "failed"
        assert case_span.attributes["test.case.failure_reason"] == "boom"
        assert case_span.attributes["test.case.failure_url"] == "http://localhost:8080/fail"
        assert case_span.status.status_code == StatusCode.ERROR
        record_fn.assert_called_once_with(False)


class TestCustomAttributes:
    @pytest.mark.asyncio
    async def test_set_attribute(self, test_case_setup):
        tc, exporter, root, _ = test_case_setup
        async with tc as t:
            t.set_attribute("arc.home.total_links", 42)
        root.end()

        spans = exporter.get_finished_spans()
        case_span = [s for s in spans if 'test("test-login")' in s.name][0]
        assert case_span.attributes["arc.home.total_links"] == 42


class TestActionSpan:
    @pytest.mark.asyncio
    async def test_custom_action_span(self, test_case_setup):
        tc, exporter, root, _ = test_case_setup
        async with tc as t:
            with t.action_span("extract_metadata") as span:
                span.set_status(StatusCode.OK)
        root.end()

        spans = exporter.get_finished_spans()
        meta = [s for s in spans if s.name == "extract_metadata"][0]
        assert meta.attributes["test.action.type"] == "extract_metadata"
