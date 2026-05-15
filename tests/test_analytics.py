"""Unit tests for the analytics module — including the track_tool decorator."""

import asyncio

import pytest

from anthropic_news_mcp import analytics


def test_capture_noop_when_uninitialised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analytics, "_initialised", False)
    analytics.capture("event", {"k": 1})
    assert analytics.is_enabled() is False


def test_track_tool_records_outcome_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(analytics, "_initialised", True)
    monkeypatch.setattr(
        analytics,
        "capture",
        lambda event, props=None: events.append((event, props or {})),
    )

    @analytics.track_tool("demo")
    async def handler(x: int) -> dict[str, int]:
        return {"value": x * 2}

    result = asyncio.run(handler(3))
    assert result == {"value": 6}

    assert len(events) == 1
    name, props = events[0]
    assert name == "tool_invoked"
    assert props["tool"] == "demo"
    assert props["outcome"] == "ok"
    assert isinstance(props["latency_ms"], int)
    assert props["latency_ms"] >= 0
    assert "error_class" not in props


def test_track_tool_records_outcome_error(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(analytics, "_initialised", True)
    monkeypatch.setattr(
        analytics,
        "capture",
        lambda event, props=None: events.append((event, props or {})),
    )

    @analytics.track_tool("failing")
    async def boom() -> dict[str, str]:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(boom())

    assert len(events) == 1
    name, props = events[0]
    assert name == "tool_invoked"
    assert props["tool"] == "failing"
    assert props["outcome"] == "error"
    assert props["error_class"] == "ValueError"


def test_track_tool_silent_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(analytics, "_initialised", False)
    monkeypatch.setattr(
        analytics,
        "capture",
        lambda event, props=None: events.append((event, props or {})),
    )

    @analytics.track_tool("quiet")
    async def handler() -> int:
        return 42

    assert asyncio.run(handler()) == 42
    assert events == []


def test_distinct_id_is_stable() -> None:
    a = analytics._distinct_id()
    b = analytics._distinct_id()
    assert a == b
    assert len(a) == 16
