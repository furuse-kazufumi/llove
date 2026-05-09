"""Shared pytest fixtures."""
from __future__ import annotations

import pytest

from llove.sources.mock import MockSource


@pytest.fixture
def mock_source() -> MockSource:
    """Deterministic mock source for unit tests."""
    return MockSource(seed=42, tick_seconds=0.001)
