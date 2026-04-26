from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


class Holding(BaseModel):
    ticker: str
    name: str
    asset_type: Literal["equity", "mutual_fund", "bond"]
    sector: str
    quantity: float
    avg_buy_price: float
    current_price: float
    holding_value: float
    weight_pct: float
    pnl_pct: float


class Portfolio(BaseModel):
    portfolio_id: str
    owner: str
    currency: str
    as_of_date: str
    total_value: float
    holdings: list[Holding]

    @classmethod
    def from_list(cls, data: list[dict]) -> "Portfolio":
        total_val = sum(item.get("holding_value", 0.0) for item in data)
        holdings = []
        for item in data:
            holdings.append(
                Holding(
                    ticker=item["ticker"],
                    name=item["name"],
                    asset_type=item["asset_type"],
                    sector=item["sector"],
                    quantity=item["quantity"],
                    avg_buy_price=item["avg_cost"],
                    current_price=item["current_price"],
                    holding_value=item["holding_value"],
                    weight_pct=(item["holding_value"] / total_val * 100) if total_val else 0.0,
                    pnl_pct=item["pnl_pct"],
                )
            )
        return cls(
            portfolio_id="default",
            owner="User",
            currency="INR",
            as_of_date="2026-04-24",
            total_value=total_val,
            holdings=holdings,
        )


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



class GeneralQaResponse(BaseModel):
    query: str
    answer: str
    sources: list[str]

