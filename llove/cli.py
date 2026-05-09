"""llove CLI — commands the user types in a shell.

Subcommands:
    llove demo                  — synthetic full-feature demo
    llove tail FILE             — tail a JSON Lines file
    llove view --source URI     — open a live view of a data source
    llove export --source URI   — write a single-file HTML snapshot
    llove version               — print version
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from llove import __version__


@click.group(help="💗 llove — terminal Artifact for LLMesh data")
@click.version_option(version=__version__, prog_name="llove")
def main() -> None:  # pragma: no cover — Click dispatch
    pass


@main.command(help="Run the synthetic 30-second demo (works offline).")
@click.option(
    "--seed",
    type=int,
    default=42,
    show_default=True,
    help="Random seed; pass 0 for non-deterministic.",
)
@click.option("--tick", type=float, default=0.1, show_default=True, help="Seconds between events.")
def demo(seed: int, tick: float) -> None:
    from llove.app import LoveApp
    from llove.sources.mock import MockSource

    source = MockSource(seed=seed if seed != 0 else None, tick_seconds=tick)
    LoveApp(source).run()


@main.command(help="Tail a JSON Lines file as a live event stream.")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--follow/--no-follow", default=True, show_default=True, help="Tail-F mode.")
def tail(path: Path, follow: bool) -> None:
    from llove.app import LoveApp
    from llove.sources.jsonl import JSONLSource

    source = JSONLSource(path, follow=follow)
    LoveApp(source).run()


@main.command(help="Print version and exit.")
def version() -> None:
    click.echo(__version__)


@main.command(name="export", help="Render a snapshot to a single HTML file.")
@click.option("--source", required=True, help="Source URI, e.g. mock://demo or jsonl:///path.jsonl")
@click.option("--html", "html_path", required=True, type=click.Path(path_type=Path))
@click.option("--duration", type=float, default=5.0, show_default=True, help="Seconds to capture.")
def export(source: str, html_path: Path, duration: float) -> None:
    from llove.export.html import export_html

    try:
        export_html(source_uri=source, output_path=html_path, duration_s=duration)
    except Exception as exc:
        click.echo(f"export failed: {exc}", err=True)
        sys.exit(1)
    click.echo(f"wrote {html_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
