from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SYMBOL_RE = re.compile(r"^[A-Za-z0-9._^=\-]{1,32}$")


class ResolveRequest(BaseModel):
    symbol: str
    asset_type: Literal["auto", "stock", "fund", "crypto"] = "auto"

    @field_validator("symbol")
    @classmethod
    def valid_symbol(cls, value: str) -> str:
        value = value.strip()
        if not SYMBOL_RE.fullmatch(value):
            raise ValueError("Invalid symbol")
        return value


class AnalysisCreate(ResolveRequest):
    analysis_date: date
    benchmark_symbol: str = "SPY"
    analysts: list[Literal["market", "social", "news", "fundamentals"]] = Field(min_length=1)
    research_depth: int = Field(default=1, ge=1, le=5)
    llm_provider: str = "openai"
    quick_model: str = "gpt-5.4-mini"
    deep_model: str = "gpt-5.5"
    output_language: str = "English"

    @field_validator("analysis_date")
    @classmethod
    def not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Analysis date cannot be in the future")
        return value

    @field_validator("benchmark_symbol")
    @classmethod
    def valid_benchmark(cls, value: str) -> str:
        if not SYMBOL_RE.fullmatch(value.strip()):
            raise ValueError("Invalid benchmark symbol")
        return value.strip().upper()
