"""Deterministic fund performance metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from math import sqrt

import pandas as pd


@dataclass(frozen=True)
class FundMetric:
    name: str
    value: float | None
    unit: str
    window: str | None = None
    reason_if_unavailable: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


WINDOW_DAYS = {"1m": 31, "3m": 92, "6m": 183, "1y": 366, "3y": 1096}


def normalize_prices(series: pd.Series, analysis_date: str | date) -> pd.Series:
    """Return sorted, finite, de-duplicated prices through analysis_date."""
    cutoff = pd.Timestamp(analysis_date)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_localize(None)
    values = pd.Series(series, dtype="float64").copy()
    index = pd.to_datetime(values.index, utc=True, errors="coerce").tz_convert(None)
    values.index = index
    values = values[~values.index.isna()]
    values = values[values.index.normalize() <= cutoff.normalize()]
    values = values[~values.index.duplicated(keep="last")].sort_index()
    return values.replace([float("inf"), float("-inf")], pd.NA).dropna()


def _unavailable(name: str, unit: str, reason: str, window: str | None = None) -> FundMetric:
    return FundMetric(name, None, unit, window, reason)


def calculate_metrics(
    prices: pd.Series,
    analysis_date: str | date,
    benchmark_prices: pd.Series | None = None,
) -> list[FundMetric]:
    clean = normalize_prices(prices, analysis_date)
    metrics: list[FundMetric] = []
    cutoff = pd.Timestamp(analysis_date)
    for window, days in WINDOW_DAYS.items():
        subset = clean[clean.index >= cutoff - pd.Timedelta(days=days)]
        if len(subset) < 2 or clean.empty or clean.index.min() > cutoff - pd.Timedelta(days=days - 7):
            metrics.append(_unavailable("total_return", "percent", "insufficient history", window))
        else:
            metrics.append(FundMetric("total_return", float(subset.iloc[-1] / subset.iloc[0] - 1), "percent", window))

    returns = clean.pct_change().dropna()
    if len(returns) < 2:
        metrics.extend([
            _unavailable("annualized_volatility", "percent", "insufficient history"),
            _unavailable("maximum_drawdown", "percent", "insufficient history"),
        ])
    else:
        metrics.append(FundMetric("annualized_volatility", float(returns.std(ddof=1) * sqrt(252)), "percent"))
        drawdown = clean / clean.cummax() - 1
        metrics.append(FundMetric("maximum_drawdown", float(drawdown.min()), "percent"))

    if benchmark_prices is None:
        metrics.extend([
            _unavailable("benchmark_relative_return", "percent", "benchmark unavailable"),
            _unavailable("correlation", "ratio", "benchmark unavailable"),
            _unavailable("tracking_error", "percent", "benchmark unavailable"),
        ])
        return metrics

    benchmark = normalize_prices(benchmark_prices, analysis_date)
    aligned = pd.concat(
        [clean.pct_change().rename("fund"), benchmark.pct_change().rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if len(aligned) < 2:
        metrics.extend([
            _unavailable("benchmark_relative_return", "percent", "insufficient overlapping history"),
            _unavailable("correlation", "ratio", "insufficient overlapping history"),
            _unavailable("tracking_error", "percent", "insufficient overlapping history"),
        ])
    else:
        relative = (1 + aligned["fund"]).prod() - (1 + aligned["benchmark"]).prod()
        metrics.append(FundMetric("benchmark_relative_return", float(relative), "percent"))
        metrics.append(FundMetric("correlation", float(aligned.corr().iloc[0, 1]), "ratio"))
        active = aligned["fund"] - aligned["benchmark"]
        metrics.append(FundMetric("tracking_error", float(active.std(ddof=1) * sqrt(252)), "percent"))
    return metrics


def premium_discount(
    market_price: float | None,
    nav: float | None,
    market_as_of: date | None,
    nav_as_of: date | None,
) -> FundMetric:
    if market_price is None or nav is None:
        return _unavailable("premium_discount", "percent", "NAV or market price unavailable")
    if nav <= 0:
        return _unavailable("premium_discount", "percent", "invalid NAV")
    if market_as_of is None or nav_as_of is None or abs((market_as_of - nav_as_of).days) > 1:
        return _unavailable("premium_discount", "percent", "NAV and market price timestamps are incompatible")
    return FundMetric("premium_discount", (market_price - nav) / nav, "percent")
