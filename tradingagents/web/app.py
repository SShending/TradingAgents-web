"""FastAPI application factory for the local Fund workspace."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import yfinance as yf
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from tradingagents.instruments import InstrumentNotFoundError, resolve_instrument
from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.llm_clients.model_catalog import get_model_options
from tradingagents.services.analysis_service import DemoAnalysisService, GraphAnalysisService

from .jobs import JobBusyError, JobManager
from .schemas import AnalysisCreate, ResolveRequest


def _price_probe(symbol: str) -> bool:
    try:
        return not yf.Ticker(symbol).history(period="5d").empty
    except Exception:
        return False


def _demo_identity(symbol: str) -> dict[str, str]:
    values = {
        "SPY": {"company_name": "SPDR S&P 500 ETF Trust", "quote_type": "ETF", "exchange": "PCX", "currency": "USD"},
        "VFIAX": {"company_name": "Vanguard 500 Index Admiral", "quote_type": "MUTUALFUND", "exchange": "NAS", "currency": "USD"},
        "AAPL": {"company_name": "Apple Inc.", "quote_type": "EQUITY", "exchange": "NMS", "currency": "USD"},
        "EMPTY": {"company_name": "Holdings Coverage Example", "quote_type": "ETF", "exchange": "PCX", "currency": "USD"},
        "FAIL": {"company_name": "Provider Failure Example", "quote_type": "ETF", "exchange": "PCX", "currency": "USD"},
        "SLOW": {"company_name": "Cancellation Example Fund", "quote_type": "ETF", "exchange": "PCX", "currency": "USD"},
    }
    return values.get(symbol.upper(), {})


def create_app(*, demo: bool | None = None, manager: JobManager | None = None) -> FastAPI:
    demo = (os.getenv("TRADINGAGENTS_WEB_DEMO") == "1") if demo is None else demo
    service = DemoAnalysisService() if demo else GraphAnalysisService()
    manager = manager or JobManager(service)
    app = FastAPI(title="TradingAgents Fund Workspace", version="0.1.0")
    app.state.jobs = manager
    app.state.demo = demo
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("TRADINGAGENTS_WEB_ORIGIN", "http://127.0.0.1:5173")],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "demo" if demo else "live"}

    @app.get("/api/config/options")
    def options():
        providers = []
        for provider in ("openai", "anthropic", "google", "ollama", "openai_compatible"):
            key_name = get_api_key_env(provider)
            providers.append({
                "id": provider,
                "configured": demo or not key_name or bool(os.getenv(key_name)),
                "models": {
                    "quick": [value for _, value in get_model_options(provider, "quick")][:12],
                    "deep": [value for _, value in get_model_options(provider, "deep")][:12],
                },
            })
        return {
            "asset_types": ["auto", "stock", "fund", "crypto"],
            "analysts": ["market", "social", "news", "fundamentals"],
            "languages": ["English", "Chinese", "Spanish", "French", "Japanese"],
            "providers": providers,
        }

    @app.post("/api/instruments/resolve")
    def resolve(body: ResolveRequest):
        try:
            descriptor = resolve_instrument(
                body.symbol,
                body.asset_type,
                identity_resolver=_demo_identity if demo else None,
                price_probe=(lambda _symbol: True) if demo else _price_probe,
            )
        except InstrumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"code": "INSTRUMENT_NOT_FOUND", "message": str(exc)}) from exc
        return descriptor.to_dict()

    @app.post("/api/analyses", status_code=202)
    def create_analysis(body: AnalysisCreate):
        request_data = body.model_dump(mode="json")
        descriptor = resolve_instrument(
            body.symbol,
            body.asset_type,
            identity_resolver=_demo_identity if demo else None,
            price_probe=(lambda _symbol: True) if demo else _price_probe,
        )
        request_data["symbol"] = descriptor.canonical_symbol
        request_data["asset_type"] = descriptor.asset_type.value
        try:
            job = manager.create(request_data)
        except JobBusyError as exc:
            raise HTTPException(status_code=409, detail={"code": "JOB_BUSY", "message": str(exc)}) from exc
        return {"job_id": job.id, "status": job.status}

    def require_job(job_id: str):
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": "Unknown or expired analysis job"})
        return job

    @app.get("/api/analyses/{job_id}")
    def get_analysis(job_id: str):
        return require_job(job_id).public()

    @app.get("/api/analyses/{job_id}/events")
    def events(job_id: str, request: Request, last_event_id: str | None = Header(default=None)):
        job = require_job(job_id)
        raw = last_event_id or request.query_params.get("last_event_id") or "0"
        try:
            cursor = max(0, int(raw))
        except ValueError:
            cursor = 0
        return StreamingResponse(manager.event_stream(job, cursor), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/analyses/{job_id}/cancel")
    def cancel(job_id: str):
        job = require_job(job_id)
        manager.cancel(job)
        return {"job_id": job.id, "status": job.status}

    @app.get("/api/analyses/{job_id}/report.md")
    def report(job_id: str):
        job = require_job(job_id)
        if job.status != "completed" or not job.result:
            raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY", "message": "Report is not ready"})
        result = job.result
        title = result.get("company_of_interest", job.request["symbol"])
        asset = result.get("asset_type", job.request["asset_type"])
        lines = [
            f"# Trading Analysis Report: {title}",
            "",
            f"- Asset type: {asset}",
            f"- Analysis date: {result.get('trade_date', job.request['analysis_date'])}",
            f"- Benchmark: {result.get('benchmark_symbol', job.request.get('benchmark_symbol', 'SPY'))}",
            f"- Generated: {result.get('generated_at', date.today().isoformat())}",
        ]
        for key, heading in (("market_report", "Market Analysis"), ("sentiment_report", "Sentiment Analysis"), ("news_report", "News Analysis"), ("fundamentals_report", "Fund Analysis" if asset == "fund" else "Fundamentals Analysis"), ("investment_plan", "Research Decision"), ("trader_investment_plan", "Trading Plan"), ("final_trade_decision", "Final Decision")):
            if result.get(key):
                lines.extend(["", f"## {heading}", "", str(result[key])])
        filename = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in title)[:48]
        return PlainTextResponse("\n".join(lines), headers={"Content-Disposition": f'attachment; filename="{filename}_report.md"'})

    dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
