"""Acceptance tests for Phase 3 high-level prompt claims."""

import fubon_api_mcp_server.server as server


def test_supported_phase3_prompts_render_real_data_boundaries():
    prompts = {
        "performance_analytics": server.performance_analytics("account", "1M"),
        "advanced_risk_management": server.advanced_risk_management("account"),
        "portfolio_optimization": server.portfolio_optimization("account", "max_sharpe"),
        "market_sentiment_analysis": server.market_sentiment_analysis("IX0001,2330"),
        "algorithmic_strategy_builder": server.algorithmic_strategy_builder("2330", "momentum"),
        "futures_spread_analyzer": server.futures_spread_analyzer("TXFQ6", "TXFU6", 252),
        "volatility_trading_advisor": server.volatility_trading_advisor("2330"),
    }

    assert len(prompts) == 7
    assert all(text.strip() for text in prompts.values())
    assert "calculate_performance_attribution" in prompts["performance_analytics"]
    assert "calculate_portfolio_var" in prompts["advanced_risk_management"]
    assert "optimize_portfolio_allocation" in prompts["portfolio_optimization"]
    assert "generate_market_sentiment_index" in prompts["market_sentiment_analysis"]
    assert "futures_calendar" in prompts["futures_spread_analyzer"]
    assert "不得聲稱已取得 VIX" in prompts["volatility_trading_advisor"]


def test_unsupported_options_prompt_is_removed():
    assert not hasattr(server, "options_strategy_optimizer")
