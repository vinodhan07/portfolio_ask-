"""Eval harness: python evals/run_eval.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from portfolio_ask.agent import QueryRouter
from portfolio_ask.models import NewsImpactResponse
from portfolio_ask.retriever import build_store

console = Console()
DATA_DIR = Path(__file__).parent.parent / "data"
CASES_FILE = Path(__file__).parent / "cases.yaml"


def _check(result_json: str, expected_facts: list[str]) -> tuple[int, list[str]]:
    hits, misses = [], []
    for fact in expected_facts:
        if fact.lower() in result_json.lower():
            hits.append(fact)
        else:
            misses.append(fact)
    return len(hits), misses


def run() -> None:
    cases = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))["cases"]

    console.print("\n[bold]Loading portfolio and vector store…[/bold]")
    portfolio_data = json.loads((DATA_DIR / "portfolio.json").read_text(encoding="utf-8"))
    store = build_store(DATA_DIR)
    router = QueryRouter(portfolio_data, store)

    results_table = Table(
        "ID", "Query (truncated)", "Type Match", "Facts Hit", "Status",
        title="Eval Results",
        show_header=True,
        header_style="bold magenta",
    )

    passed = 0
    for case in cases:
        cid = case["id"]
        query = case["query"]
        expected_type = case["expected_type"]
        expected_facts: list[str] = case.get("expected_facts", [])

        console.print(f"\n[dim]Running {cid}:[/dim] {query}")
        result = router.answer(query)
        result_json = result.model_dump_json()


        actual_type = type(result).__name__.lower().replace("response", "")
        type_map = {"allocation": "allocation", "metrics": "metrics", "newsimpact": "news_impact"}
        actual_label = type_map.get(actual_type, actual_type)
        type_ok = actual_label == expected_type


        hits, misses = _check(result_json, expected_facts)
        facts_ok = len(misses) == 0
        ok = type_ok and facts_ok

        if ok:
            passed += 1

        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        type_cell = f"[green]{actual_label}[/green]" if type_ok else f"[red]{actual_label} ≠ {expected_type}[/red]"
        facts_cell = f"{hits}/{len(expected_facts)}"
        if misses:
            facts_cell += f" (missing: {', '.join(misses)})"

        results_table.add_row(
            cid,
            query[:45] + ("…" if len(query) > 45 else ""),
            type_cell,
            facts_cell,
            status,
        )

        console.print(f"  Result type : {actual_label}")
        if isinstance(result, NewsImpactResponse):
            console.print(f"  Impacts     : {[i.ticker for i in result.impacts]}")
        console.print(f"  Facts found : {hits}/{len(expected_facts)}" + (f"  Missing: {misses}" if misses else ""))

    console.print()
    console.print(results_table)
    console.print(f"\n[bold]Score: {passed}/{len(cases)} passed[/bold]")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    run()
