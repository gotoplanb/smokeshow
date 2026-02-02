"""Tests for ActionInstrumentor."""

import pytest
from unittest.mock import AsyncMock, PropertyMock

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from smokeshow.actions import ActionInstrumentor


@pytest.fixture
def instrumentor(otel_setup, mock_page):
    tracer, exporter = otel_setup
    root = tracer.start_span("test-root")
    ctx = trace.set_span_in_context(root)
    inst = ActionInstrumentor(mock_page, tracer, ctx)
    yield inst, exporter, root


class TestNavigate:
    @pytest.mark.asyncio
    async def test_navigate_creates_span(self, instrumentor):
        inst, exporter, root = instrumentor
        await inst.navigate("http://localhost:8080/")
        root.end()

        spans = exporter.get_finished_spans()
        nav = [s for s in spans if s.name == "navigate"][0]
        assert nav.attributes["test.action.type"] == "navigate"
        assert nav.attributes["test.action.target_url"] == "http://localhost:8080/"
        assert nav.status.status_code == StatusCode.OK

    @pytest.mark.asyncio
    async def test_navigate_captures_timing(self, instrumentor, mock_page):
        mock_page.evaluate.return_value = {
            "domContentLoaded": 150.0,
            "loadEvent": 300.0,
            "transferSize": 1024,
            "domInteractive": 100.0,
        }
        inst, exporter, root = instrumentor
        await inst.navigate("http://localhost:8080/")
        root.end()

        spans = exporter.get_finished_spans()
        nav = [s for s in spans if s.name == "navigate"][0]
        assert nav.attributes["test.navigation.dom_content_loaded_ms"] == 150.0
        assert nav.attributes["test.navigation.transfer_size_bytes"] == 1024


class TestClick:
    @pytest.mark.asyncio
    async def test_click_creates_span(self, instrumentor):
        inst, exporter, root = instrumentor
        await inst.click("button#submit")
        root.end()

        spans = exporter.get_finished_spans()
        click = [s for s in spans if s.name == "click(button#submit)"][0]
        assert click.attributes["test.action.type"] == "click"
        assert click.attributes["test.action.selector"] == "button#submit"
        assert click.status.status_code == StatusCode.OK


class TestFill:
    @pytest.mark.asyncio
    async def test_fill_records_value(self, instrumentor):
        inst, exporter, root = instrumentor
        await inst.fill("input#email", "test@example.com")
        root.end()

        spans = exporter.get_finished_spans()
        fill = [s for s in spans if s.name == "fill(input#email)"][0]
        assert fill.attributes["test.action.input_value"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_fill_redacts_sensitive(self, instrumentor):
        inst, exporter, root = instrumentor
        await inst.fill("input#password", "secret123")
        root.end()

        spans = exporter.get_finished_spans()
        fill = [s for s in spans if s.name == "fill(input#password)"][0]
        assert fill.attributes["test.action.input_value"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_fill_explicit_sensitive(self, instrumentor):
        inst, exporter, root = instrumentor
        await inst.fill("input#email", "secret", sensitive=True)
        root.end()

        spans = exporter.get_finished_spans()
        fill = [s for s in spans if s.name == "fill(input#email)"][0]
        assert fill.attributes["test.action.input_value"] == "[REDACTED]"


class TestAssertVisible:
    @pytest.mark.asyncio
    async def test_assert_visible_success(self, instrumentor):
        inst, exporter, root = instrumentor
        await inst.assert_visible("h1")
        root.end()

        spans = exporter.get_finished_spans()
        av = [s for s in spans if s.name == "assert_visible(h1)"][0]
        assert av.attributes["test.action.result"] == "success"
        assert av.status.status_code == StatusCode.OK


class TestAssertText:
    @pytest.mark.asyncio
    async def test_assert_text_success(self, instrumentor):
        inst, exporter, root = instrumentor
        await inst.assert_text("h1", "Hello")
        root.end()

        spans = exporter.get_finished_spans()
        at = [s for s in spans if s.name == "assert_text(h1)"][0]
        assert at.attributes["test.action.result"] == "success"

    @pytest.mark.asyncio
    async def test_assert_text_failure(self, instrumentor):
        inst, exporter, root = instrumentor
        with pytest.raises(AssertionError, match="Expected 'Missing'"):
            await inst.assert_text("h1", "Missing")
        root.end()

        spans = exporter.get_finished_spans()
        at = [s for s in spans if s.name == "assert_text(h1)"][0]
        assert at.attributes["test.action.result"] == "failed"
        assert at.status.status_code == StatusCode.ERROR


class TestAssertCount:
    @pytest.mark.asyncio
    async def test_assert_count_success(self, instrumentor, mock_page):
        mock_page.query_selector_all.return_value = [1, 2, 3]
        inst, exporter, root = instrumentor
        await inst.assert_count("li", 3)
        root.end()

        spans = exporter.get_finished_spans()
        ac = [s for s in spans if s.name == "assert_count(li)"][0]
        assert ac.attributes["test.action.result"] == "success"

    @pytest.mark.asyncio
    async def test_assert_count_failure(self, instrumentor, mock_page):
        mock_page.query_selector_all.return_value = [1]
        inst, exporter, root = instrumentor
        with pytest.raises(AssertionError, match="Expected 3"):
            await inst.assert_count("li", 3)
        root.end()


class TestAssertUrl:
    @pytest.mark.asyncio
    async def test_assert_url_success(self, instrumentor):
        inst, exporter, root = instrumentor
        await inst.assert_url("localhost")
        root.end()

        spans = exporter.get_finished_spans()
        au = [s for s in spans if s.name == "assert_url"][0]
        assert au.attributes["test.action.result"] == "success"

    @pytest.mark.asyncio
    async def test_assert_url_failure(self, instrumentor):
        inst, exporter, root = instrumentor
        with pytest.raises(AssertionError, match="Expected '/arc/'"):
            await inst.assert_url("/arc/")
        root.end()
