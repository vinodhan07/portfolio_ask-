from __future__ import annotations

import json
import os
import re
from typing import Any, Optional, TypedDict, Union

from langchain_core.callbacks import BaseCallbackHandler

from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
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

_FLASH = "gemini-2.5-flash"
_PRO   = "gemini-2.5-flash"
_WEIGHT_SCALE = 10.0

def _parse_json(text: str) -> dict:
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
            f"  {h.ticker:<12} {h.name:<30} {h.weight_pct:>5.2f}%  P&L {h.pnl_pct:>+6.2f}%"
        )
    return "\n".join(lines)

def _history_context(history: list[dict]) -> str:
    if not history:
        return ""
    lines = ["Recent Conversation History:"]
    for turn in history[-2:]:
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"  {role}: {turn['content']}")
    return "\n".join(lines)

def _grounding_instruction() -> str:
    return "\n\nAnswer strictly using the context provided. Do not use external knowledge or invent facts."

def answer_allocation(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> AllocationResponse:
    chunks = store.search(query, top_k=5)
    context = "\n\n".join([c["text"] for c in chunks])
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist    = _history_context(history or [])

    # Use LangChain structured output binding
    llm = ChatGoogleGenerativeAI(
        model=_FLASH, 
        temperature=0.1, 
        convert_system_message_to_human=True,
        google_api_key=os.environ.get("GOOGLE_API_KEY")
    )
    structured_llm = llm.with_structured_output(AllocationResponse)

    system = ALLOCATION_SYSTEM + _grounding_instruction() + "\n\n" + _portfolio_context(portfolio)
    user   = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )

    result = structured_llm.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ])
    
    # Merge retrieved sources
    result.sources = list(set(result.sources) | set(sources))
    return result

def answer_metrics(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> MetricsResponse:
    chunks = store.search(query, top_k=5)
    context = "\n\n".join([c["text"] for c in chunks])
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist    = _history_context(history or [])

    llm = ChatGoogleGenerativeAI(
        model=_FLASH, 
        temperature=0.1, 
        convert_system_message_to_human=True,
        google_api_key=os.environ.get("GOOGLE_API_KEY")
    )
    structured_llm = llm.with_structured_output(MetricsResponse)

    system = METRICS_SYSTEM + _grounding_instruction() + "\n\n" + _portfolio_context(portfolio)
    user   = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )

    result = structured_llm.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ])
    
    result.sources = list(set(result.sources) | set(sources))
    return result

def answer_general_qa(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> GeneralQaResponse:
    chunks = store.search(query, top_k=5)
    context = "\n\n".join([c["text"] for c in chunks])
    sources = list({c["metadata"].get("source", "unknown") for c in chunks})
    hist    = _history_context(history or [])

    llm = ChatGoogleGenerativeAI(
        model=_FLASH, 
        temperature=0.1, 
        convert_system_message_to_human=True,
        google_api_key=os.environ.get("GOOGLE_API_KEY")
    )
    structured_llm = llm.with_structured_output(GeneralQaResponse)

    system = GENERAL_QA_SYSTEM + _grounding_instruction() + "\n\n" + _portfolio_context(portfolio)
    user   = (
        (f"{hist}\n\n" if hist else "")
        + f"Context:\n{context}\n\nQuestion: {query}"
    )

    result = structured_llm.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ])
    
    result.sources = list(set(result.sources) | set(sources))
    return result

def _node1_retrieve_news(query: str, store: VectorStore, k: int = 4) -> list[dict]:
    all_results = store.search(query, top_k=k * 2)
    return [r for r in all_results if r["metadata"].get("type") == "news"][:k]

def _node2_tag_holdings(
    news_chunks: list[dict],
    portfolio: Portfolio,
) -> list[tuple[dict, list[str]]]:
    company_to_ticker = {h.name: h.ticker for h in portfolio.holdings}
    tagged = []
    
    for chunk in news_chunks:
        text_lower = chunk["text"].lower()
        matched = []
        for h in portfolio.holdings:
            ticker_base = h.ticker.split('.')[0].lower()
            full_ticker = h.ticker
            if ticker_base in text_lower or full_ticker.lower() in text_lower:
                matched.append(full_ticker)

        for company_name, full_ticker in company_to_ticker.items():
            if full_ticker in matched:
                continue
            significant_words = [word for word in company_name.split() if len(word) > 4]
            if any(word in text_lower for word in significant_words):
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
        + "Instructions:\n"
        + "- Analyze the exposure of the portfolio to this news.\n"
        + "- For each affected ticker, provide a rationale and exposure level (HIGH/MEDIUM/LOW).\n"
        + "- Keep the final summary concise (max 100 words).\n"
        + "- Do not invent tickers or news not present in the provided context."
    )

    llm = ChatGoogleGenerativeAI(
        model=_PRO, 
        temperature=0.1, 
        convert_system_message_to_human=True,
        google_api_key=os.environ.get("GOOGLE_API_KEY")
    )
    structured_llm = llm.with_structured_output(NewsImpactResponse)

    result = structured_llm.invoke([
        {"role": "system", "content": NEWS_IMPACT_SYSTEM + _grounding_instruction()},
        {"role": "user", "content": user}
    ])
    return result

def run_news_impact_agent(
    query: str,
    portfolio: Portfolio,
    store: VectorStore,
    history: list[dict] | None = None,
) -> NewsImpactResponse:
    news = _node1_retrieve_news(query, store)
    if not news:
        return NewsImpactResponse(query=query, impacts=[], summary="No relevant news found.")
    
    tagged = _node2_tag_holdings(news, portfolio)
    ranked = _node3_rank_by_exposure(tagged, portfolio)
    return _node4_format_cite(query, ranked, portfolio, history)



class QueryRouter:

    def __init__(self, portfolio_data: list | dict, store: VectorStore) -> None:
        if isinstance(portfolio_data, list):
            self.portfolio = Portfolio.from_list(portfolio_data)
        else:
            self.portfolio = Portfolio(**portfolio_data)

        self.store = store
        
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


        if not os.environ.get("GOOGLE_API_KEY"):
             raise EnvironmentError("GOOGLE_API_KEY is not set.")

        llm = ChatGoogleGenerativeAI(
            model=_FLASH, 
            temperature=0.1, 
            convert_system_message_to_human=True,
            google_api_key=os.environ.get("GOOGLE_API_KEY")
        )

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
        callbacks: list[BaseCallbackHandler] | None = None,
    ) -> Union[AllocationResponse, MetricsResponse, NewsImpactResponse, GeneralQaResponse]:
        logger.info(f"User Query: {query}")
        self.current_history = history
        
        config = {"callbacks": callbacks} if callbacks else {}

        used_tools = []
        try:
            response = self.agent_executor.invoke({"input": query}, config=config)
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
