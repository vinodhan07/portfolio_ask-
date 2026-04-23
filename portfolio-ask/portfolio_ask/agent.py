from __future__ import annotations

import json
import os
import re
from typing import Union

import anthropic

from .models import (
    AllocationResponse,
    MetricsResponse,
    NewsImpactItem,
    NewsImpactResponse,
    Portfolio,
    QueryClassification,
)
from .prompts import (
    ALLOCATION_SYSTEM,
    METRICS_SYSTEM,
    NEWS_IMPACT_SYSTEM,
    ROUTER_SYSTEM,
)
from .retriever import VectorStore

_HAIKU = "claude-haiku-4-5-20251001"
_SONNET = "claude-sonnet-4-6"


def _client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set. Copy .env.example → .env and add your key.")
    return anthropic.Anthropic(api_key=key)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found in:\n{text[:300]}")


def _portfolio_context(portfolio: Portfolio) -> str:
    lines = [
        f"Portfolio ID: {portfolio.portfolio_id}",
        f"Owner: {portfolio.owner}",
        f"Currency: {portfolio.currency}",
        f"As of: {portfolio.as_of_date}",
        f"Total Value: ₹{portfolio.total_value:,.0f}",
        "",
        "Holdings:",
    ]
    for h in portfolio.holdings:
        lines.append(
            f"  {h.ticker} | {h.company} | {h.type} | {h.sector}"
            f" | weight {h.weight_pct:.2f}% | value ₹{h.current_value:,.0f}"
            f" | P&L {h.unrealized_pnl_pct:+.2f}%"
        )
    return "\n".join(lines)


# ── Query classifier ──────────────────────────────────────────────────────────

def classify_query(query: str, client: anthropic.Anthropic) -> QueryClassification:
    resp = client.messages.create(
        model=_HAIKU,
        max_tokens=128,
        system=ROUTER_SYSTEM,
        messages=[{"role": "user", "content": query}],
    )
    try:
        data = _extract_json(resp.content[0].text)
        return QueryClassification(**data)
    except Exception:
        return QueryClassification(query_type="news_impact", reasoning="fallback")


# ── Standard RAG handlers ─────────────────────────────────────────────────────

def answer_allocation(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    client: anthropic.Anthropic,
) -> AllocationResponse:
    chunks = store.search(query, k=8)
    context = "\n\n---\n".join(c["text"] for c in chunks)
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})

    resp = client.messages.create(
        model=_HAIKU,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": ALLOCATION_SYSTEM + "\n\n" + _portfolio_context(portfolio),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Retrieved context:\n{context}\n\n"
                    f"Question: {query}\n\n"
                    "Respond with JSON matching the AllocationResponse schema."
                ),
            }
        ],
    )
    try:
        data = _extract_json(resp.content[0].text)
        return AllocationResponse(**data)
    except Exception:
        return AllocationResponse(
            query=query,
            answer=resp.content[0].text,
            holdings_referenced=[],
            sources=sources,
        )


def answer_metrics(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    client: anthropic.Anthropic,
) -> MetricsResponse:
    chunks = store.search(query, k=6)
    context = "\n\n---\n".join(c["text"] for c in chunks)
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})

    resp = client.messages.create(
        model=_HAIKU,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": METRICS_SYSTEM + "\n\n" + _portfolio_context(portfolio),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Retrieved context:\n{context}\n\n"
                    f"Question: {query}\n\n"
                    "Respond with JSON matching the MetricsResponse schema."
                ),
            }
        ],
    )
    try:
        data = _extract_json(resp.content[0].text)
        return MetricsResponse(**data)
    except Exception:
        return MetricsResponse(
            query=query,
            metrics={},
            answer=resp.content[0].text,
            sources=sources,
        )


# ── 4-Node Variant C Agent ────────────────────────────────────────────────────

def _node1_retrieve_news(query: str, store: VectorStore, k: int = 8) -> list[dict]:
    """Node 1: vector search on news/*.md"""
    results = store.search(query, k=k * 3)
    return [r for r in results if r["metadata"].get("type") == "news"][:k]


