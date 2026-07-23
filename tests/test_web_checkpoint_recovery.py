from tradingagents.services.analysis_service import checkpoint_signature, has_valid_checkpoint


def request():
    return {
        "symbol": "SPY", "analysis_date": "2026-07-22", "asset_type": "fund",
        "analysts": ["market", "fundamentals"], "research_depth": 2,
    }


def test_web_checkpoint_signature_matches_graph_shape_contract():
    value = request()
    assert checkpoint_signature(value) == (
        "analysts=market,fundamentals|debate=2|risk=2|asset=fund"
    )
    changed = {**value, "research_depth": 3}
    assert checkpoint_signature(changed) != checkpoint_signature(value)


def test_checkpoint_validation_is_disabled_unless_configured(monkeypatch):
    import tradingagents.services.analysis_service as module

    monkeypatch.setitem(module.DEFAULT_CONFIG, "checkpoint_enabled", False)
    monkeypatch.setattr(module, "has_checkpoint", lambda *_args: True)
    assert has_valid_checkpoint(request()) is False
