from unittest.mock import Mock

import pytest

from tradingagents.instruments import (
    AssetType,
    FundType,
    InstrumentNotFoundError,
    resolve_instrument,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("symbol", "identity", "asset", "fund_type"),
    [
        ("spy", {"quote_type": "ETF", "company_name": "SPY"}, AssetType.FUND, FundType.ETF),
        ("VFIAX", {"quote_type": "MUTUALFUND"}, AssetType.FUND, FundType.MUTUAL_FUND),
        ("AAPL", {"quote_type": "EQUITY"}, AssetType.STOCK, None),
    ],
)
def test_instrument_classification(symbol, identity, asset, fund_type):
    result = resolve_instrument(symbol, identity_resolver=lambda _: identity)
    assert result.canonical_symbol == symbol.upper()
    assert result.asset_type == asset
    assert result.fund_type == fund_type


def test_crypto_wins_without_metadata_lookup():
    resolver = Mock(side_effect=AssertionError("should not run"))
    result = resolve_instrument("btcusd", identity_resolver=resolver)
    assert result.canonical_symbol == "BTC-USD"
    assert result.asset_type == AssetType.CRYPTO
    resolver.assert_not_called()


def test_explicit_override_warns_and_unknown_identity_requires_price():
    result = resolve_instrument("SPY", "stock", identity_resolver=lambda _: {"quote_type": "ETF"})
    assert result.asset_type == AssetType.STOCK
    assert "conflicts" in result.warnings[0]
    with pytest.raises(InstrumentNotFoundError):
        resolve_instrument("NOPE", identity_resolver=lambda _: {}, price_probe=lambda _: False)
    assert resolve_instrument("GC=F", identity_resolver=lambda _: {}, price_probe=lambda _: True).asset_type == AssetType.STOCK
