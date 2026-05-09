"""URI ルーティング — `image://path` / `pdf://path` / `mesh://path` / `web://url` / `geo://lat,lon` / `csv://path` / `code://path`.

llove のあらゆる「何を見せるか」を 1 本の URI で表現するための薄い解析層。
`parse_uri("image:///abs/path/to/cat.png")` は ``URIRef(scheme="image",
path="/abs/path/to/cat.png", ...)`` を返す。

設計の柱として大事な点:

- **拡張子による自動 scheme 推論** — 裸のパス ``"foo.png"`` を渡しても
  ``image:///foo.png`` と同等に扱える。F15 (l) の URI ルーティングが
  「ユーザがいちいち scheme を打たなくても良い」を満たす。
- **多形式対応** (F15 (q)(iii)) — 拡張子から scheme への map を一箇所
  (``_EXT_TO_SCHEME``) に集約。新形式追加はこの dict に 1 行足すだけ。
- **fail-closed** — 未知の scheme は ``URIRef(scheme="unknown", ...)``
  を返し、呼び出し側は ``resolve_renderer`` で「対応 viewer なし」案内
  に降りる。例外は投げない (UI が落ちると体験を壊す)。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


# 拡張子 → URI scheme の主索引。F15 (q)(iii) の「多形式対応」を 1 個所
# にまとめておくと、新しい形式を追加するときに viewer 側に手を入れずに
# 済む (まずは scheme を返すだけでよい)。
_EXT_TO_SCHEME: dict[str, str] = {
    # 2D ラスター画像
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".webp": "image", ".bmp": "image", ".ico": "image",
    ".tif": "image", ".tiff": "image",
    ".heic": "image", ".heif": "image",
    # 2D ベクター
    ".svg": "image",
    # RAW (将来 rawpy)
    ".cr2": "image", ".nef": "image", ".arw": "image", ".raf": "image",
    # 医療画像
    ".dcm": "image", ".dicom": "image",
    # PDF
    ".pdf": "pdf",
    # 3D メッシュ
    ".obj": "mesh", ".stl": "mesh", ".ply": "mesh", ".gltf": "mesh",
    ".glb": "mesh", ".fbx": "mesh", ".dae": "mesh", ".3mf": "mesh",
    ".usd": "mesh", ".usdz": "mesh",
    # 点群
    ".pcd": "pointcloud", ".las": "pointcloud", ".laz": "pointcloud",
    ".xyz": "pointcloud",
    # 動画
    ".mp4": "video", ".mkv": "video", ".webm": "video", ".avi": "video",
    ".mov": "video",
    # 音声
    ".wav": "audio", ".mp3": "audio", ".flac": "audio", ".ogg": "audio",
    ".m4a": "audio",
    # 表 / 構造化データ
    ".csv": "csv", ".tsv": "csv",
    ".json": "json", ".jsonl": "json", ".ndjson": "json",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml",
    ".sqlite": "sql", ".db": "sql",
    # HTML / Markdown
    ".html": "web", ".htm": "web",
    ".md": "markdown", ".markdown": "markdown",
    # コード (シンタックスハイライト)
    ".py": "code", ".js": "code", ".ts": "code", ".rs": "code",
    ".go": "code", ".c": "code", ".cpp": "code", ".h": "code",
    ".hpp": "code", ".java": "code", ".rb": "code", ".sh": "code",
    ".sql": "code",
}


_KNOWN_SCHEMES = frozenset({
    "image", "pdf", "mesh", "pointcloud", "video", "audio",
    "csv", "json", "yaml", "toml", "sql",
    "web", "markdown", "code",
    "geo",  # geo://lat,lon[,zoom]
    "qr",   # qr://text
})


@dataclass(frozen=True)
class URIRef:
    """正規化された URI リファレンス.

    Fields
    ------
    scheme
        ``"image"`` / ``"pdf"`` / ``"mesh"`` / ``"web"`` / ``"geo"`` / ...
        ``"unknown"`` は「未対応の scheme」を表す sentinel — 呼び出し側は
        ``resolve_renderer`` でフォールバックに降りる。
    path
        ファイルパス (絶対化されている)。``web`` / ``geo`` / ``qr`` のような
        non-file scheme では ``""``。
    target
        ``web``: URL / ``geo``: ``"lat,lon[,zoom]"`` / ``qr``: 元テキスト
        など、scheme 固有のペイロード。``image`` 系では ``str(path)``。
    raw
        元の入力文字列 (デバッグ / 監査用)。
    """

    scheme: str
    path: str
    target: str
    raw: str

    @property
    def is_file(self) -> bool:
        """``image`` / ``pdf`` / ``mesh`` 等の **ローカルファイル参照** か？"""
        return self.scheme not in ("web", "geo", "qr", "unknown") and bool(self.path)


def parse_uri(s: str) -> URIRef:
    """``s`` を ``URIRef`` に正規化する.

    - ``"foo.png"``                     → ``URIRef("image", "/abs/foo.png", ...)``
    - ``"image:///abs/foo.png"``        → 同上
    - ``"web://https://example.com"``  → ``URIRef("web", "", "https://example.com", ...)``
    - ``"geo://35.68,139.76"``         → ``URIRef("geo", "", "35.68,139.76", ...)``
    - ``"unknown://wat"``              → ``URIRef("unknown", "", "wat", ...)``
    """
    raw = s

    # ① scheme:// 付き?
    if "://" in s:
        head, _, tail = s.partition("://")
        scheme = head.lower()
        if scheme in _KNOWN_SCHEMES:
            if scheme in ("web", "geo", "qr"):
                # non-file scheme — ペイロードは tail そのまま
                return URIRef(scheme=scheme, path="", target=tail, raw=raw)
            # file scheme — tail はパス
            path = unquote(tail)
            # ``image:///abs/foo.png`` のように 3 連スラッシュで始まる場合
            # tail の先頭スラッシュは保持。
            return URIRef(scheme=scheme, path=path, target=path, raw=raw)
        # 未知 scheme
        return URIRef(scheme="unknown", path="", target=tail, raw=raw)

    # ② 裸のパス? — 拡張子から scheme を推論
    p = Path(s)
    suffix = p.suffix.lower()
    inferred = _EXT_TO_SCHEME.get(suffix)
    if inferred is None:
        return URIRef(scheme="unknown", path=str(p), target=str(p), raw=raw)
    return URIRef(scheme=inferred, path=str(p), target=str(p), raw=raw)


def parsed_url(uri: URIRef) -> str:
    """``web`` scheme のときに ``urlparse`` 互換の URL を取り出す."""
    if uri.scheme != "web":
        return ""
    parsed = urlparse(uri.target)
    if not parsed.scheme:
        # target が ``example.com/x`` のように scheme 抜きならデフォルト https
        return "https://" + uri.target
    return uri.target
