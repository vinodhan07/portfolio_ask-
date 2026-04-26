"""
portfolio-ask  —  interactive AI portfolio intelligence CLI
"""
from __future__ import annotations

import json
import sys
import time
import random
from pathlib import Path
from datetime import datetime

import typer
from typing import Any
from dotenv import load_dotenv

load_dotenv()

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich.spinner import Spinner
from langchain_core.callbacks import BaseCallbackHandler


from .agent import QueryRouter
from .models import AllocationResponse, GeneralQaResponse, MetricsResponse, NewsImpactResponse, Portfolio
from .retriever import VectorStore, build_store
from .logger import setup_logger, logger

setup_logger()

app = typer.Typer(help="AI-powered portfolio intelligence CLI", rich_markup_mode="rich")
console = Console()

_DATA_DIR = Path(__file__).parent.parent / "data"
_VERSION = "0.1.0"


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

# Gemini-tone ASCII Logo
_BANNER_LOGO = r"""
[bold #38BDF8] ██████╗  ██████╗ ██████╗ ████████╗ [/bold #38BDF8] [bold #60A5FA] █████╗  ██████╗ ███████╗███╗   ██╗████████╗ [/bold #60A5FA]
[bold #38BDF8] ██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝ [/bold #38BDF8] [bold #60A5FA]██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝ [/bold #60A5FA]
[bold #60A5FA] ██████╔╝██║   ██║██████╔╝   ██║    [/bold #60A5FA] [bold #818CF8]███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║    [/bold #818CF8]
[bold #818CF8] ██╔═══╝ ██║   ██║██╔══██╗   ██║    [/bold #818CF8] [bold #A78BFA]██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║    [/bold #A78BFA]
[bold #A78BFA] ██║     ╚██████╔╝██║  ██║   ██║    [/bold #A78BFA] [bold #C084FC]██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║    [/bold #C084FC]
[bold #C084FC] ╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝    [/bold #C084FC] [bold #E879F9]╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    [/bold #E879F9]
"""

# ── Header & Visuals ──────────────────────────────────────────────────────────

def _print_banner(portfolio: Portfolio, store: VectorStore) -> None:
    console.clear()
    console.print(_BANNER_LOGO)
    
    console.print(Panel(
        f" [bold white]Assets Managed:[/bold white] ₹{portfolio.total_value:,.0f} [dim]|[/dim] [bold white]Tracked Holdings:[/bold white] {len(portfolio.holdings)}",
        border_style="blue",
        padding=(0, 2)
    ))
    
    console.print(f"\n[dim]Quick Access:[/dim]")
    console.print(f"  • Use [bold cyan]/portfolio[/bold cyan] to view your latest holdings.")
    console.print(f"  • Use [bold cyan]/rebuild[/bold cyan] to sync the vector store.")
    console.print(f"  • Use [bold cyan]/help[/bold cyan] for advanced commands.")
    console.print()
    console.print(Rule(style="dim blue"))
    console.print()
    
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
    return Prompt.ask("\n[bold blue]>[/bold blue] ")


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

class ThinkingHandler(BaseCallbackHandler):
    def __init__(self, live_display: Live):
        self.live = live_display
        self.steps = []
        self._update("Searching index & preparing context...")

    def _update(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.steps.append((ts, text))
        
        display = []
        display.append("[bold blue]◈ Agent Roadmap[/bold blue]")
        
        for i, (time_str, step_text) in enumerate(self.steps[-5:]):
            is_last = (i == len(self.steps[-5:]) - 1)
            connector = "●" if is_last else "○"
            display.append(f" [blue]{connector}[/blue] [dim]{time_str}[/dim] {step_text}")
            if not is_last:
                display.append(f" [blue]│[/blue]")
        
        display.append("\n [dim]Researching...[/dim]")
        self.live.update(Group(*display))

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        if tool_name in ["_invalid_tool", "invalid_tool"]:
            return
        self._update(f"Running [bold cyan]{tool_name}[/bold cyan]...")

    def on_tool_end(self, output: str, **kwargs) -> None:
        self._update("Processing results...")

def _render_tools(result) -> str:
    """Formats tools_used into a visual tag string."""
    if hasattr(result, "tools_used") and result.tools_used:
        unique_tools = list(dict.fromkeys(result.tools_used))
        tags = " ".join([f"[[bold cyan]◈ {t}[/bold cyan]]" for t in unique_tools])
        return f"[dim]Tools:[/dim] {tags}"
    return "[dim italic]Direct knowledge retrieval[/dim italic]"

def _render_allocation_table(result: AllocationResponse):
    t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold blue", expand=True)
    t.add_column("Sector", style="cyan", ratio=3)
    t.add_column("Weight", justify="right", ratio=2)
    t.add_column("Value (₹)", justify="right", ratio=3)
    for item in result.allocation:
        t.add_row(item.sector, f"{item.weight_pct:.2f}%", f"{item.value_inr:,.0f}")
    console.print(t)

def _render_metrics_table(result: MetricsResponse):
    t = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 3), expand=True)
    t.add_column(style="bold white", ratio=1)
    t.add_column(style="green", ratio=1)
    for k, v in result.metrics.items():
        t.add_row(k, str(v))
    console.print(t)

