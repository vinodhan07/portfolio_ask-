from __future__ import annotations

import json
import os
import re
from typing import Optional, TypedDict, Union

from groq import Groq
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.tools import StructuredTool

from .models import (
    AllocationResponse,
    GeneralQaResponse,
    MetricsResponse,
    NewsImpactResponse,
    Portfolio,
)
from .prompts import (
    ALLOCATION_SYSTEM,
    GENERAL_QA_SYSTEM,
    METRICS_SYSTEM,
    NEWS_IMPACT_SYSTEM,
)
from .retriever import VectorStore
from .logger import logger

_FLASH = "llama-3.3-70b-versatile"
_PRO   = "llama-3.3-70b-versatile"

_client: Groq | None = None

_WEIGHT_SCALE = 10.0

def _setup() -> None:
    global _client
    if _client is not None:
        return

    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set.\n"
            "Copy .env.example → .env and paste your key.\n"
            "Get one at: https://console.groq.com/keys"
        )
    _client = Groq(api_key=key)

def _call(model_name: str, system: str, user: str) -> str:
    response = _client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content

def _parse_json(text: str) -> dict:
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)

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

def _grounding_instruction() -> str:
    return (
        "\nIMPORTANT: Answer strictly using the context provided above. "
        "Do not use any external knowledge or training data. "
        "If the answer cannot be found in the provided context, respond with: "
        "'I could not find that information in the available portfolio data.'"
    )


def answer_allocation(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> AllocationResponse:
    chunks  = store.search(query, k=8)
    context = "\n\n---\n".join(c["text"] for c in chunks)
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist    = _history_context(history or [])

    system = ALLOCATION_SYSTEM + _grounding_instruction() + "\n\n" + _portfolio_context(portfolio)
    user   = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )

    raw  = _call(_FLASH, system, user)
    data = _parse_json(raw)

    required_keys = {"query", "answer", "holdings_referenced", "sources"}
    missing = required_keys - data.keys()

    if missing:
        return AllocationResponse(
            query=query,
            answer=f"Response was missing required fields: {missing}. Raw: {raw[:200]}",
            holdings_referenced=[],
            sources=sources,
        )

    data["sources"] = list(set(data.get("sources", [])) | set(sources))
    return AllocationResponse(**data)

def answer_metrics(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> MetricsResponse:
    chunks  = store.search(query, k=len(portfolio.holdings) + 5)
    context = "\n\n---\n".join(c["text"] for c in chunks)
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist    = _history_context(history or [])

    system = METRICS_SYSTEM + _grounding_instruction() + "\n\n" + _portfolio_context(portfolio)
    user   = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )

    raw  = _call(_FLASH, system, user)
    data = _parse_json(raw)

    required_keys = {"query", "metrics", "answer", "sources"}
    missing = required_keys - data.keys()

    if missing:
        return MetricsResponse(
            query=query,
            metrics={},
            answer=f"Response was missing required fields: {missing}. Raw: {raw[:200]}",
            sources=sources,
        )

    data["sources"] = list(set(data.get("sources", [])) | set(sources))
    return MetricsResponse(**data)

def answer_general_qa(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> GeneralQaResponse:
    chunks  = store.search(query, k=8)
    context = "\n\n---\n".join(c["text"] for c in chunks)
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist    = _history_context(history or [])

    system = GENERAL_QA_SYSTEM + _grounding_instruction() + "\n\n" + _portfolio_context(portfolio)
    user   = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )

    raw  = _call(_FLASH, system, user)
    data = _parse_json(raw)

    required_keys = {"query", "answer", "sources"}
    missing = required_keys - data.keys()

    if missing:
        return GeneralQaResponse(
            query=query,
            answer=f"Response was missing required fields: {missing}. Raw: {raw[:200]}",
            sources=sources,
        )

    data["sources"] = list(set(data.get("sources", [])) | set(sources))
    return GeneralQaResponse(**data)

def _node1_retrieve_news(query: str, store: VectorStore, k: int = 8) -> list[dict]:
    all_results = store.search(query, k=k * 3)
    news_only   = [r for r in all_results if r["metadata"].get("type") == "news"]
    return news_only[:k]

