from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


class Holding(BaseModel):
    ticker: str
    company: str
    type: Literal["equity", "mutual_fund", "bond"]
    sector: str
    quantity: float
    avg_buy_price: float
    current_price: float
    current_value: float
    weight_pct: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class Portfolio(BaseModel):
    portfolio_id: str
    owner: str
    currency: str
    as_of_date: str
    total_value: float
    holdings: list[Holding]


class NewsImpactItem(BaseModel):
    ticker: str
    company_name: str
    exposure_level: Literal["HIGH", "MEDIUM", "LOW"]
    portfolio_weight_pct: float
    rationale: str
    sources: list[str]


class NewsImpactResponse(BaseModel):
    query: str
    impacts: list[NewsImpactItem]
    summary: str


class AllocationResponse(BaseModel):
    query: str
    answer: str
    holdings_referenced: list[str]
    sources: list[str]


class MetricsResponse(BaseModel):
    query: str
    metrics: dict[str, str]
    answer: str
    sources: list[str]


class QueryClassification(BaseModel):
    query_type: Literal["allocation", "metrics", "news_impact"]
    reasoning: str
