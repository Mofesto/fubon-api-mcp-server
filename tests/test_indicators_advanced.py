#!/usr/bin/env python3
"""
富邦 API MCP Server - Advanced Indicators 單元測試

此測試檔案使用 pytest 框架測試 indicators_advanced 的所有功能。

使用方法：
# 運行所有測試
pytest tests/test_indicators_advanced.py -v

# 只運行模擬測試
pytest tests/test_indicators_advanced.py::TestIndicatorsAdvancedMock -v
"""

import numpy as np
import pandas as pd
import pytest

from fubon_api_mcp_server.indicators_advanced import (
    assess_risk_level,
    calculate_fear_greed_index,
    calculate_historical_var,
    calculate_market_breadth,
    calculate_max_drawdown,
    calculate_money_flow,
    calculate_monte_carlo_var,
    calculate_parametric_var,
    calculate_portfolio_returns,
    calculate_tail_risk,
)


class TestIndicatorsAdvancedMock:
    """模擬測試 - 使用模擬數據測試邏輯"""

    @pytest.fixture
    def sample_stock_data(self):
        """創建樣本股票數據"""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        np.random.seed(42)

        # 生成模擬價格數據
        base_price = 100
        returns = np.random.normal(0.001, 0.02, len(dates))
        prices = base_price * np.exp(np.cumsum(returns))

        return pd.DataFrame(
            {
                "date": dates,
                "open": prices * (1 + np.random.normal(0, 0.01, len(dates))),
                "high": prices * (1 + np.random.normal(0.005, 0.01, len(dates))),
                "low": prices * (1 - np.random.normal(0.005, 0.01, len(dates))),
                "close": prices,
                "volume": np.random.randint(100000, 1000000, len(dates)),
            }
        )

    @pytest.fixture
    def sample_portfolio_positions(self):
        """創建樣本投資組合持倉"""
        return [
            {"stock_no": "2330", "quantity": 1000, "market_value": 100000},
            {"stock_no": "2454", "quantity": 500, "market_value": 50000},
            {"stock_no": "2317", "quantity": 800, "market_value": 80000},
        ]

    @pytest.fixture
    def mock_read_data_func(self, sample_stock_data):
        """模擬數據讀取函數"""

        def read_func(symbol):
            if symbol in ["2330", "2454", "2317"]:
                return sample_stock_data.copy()
            return None

        return read_func

    def test_calculate_portfolio_returns_success(self, sample_portfolio_positions, mock_read_data_func):
        """測試計算投資組合收益率 - 成功情況"""
        returns = calculate_portfolio_returns(sample_portfolio_positions, 60, mock_read_data_func)

        assert returns is not None
        assert isinstance(returns, pd.Series)
        assert len(returns) > 0
        assert all(isinstance(r, (int, float)) for r in returns)

    def test_calculate_portfolio_returns_empty_positions(self, mock_read_data_func):
        """測試計算投資組合收益率 - 空持倉"""
        returns = calculate_portfolio_returns([], 60, mock_read_data_func)
        assert returns is None

    def test_calculate_portfolio_returns_zero_value(self, mock_read_data_func):
        """測試計算投資組合收益率 - 市值為零"""
        positions = [{"stock_no": "2330", "quantity": 0, "market_value": 0}]
        returns = calculate_portfolio_returns(positions, 60, mock_read_data_func)
        assert returns is None

    def test_calculate_portfolio_returns_insufficient_data(self, sample_portfolio_positions):
        """測試計算投資組合收益率 - 數據不足"""

        def mock_read_insufficient(symbol):
            # 返回少於20天的數據
            dates = pd.date_range("2024-01-01", periods=10, freq="D")
            return pd.DataFrame({"date": dates, "close": np.random.uniform(90, 110, 10)})

        returns = calculate_portfolio_returns(sample_portfolio_positions, 60, mock_read_insufficient)
        assert returns is None

    def test_calculate_historical_var(self, sample_stock_data):
        """測試歷史模擬法計算 VaR"""
        returns = sample_stock_data["close"].pct_change().dropna()
        total_value = 1000000

        result = calculate_historical_var(returns, 0.95, total_value)

        assert "var" in result
        assert "var_pct" in result
        assert "cvar" in result
        assert "cvar_pct" in result
        assert result["var"] > 0
        assert result["var_pct"] > 0
        assert result["cvar"] >= result["var"]

    def test_calculate_parametric_var(self, sample_stock_data):
        """測試參數法計算 VaR"""
        returns = sample_stock_data["close"].pct_change().dropna()
        total_value = 1000000

        result = calculate_parametric_var(returns, 0.95, total_value)

        assert "var" in result
        assert "var_pct" in result
        assert "cvar" in result
        assert "cvar_pct" in result
        assert result["var"] > 0
        assert result["var_pct"] > 0

    def test_calculate_monte_carlo_var(self, sample_stock_data):
        """測試蒙地卡羅模擬法計算 VaR"""
        returns = sample_stock_data["close"].pct_change().dropna()
        total_value = 1000000

        result = calculate_monte_carlo_var(returns, 0.95, total_value, 10000)

        assert "var" in result
        assert "var_pct" in result
        assert "cvar" in result
        assert "cvar_pct" in result
        assert result["var"] > 0
        assert result["var_pct"] > 0

    def test_calculate_max_drawdown(self, sample_stock_data):
        """測試計算最大回撤"""
        returns = sample_stock_data["close"].pct_change().dropna()
        total_value = 1000000

        result = calculate_max_drawdown(returns, total_value)

        assert "max_dd" in result
        assert "max_dd_pct" in result
        assert "duration" in result
        assert "current_dd" in result
        assert result["max_dd"] >= 0
        assert result["max_dd_pct"] >= 0
        assert result["duration"] >= 0
        assert result["current_dd"] >= 0

    def test_calculate_tail_risk(self, sample_stock_data):
        """測試計算尾部風險指標"""
        returns = sample_stock_data["close"].pct_change().dropna()

        result = calculate_tail_risk(returns, 0.95)

        assert "skewness" in result
        assert "kurtosis" in result
        assert "tail_ratio" in result
        assert "expected_shortfall" in result
        assert isinstance(result["skewness"], (int, float))
        assert isinstance(result["kurtosis"], (int, float))
        assert result["tail_ratio"] > 0
        assert result["expected_shortfall"] >= 0

    def test_assess_risk_level_extreme_high(self):
        """測試風險等級評估 - 極高風險"""
        level = assess_risk_level(0.06, 0.35, 0.35)
        assert level == "極高風險"

    def test_assess_risk_level_high(self):
        """測試風險等級評估 - 高風險"""
        level = assess_risk_level(0.04, 0.25, 0.25)
        assert level == "高風險"

    def test_assess_risk_level_medium(self):
        """測試風險等級評估 - 中等風險"""
        level = assess_risk_level(0.025, 0.18, 0.15)
        assert level == "中等風險"

    def test_assess_risk_level_low(self):
        """測試風險等級評估 - 低風險"""
        level = assess_risk_level(0.021, 0.14, 0.09)
        assert level == "低風險"

    def test_assess_risk_level_extreme_low(self):
        """測試風險等級評估 - 極低風險"""
        level = assess_risk_level(0.01, 0.08, 0.05)
        assert level == "極低風險"

    def test_calculate_market_breadth_success(self, mock_read_data_func):
        """測試計算市場廣度指標 - 成功情況"""
        symbols = ["2330", "2454", "2317"]

        result = calculate_market_breadth(symbols, mock_read_data_func)

        assert "advance_decline_ratio" in result
        assert "advancing_stocks" in result
        assert "declining_stocks" in result
        assert "new_high_low_ratio" in result
        assert "composite_score" in result
        assert result["advance_decline_ratio"] >= 0
        assert result["advance_decline_ratio"] <= 1

    def test_calculate_market_breadth_empty_symbols(self, mock_read_data_func):
        """測試計算市場廣度指標 - 空符號列表"""
        result = calculate_market_breadth([], mock_read_data_func)
        assert result["advance_decline_ratio"] == 0.5
        assert result["composite_score"] == 0.5

    def test_calculate_market_breadth_no_data(self):
        """測試計算市場廣度指標 - 無數據"""

        def mock_read_none(symbol):
            return None

        symbols = ["INVALID"]
        result = calculate_market_breadth(symbols, mock_read_none)
        assert result["advance_decline_ratio"] == 0.5
        assert result["composite_score"] == 0.5

    def test_calculate_money_flow_success(self, sample_stock_data):
        """測試計算資金流向指標 - 成功情況"""
        result = calculate_money_flow(sample_stock_data)

        assert "mfi" in result
        assert "positive_flow" in result
        assert "negative_flow" in result
        assert "positive_flow_ratio" in result
        assert "composite_score" in result
        assert 0 <= result["mfi"] <= 100
        assert result["positive_flow"] >= 0
        assert result["negative_flow"] >= 0

    def test_calculate_money_flow_insufficient_data(self):
        """測試計算資金流向指標 - 數據不足"""
        df = pd.DataFrame({"high": [100, 101], "low": [99, 100], "close": [100, 101], "volume": [1000, 1100]})

        result = calculate_money_flow(df)
        assert result["mfi"] == 50
        assert result["composite_score"] == 0.5

    def test_calculate_money_flow_empty_data(self):
        """測試計算資金流向指標 - 空數據"""
        result = calculate_money_flow(None)
        assert result["mfi"] == 50
        assert result["composite_score"] == 0.5

    def test_calculate_fear_greed_index_extreme_fear(self):
        """測試恐懼貪婪指數 - 極度恐懼"""
        result = calculate_fear_greed_index(0.1, 0.1, 0.1)

        assert "fear_greed_index" in result
        assert "level" in result
        assert "sentiment" in result
        assert result["level"] == "極度恐懼"
        assert result["sentiment"] == "市場恐慌"

    def test_calculate_fear_greed_index_fear(self):
        """測試恐懼貪婪指數 - 恐懼"""
        result = calculate_fear_greed_index(0.3, 0.3, 0.3)
        assert result["level"] == "恐懼"
        assert result["sentiment"] == "市場悲觀"

    def test_calculate_fear_greed_index_neutral(self):
        """測試恐懼貪婪指數 - 中性"""
        result = calculate_fear_greed_index(0.5, 0.5, 0.5)
        assert result["level"] == "中性"
        assert result["sentiment"] == "市場平衡"

    def test_calculate_fear_greed_index_greed(self):
        """測試恐懼貪婪指數 - 貪婪"""
        result = calculate_fear_greed_index(0.6, 0.6, 0.6)
        assert result["level"] == "貪婪"
        assert result["sentiment"] == "市場樂觀"

    def test_calculate_fear_greed_index_extreme_greed(self):
        """測試恐懼貪婪指數 - 極度貪婪"""
        result = calculate_fear_greed_index(0.9, 0.9, 0.9)
        assert result["level"] == "極度貪婪"
        assert result["sentiment"] == "市場過熱"

    def test_calculate_var_edge_cases(self):
        """測試 VaR 計算的邊界情況"""
        # 空收益率序列
        empty_returns = pd.Series([], dtype=float)
        result = calculate_historical_var(empty_returns, 0.95, 1000000)
        # 應該不會崩潰，但結果可能不合理

        # 單一收益率
        single_return = pd.Series([0.01])
        result = calculate_historical_var(single_return, 0.95, 1000000)
        assert "var" in result

    def test_calculate_drawdown_edge_cases(self):
        """測試回撤計算的邊界情況"""
        # 空收益率序列
        empty_returns = pd.Series([], dtype=float)
        result = calculate_max_drawdown(empty_returns, 1000000)
        assert result["max_dd"] == 0

        # 單一收益率
        single_return = pd.Series([0.01])
        result = calculate_max_drawdown(single_return, 1000000)
        assert result["max_dd"] == 0

    def test_calculate_tail_risk_edge_cases(self):
        """測試尾部風險計算的邊界情況"""
        # 空收益率序列
        empty_returns = pd.Series([], dtype=float)
        result = calculate_tail_risk(empty_returns, 0.95)
        # 應該不會崩潰

        # 單一收益率
        single_return = pd.Series([0.01])
        result = calculate_tail_risk(single_return, 0.95)
        assert "skewness" in result
