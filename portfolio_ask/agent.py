from __future__ import annotations

import json
import os
import re
from typing import Union

from google import genai
from google.genai import types

from .models import (
    AllocationResponse,
    GeneralQaResponse,
    MetricsResponse,
    NewsImpactResponse,
    Portfolio,
    QueryClassification,
)
from .prompts import (
    ALLOCATION_SYSTEM,
    GENERAL_QA_SYSTEM,
    METRICS_SYSTEM,
    NEWS_IMPACT_SYSTEM,
    ROUTER_SYSTEM,
)
from .retriever import VectorStore

# gemini-2.5-flash → fast + cheap
# gemini-2.5-pro   → deeper reasoning
_FLASH = "gemini-flash-latest"
_PRO   = "gemini-pro-latest"

_client = None


def _setup() -> None:
    global _client
    if _client is not None:
        return
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GOOGLE_API_KEY not set. Copy .env.example → .env and add your key.\n"
            "Get one at: https://aistudio.google.com/apikey"
        )
    _client = genai.Client(api_key=key)


def _call(model_name: str, system: str, user: str) -> str:
    """Single Gemini call; returns raw text (always JSON due to config)."""
    response = _client.models.generate_content(
        model=model_name,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.1,
        )
    )
    return response.text


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No JSON found in:\n{text[:300]}")


def _portfolio_context(portfolio: Portfolio) -> str:
    lines = [
        f"Currency     : {portfolio.currency}",
        f"Total Value  : ₹{portfolio.total_value:,.0f}",
        f"Holdings     : {len(portfolio.holdings)}",
        "",
        "Holdings:",
    ]
    for h in portfolio.holdings:
        lines.append(
            f"  {h.ticker:<18} {h.name:<35} {h.asset_type:<12} {h.sector:<25}"
            f"  weight {h.weight_pct:>5.2f}%  value ₹{h.holding_value:>10,.0f}"
            f"  P&L {h.pnl_pct:>+6.2f}%"
        )
    return "\n".join(lines)


def _history_context(history: list[dict]) -> str:
    if not history:
        return ""
    lines = ["--- Previous questions this session ---"]
    for item in history[-4:]:
        lines.append(f"Q: {item['query']}")
        lines.append(f"A: {item['summary']}")
    lines.append("--- End of history ---")
    return "\n".join(lines)


# ── Query classifier ──────────────────────────────────────────────────────────

def classify_query(query: str) -> QueryClassification:
    try:
        data = _extract_json(_call(_FLASH, ROUTER_SYSTEM, query))
        return QueryClassification(**data)
    except Exception:
        return QueryClassification(query_type="general_qa", reasoning="fallback")


# ── Standard RAG handlers ─────────────────────────────────────────────────────

def answer_allocation(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> AllocationResponse:
    chunks = store.search(query, k=8)
    context = "\n\n---\n".join(c["text"] for c in chunks)
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist = _history_context(history or [])

    system = ALLOCATION_SYSTEM + "\n\n" + _portfolio_context(portfolio)
    user = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )
    try:
        data = _extract_json(_call(_FLASH, system, user))
        return AllocationResponse(**data)
    except Exception as e:
        return AllocationResponse(
            query=query, answer=str(e), holdings_referenced=[], sources=sources
        )


def answer_metrics(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> MetricsResponse:
    chunks = store.search(query, k=6)
    context = "\n\n---\n".join(c["text"] for c in chunks)
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist = _history_context(history or [])

    system = METRICS_SYSTEM + "\n\n" + _portfolio_context(portfolio)
    user = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )
    try:
        data = _extract_json(_call(_FLASH, system, user))
        return MetricsResponse(**data)
    except Exception as e:
        return MetricsResponse(
            query=query, metrics={}, answer=str(e), sources=sources
        )


def answer_general_qa(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> GeneralQaResponse:
    chunks = store.search(query, k=8)
    context = "\n\n---\n".join(c["text"] for c in chunks)
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist = _history_context(history or [])

    system = GENERAL_QA_SYSTEM + "\n\n" + _portfolio_context(portfolio)
    user = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )
    try:
        data = _extract_json(_call(_FLASH, system, user))
        return GeneralQaResponse(**data)
    except Exception as e:
        return GeneralQaResponse(
            query=query, answer=str(e), sources=sources
        )


# ── 4-Node Variant C Agent ────────────────────────────────────────────────────

def _node1_retrieve_news(query: str, store: VectorStore, k: int = 8) -> list[dict]:
    """Node 1: vector search on news/*.md"""
    results = store.search(query, k=k * 3)
    return [r for r in results if r["metadata"].get("type") == "news"][:k]


