"""
portfolio-ask  —  interactive AI portfolio intelligence CLI
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from datetime import datetime

import typer
from dotenv import load_dotenv

load_dotenv()

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.rule import Rule

# Assumes these exist in your project
from .agent import QueryRouter
from .models import AllocationResponse, GeneralQaResponse, MetricsResponse, NewsImpactResponse, Portfolio
from .retriever import VectorStore, build_store
from .logger import setup_logger, logger

setup_logger()

# Initialize Typer and Rich
app = typer.Typer(help="AI-powered portfolio intelligence CLI", rich_markup_mode="rich")
console = Console()

_DATA_DIR = Path(__file__).parent.parent / "data"
_VERSION = "0.1.0"

# --- GLOBAL STYLING DICTIONARIES ---
_COLORS = {
    "allocation": "cyan",
    "metrics": "green",
    "news_impact": "red",
    "general_qa": "magenta",
}
_LABELS = {
    "allocation": "ALLOCATION",
    "metrics": "METRICS",
    "news_impact": "NEWS IMPACT",
    "general_qa": "GENERAL Q&A",
}

_GEMINI_LOGO = r"""
[bold blue]
 _|_|_|      _|_|    _|_|_|    _|_|_|_|_|  _|_|_|_|    _|_|    _|        
 _|    _|  _|    _|  _|    _|      _|      _|        _|    _|  _|        
 _|_|_|    _|    _|  _|_|_|        _|      _|_|_|    _|    _|  _|        
 _|        _|    _|  _|    _|      _|      _|        _|    _|  _|        
 _|          _|_|    _|    _|      _|      _|          _|_|    _|_|_|_|  
                                                                        
                                                                        
 _|_|_|    _|_|    
   _|    _|    _|  
   _|    _|    _|  
   _|    _|    _|  
 _|_|_|    _|_|    
