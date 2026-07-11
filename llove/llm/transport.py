"""HTTP transport 抽象 — DI でテスト可能, stdlib のみ.

:mod:`llove.mcp.client` の ``MCPTransport`` と同じ哲学:

- **Transport 注入**: ``HttpTransport`` Protocol を 1 つ満たせば fake /
  record-replay / 本物 urllib へ差し替えられる. テストは実 HTTP を踏まない.
- **同期 I/O + to_thread**: transport 自体は同期. :class:`llove.llm.client.LLMClient`
  が ``asyncio.to_thread`` で包むので LoveApp の event loop を奪わない.
  こうすることで httpx / aiohttp を新規依存に加えずに async 化できる.
- **fail-closed の境界**: 接続不可 / タイムアウトは ``LLMBackendError`` を送出.
  HTTP エラー応答 (4xx/5xx) は ``(status, body)`` として返す — プロバイダが
  ステータスを見て意味づけする (401=キー不正, 404=モデル無し 等).
"""

from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from llove.llm.types import LLMBackendError

#: LLM 応答は生成に時間がかかるのでデフォルトを長めに取る.
DEFAULT_TIMEOUT_S = 60.0


class HttpTransport(Protocol):
    """最小 HTTP transport 契約.

    ``request(method, url, *, headers, body)`` -> ``(status, body_bytes)``.
    接続不可は ``LLMBackendError`` を投げる (呼び出し側が fail-closed 処理).
    """

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, bytes]: ...


@dataclass
class UrllibHttpTransport:
    """stdlib ``urllib.request`` を用いるデフォルト transport.

    SSL 検証は Python 標準挙動に従う. 接続不可 / タイムアウトは
    ``LLMBackendError`` に正規化する.
    """

    timeout: float = DEFAULT_TIMEOUT_S

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, bytes]:
        try:
            # Request 構築時にも URL 解析が走り, 不正 URL は bare ValueError を投げる
            # (例: scheme 無し "unknown url type") — try 内に置いて正規化する.
            req = urllib.request.Request(
                url,
                method=method,
                data=body,
                headers=headers or {},
            )
            with urllib.request.urlopen(  # nosec B310 — host-controlled endpoint
                req, timeout=self.timeout
            ) as resp:
                return int(resp.status), resp.read()
        except urllib.error.HTTPError as exc:
            # 4xx/5xx は「応答があった」扱い — プロバイダにステータスを渡す.
            return int(exc.code), (exc.read() if exc.fp else b"")
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
            ValueError,
        ) as exc:
            # 接続不可 / タイムアウト / 応答受信中のドロップ(RemoteDisconnected 等)/
            # 不正 URL(urllib は "unknown url type" を bare ValueError で投げる)を
            # すべて LLMBackendError に正規化する — transport は必ず
            # LLMBackendError しか投げない, という fail-closed 契約を守る.
            # (URLError/TimeoutError は OSError 部分集合だが可読性のため明示列挙.)
            raise LLMBackendError(f"connection_error: {exc}") from exc


# ---------------------------------------------------------------------------
# テスト用 fake transport
# ---------------------------------------------------------------------------


def make_fake_http_transport(
    handler: Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]],
) -> HttpTransport:
    """``handler(method, url, headers, body)`` に委譲する transport を作る.

    テストはこれでリクエスト形状を検証し, 定型応答を返せる (HTTP サーバ不要).
    ``llove.mcp.client.make_fake_transport`` と同じ流儀.
    """

    @dataclass
    class _FakeHttpTransport:
        def request(
            self,
            method: str,
            url: str,
            *,
            headers: dict[str, str] | None = None,
            body: bytes | None = None,
        ) -> tuple[int, bytes]:
            return handler(method, url, headers or {}, body)

    return _FakeHttpTransport()


__all__ = [
    "DEFAULT_TIMEOUT_S",
    "HttpTransport",
    "UrllibHttpTransport",
    "make_fake_http_transport",
]
