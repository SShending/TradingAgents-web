import inspect

from tradingagents.agents.analysts import fundamentals_analyst
from tradingagents.graph.trading_graph import TradingAgentsGraph


def test_fund_prompt_is_fund_specific_and_excludes_company_metrics():
    source = inspect.getsource(fundamentals_analyst)
    fund_branch = source.split('if state.get("asset_type") == "fund":', 1)[1].split("else:", 1)[0]
    assert "Fund Analysis" in fund_branch
    assert "get_fund_profile" in fund_branch
    for forbidden in ("balance_sheet", "cashflow", "income_statement", "revenue", "EPS"):
        assert forbidden not in fund_branch


def test_fund_and_company_tools_share_execution_node_for_runtime_binding():
    source = inspect.getsource(TradingAgentsGraph._create_tool_nodes)
    for tool_name in (
        "get_fund_profile",
        "get_fund_holdings",
        "get_fund_performance",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
    ):
        assert tool_name in source
