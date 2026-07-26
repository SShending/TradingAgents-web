"""Phase 3 China public-fund use-case orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from tradingagents.persistence import Repository

from .actions import evaluate_actions
from .catalog import FUND_CODE, FundMetadata, classify_fund, normalize_name
from .domain import ChinaFundIdentity, ChinaFundSnapshot
from .providers import CAPABILITIES, ProviderRegistry
from .trust import assess_snapshot


class FundNotFoundError(LookupError):
    pass


class AmbiguousFundError(ValueError):
    def __init__(self, candidates: list[FundMetadata]):
        self.candidates = candidates
        super().__init__("Fund name is ambiguous; select one share-class code")


def _metrics(nav_history) -> tuple[dict[str, Any], ...]:
    if len(nav_history) < 2:
        return (
            {
                "name": "total_return",
                "value": None,
                "unit": "percent",
                "reason_if_unavailable": "INSUFFICIENT_NAV_HISTORY",
            },
        )
    values = [Decimal(item.nav) for item in nav_history]
    total = values[-1] / values[0] - 1
    drawdown = Decimal(0)
    peak = values[0]
    returns: list[Decimal] = []
    for previous, current in zip(values, values[1:], strict=False):
        returns.append(current / previous - 1)
        peak = max(peak, current)
        drawdown = min(drawdown, current / peak - 1)
    volatility: Decimal | None = None
    if len(returns) > 1:
        mean = sum(returns) / Decimal(len(returns))
        variance = sum((value - mean) ** 2 for value in returns) / Decimal(len(returns) - 1)
        volatility = variance.sqrt() * Decimal(252).sqrt()
    return (
        {
            "name": "total_return",
            "value": format(total, ".8f"),
            "unit": "percent",
            "window": "available",
        },
        {
            "name": "annualized_volatility",
            "value": format(volatility, ".8f") if volatility is not None else None,
            "unit": "percent",
            "reason_if_unavailable": None if volatility is not None else "INSUFFICIENT_NAV_HISTORY",
        },
        {"name": "maximum_drawdown", "value": format(drawdown, ".8f"), "unit": "percent"},
    )


class ChinaFundService:
    def __init__(self, registry: ProviderRegistry, repository: Repository | None = None):
        self.registry = registry
        self.repository = repository

    def search(self, query: str) -> list[dict[str, Any]]:
        clean = query.strip()
        if not clean:
            return []
        if len(clean) > 100:
            raise ValueError("Fund search query is too long")
        result = self.registry.fetch(
            "identity", lambda provider: provider.search_funds(clean)
        )
        candidates: dict[str, FundMetadata] = {}
        for value in result.value or ():
            try:
                item = classify_fund(value)
            except ValueError:
                continue
            candidates.setdefault(item.code, item)
        return [self._catalog_json(item) for item in candidates.values()]

    def resolve(self, query: str) -> ChinaFundIdentity:
        identity, _result = self._resolve_with_result(query)
        return identity

    def _resolve_with_result(self, query: str):
        clean = query.strip()
        if not clean or len(clean) > 100:
            raise ValueError("Fund code or name is required")
        code = clean if FUND_CODE.fullmatch(clean) else None
        if code is None:
            search_result = self.registry.fetch(
                "identity", lambda provider: provider.search_funds(clean)
            )
            candidates: dict[str, FundMetadata] = {}
            for value in search_result.value or ():
                try:
                    item = classify_fund(value)
                except ValueError:
                    continue
                candidates.setdefault(item.code, item)
            exact = [
                item for item in candidates.values() if normalize_name(item.name) == normalize_name(clean)
            ]
            selected = exact or list(candidates.values())
            if not selected:
                raise FundNotFoundError(query)
            if len(selected) > 1:
                raise AmbiguousFundError(selected)
            code = selected[0].code
        result = self.registry.fetch(
            "identity", lambda provider: provider.fetch_identity(code)
        )
        if not result.value:
            raise FundNotFoundError(query)
        provider_value = result.value
        entry = classify_fund(provider_value)
        warnings = list(result.warnings)
        if not result.evidence:
            warnings.append("IDENTITY_PROVIDER_UNAVAILABLE")
        if entry.parent_product_id:
            warnings.append(
                "The share-class relationship was derived from the provider name and fund company."
            )
        identity = ChinaFundIdentity(
            entry.code,
            entry.name,
            entry.share_class,
            entry.vehicle_type,
            entry.strategy_type,
            entry.market_scope,
            entry.parent_product_id,
            entry.currency,
            manager_name=entry.manager_name,
            fund_company=entry.fund_company,
            tags=(entry.provider_fund_type,) if entry.provider_fund_type else (),
            evidence=result.evidence,
            warnings=tuple(dict.fromkeys(warnings)),
        )
        return identity, result

    def snapshot(self, code: str, analysis_date: str | None = None) -> ChinaFundSnapshot:
        cutoff = analysis_date or date.today().isoformat()
        cutoff_date = date.fromisoformat(cutoff)
        if cutoff_date > date.today():
            raise ValueError("analysis_date cannot be in the future")
        identity, identity_result = self._resolve_with_result(code)
        nav = self.registry.fetch("nav", lambda provider: provider.fetch_nav(code, cutoff))
        status = self.registry.fetch(
            "transaction_status", lambda provider: provider.fetch_transaction_status(code)
        )
        fees = self.registry.fetch("fees", lambda provider: provider.fetch_fees(code))
        disclosure = self.registry.fetch(
            "disclosure", lambda provider: provider.fetch_disclosure(code)
        )
        benchmark = self.registry.fetch(
            "benchmark", lambda provider: provider.fetch_benchmark(code)
        )
        disclosure_value = disclosure.value or {}
        evidence = (
            identity.evidence
            + nav.evidence
            + status.evidence
            + fees.evidence
            + disclosure.evidence
            + benchmark.evidence
        )
        warnings = (
            identity.warnings
            + nav.warnings
            + status.warnings
            + fees.warnings
            + disclosure.warnings
            + benchmark.warnings
        )
        capability_status = {
            name: (
                "unavailable"
                if result.value is None
                else "expired"
                if result.cache_status == "expired"
                else "cached"
                if result.cache_status == "hit"
                else "available"
            )
            for name, result in {
                "identity": identity_result,
                "nav": nav,
                "transaction_status": status,
                "fees": fees,
                "disclosure": disclosure,
                "benchmark": benchmark,
            }.items()
        }
        latest_nav = nav.value[-1] if nav.value else None
        qdii_context = {}
        if identity.is_qdii:
            qdii_context = {
                "nav_publication_lag_trading_days": None,
                "overseas_market_cutoff": latest_nav.date if latest_nav else None,
                "valuation_currency": identity.currency,
                "fx_context": "unavailable" if identity.currency == "CNY" else identity.currency,
                "latest_market_move_reflected": "unknown",
            }
        value = ChinaFundSnapshot(
            identity,
            cutoff,
            datetime.now(UTC).isoformat(),
            tuple(nav.value or ()),
            status.value,
            tuple(fees.value or ()),
            disclosure_value.get("manager") or {},
            tuple(disclosure_value.get("holdings") or ()),
            disclosure_value.get("sector_allocation") or {},
            disclosure_value.get("asset_allocation") or {},
            benchmark.value,
            qdii_context,
            _metrics(nav.value or ()),
            evidence,
            tuple(dict.fromkeys(warnings)),
            capability_status,
        )
        trust = assess_snapshot(value)
        if identity.is_qdii:
            qdii_context["nav_publication_lag_trading_days"] = trust.get("nav_lag_trading_days")
        value = replace(value, trust=trust, qdii_context=qdii_context)
        if self.repository is not None:
            self.repository.save_china_fund_snapshot(value.to_dict())
        return value

    def evaluate(self, code: str, **context):
        analysis_date = context.pop("analysis_date", None)
        snapshot = self.snapshot(code, analysis_date)
        target_code = context.pop("target_code", None)
        target_snapshot = self.snapshot(target_code, analysis_date) if target_code else None
        return snapshot, evaluate_actions(snapshot, target_snapshot=target_snapshot, **context)

    def persist_formal_advice(self, snapshot, evaluation):
        if self.repository is None or not evaluation.executable:
            return None
        persisted = self.repository.save_china_fund_snapshot(snapshot.to_dict())
        existing = self.repository.list_china_fund_advice(snapshot.identity.code)
        parent_id = existing[-1]["id"] if existing else None
        return self.repository.create_china_fund_advice(
            persisted["id"],
            snapshot.identity.code,
            evaluation.to_dict(),
            parent_id=parent_id,
        )

    @staticmethod
    def _catalog_json(item: FundMetadata) -> dict[str, Any]:
        return {
            "code": item.code,
            "display_name": item.name,
            "share_class": item.share_class,
            "vehicle_type": item.vehicle_type,
            "strategy_type": item.strategy_type,
            "market_scope": item.market_scope,
            "parent_product_id": item.parent_product_id,
            "tags": [item.provider_fund_type] if item.provider_fund_type else [],
        }


def default_registry(provider) -> ProviderRegistry:
    registry = ProviderRegistry()
    for capability in CAPABILITIES:
        registry.register(capability, provider)
    return registry