def _render_impact_table(result: NewsImpactResponse):
    if not result.impacts:
        console.print("  [dim]No specific holdings impacted by recent news.[/dim]")
        return

    t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold red", expand=True)
    t.add_column("Asset", style="bold white", ratio=2)
    t.add_column("Risk", justify="center", ratio=1)
    t.add_column("Insights & Rationale", ratio=6)
    
    exposure_badges = {
        "HIGH":   "[bold red]HIGH[/bold red]",
        "MEDIUM": "[bold orange3]MED[/bold orange3]",
        "MED":    "[bold orange3]MED[/bold orange3]",
        "LOW":    "[bold blue]LOW[/bold blue]",
    }

    for item in result.impacts:
        badge = exposure_badges.get(item.exposure_level.upper(), f"[{item.exposure_level}]")
        sources = f"\n[dim italic]› Sources: {', '.join(item.sources)}[/dim italic]" if item.sources else ""
        t.add_row(
            f"{item.ticker}\n[dim]{item.company_name}[/dim]",
            badge,
            f"{item.rationale}{sources}"
        )
    console.print(t)


def _route_and_render(result: Any, json_mode: bool):
    """Professional Master Router for result presentation"""
    if json_mode:
        console.print(Syntax(result.model_dump_json(indent=2), "json", theme="monokai"))
        return

    console.print(Rule(style="bold blue"))
    console.print(f" [bold blue]◆ Analysis Report[/bold blue] [dim]· {datetime.now().strftime('%H:%M:%S')}[/dim]\n")

    answer_text = getattr(result, "answer", getattr(result, "summary", ""))
    if answer_text:
        console.print(
            Panel(
                Markdown(answer_text),
                title="[bold cyan]Executive Summary[/bold cyan]",
                subtitle=_render_tools(result),
                subtitle_align="right",
                border_style="cyan",
                padding=(1, 2)
            )
        )
        console.print("")

    rtype = _get_rtype(result)
    if rtype == "allocation": 
        _render_allocation_table(result)
    elif rtype == "news_impact": 
        _render_impact_table(result)
    elif rtype == "metrics": 
        _render_metrics_table(result)
    
    if hasattr(result, "sources") and result.sources:
        sources_str = ", ".join(result.sources)
        console.print(f"  [dim italic]Sources: {sources_str}[/dim italic]")
    
    console.print(Rule(style="dim blue"))
    console.print("")

def _cmd_help() -> None:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="bold cyan", min_width=14)
    t.add_column(style="white")
    rows = [
        ("/portfolio, /p",  "Show full portfolio holdings table"),
        ("/rebuild",        "Force-rebuild the FAISS vector index from data/"),
        ("/clear,    /c",   "Clear screen and redraw the banner"),
        ("/json",           "Toggle raw JSON output mode (current session)"),
        ("/quit,     /q",   "Exit PORT AGENT"),
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


def _graceful_shutdown():
    """Professional multi-step shutdown sequence"""
    steps = [
        ("[bold red]●[/bold red] Terminating active agent processes...", 0.4),
        ("[bold red]●[/bold red] Clearing session cache and memory...", 0.3),
        ("[bold red]●[/bold red] Disconnecting from vector store...", 0.3),
        ("[bold blue]◆ System shutdown...[/bold blue] [blue]PORT AGENT[/blue] terminated. [green]✓[/green]\n", 0.1),
    ]
    console.print()
    for msg, delay in steps:
        console.print(msg)
        time.sleep(delay)
    sys.exit(0)

def _handle_slash_command(cmd: str, portfolio: Portfolio, store: VectorStore, router: QueryRouter, json_mode: bool) -> bool:
    """Returns the new state of json_mode."""
    logger.info(f"Slash Command: {cmd}")
    if cmd in ("/quit", "/exit", "/q"):
        _graceful_shutdown()
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


@app.command()
def main(
    query: str = typer.Argument(None, help="Run a single query non-interactively."),
    json_mode_opt: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force-rebuild vector index"),
):
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

    if query:
        logger.info(f"Single-shot Query: {query}")
        console.print(f"\n[dim]Query:[/dim] {query}\n")
        
        with Live(Panel("Initializing agent...", title="[bold blue]Thinking...[/bold blue]", border_style="blue"), refresh_per_second=4) as live:
            handler = ThinkingHandler(live)
            result = router.answer(query, callbacks=[handler])
            
        _route_and_render(result, json_mode_opt)
        return

    _print_banner(portfolio, store)
    json_mode = json_mode_opt

    while True:
        try:
            raw_query = _get_user_input().strip()
        except (KeyboardInterrupt, EOFError):
            _graceful_shutdown()
            break

        if not raw_query:
            continue

        if raw_query.startswith("/"):
            json_mode = _handle_slash_command(raw_query.lower().split()[0], portfolio, store, router, json_mode)
            continue

        with Live(Panel("Initializing agent...", title="[bold blue]Thinking...[/bold blue]", border_style="blue"), refresh_per_second=4) as live:
            handler = ThinkingHandler(live)
            result = router.answer(raw_query, callbacks=[handler])

        _route_and_render(result, json_mode)


if __name__ == "__main__":
    app()
