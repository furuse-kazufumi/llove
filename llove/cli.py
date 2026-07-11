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


@main.group(help="Run a real LLM-vs-LLM game (shogi today; chess / go / mahjong on the v0.7 roadmap).")
def play() -> None:  # pragma: no cover — Click dispatch
    pass


@play.command(name="shogi", help="Play a real shogi game between two players.")
@click.option(
    "--sente",
    default="mock:script",
    show_default=True,
    help="Sente (first player) provider:model. Examples: mock:script, "
    "mock:illegal, mock:resign. anthropic / ollama land in MVP2b.",
)
@click.option(
    "--gote",
    default="mock:script",
    show_default=True,
    help="Gote (second player) provider:model.",
)
@click.option("--max-ply", type=int, default=400, show_default=True)
@click.option(
    "--log",
    "log_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Append every event as one JSON line to this file (kifu + signed moves).",
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="Skip the TUI; stream JSONL events to stdout. Useful for CI / batch eval.",
)
@click.option(
    "--stream",
    is_flag=True,
    help="In TUI mode, also stream events to stdout. Pair with --log for tee.",
)
def play_shogi(
    sente: str,
    gote: str,
    max_ply: int,
    log_path: Path | None,
    no_tui: bool,
    stream: bool,
) -> None:
    """Drive ``llove.shogi.run_game`` and route events to TUI / stdout / log."""
    import asyncio
    from datetime import UTC, datetime

    try:
        from llove.shogi import make_player, run_game
    except ImportError as exc:
        # python-shogi missing — surface the install hint, not the traceback.
        click.echo(
            f"shogi engine unavailable: {exc}\n"
            "Install: pip install 'llmesh-llove[shogi]'",
            err=True,
        )
        sys.exit(2)

    try:
        sente_p = make_player(sente, side="sente")
        gote_p = make_player(gote, side="gote")
    except (ValueError, NotImplementedError) as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)

    # Auto-log to out/shogi/play-<ts>.jsonl when no explicit --log given,
    # mirroring the demo scenario's auto-log behaviour.
    if log_path is None:
        ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        log_path = Path("out") / "shogi" / f"play-{ts}.jsonl"
        click.echo(f"Logging this game to {log_path}", err=True)

    if no_tui:
        async def _stream() -> None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", encoding="utf-8") as fh:
                async for ev in run_game(sente_p, gote_p, max_ply=max_ply):
                    line = ev.model_dump_json()
                    fh.write(line + "\n")
                    fh.flush()
                    click.echo(line)

        asyncio.run(_stream())
        return

    # TUI mode (default).
    from llove.app import LoveApp
    from llove.shogi.source import ShogiSource

    source = ShogiSource(sente_p, gote_p, max_ply=max_ply, also_stdout=stream)
    LoveApp(source, with_narration=True, log_path=log_path).run()


@play.command(name="chess", help="Play a real chess game between two LLM players.")
@click.option(
    "--white",
    default="ollama:llama3.2",
    show_default=True,
    help="White (first player) provider:model. Examples: ollama:llama3.2, "
    "ollama:qwen2.5:14b, anthropic:claude-haiku-4-5, llmesh:<model>.",
)
@click.option(
    "--black",
    default="ollama:llama3.2",
    show_default=True,
    help="Black (second player) provider:model.",
)
@click.option("--max-ply", type=int, default=200, show_default=True)
@click.option(
    "--log",
    "log_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Append every event as one JSON line to this file (moves + signed).",
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="Skip the TUI; stream JSONL events to stdout. Useful for CI / batch eval.",
)
@click.option(
    "--stream",
    is_flag=True,
    help="In TUI mode, also stream events to stdout. Pair with --log for tee.",
)
def play_chess(
    white: str,
    black: str,
    max_ply: int,
    log_path: Path | None,
    no_tui: bool,
    stream: bool,
) -> None:
    """Drive the generic ``run_game`` for chess and route events to TUI/stdout/log."""
    import asyncio
    from datetime import UTC, datetime

    from llove.games.base import run_game
    from llove.games.base.llm_player import make_game_player
    from llove.games.base.player import GamePlayer
    from llove.games.chess.engine import EngineUnavailable
    from llove.games.registry import make_engine

    try:
        engine = make_engine("chess")  # ChessEngine(); raises EngineUnavailable
    except EngineUnavailable as exc:
        click.echo(
            f"chess engine unavailable: {exc}\n"
            "Install: pip install 'llmesh-llove[chess]'",
            err=True,
        )
        sys.exit(2)

    white_id, black_id = engine.player_ids()  # ["white", "black"]
    try:
        players: dict[str, GamePlayer] = {
            white_id: make_game_player(white, player_id=white_id, game="chess"),
            black_id: make_game_player(black, player_id=black_id, game="chess"),
        }
    except Exception as exc:
        # surface config errors (bad spec / missing key) as a hint, not a traceback.
        click.echo(str(exc), err=True)
        sys.exit(2)

    # Auto-log to out/chess/play-<ts>.jsonl when no explicit --log given.
    if log_path is None:
        ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        log_path = Path("out") / "chess" / f"play-{ts}.jsonl"
        click.echo(f"Logging this game to {log_path}", err=True)

    if no_tui:
        async def _stream() -> None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", encoding="utf-8") as fh:
                async for ev in run_game(engine, players, max_ply=max_ply):
                    line = ev.model_dump_json()
                    fh.write(line + "\n")
                    fh.flush()
                    click.echo(line)

        asyncio.run(_stream())
        return

    # TUI mode (default).
    from llove.app import LoveApp
    from llove.games.base.source import GameSource

    source = GameSource(engine, players, max_ply=max_ply, also_stdout=stream)
    LoveApp(source, with_narration=True, log_path=log_path).run()


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


@main.command(
    name="export-svg",
    help="Render the 10 思考因子 ring chart to a single animated SVG (SMIL).",
)
@click.option(
    "--out",
    "out_path",
    required=True,
    type=click.Path(path_type=Path),
    help="Output SVG path.",
)
@click.option(
    "--persona",
    default=None,
    help="Sample persona id (e.g. oka-kiyoshi, feynman, newton, galois). "
    "Mutually exclusive with --factors.",
)
@click.option(
    "--factors",
    default=None,
    help="Comma-separated 10 affinity values in [0,1], e.g. '0.7,0.5,...'. "
    "Defaults to a balanced 0.5 vector when neither --persona nor "
    "--factors is given.",
)
@click.option("--duration", type=float, default=6.0, show_default=True, help="Rotation period in seconds.")
def export_svg(out_path: Path, persona: str | None, factors: str | None, duration: float) -> None:
    from xml.dom import minidom

    from llove.export.svg import (
        THOUGHT_FACTOR_LABELS,
        SvgExportConfig,
        sample_persona_factors,
        thought_factor_ring_svg,
    )

    if persona and factors:
        click.echo("export-svg failed: pass only one of --persona / --factors", err=True)
        sys.exit(1)

    try:
        if persona:
            values = sample_persona_factors(persona)
        elif factors:
            values = tuple(float(x) for x in factors.split(","))
        else:
            values = (0.5,) * len(THOUGHT_FACTOR_LABELS)
        svg = thought_factor_ring_svg(values, config=SvgExportConfig(duration_s=duration))
        # fail-closed: refuse to write malformed XML.
        minidom.parseString(svg.encode("utf-8"))
    except Exception as exc:
        click.echo(f"export-svg failed: {exc}", err=True)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    click.echo(f"wrote {out_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
