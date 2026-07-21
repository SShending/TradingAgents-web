from enum import Enum

from tradingagents.instruments import AssetType as AssetType, FundType as FundType

__all__ = ["AnalystType", "AssetType", "FundType"]


class AnalystType(str, Enum):
    MARKET = "market"
    # Wire value stays "social" for saved-config and string-keyed-caller
    # back-compat; the user-facing label is "Sentiment Analyst".
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"
