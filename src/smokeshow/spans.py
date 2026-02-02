"""Span helpers and VCS metadata."""

import subprocess
from contextlib import contextmanager

from opentelemetry import trace


def get_git_info() -> dict:
    """Get git commit SHA and branch for VCS metadata."""
    info = {}
    try:
        info["vcs.commit.sha"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        pass
    try:
        info["vcs.branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
    return info


def action_span(tracer, parent_ctx, action_type, selector=None, **extra_attrs):
    """Create an action-level span (grandchild of suite span).

    Returns a context manager that yields the span.
    """
    name = f"{action_type}({selector})" if selector else action_type
    attrs = {"test.action.type": action_type}
    if selector:
        attrs["test.action.selector"] = selector
    attrs.update(extra_attrs)
    return tracer.start_as_current_span(name, context=parent_ctx, attributes=attrs)
