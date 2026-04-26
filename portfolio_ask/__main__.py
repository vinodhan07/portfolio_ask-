"""
portfolio-ask  —  interactive AI portfolio intelligence CLI

Start:
    python -m portfolio_ask
    portfolio-ask            (after pip install -e .)

One-shot (non-interactive):
    python -m portfolio_ask --query "What is my IT exposure?"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .agent import QueryRouter
from .models import AllocationResponse, GeneralQaResponse, MetricsResponse, NewsImpactResponse, Portfolio
from .retriever import VectorStore, build_store
from .logger import setup_logger

setup_logger()

console = Console()

_DATA_DIR = Path(__file__).parent.parent / "data"
_VERSION = "0.1.0"

_WELCOME_QUERIES = [
    "What is my allocation to the banking sector?",
    "How does the latest RBI rate decision affect my portfolio?",
    "What is my total unrealized P&L?",
    "Which holdings are exposed to IT sector headwinds?",
    "What percentage of my portfolio is in equities?",
]


# ── Banner ────────────────────────────────────────────────────────────────────

_WELCOME_ART = r"""[bold cyan]
 __      __   _                    _          _   _          ___ _    ___ 
 \ \    / /__| |__ ___ _ __  ___  | |_ ___   | |_| |_  ___  / __| |  |_ _|
  \ \/\/ / -_) / _/ _ \ '  \/ -_) |  _/ _ \  |  _| ' \/ -_) | (__| |__ | | 
   \_/\_/\___|_\__\___/_|_|_\___|  \__\___/   \__|_||_\___|  \___|____|___|
[/bold cyan]"""


def _banner(portfolio: Portfolio, store: VectorStore) -> None:
    console.clear()
    console.print(_WELCOME_ART)
    console.print()

    # Title block
    title = Text(justify="left")
    title.append("  portfolio", style="bold white")
    title.append("-ask", style="bold dark_red")
    title.append(f"  v{_VERSION}", style="dim")
    console.print(title)
    console.print()

    # Stats grid
    g = Table.grid(padding=(0, 3))
    g.add_column(style="bold cyan", min_width=12)
    g.add_column(style="white")
    g.add_row(
        "Portfolio",
        f"₹{portfolio.total_value:,.0f}  ·  {len(portfolio.holdings)} holdings",
    )

    console.print(g)
    console.print()

    # Suggested queries
    console.print("  [bold yellow]💻 Suggestions:[/bold yellow]")
    for i, q in enumerate(_WELCOME_QUERIES, 1):
        console.print(f"    [bold cyan]{i}.[/bold cyan] {q}")

    console.print()


# ── Slash command handlers ────────────────────────────────────────────────────

def _cmd_help() -> None:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="bold cyan", min_width=14)
    t.add_column(style="white")
    rows = [
        ("/portfolio, /p",  "Show full portfolio holdings table"),
        ("/history,  /h",   "Show Q&A history for this session"),
        ("/rebuild",        "Force-rebuild the FAISS vector index from data/"),
        ("/clear,    /c",   "Clear screen and redraw the banner"),
        ("/json",           "Toggle raw JSON output mode (current session)"),
        ("/quit,     /q",   "Exit portfolio-ask"),
    ]
    for cmd, desc in rows:
        t.add_row(cmd, desc)
    console.print(Panel(t, title="[bold]Commands[/bold]", border_style="dim", padding=(1, 2)))


def _cmd_portfolio(portfolio: Portfolio) -> None:
    t = Table(
        "Ticker", "Name", "Type", "Sector", "Weight %", "Value ₹", "P&L %",
        title=f"[bold]Portfolio  ·  ₹{portfolio.total_value:,.0f}[/bold]",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold blue",
    )
    for h in portfolio.holdings:
        pnl_color = "green" if h.pnl_pct >= 0 else "red"
        t.add_row(
            f"[bold]{h.ticker}[/bold]",
            h.name,
            h.asset_type,
            h.sector,
            f"{h.weight_pct:.2f}%",
            f"₹{h.holding_value:,.0f}",
            f"[{pnl_color}]{h.pnl_pct:+.2f}%[/{pnl_color}]",
        )
    console.print(t)


def _cmd_history(history: list[dict]) -> None:
    if not history:
        console.print("  [dim]No queries yet this session.[/dim]")
        return
    for i, item in enumerate(history, 1):
        label_color = {"allocation": "cyan", "metrics": "green", "newsimpact": "red"}.get(
            item["type"], "white"
        )
        console.print(
            f"  [dim]{i:2}.[/dim]  [{label_color}]{item['type']:<12}[/{label_color}]  {item['query']}"
        )


# ── Result renderers ──────────────────────────────────────────────────────────

def _render(
    result: AllocationResponse | MetricsResponse | NewsImpactResponse | GeneralQaResponse,
    json_mode: bool,
) -> str:
    """Render result to console; return short summary string for history."""
    if json_mode:
        console.print(Syntax(result.model_dump_json(indent=2), "json", theme="monokai"))
        return result.model_dump_json()[:80]

    if isinstance(result, AllocationResponse):
        console.print(
            Panel(
                result.answer,
                title="[bold cyan]Allocation Analysis[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        if result.holdings_referenced:
            refs = "  ·  ".join(f"[bold]{t}[/bold]" for t in result.holdings_referenced)
            console.print(f"  [dim]Holdings:[/dim]  {refs}")
        if result.sources:
            src = "  ·  ".join(f"[dim]{s}[/dim]" for s in set(result.sources) if s != "unknown")
            if src:
                console.print(f"  [dim]Sources:[/dim]   {src}")
        return result.answer[:100]

    if isinstance(result, MetricsResponse):
        console.print(
            Panel(
                result.answer,
                title="[bold green]Portfolio Metrics[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )
        if result.metrics:
            t = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
            t.add_column(style="bold", min_width=28)
            t.add_column(style="green")
            for k, v in result.metrics.items():
                t.add_row(k, str(v))
            console.print(t)
        if result.sources:
            src = "  ·  ".join(f"[dim]{s}[/dim]" for s in set(result.sources) if s != "unknown")
            if src:
                console.print(f"  [dim]Sources:[/dim]  {src}")
        return result.answer[:100]

    if isinstance(result, NewsImpactResponse):
        console.print(
            Panel(
                result.summary,
                title="[bold red]News Impact[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        if result.impacts:
            t = Table(
                "Ticker", "Company", "Exposure", "Weight %", "Sources",
                box=box.SIMPLE_HEAVY,
                show_header=True,
                header_style="bold red",
            )
            color_map = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
            for item in result.impacts:
                c = color_map.get(item.exposure_level, "white")
                t.add_row(
                    f"[bold]{item.ticker}[/bold]",
                    item.company_name,
                    f"[{c}]{item.exposure_level}[/{c}]",
                    f"{item.portfolio_weight_pct:.2f}%",
                    ", ".join(item.sources),
                )
            console.print(t)
            console.print()
            for item in result.impacts:
                console.print(f"  [bold]{item.ticker}[/bold]  {item.rationale}")
        else:
            console.print("  [dim]No portfolio holdings directly mentioned in retrieved news.[/dim]")
        return result.summary[:100]

    if isinstance(result, GeneralQaResponse):
        console.print(
            Panel(
                result.answer,
                title="[bold magenta]General Knowledge / RAG[/bold magenta]",
                border_style="magenta",
                padding=(1, 2),
            )
        )
        if result.sources:
            refs = "  ·  ".join(f"[dim]{s}[/dim]" for s in set(result.sources) if s != "unknown")
            if refs:
                console.print(f"  [dim]Sources:[/dim]  {refs}")
        return result.answer[:100]

    return str(result)[:100]


# ── REPL ──────────────────────────────────────────────────────────────────────

def _repl(router: QueryRouter, portfolio: Portfolio, store: VectorStore) -> None:
    history: list[dict] = []
    json_mode = False

    _banner(portfolio, store)

    while True:
        console.rule(title="[bold cyan]Command Input[/bold cyan]", style="bold cyan")
        console.print()
        console.rule(style="bold cyan")
        console.print("  [bold green]If you need any requirements use [white]/help[/white] | To quit use [white]/quit[/white][/bold green]")
        
        sys.stdout.write("\033[3A\033[2C")
        console.print("[bold cyan]>[/bold cyan] ", end="")
        sys.stdout.flush()
        
        try:
            raw = input()
            sys.stdout.write("\033[4B\r")
            sys.stdout.flush()
        except (KeyboardInterrupt, EOFError):
            sys.stdout.write("\033[4B\r")
            sys.stdout.flush()
            console.print("\n  [bold cyan]●[/bold cyan] [dim]Shutting down Portfolio-Ask... Goodbye.[/dim]\n")
            break

        query = raw.strip()
        if not query:
            continue

        # ── slash commands ──────────────────────────────────────────────────
        if query.startswith("/"):
            cmd = query.lower().split()[0]

            if cmd in ("/quit", "/exit", "/q"):
                console.print("\n  [bold cyan]●[/bold cyan] [dim]Shutting down Portfolio-Ask... Goodbye.[/dim]\n")
                break
            elif cmd in ("/help",):
                _cmd_help()
            elif cmd in ("/portfolio", "/p"):
                _cmd_portfolio(portfolio)
            elif cmd in ("/history", "/h"):
                _cmd_history(history)
            elif cmd == "/rebuild":
                with console.status("[bold]Rebuilding FAISS index…[/bold]"):
                    new_store = build_store(_DATA_DIR, force_rebuild=True)
                    router.store = new_store
                console.print(
                    f"  [green]✓[/green] Index rebuilt  ·  {new_store.total_docs} documents"
                )
            elif cmd in ("/clear", "/c"):
                _banner(portfolio, store)
            elif cmd == "/json":
                json_mode = not json_mode
                state = "[green]ON[/green]" if json_mode else "[dim]OFF[/dim]"
                console.print(f"  JSON mode {state}")
            else:
                console.print(
                    f"  [red]Unknown command:[/red] {cmd}  —  type [bold]/help[/bold]"
                )
            console.print()
            continue

        # ── natural language query ──────────────────────────────────────────
        with console.status("[bold]Thinking…[/bold]"):
            result = router.answer(query, history=history)

        summary = _render(result, json_mode)
        console.print()
        console.rule(style="dim")
        console.print()

        history.append(
            {
                "query": query,
                "type": type(result).__name__.replace("Response", "").lower(),
                "summary": summary,
            }
        )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="portfolio-ask",
        description="AI-powered portfolio intelligence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m portfolio_ask\n"
            '  python -m portfolio_ask --query "What is my IT sector exposure?"\n'
            '  python -m portfolio_ask --query "RBI impact" --json\n'
            "  python -m portfolio_ask --rebuild\n"
        ),
    )
    parser.add_argument("--query", "-q", help="Run a single query non-interactively and exit")
    parser.add_argument("--json",  "-j", action="store_true", help="Output raw JSON (with --query)")
    parser.add_argument("--rebuild", action="store_true", help="Force-rebuild vector index then exit")
    args = parser.parse_args()

    if not (_DATA_DIR / "portfolio.json").exists():
        console.print(
            "[red]Error:[/red] data/portfolio.json not found.\n\n"
            "Run  [bold]python scripts/build_index.py[/bold]  after populating data/.\n"
            "Set  [bold]GOOGLE_API_KEY[/bold]  in your .env file."
        )
        sys.exit(1)

    with console.status("[bold]Loading portfolio and index…[/bold]"):
        portfolio_data = json.loads((_DATA_DIR / "portfolio.json").read_text(encoding="utf-8"))
        store = build_store(_DATA_DIR, force_rebuild=args.rebuild)
        router = QueryRouter(portfolio_data, store)
        portfolio = router.portfolio

    if args.rebuild and not args.query:
        console.print(f"[green]✓[/green] Index rebuilt  ·  {store.total_docs} documents")
        return

    if args.query:
        # Non-interactive single-shot mode
        console.print(f"\n[dim]Query:[/dim] {args.query}\n")
        with console.status("[bold]Thinking…[/bold]"):
            result = router.answer(args.query)
        if args.json:
            console.print(Syntax(result.model_dump_json(indent=2), "json", theme="monokai"))
        else:
            _render(result, json_mode=False)
        return

    # Default: interactive REPL
    _repl(router, portfolio, store)


if __name__ == "__main__":
    main()