def _node2_cross_reference(
    news_chunks: list[dict], portfolio: Portfolio
) -> list[tuple[dict, list[str]]]:
    """Node 2: map each news chunk to portfolio tickers via string match"""
    ticker_set = {h.ticker for h in portfolio.holdings}
    company_to_ticker = {h.company.lower(): h.ticker for h in portfolio.holdings}

    tagged: list[tuple[dict, list[str]]] = []
    for chunk in news_chunks:
        text_upper = chunk["text"].upper()
        text_lower = chunk["text"].lower()
        matched: list[str] = []

        for ticker in ticker_set:
            if ticker in text_upper and ticker not in matched:
                matched.append(ticker)

        for company, ticker in company_to_ticker.items():
            parts = company.split()
            if any(p in text_lower for p in parts if len(p) > 4) and ticker not in matched:
                matched.append(ticker)

        tagged.append((chunk, matched))
    return tagged


def _node3_rank_by_exposure(
    tagged: list[tuple[dict, list[str]]], portfolio: Portfolio
) -> list[tuple[dict, list[str], float]]:
    """Node 3: score = sum of affected ticker weights + relevance boost"""
    weight_map = {h.ticker: h.weight_pct for h in portfolio.holdings}

    scored: list[tuple[dict, list[str], float]] = []
    for chunk, tickers in tagged:
        exposure = sum(weight_map.get(t, 0.0) for t in tickers)
        combined = exposure + chunk["score"] * 10.0
        scored.append((chunk, tickers, combined))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:6]


def _node4_format_cite(
    query: str,
    ranked: list[tuple[dict, list[str], float]],
    portfolio: Portfolio,
    client: anthropic.Anthropic,
) -> NewsImpactResponse:
    """Node 4: Claude Sonnet generates typed Pydantic JSON + source citations"""
    ticker_info = {
        h.ticker: {"company": h.company, "weight_pct": h.weight_pct, "sector": h.sector}
        for h in portfolio.holdings
    }

    news_context = [
        {
            "source": chunk["metadata"].get("source", "unknown"),
            "affected_tickers": tickers,
            "text": chunk["text"][:500],
        }
        for chunk, tickers, _ in ranked
    ]

    prompt = (
        f"Query: {query}\n\n"
        f"Portfolio tickers:\n{json.dumps(ticker_info, indent=2)}\n\n"
        f"Relevant news (sorted by portfolio exposure):\n{json.dumps(news_context, indent=2)}\n\n"
        "Analyze the impact of this news on the portfolio. "
        "Return JSON:\n"
        '{\n'
        '  "query": "...",\n'
        '  "impacts": [\n'
        '    {\n'
        '      "ticker": "RELIANCE",\n'
        '      "company_name": "Reliance Industries",\n'
        '      "exposure_level": "HIGH",\n'
        '      "portfolio_weight_pct": 5.74,\n'
        '      "rationale": "...",\n'
        '      "sources": ["news_01.md"]\n'
        '    }\n'
        '  ],\n'
        '  "summary": "..."\n'
        '}\n\n'
        "Only include tickers that appear in the news. "
        "HIGH = direct earnings impact, MEDIUM = sector/macro, LOW = sentiment only."
    )

    resp = client.messages.create(
        model=_SONNET,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": NEWS_IMPACT_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        data = _extract_json(resp.content[0].text)
        return NewsImpactResponse(**data)
    except Exception:
        return NewsImpactResponse(
            query=query,
            impacts=[],
            summary=resp.content[0].text,
        )


def run_news_impact_agent(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    client: anthropic.Anthropic,
) -> NewsImpactResponse:
    news_chunks = _node1_retrieve_news(query, store)
    tagged = _node2_cross_reference(news_chunks, portfolio)
    ranked = _node3_rank_by_exposure(tagged, portfolio)
    return _node4_format_cite(query, ranked, portfolio, client)


# ── Public router ─────────────────────────────────────────────────────────────

class QueryRouter:
    def __init__(self, portfolio_data: dict, store: VectorStore) -> None:
        self.portfolio = Portfolio(**portfolio_data)
        self.store = store
        self.client = _client()

    def answer(self, query: str) -> Union[AllocationResponse, MetricsResponse, NewsImpactResponse]:
        classification = classify_query(query, self.client)
        if classification.query_type == "allocation":
            return answer_allocation(query, self.portfolio, self.store, self.client)
        if classification.query_type == "metrics":
            return answer_metrics(query, self.portfolio, self.store, self.client)
        return run_news_impact_agent(query, self.portfolio, self.store, self.client)
