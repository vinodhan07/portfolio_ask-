from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.table import Table
from rich import box

from portfolio_ask.retriever import (
    VectorStore,
    _chunk_augmented,
    _chunk_glossary,
    _chunk_news,
    _chunk_portfolio,
)

console = Console()
_STORE_DIR = ROOT / ".faiss_store"


def build(data_dir: Path, force: bool = False) -> None:
    if not data_dir.exists():
        console.print(f"[red]Error:[/red] {data_dir} does not exist.")
        sys.exit(1)

    if not force and (_STORE_DIR / "portfolio.faiss").exists():
        console.print(
            f"[yellow]Index already exists at {_STORE_DIR}/[/yellow]\n"
            "Pass [bold]--force[/bold] to rebuild."
        )
        return

    console.print(f"\n  [bold]Building FAISS index[/bold]  →  {_STORE_DIR}/\n")
    t0 = time.perf_counter()

    loaders = [
        ("portfolio.json",           _chunk_portfolio,  data_dir / "portfolio.json"),
        ("glossary.md",              _chunk_glossary,   data_dir / "glossary.md"),
        ("news/*.md",                _chunk_news,       data_dir / "news"),
    ]

    store = VectorStore()
    stats: list[tuple[str, int, str]] = []

    for label, loader, path in loaders:
        if not path.exists():
            stats.append((label, 0, "[dim]skipped (not found)[/dim]"))
            continue
        texts, meta = loader(path)
        if texts:
            store.add_documents(texts, meta)
        status = f"[green]✓[/green]  {len(texts)} chunks" if texts else "[dim]0 chunks[/dim]"
        stats.append((label, len(texts), status))

    store.save(_STORE_DIR)
    elapsed = time.perf_counter() - t0

    t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    t.add_column("Source", style="cyan")
    t.add_column("Chunks", justify="right")
    t.add_column("Status")
    for label, count, status in stats:
        t.add_row(label, str(count), status)
    t.add_row("", "", "")
    t.add_row("[bold]TOTAL[/bold]", f"[bold]{store.total_docs}[/bold]", "[bold green]saved[/bold green]")
    console.print(t)
    console.print(
        f"  [green]✓[/green] Index saved to [bold]{_STORE_DIR}/[/bold]  "
        f"·  {store.total_docs} docs  ·  {elapsed:.1f}s\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the FAISS vector index from data/")
    parser.add_argument("--data-dir", default=str(ROOT / "data"), help="Path to data directory")
    parser.add_argument("--force", action="store_true", help="Rebuild even if index exists")
    args = parser.parse_args()
    build(Path(args.data_dir), force=args.force)


if __name__ == "__main__":
    main()
