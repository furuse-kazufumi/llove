"""F15 (t2/t3) — Graphviz dot → SVG → ターミナル画像チェイン.

`mermaid_render.py` / `svg_render.py` / `plantuml_render.py` と並行する
構造の薄い shim:

    dot source
       │  (1) dot -Tsvg -o output.svg input.dot
       ▼
    SVG file
       │  (2) chafa / viu / timg / kitty +kitten icat / wezterm imgcat
       ▼
    ターミナル画像

両ツールが揃わないか subprocess が失敗した場合は、ASCII フォールバックに
降りる。``MarkdownView`` の ``diagram_renderers={"dot": render_dot}`` に
登録すれば、`folding.find_code_block_regions` が ``kind="dot"`` を返した
時点で自動展開される。

dot CLI は ``-Tsvg -o output.svg input.dot`` のように **出力ファイル名を
直接指定できる** (mmdc に近い、plantuml は不可)。そのため src_path だけ
合わせれば output 名は自由に指定できる。

セキュリティ:
- subprocess は **list-based 引数のみ** (shell=True 禁止)
- 入力 dot source はテンポラリ ``.dot`` ファイルに書き出してから読ませる
  (引数経由の長文流入を避ける)

Pure 関数 + 依存性注入で書いてあるので、dot / 画像ツール未インストールの
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
class DotRender:
    """``render_dot`` の戻り値.

    `MermaidRender` / `SVGRender` / `PlantUMLRender` と同じ
    ``DiagramRenderResult`` shape (``kind`` / ``argv`` / ``ascii_text``)
    を満たす。MarkdownView の `ImageRenderPane` にそのまま流せる。
    """

    kind: Literal["image", "ascii"]
    argv: tuple[str, ...] = ()
    svg_path: Path | None = None
    ascii_text: str = ""
    image_tool: ExternalTool | None = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# 検出
# ---------------------------------------------------------------------------


def dot_available() -> bool:
    """``dot`` バイナリが PATH 上に存在するかを返す."""
    return shutil.which("dot") is not None


def find_image_tool() -> ExternalTool | None:
    """画像 scheme で利用可能な最優先ツールを返す (mermaid_render と共有方針)."""
    tools = available_tools("image")
    return tools[0] if tools else None


# ---------------------------------------------------------------------------
# dot 呼び出し
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
        raise


def render_dot_to_svg(
    source: str,
    output: Path,
    *,
    dot_path: str | None = None,
    runner: Runner | None = None,
) -> Path | None:
    """Graphviz dot source を dot で SVG に変換し、出力 Path を返す.

    dot CLI は ``-Tsvg -o output.svg input.dot`` のように出力ファイル名を
    直接指定できる (mmdc と同じ流儀)。caller は output Path を自由に決められる。

    Parameters
    ----------
    source
        Graphviz DOT 文字列 (``digraph G { ... }`` 等)。
    output
        SVG 出力先 Path。親ディレクトリは存在前提 (caller 側で確保)。
    dot_path
        ``dot`` 実行ファイルへの絶対パス。``None`` なら即座に失敗。
    runner
        テスト差し替え用の subprocess shim. ``None`` なら ``_default_runner``。

    Returns
    -------
    出力 SVG の Path、または失敗時 ``None``。
    """
    if not dot_path:
        return None
    run = runner or _default_runner

    src_path = output.with_suffix(".dot")
    try:
        src_path.write_text(source, encoding="utf-8")
    except OSError:
        return None

    argv = [dot_path, "-Tsvg", "-o", str(output), str(src_path)]
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


_FALLBACK_HEADER = (
    "◇ dot (ASCII fallback — install graphviz + chafa for image render)"
)
_FALLBACK_RULE = "─" * 60


def ascii_fallback(source: str) -> str:
    """画像レンダ不能時に表示する ASCII ブロック.

    DOT 言語は人間可読 (mermaid / plantuml 同様) なので、source 全体を
    罫線で囲んでそのまま出す。
    """
    body = source.rstrip() if isinstance(source, str) else ""
    return f"{_FALLBACK_HEADER}\n{_FALLBACK_RULE}\n{body}\n{_FALLBACK_RULE}\n"


# ---------------------------------------------------------------------------
# 高レベル統合
# ---------------------------------------------------------------------------


def render_dot(
    source: str,
    *,
    output_dir: Path,
    dot_path: str | None = None,
    image_tool: ExternalTool | None = None,
    runner: Runner | None = None,
) -> DotRender:
    """source を可能な限りターミナル画像化し、不可なら ASCII で返す.

    引数を省略した場合は ``dot_available`` / ``find_image_tool`` で自動検出。
    テストや明示的な切替が必要なときだけ引数を埋める。

    成功時:
        ``DotRender(kind="image", argv=(...,), svg_path=Path(...))``

    失敗 / 未インストール時:
        ``DotRender(kind="ascii", ascii_text="...")``
    """
    resolved_dot = dot_path if dot_path else (shutil.which("dot") or None)
    resolved_tool = image_tool if image_tool is not None else find_image_tool()

    if not resolved_dot or resolved_tool is None:
        return DotRender(kind="ascii", ascii_text=ascii_fallback(source))

    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / "diagram.svg"
    rendered = render_dot_to_svg(
        source, svg_path, dot_path=resolved_dot, runner=runner
    )
    if rendered is None:
        return DotRender(kind="ascii", ascii_text=ascii_fallback(source))

    argv = tuple(resolved_tool.build_argv(path=str(rendered)))
    return DotRender(
        kind="image",
        argv=argv,
        svg_path=rendered,
        image_tool=resolved_tool,
    )


__all__ = [
    "DotRender",
    "ascii_fallback",
    "available_tools",  # re-exported for monkeypatch convenience in tests
    "dot_available",
    "find_image_tool",
    "render_dot",
    "render_dot_to_svg",
    "shutil",  # re-exported for monkeypatch convenience in tests
]
