"""外部 CLI ツールカタログ — F15(o) 「外部ツール subprocess 呼び出し OK」方針.

llove は薄い shim に徹し、画像 / PDF / HTML / 動画などの実描画は既存の
高品質 OSS CLI ツール (chafa / viu / pdftoppm / mpv / w3m / gnuplot ...)
に任せる。このモジュールは「どの scheme でどのツールが使えるか」の
カタログと、``shutil.which`` での実行時検出だけを担当する。

セキュリティ:

- ``subprocess`` 呼び出しは **list-based 引数のみ** (shell=True 禁止).
- 引数テンプレに渡る ``path`` は呼び出し側で必ず絶対化 + ``shlex.quote``
  しなくても、list 形式なので shell 解釈は介在しない。
- 各ツールに ``--`` 区切りを入れて optional argument 注入を防ぐ.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExternalTool:
    """1 つの外部 CLI ツールの記述子.

    Fields
    ------
    name
        実行ファイル名 (PATH 上で ``shutil.which`` で検索される).
    scheme
        対応する URI scheme (``"image"`` / ``"pdf"`` / ...).
    args_template
        実行時に組み立てる引数テンプレ。``{path}`` プレースホルダを
        フォーマット時に置換する。
    priority
        小さいほど先に試す。同じ scheme で複数ヒット可。
    notes
        ヘルプ表示用の説明。
    install_hint
        未インストール時に Settings モーダルに出す案内 (例:
        ``"apt install chafa"`` / ``"brew install viu"``).
    """

    name: str
    scheme: str
    args_template: list[str]
    priority: int = 100
    notes: str = ""
    install_hint: str = ""

    @property
    def available(self) -> bool:
        return shutil.which(self.name) is not None

    def build_argv(self, *, path: str = "", target: str = "") -> list[str]:
        """テンプレを実引数リストに展開する."""
        argv = [self.name]
        for tok in self.args_template:
            argv.append(tok.format(path=path, target=target))
        return argv


# ---------------------------------------------------------------------------
# カタログ — 新ツールを追加するときはここに 1 行足す
# ---------------------------------------------------------------------------

_CATALOG: list[ExternalTool] = [
    # ---- image -----------------------------------------------------------
    ExternalTool(
        name="chafa", scheme="image",
        args_template=["--", "{path}"], priority=10,
        notes="Sixel / kitty / iTerm2 graphics 自動切替の terminal 画像ビューア (推奨)",
        install_hint="apt install chafa | brew install chafa",
    ),
    ExternalTool(
        name="viu", scheme="image",
        args_template=["--", "{path}"], priority=20,
        notes="Rust 製の terminal 画像ビューア (Sixel / kitty 対応)",
        install_hint="cargo install viu | brew install viu",
    ),
    ExternalTool(
        name="timg", scheme="image",
        args_template=["--", "{path}"], priority=30,
        notes="複数フォーマット対応の terminal 画像 / 動画ビューア",
        install_hint="apt install timg",
    ),
    ExternalTool(
        name="kitty", scheme="image",
        args_template=["+kitten", "icat", "--", "{path}"], priority=40,
        notes="Kitty terminal 標準の画像表示 (kitty graphics protocol)",
        install_hint="kitty terminal を使う",
    ),
    ExternalTool(
        name="wezterm", scheme="image",
        args_template=["imgcat", "{path}"], priority=50,
        notes="WezTerm の imgcat (iTerm2 protocol 互換)",
        install_hint="wezterm terminal を使う",
    ),

    # ---- pdf -------------------------------------------------------------
    ExternalTool(
        name="pdftoppm", scheme="pdf",
        args_template=["-f", "1", "-l", "1", "-png", "--", "{path}", "/tmp/llove-pdf"],
        priority=10,
        notes="poppler の PDF → PNG コンバータ (1 ページ目のみ)",
        install_hint="apt install poppler-utils | brew install poppler",
    ),

    # ---- web / html ------------------------------------------------------
    ExternalTool(
        name="w3m", scheme="web",
        args_template=["-dump", "{target}"], priority=10,
        notes="terminal HTML browser、画像表示拡張あり",
        install_hint="apt install w3m | brew install w3m",
    ),
    ExternalTool(
        name="lynx", scheme="web",
        args_template=["-dump", "{target}"], priority=20,
        notes="テキスト browser",
        install_hint="apt install lynx | brew install lynx",
    ),

    # ---- video -----------------------------------------------------------
    ExternalTool(
        name="mpv", scheme="video",
        args_template=["--vo=tct", "--", "{path}"], priority=10,
        notes="mpv の terminal output ドライバ (color text)",
        install_hint="apt install mpv | brew install mpv",
    ),
    ExternalTool(
        name="ffmpeg", scheme="video",
        args_template=["-i", "{path}", "-frames:v", "1", "/tmp/llove-frame.png"],
        priority=20,
        notes="動画から 1 フレームだけ抜き出して画像レンダラに流す",
        install_hint="apt install ffmpeg | brew install ffmpeg",
    ),

    # ---- code / json -----------------------------------------------------
    ExternalTool(
        name="bat", scheme="code",
        args_template=["--", "{path}"], priority=10,
        notes="シンタックスハイライト付き cat",
        install_hint="apt install bat | brew install bat",
    ),
    ExternalTool(
        name="jq", scheme="json",
        args_template=[".", "{path}"], priority=10,
        notes="JSON 整形",
        install_hint="apt install jq | brew install jq",
    ),

    # ---- qr --------------------------------------------------------------
    ExternalTool(
        name="qrencode", scheme="qr",
        args_template=["-t", "ANSI", "{target}"], priority=10,
        notes="ANSI 出力で QR コード生成",
        install_hint="apt install qrencode",
    ),

    # ---- geo -------------------------------------------------------------
    ExternalTool(
        name="mapscii", scheme="geo",
        args_template=[], priority=10,
        notes="terminal 地図 (interactive、座標は標準入力で渡す系)",
        install_hint="npm install -g mapscii",
    ),

    # ---- chart -----------------------------------------------------------
    ExternalTool(
        name="gnuplot", scheme="chart",
        args_template=["-e", "set term sixel; plot '{path}'"], priority=10,
        notes="Sixel グラフ出力",
        install_hint="apt install gnuplot | brew install gnuplot",
    ),
]


def available_tools(scheme: str) -> list[ExternalTool]:
    """``scheme`` で使える、かつ実際に PATH 上に存在するツールを優先順に返す.

    一覧が空なら呼び出し側は ASCII フォールバック / Qt fallback / 「インストール案内」に
    降りる。
    """
    tools = [t for t in _CATALOG if t.scheme == scheme and t.available]
    return sorted(tools, key=lambda t: t.priority)


def all_catalogued_tools(scheme: str | None = None) -> list[ExternalTool]:
    """カタログ全件 (available 問わず). Settings モーダルで「✗ missing」表示用."""
    if scheme is None:
        return list(_CATALOG)
    return [t for t in _CATALOG if t.scheme == scheme]


def register_tool(tool: ExternalTool) -> None:
    """サードパーティ拡張やテストから新ツールを差し込むための公開 API."""
    _CATALOG.append(tool)


def _registered_for_test_only() -> list[ExternalTool]:  # pragma: no cover
    """テスト用 — register_tool で追加されたエントリを差し戻すための内部 view."""
    return _CATALOG
