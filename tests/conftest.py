"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from llove.i18n import set_locale
from llove.sources.mock import MockSource


@pytest.fixture(autouse=True)
def _force_en_locale():
    """All tests use the 'en' locale unless they opt out explicitly.

    This keeps assertions on literal strings stable on JP-locale dev machines.
    """
    set_locale("en")
    yield
    set_locale("en")


@pytest.fixture
def mock_source() -> MockSource:
    """Deterministic mock source for unit tests."""
    return MockSource(seed=42, tick_seconds=0.001)
