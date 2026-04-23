# portfolio-ask

AI-powered CLI for querying an Indian equity portfolio using RAG and a 4-node agentic pipeline.

```
python -m portfolio_ask "How does the RBI rate decision affect my holdings?"
```

## Architecture

```
Query → Router → allocation  → Standard RAG          → AllocationResponse
               → metrics     → RAG + Pydantic         → MetricsResponse
               → news_impact → 4-Node Variant C Agent → NewsImpactResponse
                                 Node 1: retrieve news (FAISS)
                                 Node 2: cross-reference tickers
                                 Node 3: rank by portfolio weight
                                 Node 4: Claude Sonnet → typed JSON + citations
```

Vector store: FAISS + `all-MiniLM-L6-v2` embeddings over `data/news/*.md`, `data/portfolio.json`, `data/glossary.md`.

## Setup

```bash
cp .env.example .env          # add your ANTHROPIC_API_KEY
make setup                    # pip install -e .
```

## Data

Populate `data/` before running:

```
data/
├── portfolio.json    # 15 holdings — see schema below
├── glossary.md       # wealth-tech term definitions (## Term headings)
└── news/
    ├── news_01.md    # 100-300 word news snippets
    └── ...
```

**portfolio.json schema** (one holding):
```json
{
  "ticker": "RELIANCE",
  "company": "Reliance Industries",
  "type": "equity",
  "sector": "Energy/Conglomerate",
  "quantity": 100,
  "avg_buy_price": 2400.0,
  "current_price": 2850.0,
  "current_value": 285000,
  "weight_pct": 5.74,
  "unrealized_pnl": 45000,
  "unrealized_pnl_pct": 18.75
}
```

## Usage

```bash
# Ask a question (pretty-printed)
python -m portfolio_ask "What is my IT sector exposure?"

# Raw JSON output
python -m portfolio_ask --json "What is my total unrealized P&L?"

# Force-rebuild the vector store cache
python -m portfolio_ask --rebuild "How does Reliance news affect me?"

# Or via make
make run QUERY="What percentage is in mutual funds?"
```

## Eval

```bash
make eval
```

Runs 5 cases from `evals/cases.yaml`. Prints pass/fail per case with reasoning trace.

## Models used

| Task | Model |
|------|-------|
| Query classification | `claude-haiku-4-5-20251001` |
| Allocation / Metrics RAG | `claude-haiku-4-5-20251001` |
| News impact (Node 4) | `claude-sonnet-4-6` |

Prompt caching is enabled on portfolio context blocks to reduce token costs.
