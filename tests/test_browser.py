"""Tests for InstrumentedBrowser — suite-level span + lifecycle."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch, Mock

from opentelemetry.trace import StatusCode

from smokeshow.browser import InstrumentedBrowser


@pytest.fixture
def mock_playwright():
    """Mock the entire Playwright async context."""
    with patch("smokeshow.browser.async_playwright") as mock_ap:
        # async_playwright() returns an object whose .start() is a coroutine
        pw_instance = AsyncMock()

        # Make async_playwright() return an object with async start()
        cm = Mock()
        cm.start = AsyncMock(return_value=pw_instance)
        mock_ap.return_value = cm

        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()
        type(page).url = PropertyMock(return_value="http://localhost:8080/")
        page.evaluate.return_value = None

        response = AsyncMock()
        response.status = 200
        page.goto.return_value = response

        element = AsyncMock()
        element.text_content.return_value = "Test Content"
        page.wait_for_selector.return_value = element

        context.new_page.return_value = page
        browser.new_context.return_value = context
        pw_instance.chromium.launch.return_value = browser

        yield mock_ap, pw_instance, browser, page


class TestSuiteSpan:
    @pytest.mark.asyncio
    async def test_suite_span_attributes(self, mock_playwright):
        _, _, _, page = mock_playwright

        async with InstrumentedBrowser(
            service_name="test-e2e",
            suite_name="test-smoke",
            base_url="http://localhost:8080",
        ) as browser:
            pass

        assert browser.passed == 0
        assert browser.failed == 0
        assert browser.total == 0


class TestResultTracking:
    @pytest.mark.asyncio
    async def test_tracks_pass_and_fail(self, mock_playwright):
        _, _, _, page = mock_playwright

        async with InstrumentedBrowser(
            service_name="test-e2e",
            suite_name="test-smoke",
        ) as browser:
            # Passing test
            async with browser.test_case(name="passes", case_id="TC-P") as test:
                await test.navigate("http://localhost:8080/")

            # Failing test
            try:
                async with browser.test_case(name="fails", case_id="TC-F") as test:
                    raise RuntimeError("intentional")
            except RuntimeError:
                pass

        assert browser.passed == 1
        assert browser.failed == 1
        assert browser.total == 2


class TestBrowserLifecycle:
    @pytest.mark.asyncio
    async def test_browser_close_called(self, mock_playwright):
        _, pw_instance, browser_mock, _ = mock_playwright

        async with InstrumentedBrowser(
            service_name="test-e2e",
            suite_name="test-smoke",
        ) as browser:
            pass

        browser_mock.close.assert_awaited_once()
        pw_instance.stop.assert_awaited_once()


class TestVcsMetadata:
    @pytest.mark.asyncio
    async def test_git_info_included(self, mock_playwright):
        """Verify InstrumentedBrowser doesn't crash when git info is collected."""
        _, _, _, _ = mock_playwright

        async with InstrumentedBrowser(
            service_name="test-e2e",
            suite_name="test-smoke",
        ) as browser:
            pass
