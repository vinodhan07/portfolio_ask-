from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .agent import QueryRouter
from .models import AllocationResponse, MetricsResponse, NewsImpactResponse
from .retriever import build_store

console = Console()
_DATA_DIR = Path(__file__).parent.parent / "data"


def _render_allocation(result: AllocationResponse) -> None:
    console.print(
        Panel(result.answer, title="[bold cyan]Allocation Analysis[/bold cyan]", border_style="cyan")
    )
    if result.holdings_referenced:
        t = Table("Ticker", title="Holdings Referenced", show_header=True, header_style="bold cyan")
        for ticker in result.holdings_referenced:
            t.add_row(ticker)
        console.print(t)


def _render_metrics(result: MetricsResponse) -> None:
    console.print(
        Panel(result.answer, title="[bold green]Portfolio Metrics[/bold green]", border_style="green")
    )
    if result.metrics:
        t = Table("Metric", "Value", title="Key Figures", show_header=True, header_style="bold green")
        for k, v in result.metrics.items():
            t.add_row(k, str(v))
        console.print(t)


def _render_news_impact(result: NewsImpactResponse) -> None:
    console.print(
        Panel(result.summary, title="[bold red]News Impact Summary[/bold red]", border_style="red")
    )
    if not result.impacts:
        console.print("[dim]No portfolio holdings directly affected by retrieved news.[/dim]")
        return

    t = Table(
        "Ticker", "Company", "Exposure", "Weight %", "Sources",
        title="Impact by Holding",
        show_header=True,
        header_style="bold red",
    )
    color_map = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
    for item in result.impacts:
        color = color_map.get(item.exposure_level, "white")
        t.add_row(
            f"[bold]{item.ticker}[/bold]",
            item.company_name,
            f"[{color}]{item.exposure_level}[/{color}]",
            f"{item.portfolio_weight_pct:.2f}%",
            ", ".join(item.sources),
        )
    console.print(t)

    console.print()
    for item in result.impacts:
        console.print(f"[bold]{item.ticker}[/bold]: {item.rationale}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-powered portfolio Q&A CLI",
        prog="python -m portfolio_ask",
    )
    parser.add_argument("query", nargs="+", help="Question about your portfolio")
    parser.add_argument(
        "--rebuild", action="store_true", help="Force-rebuild the vector store cache"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true", help="Output raw JSON"
    )
    args = parser.parse_args()
    query = " ".join(args.query)

    if not (_DATA_DIR / "portfolio.json").exists():
        console.print(
            f"[red]Error:[/red] {_DATA_DIR / 'portfolio.json'} not found.\n"
            "Run [bold]make setup[/bold] first, then ensure data/ is populated."
        )
        sys.exit(1)

    with console.status("[bold]Indexing data…[/bold]"):
        portfolio_data = json.loads((_DATA_DIR / "portfolio.json").read_text(encoding="utf-8"))
        store = build_store(_DATA_DIR, force_rebuild=args.rebuild)
        router = QueryRouter(portfolio_data, store)

    console.print(f"\n[dim]Query:[/dim] {query}\n")

    with console.status("[bold]Thinking…[/bold]"):
        result = router.answer(query)

    if args.output_json:
        console.print(Syntax(result.model_dump_json(indent=2), "json", theme="monokai"))
        return

    if isinstance(result, AllocationResponse):
        _render_allocation(result)
    elif isinstance(result, MetricsResponse):
        _render_metrics(result)
    elif isinstance(result, NewsImpactResponse):
        _render_news_impact(result)
    else:
        console.print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
