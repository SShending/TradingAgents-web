"""Shared instrument classification and identity resolution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum

from tradingagents.dataflows.symbol_utils import normalize_symbol


class AssetType(str, Enum):
    STOCK = "stock"
    FUND = "fund"
    CRYPTO = "crypto"


class FundType(str, Enum):
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    UNKNOWN = "unknown"


CRYPTO_SUFFIXES = ("-USD", "-USDT", "-USDC", "-BTC", "-ETH")


class InstrumentNotFoundError(ValueError):
    """Raised when neither metadata nor price data confirms a symbol."""


@dataclass(frozen=True)
class InstrumentDescriptor:
    requested_symbol: str
    canonical_symbol: str
    asset_type: AssetType
    fund_type: FundType | None = None
    quote_type: str | None = None
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    identity_source: str = "symbol"
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)


def is_crypto_symbol(symbol: str) -> bool:
    return normalize_symbol(symbol).endswith(CRYPTO_SUFFIXES)


def classify_quote_type(quote_type: str | None) -> tuple[AssetType, FundType | None]:
    normalized = (quote_type or "").upper()
    if normalized == "ETF":
        return AssetType.FUND, FundType.ETF
    if normalized == "MUTUALFUND":
        return AssetType.FUND, FundType.MUTUAL_FUND
    return AssetType.STOCK, None


def resolve_instrument(
    symbol: str,
    override: str | AssetType = "auto",
    *,
    identity_resolver: Callable[[str], Mapping[str, str]] | None = None,
    price_probe: Callable[[str], bool] | None = None,
) -> InstrumentDescriptor:
    """Resolve one canonical identity, applying an explicit override last."""
    requested = symbol.strip()
    if not requested:
        raise InstrumentNotFoundError("A symbol is required")
    canonical = normalize_symbol(requested)
    identity: Mapping[str, str] = {}
    source = "symbol"

    if is_crypto_symbol(canonical):
        detected, fund_type = AssetType.CRYPTO, None
        source = "symbol"
    else:
        if identity_resolver is None:
            from tradingagents.agents.utils.agent_utils import resolve_instrument_identity

            identity_resolver = resolve_instrument_identity
        identity = identity_resolver(canonical) or {}
        if identity:
            source = "yfinance"
        elif price_probe is None or not price_probe(canonical):
            raise InstrumentNotFoundError(f"No usable identity or market data for {canonical}")
        detected, fund_type = classify_quote_type(identity.get("quote_type"))

    warnings: list[str] = []
    selected = detected
    if override != "auto":
        selected = AssetType(override)
        if selected != detected:
            warnings.append(
                f"Explicit {selected.value} override conflicts with resolved {detected.value} metadata."
            )
        if selected == AssetType.FUND and fund_type is None:
            fund_type = FundType.UNKNOWN
        elif selected != AssetType.FUND:
            fund_type = None

    return InstrumentDescriptor(
        requested_symbol=requested,
        canonical_symbol=canonical,
        asset_type=selected,
        fund_type=fund_type,
        quote_type=identity.get("quote_type"),
        name=identity.get("company_name"),
        exchange=identity.get("exchange"),
        currency=identity.get("currency"),
        identity_source=source,
        warnings=tuple(warnings),
    )
