"""Single-file HTML snapshot exporter.

The v0.1 implementation renders a recent slice of events as a static HTML page
inspired by Claude HTML Artifacts:
    - one self-contained file (no CDN, no external assets)
    - inline CSS and minimal JS for Replay slider
    - read-only

We deliberately keep this independent of Textual's experimental web mode so the
output is robust even when running in a headless CI.
"""

from __future__ import annotations

import asyncio
import html as _html
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from llove.events import Event, EventKind
from llove.sources.base import DataSource
from llove.sources.jsonl import JSONLSource
from llove.sources.mock import MockSource


def export_html(*, source_uri: str, output_path: Path, duration_s: float = 5.0) -> Path:
    """Build a snapshot HTML file from ``duration_s`` seconds of ``source_uri``.

    Returns the path written.
    """
    source = _build_source(source_uri)
    events = asyncio.run(_collect(source, duration_s))
    output_path.write_text(_render(source_uri, events), encoding="utf-8")
    return output_path


def _build_source(uri: str) -> DataSource:
    """Build a DataSource from a URI *or* a plain local path.

    Robust to several forms that the naive ``urlparse(uri).path`` mishandles:
      - ``mock://...`` or empty string → synthetic :class:`MockSource`.
      - ``jsonl://`` / ``file://`` URIs, including Windows drive letters that
        ``urlparse`` leaves with a spurious leading slash (``jsonl:///D:/x`` →
        path ``/D:/x``).
      - plain local paths that are *not* valid URIs: ``D:\\x.jsonl`` /
        ``D:/x.jsonl`` (a single-letter drive that ``urlparse`` reads as a
        ``scheme``), ``/home/x.jsonl``, ``out/x.jsonl``.

    Fail-closed: an unknown scheme raises ``ValueError`` and a missing JSONL
    file raises ``FileNotFoundError`` (so a bad path surfaces an error instead of
    silently producing an empty snapshot).
    """
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()

    # 1) explicit mock or empty → synthetic source (backward compatible).
    if scheme == "mock" or uri == "":
        return MockSource()

    # 2) jsonl:// / file:// → normalise to a local filesystem path.
    if scheme in {"jsonl", "file"}:
        return _jsonl_source_or_raise(_uri_to_local_path(uri))

    # 3) plain local path: no scheme, or a single-letter "scheme" that is really
    #    a Windows drive letter (urlparse reads 'D:/x' as scheme='d').
    if scheme == "" or _looks_like_windows_path(uri):
        return _jsonl_source_or_raise(Path(uri))

    raise ValueError(
        f"unsupported source scheme: {scheme!r} "
        "(use 'mock://', 'jsonl:///<path>', 'file://<path>', or a plain local path)"
    )


def _looks_like_windows_path(s: str) -> bool:
    """True for ``D:\\x`` / ``D:/x`` — a Windows drive letter, not a URI scheme."""
    return bool(re.match(r"^[A-Za-z]:[\\/]", s))


def _uri_to_local_path(uri: str) -> Path:
    """Local ``Path`` from a ``jsonl://`` / ``file://`` URI, tolerant of Windows drives."""
    parsed = urlparse(uri)
    path = unquote(parsed.path)
    # 'file://D:/x' can put the drive in netloc (e.g. netloc='D:'); recombine.
    if re.match(r"^[A-Za-z]:$", parsed.netloc):
        path = parsed.netloc + path
    # 'jsonl:///D:/x' → urlparse path '/D:/x'; strip the spurious leading slash.
    if re.match(r"^/[A-Za-z]:", path):
        path = path[1:]
    return Path(path)


def _jsonl_source_or_raise(path: Path) -> JSONLSource:
    """JSONLSource for an existing file; fail-closed (明示エラー) if it is missing."""
    if not path.exists():
        raise FileNotFoundError(f"source file not found: {path}")
    return JSONLSource(path)


async def _collect(source: DataSource, duration_s: float) -> list[Event]:
    out: list[Event] = []

    async def runner() -> None:
        async for ev in source.stream():
            out.append(ev)

    try:
        await asyncio.wait_for(runner(), timeout=duration_s)
    except TimeoutError:
        pass
    finally:
        await source.close()
    return out


def _render(source_uri: str, events: list[Event]) -> str:
    rows = []
    for ev in events[-200:]:
        css = f"k-{ev.kind.value}"
        ts = ev.ts.strftime("%H:%M:%S")
        rows.append(
            f'<tr class="{css}"><td>{ts}</td><td>{ev.kind.value}</td>'
            f"<td>{_html.escape(_pretty(ev))}</td></tr>"
        )
    by_kind = {k.value: 0 for k in EventKind}
    for ev in events:
        by_kind[ev.kind.value] += 1
    summary = " · ".join(f"{k}:{n}" for k, n in by_kind.items() if n)
    title = f"llove snapshot ({source_uri})"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return _PAGE.format(
        title=_html.escape(title),
        rows="\n".join(rows) or "<tr><td colspan=3>(no events)</td></tr>",
        summary=_html.escape(summary or "no events"),
        generated=generated,
        count=len(events),
    )


def _pretty(ev: Event) -> str:
    if ev.kind == EventKind.SENSOR:
        sid = ev.payload.get("sensor_id", "?")
        val = ev.payload.get("value", "?")
        q = ev.payload.get("quality", "")
        return f"{sid} = {val} ({q})"
    if ev.kind == EventKind.SPC_ALARM:
        sid = ev.payload.get("sensor_id", "?")
        cu = ev.payload.get("cusum", "?")
        return f"ALARM {sid}  cusum={cu}"
    return ", ".join(f"{k}={v}" for k, v in ev.payload.items())


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
          background: #0e1116; color: #e6edf3; margin: 0; padding: 24px; }}
  h1 {{ font-size: 18px; margin: 0 0 8px 0; }}
  .meta {{ color: #8b949e; font-size: 12px; margin-bottom: 16px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  td {{ padding: 4px 8px; border-bottom: 1px solid #21262d; vertical-align: top; }}
  tr.k-sensor td:nth-child(2) {{ color: #79c0ff; }}
  tr.k-spc_alarm td {{ color: #ff7b72; }}
  tr.k-audit td:nth-child(2) {{ color: #a5d6ff; }}
  tr.k-llm_call td:nth-child(2) {{ color: #d2a8ff; }}
  footer {{ color: #6e7681; font-size: 11px; margin-top: 24px; }}
</style>
</head>
<body>
  <h1>💗 llove snapshot — {title}</h1>
  <div class="meta">{count} events · {summary} · generated {generated}</div>
  <table>
    <thead><tr><td>time</td><td>kind</td><td>detail</td></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  <footer>Made with <a style="color:#ff7b72" href="https://github.com/furuse-kazufumi/llove">llove</a>.</footer>
</body>
</html>
"""
