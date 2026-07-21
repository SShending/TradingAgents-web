"""Fund-only LangChain tools backed by normalized deterministic data."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.fund_data import fetch_fund_snapshot
from tradingagents.instruments import resolve_instrument


def _snapshot(ticker: str, curr_date: str, benchmark: str):
    descriptor = resolve_instrument(ticker, "fund")
    return fetch_fund_snapshot(descriptor, curr_date, benchmark)


@tool
def get_fund_profile(
    ticker: Annotated[str, "fund ticker symbol"],
    curr_date: Annotated[str, "analysis date, yyyy-mm-dd"],
    benchmark: Annotated[str, "benchmark ticker"] = "SPY",
) -> dict:
    """Return normalized fund profile and provider/date warnings."""
    data = _snapshot(ticker, curr_date, benchmark)
    return {"profile": data.to_dict()["profile"], "warnings": data.warnings, "source": data.source}


@tool
def get_fund_holdings(
    ticker: Annotated[str, "fund ticker symbol"],
    curr_date: Annotated[str, "analysis date, yyyy-mm-dd"],
    benchmark: Annotated[str, "benchmark ticker"] = "SPY",
) -> dict:
    """Return normalized top holdings and allocation weights."""
    data = _snapshot(ticker, curr_date, benchmark)
    return {"top": data.to_dict()["top_holdings"], "sectors": data.sectors, "asset_classes": data.asset_classes, "warnings": data.warnings}


@tool
def get_fund_performance(
    ticker: Annotated[str, "fund ticker symbol"],
    curr_date: Annotated[str, "analysis date, yyyy-mm-dd"],
    benchmark: Annotated[str, "benchmark ticker"] = "SPY",
) -> dict:
    """Return Python-computed fund return, risk, and benchmark metrics."""
    data = _snapshot(ticker, curr_date, benchmark)
    return {"metrics": [metric.to_dict() for metric in data.metrics], "warnings": data.warnings}