def _node2_cross_reference(
    news_chunks: list[dict],
    portfolio: Portfolio,
) -> list[tuple[dict, list[str]]]:
    # Build two lookup maps from portfolio holdings
    short_to_full: dict[str, str] = {}
    for h in portfolio.holdings:
        # 'TCS.NS' → 'TCS',  'HDFCBANK.NS' → 'HDFCBANK'
        short = h.ticker.split(".")[0]
        short_to_full[short] = h.ticker

    company_to_ticker: dict[str, str] = {
        h.name.lower(): h.ticker for h in portfolio.holdings
    }

    tagged: list[tuple[dict, list[str]]] = []

    for chunk in news_chunks:
        text_upper = chunk["text"].upper()
        text_lower = chunk["text"].lower()
        matched: list[str] = []

        for short_ticker, full_ticker in short_to_full.items():
            if short_ticker in text_upper and full_ticker not in matched:
                matched.append(full_ticker)

        for company_name, full_ticker in company_to_ticker.items():
            if full_ticker in matched:
                continue
            significant_words = [word for word in company_name.split() if len(word) > 4]
            word_found = any(word in text_lower for word in significant_words)
            if word_found:
                matched.append(full_ticker)

        tagged.append((chunk, matched))

    return tagged

def _node3_rank_by_exposure(
    tagged: list[tuple[dict, list[str]]],
    portfolio: Portfolio,
) -> list[tuple[dict, list[str], float]]:
    weight_map = {h.ticker: h.weight_pct for h in portfolio.holdings}

    scored: list[tuple[dict, list[str], float]] = []
    for chunk, tickers in tagged:
        weight_sum     = sum(weight_map.get(t, 0.0) for t in tickers)
        retrieval_term = chunk["score"] * _WEIGHT_SCALE
        composite      = weight_sum + retrieval_term
        scored.append((chunk, tickers, composite))

    scored.sort(key=lambda item: item[2], reverse=True)
    return scored[:6]

def _node4_format_cite(
    query: str,
    ranked: list[tuple[dict, list[str], float]],
    portfolio: Portfolio,
    history: list[dict] | None = None,
) -> NewsImpactResponse:
    ticker_info = {
        h.ticker: {
            "company":    h.name,
            "weight_pct": h.weight_pct,
            "sector":     h.sector,
        }
        for h in portfolio.holdings
    }

    news_context = [
        {
            "source":           chunk["metadata"].get("source"),
            "affected_tickers": tickers,
            "text":             chunk["text"][:500],
        }
        for chunk, tickers, _ in ranked
    ]

    hist = _history_context(history or [])

    user = (
        (f"{hist}\n\n" if hist else "")
        + f"Query: {query}\n\n"
        + f"Portfolio context:\n{json.dumps(ticker_info, indent=2)}\n\n"
        + f"Relevant news (ranked by portfolio exposure):\n{json.dumps(news_context, indent=2)}\n\n"
        + "Return JSON with this exact structure:\n"
        + "{\n"
        + '  "query": "<original question>",\n'
        + '  "impacts": [\n'
        + "    {\n"
        + '      "ticker": "<NSE ticker e.g. RELIANCE.NS>",\n'
        + '      "company_name": "<full company name>",\n'
        + '      "exposure_level": "HIGH | MEDIUM | LOW",\n'
        + '      "portfolio_weight_pct": <float>,\n'
        + '      "rationale": "<one sentence explanation>",\n'
        + '      "sources": ["<filename e.g. news_05.md>"]\n'
        + "    }\n"
        + "  ],\n"
        + '  "summary": "<detailed analytical explanation. Start with \'Based on the question, I have analyzed your portfolio holdings against the relevant news...\'. Reason over the specific portfolio weights and how the news affects them. Produce a clear, professional explanation of the potential impact.>"\n'
        + "}\n\n"
        + "Rules:\n"
        + "- Analyze the question carefully.\n"
        + "- Reason over both the portfolio weights and the news content.\n"
        + "- Only include tickers that appear in the provided news chunks.\n"
        + "- HIGH = direct material impact on the company's earnings or fundamentals.\n"
        + "- MEDIUM = indirect sector-level or macroeconomic impact.\n"
        + "- LOW = tangential or sentiment-only impact.\n"
        + "- sources must list the exact filename from the news context above.\n"
        + "- Do not invent tickers or news not present in the provided context."
    )

    raw  = _call(_PRO, NEWS_IMPACT_SYSTEM + _grounding_instruction(), user)
    data = _parse_json(raw)

    required_keys = {"query", "impacts", "summary"}
    missing = required_keys - data.keys()

    if missing:
        return NewsImpactResponse(
            query=query,
            impacts=[],
            summary=f"Node 4 response was missing required fields: {missing}. Raw: {raw[:200]}",
        )

    return NewsImpactResponse(**data)

