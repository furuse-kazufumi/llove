"""F15 (t2/t3) — PlantUML → SVG → ターミナル画像チェイン.

`mermaid_render.py` / `svg_render.py` と並行する構造の薄い shim:

    PlantUML source
       │  (1) plantuml -tsvg input.puml  (出力は同じディレクトリの input.svg)
       ▼
    SVG file
       │  (2) chafa / viu / timg / kitty +kitten icat / wezterm imgcat
       ▼
    ターミナル画像

両ツールが揃わないか subprocess が失敗した場合は、ASCII フォールバックに
降りる。``MarkdownView`` の ``diagram_renderers={"plantuml": render_plantuml}``
に登録すれば、`folding.find_code_block_regions` が ``kind="plantuml"`` を
返した時点で自動展開される。

セキュリティ:
- subprocess は **list-based 引数のみ** (shell=True 禁止)
- 入力 PlantUML source はテンポラリ ``.puml`` ファイルに書き出してから
  読ませる (引数経由の長文流入を避ける、mermaid_render と同じ哲学)。

Pure 関数 + 依存性注入で書いてあるので、plantuml / 画像ツール未インストール
の CI でもフルテスト可能。
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
class PlantUMLRender:
    """``render_plantuml`` の戻り値.

    ``MermaidRender`` / ``SVGRender`` と同じ ``DiagramRenderResult`` shape
    (``kind`` / ``argv`` / ``ascii_text``) を満たす。MarkdownView の
    ``ImageRenderPane`` にそのまま流せる。
    """

    kind: Literal["image", "ascii"]
    argv: tuple[str, ...] = ()
    svg_path: Path | None = None
    ascii_text: str = ""
    image_tool: ExternalTool | None = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# 検出
# ---------------------------------------------------------------------------


def plantuml_available() -> bool:
    """``plantuml`` バイナリが PATH 上に存在するかを返す."""
    return shutil.which("plantuml") is not None


def find_image_tool() -> ExternalTool | None:
    """画像 scheme で利用可能な最優先ツールを返す (mermaid_render と共有方針)."""
    tools = available_tools("image")
    return tools[0] if tools else None


# ---------------------------------------------------------------------------
# plantuml 呼び出し
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


def render_plantuml_to_svg(
    source: str,
    output: Path,
    *,
    plantuml_path: str | None = None,
    runner: Runner | None = None,
) -> Path | None:
    """PlantUML source を plantuml で SVG に変換し、出力 Path を返す.

    plantuml CLI は ``-tsvg input.puml`` で **同じディレクトリに input.svg
    を作る** (mmdc のように ``-o`` で出力ファイル名を指定できない)。
    そのため caller が望む output (例: ``foo.svg``) と一致させるため、
    入力 ``.puml`` のステムを output のステムに合わせて書き出す。

    Parameters
    ----------
    source
        PlantUML DSL 文字列 (``@startuml`` 〜 ``@enduml`` の中身でも全体でも可)。
    output
        SVG 出力先 Path。親ディレクトリは存在前提 (caller 側で確保)。
        ステムが ``foo`` なら ``foo.puml`` を一時的に書き出し、plantuml が
        同名 ``foo.svg`` を生成する。
    plantuml_path
        ``plantuml`` 実行ファイルへの絶対パス。``None`` なら即座に失敗。
    runner
        テスト差し替え用の subprocess shim. ``None`` なら ``_default_runner``。

    Returns
    -------
    出力 SVG の Path、または失敗時 ``None``。
    """
    if not plantuml_path:
        return None
    run = runner or _default_runner

    src_path = output.with_suffix(".puml")
    try:
        src_path.write_text(source, encoding="utf-8")
    except OSError:
        return None

    argv = [plantuml_path, "-tsvg", str(src_path)]
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
    "◇ plantuml (ASCII fallback — install plantuml + chafa for image render)"
)
_FALLBACK_RULE = "─" * 60


def ascii_fallback(source: str) -> str:
    """画像レンダ不能時に表示する ASCII ブロック.

    PlantUML DSL は人間可読 (mermaid 同様) なので、source 全体を罫線で
    囲んでそのまま出す。MarkdownView などはこの文字列を fence の代わりに
    貼り付ける想定。
    """
    body = source.rstrip() if isinstance(source, str) else ""
    return f"{_FALLBACK_HEADER}\n{_FALLBACK_RULE}\n{body}\n{_FALLBACK_RULE}\n"


# ---------------------------------------------------------------------------
# 高レベル統合
# ---------------------------------------------------------------------------


def render_plantuml(
    source: str,
    *,
    output_dir: Path,
    plantuml_path: str | None = None,
    image_tool: ExternalTool | None = None,
    runner: Runner | None = None,
) -> PlantUMLRender:
    """source を可能な限りターミナル画像化し、不可なら ASCII で返す.

    引数を省略した場合は ``plantuml_available`` / ``find_image_tool`` で
    自動検出する。テストや明示的な切替が必要なときだけ引数を埋める。

    成功時:
        ``PlantUMLRender(kind="image", argv=(...,), svg_path=Path(...))``

    失敗 / 未インストール時:
        ``PlantUMLRender(kind="ascii", ascii_text="...")``
    """
    resolved_pu = (
        plantuml_path if plantuml_path else (shutil.which("plantuml") or None)
    )
    resolved_tool = image_tool if image_tool is not None else find_image_tool()

    if not resolved_pu or resolved_tool is None:
        return PlantUMLRender(kind="ascii", ascii_text=ascii_fallback(source))

    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / "diagram.svg"
    rendered = render_plantuml_to_svg(
        source, svg_path, plantuml_path=resolved_pu, runner=runner
    )
    if rendered is None:
        return PlantUMLRender(kind="ascii", ascii_text=ascii_fallback(source))

    argv = tuple(resolved_tool.build_argv(path=str(rendered)))
    return PlantUMLRender(
        kind="image",
        argv=argv,
        svg_path=rendered,
        image_tool=resolved_tool,
    )


__all__ = [
    "PlantUMLRender",
    "ascii_fallback",
    "available_tools",  # re-exported for monkeypatch convenience in tests
    "find_image_tool",
    "plantuml_available",
    "render_plantuml",
    "render_plantuml_to_svg",
    "shutil",  # re-exported for monkeypatch convenience in tests
]
