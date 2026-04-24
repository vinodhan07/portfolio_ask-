# portfolio-ask

AI-powered portfolio intelligence CLI — conversational interface over your Indian equity portfolio.

```
  portfolio-ask  v0.1.0

  Portfolio    PORT-2024-001  ·  ₹49,66,500  ·  15 holdings
  Index        53 documents  ·  FAISS cosine  ·  MiniLM-L6
  Models       Haiku 4.5 (router / RAG)   Sonnet 4.6 (news-impact agent)

  ──────────────────────────────────────────────────────────────
  Type your question below  ·  /help for commands  ·  /quit to exit
  ──────────────────────────────────────────────────────────────

  You ▶ What is my banking sector exposure?
```

## Architecture

```
User query
    │
    ▼
Floor 3 — Agent layer (agent.py)
    QueryRouter → classify → allocation | metrics | news_impact
                                │               │            │
                          Standard RAG    RAG+Pydantic   4-Node Variant C
                                                           Node 1: retrieve news  (FAISS)
                                                           Node 2: cross-reference tickers
                                                           Node 3: rank by portfolio weight
                                                           Node 4: Claude Sonnet → typed JSON
    │
    ▼
Floor 2 — RAG layer (retriever.py)
    embed query → search FAISS → return top-K chunks with sources
    │
    ▼
Floor 1 — Data layer (data/)
    portfolio.json · portfolio_augmented.json · glossary.md · news/*.md
    (static, embedded once by scripts/build_index.py → .faiss_store/)
```

## Quick start

```bash
# 1. Install
cp .env.example .env          # add GOOGLE_API_KEY  (get one at aistudio.google.com/apikey)
make setup                    # pip install -e .

# 2. Add your data to data/
#    portfolio.json, glossary.md, news/*.md

# 3. Build the vector index (once)
make index

# 4. Start the interactive CLI
make start
```

## Usage

### Interactive (default)
```bash
python -m portfolio_ask
# or
make start
```

Commands inside the REPL:

| Command | Description |
|---------|-------------|
| `/portfolio` or `/p` | Show full holdings table |
| `/history` or `/h` | Show Q&A history for this session |
| `/rebuild` | Force-rebuild the FAISS index |
| `/clear` or `/c` | Clear screen and redraw banner |
| `/json` | Toggle raw JSON output mode |
| `/quit` or `/q` | Exit |

### One-shot (non-interactive)
```bash
python -m portfolio_ask --query "What is my IT sector exposure?"
python -m portfolio_ask --query "RBI rate impact" --json
make run QUERY="What is my total unrealized P&L?"
```

### Build/rebuild index
```bash
make index           # build (skips if already exists)
make index-force     # force rebuild
python scripts/build_index.py --force
```

### Run evals
```bash
make eval
```

## Data format

### `data/portfolio.json`
```json
{
  "portfolio_id": "PORT-2024-001",
  "owner": "Investor",
  "currency": "INR",
  "as_of_date": "2024-01-15",
  "total_value": 4966500,
  "holdings": [
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
  ]
}
```

### `data/glossary.md`
```markdown
## XIRR
Extended Internal Rate of Return…

## CAGR
Compound Annual Growth Rate…
```

### `data/news/news_01.md`
Plain markdown, 100–300 words per file. Mention company names or tickers so the cross-reference node picks them up.

## Models used

| Task | Model |
|------|-------|
| Query classification | `gemini-2.0-flash` |
| Allocation / Metrics RAG | `gemini-2.0-flash` |
| News impact (Node 4) | `gemini-1.5-pro` |

JSON mode (`response_mime_type: application/json`) is enabled on every call — no regex parsing needed.

## Two more days

- **Day 2:** Add `portfolio_augmented.json` with XIRR / CAGR per holding; update `MetricsResponse` to surface computed returns.
- **Day 3:** Streaming output via `client.messages.stream`; persist session history to `~/.portfolio_ask_history.json`; add `--since` date filter on news retrieval.
