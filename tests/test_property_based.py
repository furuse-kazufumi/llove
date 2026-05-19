"""Hypothesis property-based tests.

These exercise the parts of llove that ingest external / arbitrary data:
    - Event payload survives roundtrip through model_dump
    - JSONLSource never raises on arbitrary text input
    - NarrationView never lets Rich tags from user data escape into the UI
    - MockSource is deterministic for any seed and reasonable tick value
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from llove.events import Event, EventKind
from llove.sources.jsonl import JSONLSource
from llove.sources.mock import MockSource
from llove.views.narration import NarrationView

# Reasonable JSON-friendly value strategy: scalars + small dicts/lists.
_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31 - 1),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(max_size=64),
)
_payload = st.dictionaries(
    keys=st.text(min_size=1, max_size=16, alphabet=st.characters(blacklist_categories=("Cs",))),
    values=_scalar,
    max_size=8,
)


@settings(deadline=None)  # Windows での初回 import で 200ms 超えるケースあり (flaky 防止)
@given(kind=st.sampled_from(list(EventKind)), payload=_payload, source_id=st.text(max_size=24))
def test_event_roundtrip_through_json(kind: EventKind, payload: dict, source_id: str) -> None:
    """Any constructible Event must survive a full JSON roundtrip."""
    ev = Event(kind=kind, source_id=source_id, payload=payload)
    encoded = ev.model_dump_json()
    decoded = json.loads(encoded)
    assert decoded["kind"] == kind.value
    assert decoded["source_id"] == source_id
    # short() must never raise even on weird payloads.
    ev.short()


@settings(
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    max_examples=60,
    deadline=None,
)
@given(text=st.text(max_size=1024))
@pytest.mark.asyncio
async def test_jsonl_source_never_raises_on_arbitrary_text(text: str, tmp_path: Path) -> None:
    """JSONLSource is fail-closed: garbage in -> empty (or partial) out, never a crash."""
    p = tmp_path / "fuzz.jsonl"
    p.write_text(text, encoding="utf-8")
    # Just make sure iteration finishes without raising.
    out = []
    async for ev in JSONLSource(p).stream():
        out.append(ev)
    # No assertion on contents — the property is "no exception".
    assert isinstance(out, list)


@given(
    text=st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cc",))),
    title=st.one_of(st.none(), st.text(max_size=40)),
)
def test_narration_view_never_leaks_user_rich_tags(text: str, title: str | None) -> None:
    """User-supplied [tag]…[/tag] markers must be neutralised before render."""
    v = NarrationView()
    payload: dict = {"text": text}
    if title:
        payload["title"] = title
    v.feed(Event(kind=EventKind.NARRATION, payload=payload))
    rendered = v.last_render
    # Any literal '[' from the user data must be escaped to '\['; the only
    # bracketed tags allowed in `rendered` are those we ourselves emit:
    # [dim], [bold], [reverse], and their close forms.
    allowed = {"[dim]", "[/dim]", "[bold]", "[/bold]", "[reverse]", "[/reverse]"}
    # Strip allowed tags first; any remaining unescaped '[' is a leak.
    stripped = rendered
    for token in allowed:
        stripped = stripped.replace(token, "")
    # All '[' that remain must be escaped (preceded by backslash).
    idx = 0
    while True:
        i = stripped.find("[", idx)
        if i == -1:
            break
        assert (
            i > 0 and stripped[i - 1] == "\\"
        ), f"unescaped '[' leaked into render at position {i}: {stripped!r}"
        idx = i + 1


@settings(
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    max_examples=12,
    deadline=None,
)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
@pytest.mark.asyncio
async def test_mock_source_is_deterministic_for_any_seed(seed: int) -> None:
    """Same seed -> same value sequence."""
    a = await _take_sensor_values(MockSource(seed=seed, tick_seconds=0.0001), n=15)
    b = await _take_sensor_values(MockSource(seed=seed, tick_seconds=0.0001), n=15)
    assert a == b


async def _take_sensor_values(src: MockSource, n: int) -> list[float]:
    out: list[float] = []
    async for ev in src.stream():
        if ev.kind == EventKind.SENSOR:
            out.append(float(ev.payload.get("value", 0.0)))
        if len(out) >= n:
            break
    return out
