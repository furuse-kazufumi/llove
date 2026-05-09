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
from llove.i18n import available_locales, set_locale


@click.group(help="💗 llove — terminal Artifact for LLMesh data")
@click.version_option(version=__version__, prog_name="llove")
@click.option(
    "--lang",
    type=click.Choice(available_locales(), case_sensitive=False),
    default=None,
    help="UI language (defaults to LLOVE_LANG env or system locale; falls back to 'en').",
)
def main(lang: str | None) -> None:  # pragma: no cover — Click dispatch
    if lang:
        set_locale(lang)


@main.command(help="Run an interactive demo (works offline).")
@click.option(
    "--seed",
    type=int,
    default=42,
    show_default=True,
    help="Random seed; pass 0 for non-deterministic.",
)
@click.option("--tick", type=float, default=0.1, show_default=True, help="Seconds between events.")
@click.option(
    "--scenario",
    "scenario_name",
    default=None,
    help="Scenario name (run with --list to see options). Omit to pick interactively.",
)
@click.option("--list", "list_only", is_flag=True, help="List available scenarios and exit.")
@click.option(
    "--log",
    "log_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Append every event as one JSON line to this file. The result is "
    "replayable with `llove tail`, and for `--scenario shogi` it gives you a "
    "full game record (kifu + eval + commentary) without watching the run live.",
)
def demo(
    seed: int,
    tick: float,
    scenario_name: str | None,
    list_only: bool,
    log_path: Path | None,
) -> None:
    from datetime import UTC, datetime

    from llove.app import LoveApp
    from llove.demo.scenarios import SCENARIOS, get_scenario
    from llove.sources.mock import MockSource

    if list_only:
        click.echo("Available scenarios:")
        for key, cls in SCENARIOS.items():
            instance = cls()
            click.echo(f"  {key:12}  {instance.title}")
            click.echo(f"  {'':12}  {instance.description}")
        click.echo("\nRun: llove demo --scenario <name>")
        return

    if scenario_name is None:
        # No scenario chosen — run the original mixed-stream demo.
        source = MockSource(seed=seed if seed != 0 else None, tick_seconds=tick)
        LoveApp(source, log_path=log_path).run()
        return

    # For scenarios that produce a record worth keeping (e.g. a shogi game
    # log = kifu), write a JSONL by default into out/<scenario>/<timestamp>
    # so users don't have to remember --log every run. Explicit --log still
    # wins.
    auto_log_scenarios = {"shogi"}
    if log_path is None and scenario_name in auto_log_scenarios:
        ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        log_path = Path("out") / scenario_name / f"{scenario_name}-{ts}.jsonl"
        click.echo(f"Logging this run to {log_path}", err=True)

    try:
        scenario = get_scenario(scenario_name)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)
    LoveApp(scenario, with_narration=True, log_path=log_path).run()


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
