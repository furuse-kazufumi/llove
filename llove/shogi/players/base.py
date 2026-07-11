"""Player ABC + provider spec parser for ``llove play shogi``.

A "player" is anything that, given the current ``Engine`` state, can return
a USI half-move. The contract is intentionally tiny:

    class Player(ABC):
        async def think(self, engine: Engine) -> ThinkResult: ...

We standardise on **async** because LoveApp already runs an asyncio loop
and the real implementations (Anthropic HTTP, Ollama HTTP, llmesh peer
HTTP) are all network-bound. ``mock`` simulates thinking time with
``asyncio.sleep`` so the TUI cadence is identical.

The ``parse_provider_spec`` helper turns ``"anthropic:claude-haiku-4-5"``
into a concrete :class:`Player`. Importing the SDK is **lazy** — a default
``llmesh-llove[shogi]`` install does not need ``anthropic`` /
``httpx`` / ``llmesh-mcp`` until you actually pick that provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — type-only
    from llove.llm.config import LLMConfig
    from llove.llm.transport import HttpTransport
    from llove.shogi.engine import Engine


# ---------------------------------------------------------------------------
# Move + ThinkResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Move:
    """One half-move proposal.

    ``usi`` is the only required field. ``thinking_ms`` and ``commentary``
    surface in the kifu pane / narration; ``raw_response`` is whatever the
    backend returned (kept for audit + debugging — for LLM providers this is
    the model's full text answer before USI extraction).
    """

    usi: str
    thinking_ms: int | None = None
    commentary: str = ""
    raw_response: str = ""


@dataclass(frozen=True)
class ThinkResult:
    """What :meth:`Player.think` returns.

    ``move`` is ``None`` when the player resigns (e.g. ran out of legal
    options, or chose to). ``resign_reason`` carries the human-readable
    "why" — surfaces in the audit pane.
    """

    move: Move | None
    resign: bool = False
    resign_reason: str = ""


# ---------------------------------------------------------------------------
# Player ABC
# ---------------------------------------------------------------------------


class Player(ABC):
    """Async base class for all shogi players.

    Subclasses **must** be safe to call from the LoveApp event loop — i.e.
    no blocking network calls, use httpx / aiohttp / asyncio.to_thread.
    """

    #: Display name shown in audit / kifu / narration. Subclasses set this.
    name: str = "?"
    #: Provider tag (``"mock"`` / ``"anthropic"`` / ``"ollama"`` / ``"llmesh"``).
    provider: str = "?"
    #: Concrete model identifier (``"claude-haiku-4-5"`` / ``"llama3:70b"`` / ...).
    model: str = ""

    @abstractmethod
    async def think(self, engine: Engine) -> ThinkResult:
        """Return one legal-USI proposal (or a resign signal).

        The engine is passed read-only; players that need legal moves can
        call ``engine.legal_moves_usi()``. The loop validates the returned
        USI before applying it — players are *not* required to pre-validate
        (and shouldn't, because the loop is the legality oracle).
        """

    async def aclose(self) -> None:
        """Optional teardown hook (close HTTP clients etc.). Default no-op."""


# ---------------------------------------------------------------------------
# Provider spec parser
# ---------------------------------------------------------------------------


_KNOWN_PROVIDERS = ("mock", "anthropic", "ollama", "llmesh")


def parse_provider_spec(spec: str) -> tuple[str, str]:
    """Split ``"provider:model"`` into ``(provider, model)``.

    Examples
    --------
    >>> parse_provider_spec("anthropic:claude-haiku-4-5")
    ('anthropic', 'claude-haiku-4-5')
    >>> parse_provider_spec("ollama:llama3:70b")           # model can contain colons
    ('ollama', 'llama3:70b')
    >>> parse_provider_spec("mock")                         # no model — default to "script"
    ('mock', 'script')
    >>> parse_provider_spec("llmesh:peer:CtestNodeID")     # full provider:model:variant
    ('llmesh', 'peer:CtestNodeID')

    Raises ``ValueError`` on unknown providers.
    """
    if ":" not in spec:
        provider, model = spec, "script" if spec == "mock" else ""
    else:
        provider, model = spec.split(":", 1)

    provider = provider.lower()
    if provider not in _KNOWN_PROVIDERS:
        known = ", ".join(_KNOWN_PROVIDERS)
        raise ValueError(
            f"unknown provider {provider!r}. Known: {known}. "
            "Use e.g. 'mock:script', 'anthropic:claude-haiku-4-5', or "
            "'ollama:llama3:70b'."
        )
    return provider, model


def make_player(
    spec: str,
    *,
    side: str,
    config: object | None = None,
    transport: object | None = None,
) -> Player:
    """Resolve a provider spec to a concrete :class:`Player` instance.

    Lazy-imports the provider module so that, for example, picking
    ``mock:script`` does not pull in the LLM machinery.

    ``side`` is ``"sente"`` or ``"gote"`` — passed to the player so its
    display name and prompt can address the right side. ``config`` /
    ``transport`` are forwarded to the LLM factory (tests inject a fake
    transport; ``config`` defaults to ``LLMConfig.from_env()``).

    MVP2b: ``anthropic`` / ``ollama`` / ``llmesh`` now return a real
    :class:`llove.shogi.players.llm.LLMShogiPlayer`. Missing API keys /
    endpoints surface as ``LLMConfigError`` (fail-closed).
    """
    provider, _model = parse_provider_spec(spec)
    if provider == "mock":
        from llove.shogi.players.mock import MockPlayer

        return MockPlayer(model=_model, side=side)
    if provider in ("anthropic", "ollama", "llmesh"):
        from llove.llm.config import LLMConfig
        from llove.llm.transport import HttpTransport
        from llove.shogi.players.llm import make_shogi_llm_player

        cfg = config if isinstance(config, LLMConfig) else None
        tr = transport if isinstance(transport, HttpTransport) else None
        return make_shogi_llm_player(spec, side=side, config=cfg, transport=tr)
    # Should be unreachable thanks to parse_provider_spec validation, but
    # keep the safety net in case _KNOWN_PROVIDERS gains entries.
    raise ValueError(f"no factory for provider {provider!r}")  # pragma: no cover
