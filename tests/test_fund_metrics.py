import math
from datetime import date

import pandas as pd
import pytest

from tradingagents.dataflows.fund_metrics import (
    calculate_metrics,
    normalize_prices,
    premium_discount,
)


def _metric(metrics, name, window=None):
    return next(item for item in metrics if item.name == name and item.window == window)


def test_metrics_are_deterministic_and_exclude_future_rows():
    index = pd.date_range('2025-01-01', periods=500, freq='D')
    prices = pd.Series([100 + value * 0.1 for value in range(500)], index=index)
    prices.loc[pd.Timestamp('2026-08-01')] = 9999
    benchmark = pd.Series([100 + value * 0.08 for value in range(500)], index=index)
    metrics = calculate_metrics(prices, '2026-01-15', benchmark)
    expected = prices.loc['2025-12-15':'2026-01-15'].iloc[-1] / prices.loc['2025-12-15':'2026-01-15'].iloc[0] - 1
    assert _metric(metrics, 'total_return', '1m').value == pytest.approx(expected)
    assert _metric(metrics, 'annualized_volatility').value is not None
    assert _metric(metrics, 'maximum_drawdown').value == pytest.approx(0)
    assert _metric(metrics, 'tracking_error').value is not None


def test_normalization_handles_unsorted_duplicates_nan_and_timezones():
    series = pd.Series([2, math.nan, 4, 3], index=pd.to_datetime(['2026-01-03','2026-01-02','2026-01-03','2026-01-01'], utc=True))
    result = normalize_prices(series, '2026-01-02')
    assert list(result) == [3]


def test_unavailable_metrics_and_premium_discount_reasons():
    metrics = calculate_metrics(pd.Series([100], index=pd.to_datetime(['2026-01-01'])), '2026-01-01')
    assert _metric(metrics, 'total_return', '1m').reason_if_unavailable == 'insufficient history'
    assert premium_discount(101, 0, date(2026,1,1), date(2026,1,1)).reason_if_unavailable == 'invalid NAV'
    assert premium_discount(101, 100, date(2026,1,4), date(2026,1,1)).reason_if_unavailable is not None
    assert premium_discount(101, 100, date(2026,1,1), date(2026,1,1)).value == pytest.approx(.01)
