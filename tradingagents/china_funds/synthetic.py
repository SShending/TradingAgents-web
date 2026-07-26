"""License-safe deterministic provider used by tests and local demo mode."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

from tradingagents.domain import EvidenceField

from .catalog import classify_fund, normalize_name
from .domain import Benchmark, FeeRule, Holding, NavPoint, TransactionStatus
from .providers import CapabilityResult

SYNTHETIC_FUNDS = {
    "900001": {
        "code": "900001",
        "display_name": "示例稳健混合A",
        "provider_fund_type": "混合型",
    },
    "900002": {
        "code": "900002",
        "display_name": "示例稳健混合C",
        "provider_fund_type": "混合型",
    },
    "900101": {
        "code": "900101",
        "display_name": "示例全球指数(QDII)C",
        "provider_fund_type": "QDII-指数型",
    },
    "900201": {
        "code": "900201",
        "display_name": "示例债券基金A",
        "provider_fund_type": "债券型",
    },
}


class SyntheticChinaFundProvider:
    provider_id = "synthetic_phase3_fixture"

    @staticmethod
    def _evidence(name, value, code, effective_at, unit=None):
        retrieved = datetime.now(UTC).isoformat()
        raw_hash = hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()
        return EvidenceField(
            name,
            value,
            unit,
            str(uuid.uuid4()),
            f"fixture://china-funds/{code}/{name}",
            retrieved,
            effective_at,
            effective_at,
            raw_hash,
            "fresh",
            (),
        )

    @staticmethod
    def _identity(code: str):
        item = SYNTHETIC_FUNDS.get(code)
        if item is None:
            return None
        return {
            **item,
            "currency": "CNY",
            "fund_company": "Synthetic Fund Manager",
            "manager_name": "Fixture Manager",
        }

    def search_funds(self, query: str) -> CapabilityResult:
        normalized = normalize_name(query)
        values = tuple(
            value
            for code in SYNTHETIC_FUNDS
            if (value := self._identity(code)) is not None
            and (query == code or normalized in normalize_name(value["display_name"]))
        )
        evidence = (
            self._evidence(
                "identity.search_results",
                [value["code"] for value in values],
                "search",
                date.today().isoformat(),
            ),
        )
        return CapabilityResult(values, evidence, cache_status="fixture")

    def fetch_identity(self, code: str) -> CapabilityResult:
        value = self._identity(code)
        if value is None:
            return CapabilityResult(None)
        return CapabilityResult(
            value,
            (self._evidence("identity", value, code, date.today().isoformat()),),
            cache_status="fixture",
        )

    def fetch_nav(self, code: str, analysis_date: str) -> CapabilityResult:
        cutoff = date.fromisoformat(analysis_date)
        days = [cutoff - timedelta(days=offset) for offset in range(12, -1, -1)]
        trading_days = [value for value in days if value.weekday() < 5]
        points = tuple(
            NavPoint(value.isoformat(), format(1 + index / 100, ".4f"))
            for index, value in enumerate(trading_days)
        )
        return CapabilityResult(
            points,
            (
                self._evidence(
                    "nav_history",
                    [asdict(item) for item in points],
                    code,
                    points[-1].date,
                    "CNY_per_unit",
                ),
            ),
            cache_status="fixture",
        )

    def fetch_transaction_status(self, code: str) -> CapabilityResult:
        observed = datetime.now(UTC).isoformat()
        value = TransactionStatus("open", "open", observed)
        return CapabilityResult(
            value,
            (self._evidence("transaction_status", asdict(value), code, observed[:10]),),
            cache_status="fixture",
        )

    def fetch_fees(self, code: str) -> CapabilityResult:
        value = (
            FeeRule("subscribe", "amount<1,000,000 CNY", "0.15%"),
            FeeRule("redeem", "holding_days<7", "1.50%"),
            FeeRule("redeem", "holding_days>=7", "0.50%"),
        )
        return CapabilityResult(
            value,
            (
                self._evidence(
                    "fees", [asdict(item) for item in value], code, date.today().isoformat()
                ),
            ),
            cache_status="fixture",
        )

    def fetch_disclosure(self, code: str) -> CapabilityResult:
        today = date.today()
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        disclosure = date(today.year, quarter_month, 1) - timedelta(days=1)
        holdings = (
            Holding("SYN001", "Synthetic Holding One", "0.0800", disclosure.isoformat()),
            Holding("SYN002", "Synthetic Holding Two", "0.0600", disclosure.isoformat()),
        )
        value = {
            "manager": {"name": "Fixture Manager", "as_of": today.isoformat()},
            "holdings": holdings,
            "sector_allocation": {"Technology": "0.45", "Other": "0.55"},
            "asset_allocation": {"Equity": "0.90", "Cash": "0.10"},
            "disclosure_date": disclosure.isoformat(),
        }
        serializable = {**value, "holdings": [asdict(item) for item in holdings]}
        return CapabilityResult(
            value,
            (self._evidence("disclosure", serializable, code, disclosure.isoformat()),),
            cache_status="fixture",
        )

    def fetch_benchmark(self, code: str) -> CapabilityResult:
        item = classify_fund(self._identity(code) or {})
        name = (
            "Nasdaq 100 Total Return"
            if item.market_scope.value == "qdii"
            else "CSI 300 Total Return"
        )
        value = Benchmark(name, selected_name=name)
        return CapabilityResult(
            value,
            (self._evidence("benchmark", asdict(value), code, date.today().isoformat()),),
            cache_status="fixture",
        )
