"""Deterministic classification for provider-resolved China public funds."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .domain import MarketScope, ShareClass, StrategyType, VehicleType

FUND_CODE = re.compile(r"\d{6}")


@dataclass(frozen=True)
class FundMetadata:
    code: str
    name: str
    vehicle_type: VehicleType
    strategy_type: StrategyType
    market_scope: MarketScope
    share_class: ShareClass
    parent_product_id: str | None = None
    provider_fund_type: str | None = None
    fund_company: str | None = None
    manager_name: str | None = None
    currency: str = "CNY"


def normalize_name(value: str) -> str:
    return re.sub(r"[\s（）()\-_/·]", "", value).casefold()


def _share_class(name: str) -> ShareClass:
    match = re.search(r"(?:^|[^A-Za-z])(A|C)(?:类)?$", name.strip(), re.IGNORECASE)
    if not match:
        return ShareClass.OTHER
    return ShareClass.A if match.group(1).upper() == "A" else ShareClass.C


def _base_product_name(name: str, share_class: ShareClass) -> str:
    if share_class == ShareClass.OTHER:
        return ""
    return normalize_name(re.sub(r"(?:A|C)(?:类)?$", "", name.strip(), flags=re.IGNORECASE))


def _vehicle_type(text: str) -> VehicleType:
    upper = text.upper()
    if "ETF联接" in upper or "ETF连接" in upper:
        return VehicleType.ETF_FEEDER
    if "LOF" in upper:
        return VehicleType.LOF
    if "联接" in text or "连接" in text:
        return VehicleType.INDEX_FEEDER
    return VehicleType.OPEN_END


def _strategy_type(text: str) -> StrategyType:
    upper = text.upper()
    if "FOF" in upper:
        return StrategyType.FOF
    if "指数" in text or "ETF" in upper:
        return StrategyType.INDEX
    if "股票" in text:
        return StrategyType.ACTIVE_EQUITY
    if "混合" in text:
        return StrategyType.ACTIVE_MIXED
    if "债" in text:
        return StrategyType.BOND
    if "货币" in text:
        return StrategyType.MONEY
    return StrategyType.OTHER


def _market_scope(text: str) -> MarketScope:
    upper = text.upper()
    if "QDII" in upper:
        return MarketScope.QDII
    if any(value in text for value in ("香港", "港股", "恒生")):
        return MarketScope.HONG_KONG
    if any(value in text for value in ("全球", "海外")):
        return MarketScope.GLOBAL
    return MarketScope.MAINLAND


def classify_fund(value: dict[str, Any]) -> FundMetadata:
    code = str(value.get("code") or "").strip()
    name = str(value.get("display_name") or "").strip()
    if not FUND_CODE.fullmatch(code) or not name:
        raise ValueError("Provider returned an invalid China public-fund identity")
    provider_type = str(value.get("provider_fund_type") or "").strip()
    combined = f"{name} {provider_type}"
    share_class = _share_class(name)
    company = str(value.get("fund_company") or "").strip() or None
    base_name = _base_product_name(name, share_class)
    parent_product_id = None
    if base_name:
        parent_material = f"{normalize_name(company or '')}|{base_name}"
        parent_product_id = "provider-name:" + hashlib.sha256(
            parent_material.encode("utf-8")
        ).hexdigest()[:20]
    return FundMetadata(
        code=code,
        name=name,
        vehicle_type=_vehicle_type(combined),
        strategy_type=_strategy_type(combined),
        market_scope=_market_scope(combined),
        share_class=share_class,
        parent_product_id=parent_product_id,
        provider_fund_type=provider_type or None,
        fund_company=company,
        manager_name=str(value.get("manager_name") or "").strip() or None,
        currency=str(value.get("currency") or "CNY"),
    )