def run_news_impact_agent(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> NewsImpactResponse:
    news_chunks = _node1_retrieve_news(query, store)
    tagged      = _node2_cross_reference(news_chunks, portfolio)
    ranked      = _node3_rank_by_exposure(tagged, portfolio)
    result      = _node4_format_cite(query, ranked, portfolio, history)
    return result



class QueryRouter:

    def __init__(self, portfolio_data: list | dict, store: VectorStore) -> None:
        if isinstance(portfolio_data, list):
            self.portfolio = Portfolio.from_list(portfolio_data)
        else:
            self.portfolio = Portfolio(**portfolio_data)

        self.store = store
        _setup()
        
        def allocation_func(query: str) -> str:
            logger.info(f"Tool Call: allocation_tool | Query: {query}")
            res = answer_allocation(query, self.portfolio, self.store, getattr(self, "current_history", None)).model_dump_json()
            logger.info(f"Tool Result [ALLOCATION]: {res}")
            return res

        def metrics_func(query: str) -> str:
            logger.info(f"Tool Call: metrics_tool | Query: {query}")
            res = answer_metrics(query, self.portfolio, self.store, getattr(self, "current_history", None)).model_dump_json()
            logger.info(f"Tool Result [METRICS]: {res}")
            return res

        def general_qa_func(query: str) -> str:
            logger.info(f"Tool Call: general_qa_tool | Query: {query}")
            res = answer_general_qa(query, self.portfolio, self.store, getattr(self, "current_history", None)).model_dump_json()
            logger.info(f"Tool Result [GENERAL_QA]: {res}")
            return res

        def news_impact_func(query: str) -> str:
            logger.info(f"Tool Call: news_impact_tool | Query: {query}")
            res = run_news_impact_agent(query, self.portfolio, self.store, getattr(self, "current_history", None)).model_dump_json()
            logger.info(f"Tool Result [NEWS_IMPACT]: {res}")
            return res

        tools = [
            StructuredTool.from_function(
                func=allocation_func,
                name="allocation_tool",
                description="Answers questions about portfolio composition, sector exposure, asset class breakdown, and holdings list."
            ),
            StructuredTool.from_function(
                func=metrics_func,
                name="metrics_tool",
                description="Answers questions about returns, P&L, XIRR, CAGR, NAV, and other performance metrics."
            ),
            StructuredTool.from_function(
                func=general_qa_func,
                name="general_qa_tool",
                description="Answers glossary lookups, open-ended questions, and queries that do not fit the allocation or metrics categories."
            ),
            StructuredTool.from_function(
                func=news_impact_func,
                name="news_impact_tool",
                description="Answers how recent news affects the portfolio holdings and computes exposure."
            )
        ]
        
        # Initialize Groq Model via LangChain
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)

        template = '''Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}'''
        
        prompt = PromptTemplate.from_template(template)
        
        self.agent = create_react_agent(llm, tools, prompt)
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=tools,
            verbose=False,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )
        self.current_history = None

        # Map tool names → response model classes
        self._tool_response_map: dict[str, type] = {
            "allocation_tool": AllocationResponse,
            "metrics_tool": MetricsResponse,
            "news_impact_tool": NewsImpactResponse,
            "general_qa_tool": GeneralQaResponse,
        }

    def answer(
        self,
        query: str,
        history: list[dict] | None = None,
    ) -> Union[AllocationResponse, MetricsResponse, NewsImpactResponse, GeneralQaResponse]:
        logger.info(f"User Query: {query}")
        self.current_history = history

        used_tools = []
        try:
            response = self.agent_executor.invoke({"input": query})
            final_answer = response.get("output", str(response))
            intermediate_steps = response.get("intermediate_steps", [])

            if intermediate_steps:
                for action, _ in intermediate_steps:
                    used_tools.append(action.tool)

                last_action, last_output = intermediate_steps[-1]
                tool_name = last_action.tool
                response_cls = self._tool_response_map.get(tool_name)

                if response_cls and isinstance(last_output, str):
                    try:
                        data = _parse_json(last_output)
                        result = response_cls(**data)
                        if hasattr(result, "tools_used"):
                            result.tools_used = used_tools
                        return result
                    except Exception:
                        pass  # Fall through to default

        except Exception as e:
            final_answer = f"Agent encountered an error: {e}"

        return GeneralQaResponse(
            query=query,
            answer=final_answer,
            sources=[],
            tools_used=used_tools
        )
