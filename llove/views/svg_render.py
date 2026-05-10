"""F15 (t2) — SVG → PNG → ターミナル画像チェイン.

`mermaid_render.py` と並行する構造の薄い shim:

    SVG XML
       │  (1) rsvg-convert -o output.png input.svg
       ▼
    PNG file
       │  (2) chafa / viu / timg / kitty +kitten icat / wezterm imgcat
       ▼
    ターミナル画像

両ツールが揃わないか subprocess が失敗した場合は、ASCII フォール
バック (マーカー文字列) に降りる。MarkdownView や DiagramPane は結果
(``SVGRender``) を見て分岐するだけで良い (mermaid_render と統一)。

セキュリティ:
- subprocess は **list-based 引数のみ** (shell=True 禁止)
- ``-o output.png input.svg`` で path はテンプレ解釈なしで直接渡る
- 入力 SVG XML はテンポラリ ``.svg`` ファイルに書き出してから読ませる
  (引数経由の長文 XML 流入を避ける)

Pure 関数 + 依存性注入で書いてあるので、rsvg-convert / 画像ツール未
インストールの CI でもフルテスト可能 (mermaid_render と同じ哲学)。
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
class SVGRender:
    """``render_svg`` の戻り値.

    ``kind == "image"`` のとき:
        - ``argv``: そのまま subprocess.run できる引数列 (chafa / viu / ...)
        - ``png_path``: 中間 PNG の実体ファイル (caller がライフサイクルを管理)

    ``kind == "ascii"`` のとき:
        - ``ascii_text``: ターミナルにそのまま流せる文字列 (マーカー付き)
        - ``argv`` は空、``png_path`` は ``None``
    """

    kind: Literal["image", "ascii"]
    argv: tuple[str, ...] = ()
    png_path: Path | None = None
    ascii_text: str = ""
    image_tool: ExternalTool | None = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# 検出
# ---------------------------------------------------------------------------


def rsvg_convert_available() -> bool:
    """``rsvg-convert`` バイナリが PATH 上に存在するかを返す."""
    return shutil.which("rsvg-convert") is not None


def find_image_tool() -> ExternalTool | None:
    """画像 scheme で利用可能な最優先ツールを返す (mermaid_render と共有方針)."""
    tools = available_tools("image")
    return tools[0] if tools else None


# ---------------------------------------------------------------------------
# rsvg-convert 呼び出し
# ---------------------------------------------------------------------------

Runner = Callable[[list[str]], int]


def _default_runner(argv: list[str]) -> int:
    """``subprocess.run`` のデフォルト実装. 失敗時は非ゼロを返す."""
    try:
        proc = subprocess.run(  # nosec B603 — argv is fully controlled.
            argv,
            check=False,
            capture_output=True,
            timeout=30,
        )
        return proc.returncode
    except (OSError, subprocess.SubprocessError):
        # 呼び出し側で None に降りるようシグナル
        raise


def render_svg_to_png(
    source: str,
    output: Path,
    *,
    rsvg_path: str | None = None,
    runner: Runner | None = None,
) -> Path | None:
    """SVG XML を rsvg-convert で PNG に変換し、出力 Path を返す.

    Parameters
    ----------
    source
        SVG XML 文字列。
    output
        PNG 出力先 Path。親ディレクトリは存在前提 (caller 側で確保)。
    rsvg_path
        ``rsvg-convert`` 実行ファイルへの絶対パス。``None`` なら即座に失敗
        (=描画不能なので argv を作らない)。
    runner
        テスト差し替え用の subprocess shim。``None`` なら ``_default_runner``。

    Returns
    -------
    出力 PNG の Path、または失敗時 ``None``。
    """
    if not rsvg_path:
        return None
    run = runner or _default_runner

    # rsvg-convert は stdin SVG も受け付けるが、テスト容易性 / 一貫性のため
    # mermaid_render と同様に temp ``.svg`` 経由にする。出力 PNG と同じ
    # ディレクトリに置けば caller が tmpdir を 1 つ管理するだけで済む。
    src_path = output.with_suffix(".svg")
    try:
        src_path.write_text(source, encoding="utf-8")
    except OSError:
        return None

    argv = [rsvg_path, "-o", str(output), str(src_path)]
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


_FALLBACK_HEADER = "◇ svg (ASCII fallback — install rsvg-convert + chafa for image render)"
_FALLBACK_RULE = "─" * 60
_EXCERPT_MAX = 240  # XML 全文を流すと大爆発する → 先頭 240 文字に切る


def ascii_fallback_for_svg(source: str) -> str:
    """画像レンダ不能時に表示する ASCII ブロック.

    SVG は人間可読な DSL ではないので XML 全文ではなく **先頭の抜粋** を
    出す。これでも「何の SVG か (root tag や属性) 」は分かる。
    """
    src = source if isinstance(source, str) else ""
    excerpt = src.strip()[:_EXCERPT_MAX]
    if len(src.strip()) > _EXCERPT_MAX:
        excerpt = excerpt + " ..."
    if not excerpt:
        excerpt = "(empty svg source)"
    return f"{_FALLBACK_HEADER}\n{_FALLBACK_RULE}\n{excerpt}\n{_FALLBACK_RULE}\n"


# ---------------------------------------------------------------------------
# 高レベル統合
# ---------------------------------------------------------------------------


def render_svg(
    source: str,
    *,
    output_dir: Path,
    rsvg_path: str | None = None,
    image_tool: ExternalTool | None = None,
    runner: Runner | None = None,
) -> SVGRender:
    """source を可能な限りターミナル画像化し、不可なら ASCII で返す.

    引数を省略した場合は ``rsvg_convert_available`` / ``find_image_tool`` で
    自動検出する。テストや明示的な切替が必要なときだけ引数を埋める。

    成功時:
        ``SVGRender(kind="image", argv=(...,), png_path=Path(...))``

    失敗 / 未インストール時:
        ``SVGRender(kind="ascii", ascii_text="...")``
    """
    resolved_rsvg = (
        rsvg_path if rsvg_path else (shutil.which("rsvg-convert") or None)
    )
    resolved_tool = image_tool if image_tool is not None else find_image_tool()

    if not resolved_rsvg or resolved_tool is None:
        return SVGRender(kind="ascii", ascii_text=ascii_fallback_for_svg(source))

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "diagram.png"
    rendered = render_svg_to_png(
        source, png_path, rsvg_path=resolved_rsvg, runner=runner
    )
    if rendered is None:
        return SVGRender(kind="ascii", ascii_text=ascii_fallback_for_svg(source))

    argv = tuple(resolved_tool.build_argv(path=str(rendered)))
    return SVGRender(
        kind="image",
        argv=argv,
        png_path=rendered,
        image_tool=resolved_tool,
    )


__all__ = [
    "SVGRender",
    "ascii_fallback_for_svg",
    "available_tools",  # re-exported for monkeypatch convenience in tests
    "find_image_tool",
    "render_svg",
    "render_svg_to_png",
    "rsvg_convert_available",
    "shutil",  # re-exported for monkeypatch convenience in tests
]
