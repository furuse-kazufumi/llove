"""F15 (t3) — Mermaid → SVG → ターミナル画像チェイン.

`folding.find_code_block_regions` が ` ```mermaid ` ブロックを
``kind="mermaid"`` として識別済 (F15 (t3 prep))。本モジュールはその次の段、
**実描画** を担当する薄い shim:

    mermaid source
       │  (1) mmdc -i .mmd -o .svg
       ▼
    SVG file
       │  (2) chafa / viu / timg / kitty +kitten icat / wezterm imgcat
       ▼
    ターミナル画像

両ツールが揃わないか subprocess が失敗した場合は、ASCII フォールバック
(マーカー付きで mermaid source をそのまま表示) に降りる。MarkdownView や
将来の DiagramPane はこの結果 (``MermaidRender``) を見て分岐するだけで良い。

セキュリティ:
- subprocess は **list-based 引数のみ** (shell=True 禁止)
- ``-i input.mmd -o output.svg`` で path はテンプレ解釈なしで直接渡る
- 入力 mermaid source はテンポラリ ``.mmd`` ファイルに書き出してから
  読ませる (引数経由の長文流入を避ける)

Pure 関数 + 依存性注入で書いてあるので、mmdc / 画像ツール未インストールの
CI でもフルテスト可能。
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 — list-based argv only, no shell.
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from llove.browser.external import ExternalTool, available_tools


# ---------------------------------------------------------------------------
# 結果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MermaidRender:
    """``render_mermaid`` の戻り値.

    ``kind == "image"`` のとき:
        - ``argv``: そのまま subprocess.run できる引数列 (chafa / viu / ...)
        - ``svg_path``: 実体ファイル (caller がライフサイクルを管理)

    ``kind == "ascii"`` のとき:
        - ``ascii_text``: ターミナルにそのまま流せる文字列 (マーカー付き)
        - ``argv`` は空、``svg_path`` は ``None``
    """

    kind: Literal["image", "ascii"]
    argv: tuple[str, ...] = ()
    svg_path: Path | None = None
    ascii_text: str = ""
    image_tool: ExternalTool | None = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# 検出
# ---------------------------------------------------------------------------


def mmdc_available() -> bool:
    """``mmdc`` バイナリが PATH 上に存在するかを返す."""
    return shutil.which("mmdc") is not None


def find_image_tool() -> ExternalTool | None:
    """カタログから「画像 scheme で利用可能な」最優先ツールを返す.

    1 件も無ければ ``None``。呼び出し側はその時点で ASCII に降りる。
    """
    tools = available_tools("image")
    return tools[0] if tools else None


# ---------------------------------------------------------------------------
# mmdc 呼び出し
# ---------------------------------------------------------------------------


# テストはこの runner を差し替えて subprocess を踏まずに argv を検証する。
Runner = Callable[[list[str]], int]


def _default_runner(argv: list[str]) -> int:
    """``subprocess.run`` のデフォルト実装. 失敗時は非ゼロを返す."""
    try:
        proc = subprocess.run(  # nosec B603 — argv is fully controlled.
            argv,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        return proc.returncode
    except (OSError, subprocess.SubprocessError):
        # 呼び出し側で None に降りるようシグナル
        raise


def render_mermaid_to_svg(
    source: str,
    output: Path,
    *,
    mmdc_path: str | None = None,
    runner: Runner | None = None,
) -> Path | None:
    """Mermaid source を mmdc で SVG に変換し、出力 Path を返す.

    Parameters
    ----------
    source
        Mermaid DSL 文字列 (` ```mermaid ` フェンス内の中身)。
    output
        SVG 出力先 Path。親ディレクトリは存在前提 (caller 側で確保)。
    mmdc_path
        ``mmdc`` 実行ファイルへの絶対パス。``None`` なら ``shutil.which``
        にフォールバックせず即座に失敗 (=描画不能なので argv を作らない)。
    runner
        テスト差し替え用の subprocess shim. ``None`` なら ``_default_runner``。

    Returns
    -------
    出力 SVG の Path、または失敗時 ``None``。
    """
    if not mmdc_path:
        return None
    run = runner or _default_runner

    # mmdc は stdin 入力を受け付けないバージョンがあるため、テンポラリ .mmd
    # ファイルに書き出してから -i で渡す。output と同じディレクトリに置けば
    # caller が tmpdir を 1 つ管理するだけで両者をまとめて掃除できる。
    src_path = output.with_suffix(".mmd")
    try:
        src_path.write_text(source, encoding="utf-8")
    except OSError:
        return None

    argv = [mmdc_path, "-i", str(src_path), "-o", str(output)]
    try:
        rc = run(argv)
    except Exception:
        return None
    if rc != 0:
        return None
    if not output.exists():
        return None
    return output


# ---------------------------------------------------------------------------
# ASCII フォールバック
# ---------------------------------------------------------------------------


_FALLBACK_HEADER = "◇ mermaid (ASCII fallback — install mmdc + chafa for image render)"
_FALLBACK_RULE = "─" * 60


def ascii_fallback(source: str) -> str:
    """画像レンダ不能時に表示する ASCII ブロック.

    マーカー行 + 区切り + 元 source を返す。MarkdownView などはそのまま
    Markdown コードブロックの代わりにこの文字列を貼り付ける想定。
    """
    body = source.rstrip() if isinstance(source, str) else ""
    return f"{_FALLBACK_HEADER}\n{_FALLBACK_RULE}\n{body}\n{_FALLBACK_RULE}\n"


# ---------------------------------------------------------------------------
# 高レベル統合
# ---------------------------------------------------------------------------


def render_mermaid(
    source: str,
    *,
    output_dir: Path,
    mmdc_path: str | None = None,
    image_tool: ExternalTool | None = None,
    runner: Runner | None = None,
) -> MermaidRender:
    """source を可能な限りターミナル画像化し、不可なら ASCII で返す.

    引数を省略した場合は ``mmdc_available`` / ``find_image_tool`` で
    自動検出する。テストや明示的な切替が必要なときだけ引数を埋める。

    成功時:
        ``MermaidRender(kind="image", argv=(...,), svg_path=Path(...))``

    失敗 / 未インストール時:
        ``MermaidRender(kind="ascii", ascii_text="...")``
    """
    resolved_mmdc = mmdc_path if mmdc_path else (shutil.which("mmdc") or None)
    resolved_tool = image_tool if image_tool is not None else find_image_tool()

    if not resolved_mmdc or resolved_tool is None:
        return MermaidRender(kind="ascii", ascii_text=ascii_fallback(source))

    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / "diagram.svg"
    rendered = render_mermaid_to_svg(
        source, svg_path, mmdc_path=resolved_mmdc, runner=runner
    )
    if rendered is None:
        return MermaidRender(kind="ascii", ascii_text=ascii_fallback(source))

    argv = tuple(resolved_tool.build_argv(path=str(rendered)))
    return MermaidRender(
        kind="image",
        argv=argv,
        svg_path=rendered,
        image_tool=resolved_tool,
    )


__all__ = [
    "MermaidRender",
    "ascii_fallback",
    "available_tools",  # re-exported for monkeypatch convenience in tests
    "find_image_tool",
    "mmdc_available",
    "render_mermaid",
    "render_mermaid_to_svg",
    "shutil",  # re-exported for monkeypatch convenience in tests
]