def _node2_cross_reference(
    news_chunks: list[dict], portfolio: Portfolio
) -> list[tuple[dict, list[str]]]:
    """Node 2: map news chunks to portfolio tickers via string match"""
    ticker_set = {h.ticker for h in portfolio.holdings}
    company_to_ticker = {h.name.lower(): h.ticker for h in portfolio.holdings}

    tagged: list[tuple[dict, list[str]]] = []
    for chunk in news_chunks:
        text_upper = chunk["text"].upper()
        text_lower = chunk["text"].lower()
        matched: list[str] = []
        for ticker in ticker_set:
            if ticker in text_upper and ticker not in matched:
                matched.append(ticker)
        for company, ticker in company_to_ticker.items():
            significant_parts = [p for p in company.split() if len(p) > 4]
            if any(p in text_lower for p in significant_parts) and ticker not in matched:
                matched.append(ticker)
        tagged.append((chunk, matched))
    return tagged


def _node3_rank_by_exposure(
    tagged: list[tuple[dict, list[str]]], portfolio: Portfolio
) -> list[tuple[dict, list[str], float]]:
    """Node 3: score = sum of affected ticker weights + retrieval relevance"""
    weight_map = {h.ticker: h.weight_pct for h in portfolio.holdings}
    scored = [
        (chunk, tickers, sum(weight_map.get(t, 0.0) for t in tickers) + chunk["score"] * 10.0)
        for chunk, tickers in tagged
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:6]


def _node4_format_cite(
    query: str,
    ranked: list[tuple[dict, list[str], float]],
    portfolio: Portfolio,
    history: list[dict] | None = None,
) -> NewsImpactResponse:
    """Node 4: Gemini Pro generates Pydantic-typed JSON + source citations"""
    ticker_info = {
        h.ticker: {"company": h.name, "weight_pct": h.weight_pct, "sector": h.sector}
        for h in portfolio.holdings
    }
    news_context = [
        {
            "source": chunk["metadata"].get("source"),
            "affected_tickers": tickers,
            "text": chunk["text"][:500],
        }
        for chunk, tickers, _ in ranked
    ]
    hist = _history_context(history or [])
    user = (
        (f"{hist}\n\n" if hist else "")
        + f"Query: {query}\n\n"
        + f"Portfolio:\n{json.dumps(ticker_info, indent=2)}\n\n"
        + f"Relevant news (ranked by portfolio exposure):\n{json.dumps(news_context, indent=2)}\n\n"
        + "Return JSON:\n"
        + '{"query":"...","impacts":[{"ticker":"...","company_name":"...","exposure_level":"HIGH|MEDIUM|LOW",'
        + '"portfolio_weight_pct":0.0,"rationale":"...","sources":["news_XX.md"]}],"summary":"..."}\n\n'
        + "Only include tickers present in the news. "
        + "HIGH=direct earnings impact, MEDIUM=sector/macro, LOW=sentiment only."
    )
    try:
        data = _extract_json(_call(_PRO, NEWS_IMPACT_SYSTEM, user))
        return NewsImpactResponse(**data)
    except Exception as e:
        return NewsImpactResponse(query=query, impacts=[], summary=str(e))


def run_news_impact_agent(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> NewsImpactResponse:
    news_chunks = _node1_retrieve_news(query, store)
    tagged     = _node2_cross_reference(news_chunks, portfolio)
    ranked     = _node3_rank_by_exposure(tagged, portfolio)
    return _node4_format_cite(query, ranked, portfolio, history)


# ── Public router ─────────────────────────────────────────────────────────────

class QueryRouter:
    def __init__(self, portfolio_data: list | dict, store: VectorStore) -> None:
        if isinstance(portfolio_data, list):
            self.portfolio = Portfolio.from_list(portfolio_data)
        else:
            self.portfolio = Portfolio(**portfolio_data)
        self.store = store
        _setup()  # configures genai globally once

    def answer(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> Union[AllocationResponse, MetricsResponse, NewsImpactResponse, GeneralQaResponse]:
        classification = classify_query(query)
        if classification.query_type == "allocation":
            return answer_allocation(query, self.portfolio, self.store, history)
        if classification.query_type == "metrics":
            return answer_metrics(query, self.portfolio, self.store, history)
        if classification.query_type == "general_qa":
            return answer_general_qa(query, self.portfolio, self.store, history)
        return run_news_impact_agent(query, self.portfolio, self.store, history)
