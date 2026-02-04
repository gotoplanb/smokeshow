"""Shared test fixtures for smokeshow tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.resources import Resource


@pytest.fixture
def otel_setup():
    """Set up an in-memory OTEL tracer for testing.

    Returns (tracer, exporter) without touching the global tracer provider,
    so tests don't interfere with each other.
    """
    exporter = InMemorySpanExporter()
    resource = Resource.create({"service.name": "test-service"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("smokeshow-test", "0.2.0")
    yield tracer, exporter
    exporter.clear()
    provider.shutdown()


@pytest.fixture
def mock_page():
    """Create a mock Playwright Page with common methods."""
    page = AsyncMock()
    # url property needs to be a regular attribute, not a coroutine
    type(page).url = PropertyMock(return_value="http://localhost:8080/")

    # goto returns a response mock
    response = AsyncMock()
    response.status = 200
    page.goto.return_value = response

    # wait_for_selector returns an element mock
    element = AsyncMock()
    element.text_content.return_value = "Hello World"
    page.wait_for_selector.return_value = element

    # evaluate returns None by default (can be overridden per-test)
    page.evaluate.return_value = None

    # query_selector_all returns empty list by default
    page.query_selector_all.return_value = []

    return page