[/bold blue]
"""

# ── Header & Visuals ──────────────────────────────────────────────────────────

def _print_banner(portfolio: Portfolio, store: VectorStore) -> None:
    console.clear()
    
    # Custom ASCII Art Logo (Blue/Gemini style)
    console.print(_GEMINI_LOGO, highlight=False)
    
    # Branding & Version
    title = Text(justify="left")
    title.append("   portfolio", style="bold white")
    title.append("-ask", style="bold dark_red")
    console.print(title)
    console.print()

    tips = """[bold dim]Tips for getting started:[/bold dim]
    [dim]1. Ask natural questions about your holdings or market impacts.
    2. Be specific for the best results.
    3. Use [bold cyan]/portfolio[/bold cyan] to see your current tracked assets.
    4. Use [bold cyan]/help[/bold cyan] for more slash commands.[/dim]
    """
    console.print(tips)

    # Dynamic Suggestions based on actual holdings
    import random
    holdings = [h.ticker.split('.')[0] for h in portfolio.holdings]
    sectors = list(set(h.sector for h in portfolio.holdings))
    
    pool = [
        f"How does the latest news affect my {random.choice(holdings)} holdings?",
        f"What is my current allocation to the {random.choice(sectors)} sector?",
        f"Compare the performance of {random.choice(holdings)} and {random.choice(holdings)}.",
        f"What is the total unrealized P&L for my {random.choice(sectors)} assets?",
        f"Give me a summary of the latest news for {random.choice(holdings)}."
    ]
    suggested_queries = random.sample(pool, 3)
    
    console.print("[bold dim]Suggested questions:[/bold dim]")
    for q in suggested_queries:
        console.print(f"    [dim italic]• {q}[/dim italic]")
    console.print()


def _get_user_input() -> str:
    """Renders the bounding box footer and gets user input"""
    # Create a clean command bar instead of technical info
    cmd_bar = Text.assemble(
        (" /portfolio ", "bold cyan"), ("view holdings", "dim"), ("  •  ", "white dim"),
        (" /help ", "bold yellow"), ("all commands", "dim"), ("  •  ", "white dim"),
        (" /quit ", "bold red"), ("exit", "dim")
    )

    info_panel = Panel(
        cmd_bar,
        title="[dim]Available Commands[/dim]",
        title_align="left",
        border_style="blue dim",
        padding=(1, 2),
    )
    console.print(info_panel)
    
    # Safe Rich input instead of raw input()
    return Prompt.ask("\n[bold blue]>[/bold blue] ")


# ── Renderers ─────────────────────────────────────────────────────────────────

def _get_rtype(result) -> str:
    if isinstance(result, AllocationResponse): return "allocation"
    if isinstance(result, MetricsResponse): return "metrics"
    if isinstance(result, NewsImpactResponse): return "news_impact"
    if isinstance(result, GeneralQaResponse): return "general_qa"
    return "general_qa"

def _render_footer(rtype: str):
    """Adds the timestamp and type label to every response"""
    ts = datetime.now().strftime("%H:%M")
    color = _COLORS.get(rtype, "white")
    label = _LABELS.get(rtype, "UNKNOWN")
    console.print(f"\n  [dim][{color}]{label}[/{color}]  ·  {ts}[/dim]")
    console.print(Rule(style="dim"))
    console.print()

from rich.markdown import Markdown

def _render_tools(result) -> str:
    """Formats tools_used into a visual tag string."""
    if hasattr(result, "tools_used") and result.tools_used:
        unique_tools = list(dict.fromkeys(result.tools_used))
        tags = " ".join([f"[[bold cyan]◈ {t}[/bold cyan]]" for t in unique_tools])
        return f"[dim]Logic:[/dim] {tags}"
    return "[dim italic]Direct knowledge retrieval[/dim italic]"

def _render_allocation(result: AllocationResponse):
    console.print(
        Panel(
            Markdown(result.answer), 
            title="[bold cyan]◆ Allocation Analysis[/bold cyan]", 
            subtitle=_render_tools(result),
            subtitle_align="right",
            border_style="cyan", 
            padding=(0, 2)
        )
    )
    if result.holdings_referenced:
        refs = "  ·  ".join(f"[bold]{t}[/bold]" for t in result.holdings_referenced)
        console.print(f"  [dim]Holdings:[/dim]  {refs}")

def _render_news_impact(result: NewsImpactResponse):
    # 1. The Summary Panel
    summary_text = Markdown(result.summary)
    console.print(
        Panel(
            summary_text, 
            title="[bold red]◆ News Impact Analysis[/bold red]", 
            subtitle=_render_tools(result),
            subtitle_align="right",
            border_style="red", 
            padding=(0, 2)
        )
    )
    console.print()

    if not result.impacts:
        console.print("  [dim]No portfolio holdings directly mentioned in retrieved news.[/dim]")
        return

    # 2. The Professional Data Table
    t = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold white",
        expand=True,
        padding=(0, 1)
    )
    
    t.add_column("Asset", justify="left", style="bold cyan", ratio=2)
    t.add_column("Exposure", justify="center", ratio=1)
    t.add_column("Weight", justify="right", style="dim", ratio=1)
    t.add_column("Rationale & Sources", justify="left", ratio=6)

    exposure_badges = {
        "HIGH": "[bold white on red] HIGH [/bold white on red]",
        "MEDIUM": "[bold black on yellow] MED [/bold black on yellow]",
        "LOW": "[bold black on green] LOW [/bold black on green]"
    }

    for item in result.impacts:
        asset = f"{item.ticker}\n[dim]{item.company_name}[/dim]"
        badge = exposure_badges.get(item.exposure_level.upper(), f"[{item.exposure_level}]")
        weight = f"{item.portfolio_weight_pct:.2f}%"
        
        if hasattr(item, 'sources') and item.sources:
            sources_str = ", ".join(item.sources)
            rationale_display = f"{item.rationale}\n\n[dim italic]› Sources: {sources_str}[/dim italic]"
        else:
            rationale_display = item.rationale

        t.add_row(asset, badge, weight, rationale_display)
        t.add_section() 

    console.print(t)

def _render_metrics(result: MetricsResponse):
    console.print(
        Panel(
            Markdown(result.answer), 
            title="[bold green]◆ Portfolio Metrics[/bold green]", 
            subtitle=_render_tools(result),
            subtitle_align="right",
            border_style="green", 
            padding=(0, 2)
        )
    )
    if result.metrics:
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
        t.add_column(style="bold", min_width=28)
        t.add_column(style="green")
        for k, v in result.metrics.items():
            t.add_row(k, str(v))
        console.print(t)

def _render_general(result: GeneralQaResponse):
    console.print(
        Panel(
            Markdown(result.answer), 
            title="[bold magenta]◆ General Knowledge[/bold magenta]", 
            subtitle=_render_tools(result),
            subtitle_align="right",
            border_style="magenta", 
            padding=(0, 2)
        )
    )


def _route_and_render(result, json_mode: bool) -> str:
    """Master render router"""
    if json_mode:
        console.print(Syntax(result.model_dump_json(indent=2), "json", theme="monokai"))
        return result.model_dump_json()[:80]

    rtype = _get_rtype(result)
    
    if rtype == "allocation": _render_allocation(result)
    elif rtype == "news_impact": _render_news_impact(result)
    elif rtype == "metrics": _render_metrics(result)
    else: _render_general(result)

    _render_footer(rtype)
    
    summary = getattr(result, "answer", getattr(result, "summary", str(result)))
    logger.info(f"Rendered Result [{rtype.upper()}]: {summary[:100]}...")
    return summary[:100]


# ── Slash commands ────────────────────────────────────────────────────────────

def _cmd_help() -> None:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="bold cyan", min_width=14)
    t.add_column(style="white")
    rows = [
        ("/portfolio, /p",  "Show full portfolio holdings table"),
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


def _handle_slash_command(cmd: str, portfolio: Portfolio, store: VectorStore, router: QueryRouter, json_mode: bool) -> bool:
    """Returns the new state of json_mode."""
    logger.info(f"Slash Command: {cmd}")
    if cmd in ("/quit", "/exit", "/q"):
        console.print("\n  [bold cyan]●[/bold cyan] [dim]Shutting down Portfolio-Ask... Goodbye.[/dim]\n")
        sys.exit(0)
    elif cmd in ("/clear", "/c"):
        _print_banner(portfolio, store)
    elif cmd in ("/portfolio", "/p"):
        _cmd_portfolio(portfolio)
    elif cmd in ("/help",):
        _cmd_help()
    elif cmd == "/rebuild":
        with console.status("[bold]Rebuilding FAISS index…[/bold]"):
            new_store = build_store(_DATA_DIR, force_rebuild=True)
            router.store = new_store
        console.print(f"  [green]✓[/green] Index rebuilt  ·  {new_store.total_docs} documents")
    elif cmd == "/json":
        json_mode = not json_mode
        state = "[green]ON[/green]" if json_mode else "[dim]OFF[/dim]"
        console.print(f"  JSON mode {state}")
        return json_mode
    else:
        console.print(f"  [red]Unknown command:[/red] {cmd}")
    console.print()
    return json_mode


# ── Typer Application ─────────────────────────────────────────────────────────

@app.command()
def main(
    query: str = typer.Argument(None, help="Run a single query non-interactively."),
    json_mode_opt: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force-rebuild vector index"),
):
    # --- 1. Startup & Loading ---
    if not (_DATA_DIR / "portfolio.json").exists():
        console.print("[red]Error:[/red] data/portfolio.json not found.")
        sys.exit(1)

    with console.status("[bold]Loading portfolio and index…[/bold]"):
        portfolio_data = json.loads((_DATA_DIR / "portfolio.json").read_text(encoding="utf-8"))
        store = build_store(_DATA_DIR, force_rebuild=rebuild)
        router = QueryRouter(portfolio_data, store)
        portfolio = router.portfolio

    if rebuild and not query:
        console.print(f"[green]✓[/green] Index rebuilt  ·  {store.total_docs} documents")
        return

    # --- 2. Single-shot Mode ---
    if query:
        logger.info(f"Single-shot Query: {query}")
        console.print(f"\n[dim]Query:[/dim] {query}\n")
        with console.status("[bold]Thinking…[/bold]"):
            result = router.answer(query)
        _route_and_render(result, json_mode_opt)
        return

    # --- 3. Interactive REPL Mode ---
    _print_banner(portfolio, store)
    json_mode = json_mode_opt

    while True:
        try:
            raw_query = _get_user_input().strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [bold cyan]●[/bold cyan] [dim]Shutting down Portfolio-Ask... Goodbye.[/dim]\n")
            break

        if not raw_query:
            continue

        if raw_query.startswith("/"):
            json_mode = _handle_slash_command(raw_query.lower().split()[0], portfolio, store, router, json_mode)
            continue

        with console.status("[bold dim]Agent is thinking...[/bold dim]", spinner="dots"):
            result = router.answer(raw_query)

        summary = _route_and_render(result, json_mode)


if __name__ == "__main__":
    app()
