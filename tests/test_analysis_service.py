#!/usr/bin/env python3
"""
富邦 API MCP Server - Analysis Service 單元測試

此測試檔案使用 pytest 框架測試 analysis_service 的所有功能。
測試分為兩類：
1. 模擬測試：使用 mock 物件測試邏輯
2. 整合測試：使用真實 API 測試（需要環境變數）

使用方法：
# 運行所有測試
pytest tests/test_analysis_service.py -v

# 只運行模擬測試
pytest tests/test_analysis_service.py::TestAnalysisServiceMock -v

# 只運行整合測試（需要真實憑證）
pytest tests/test_analysis_service.py::TestAnalysisServiceIntegration -v
"""

import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from fubon_api_mcp_server.analysis_service import AnalysisService


class TestAnalysisServiceMock:
    """模擬測試 - 不依賴真實 API"""

    @pytest.fixture
    def mock_mcp(self):
        """模擬 MCP 實例"""
        return Mock()

    @pytest.fixture
    def mock_sdk(self):
        """模擬 SDK 實例"""
        sdk = Mock()
        return sdk

    @pytest.fixture
    def mock_accounts(self):
        """模擬帳戶列表"""
        return ["1234567"]

    @pytest.fixture
    def mock_reststock(self):
        """模擬股票 REST 客戶端"""
        return Mock()

    @pytest.fixture
    def mock_restfutopt(self):
        """模擬期貨/選擇權 REST 客戶端"""
        return Mock()

    @pytest.fixture
    def base_data_dir(self, tmp_path):
        """臨時數據目錄"""
        return tmp_path / "data"

    @pytest.fixture
    def analysis_service(self, mock_mcp, mock_sdk, mock_accounts, mock_reststock, mock_restfutopt, base_data_dir):
        """建立 AnalysisService 實例"""
        return AnalysisService(mock_mcp, mock_sdk, mock_accounts, mock_reststock, mock_restfutopt)

    def test_initialization(self, analysis_service):
        """測試 AnalysisService 初始化"""
        assert analysis_service.mcp is not None
        assert analysis_service.sdk is not None
        assert analysis_service.accounts is not None
        assert analysis_service.reststock is not None
        assert analysis_service.restfutopt is not None

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_calculate_portfolio_var_historical(self, mock_validate, analysis_service):
        """測試計算投資組合VaR - 歷史模擬法"""
        # 模擬帳戶驗證
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬投資組合數據
        mock_portfolio = {
            "inventory": [
                {"stock_no": "2330", "market_value": 100000, "quantity": 1000},
                {"stock_no": "2454", "market_value": 50000, "quantity": 500},
            ]
        }

        with patch.object(analysis_service, "_get_portfolio_data", return_value=mock_portfolio):
            with patch.object(analysis_service, "_calculate_portfolio_volatility", return_value=0.15):
                result = analysis_service.calculate_portfolio_var(
                    {"account": "1234567", "confidence_level": 0.95, "time_horizon": 1, "method": "historical"}
                )

        assert result["status"] == "success"
        assert "var_estimate" in result["data"]
        assert "var_percentage" in result["data"]
        assert result["data"]["confidence_level"] == 0.95
        assert result["data"]["method"] == "historical"
        assert "成功計算投資組合VaR" in result["message"]

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_calculate_portfolio_var_parametric(self, mock_validate, analysis_service):
        """測試計算投資組合VaR - 參數法"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_portfolio = {"inventory": [{"stock_no": "2330", "market_value": 100000, "quantity": 1000}]}

        with patch.object(analysis_service, "_get_portfolio_data", return_value=mock_portfolio):
            with patch.object(analysis_service, "_calculate_portfolio_volatility", return_value=0.15):
                result = analysis_service.calculate_portfolio_var(
                    {"account": "1234567", "confidence_level": 0.99, "time_horizon": 1, "method": "parametric"}
                )

        assert result["status"] == "success"
        assert result["data"]["confidence_level"] == 0.99
        assert result["data"]["method"] == "parametric"

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_run_portfolio_stress_test_market_crash(self, mock_validate, analysis_service):
        """測試投資組合壓力測試 - 市場崩盤情境"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_portfolio = {"inventory": [{"stock_no": "2330", "market_value": 100000, "quantity": 1000}]}

        with patch.object(analysis_service, "_get_portfolio_data", return_value=mock_portfolio):
            with patch.object(analysis_service, "_calculate_market_crash_sensitivity", return_value=1.2):
                result = analysis_service.run_portfolio_stress_test(
                    {"account": "1234567", "scenarios": [{"name": "market_crash", "equity_drop": -0.3}]}
                )

        assert result["status"] == "success"
        assert "stress_test_results" in result["data"]
        assert len(result["data"]["stress_test_results"]) == 1
        assert result["data"]["stress_test_results"][0]["scenario"] == "market_crash"
        assert "total_projected_loss" in result["data"]["stress_test_results"][0]
        assert "成功執行 1 個壓力測試情境" in result["message"]

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_run_portfolio_stress_test_rate_hike(self, mock_validate, analysis_service):
        """測試投資組合壓力測試 - 利率上升情境"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_portfolio = {"inventory": [{"stock_no": "2330", "market_value": 100000, "quantity": 1000}]}

        with patch.object(analysis_service, "_get_portfolio_data", return_value=mock_portfolio):
            with patch.object(analysis_service, "_calculate_rate_sensitivity", return_value=0.8):
                result = analysis_service.run_portfolio_stress_test(
                    {"account": "1234567", "scenarios": [{"name": "rate_hike", "rate_increase": 0.025}]}
                )

        assert result["status"] == "success"
        assert result["data"]["stress_test_results"][0]["scenario"] == "rate_hike"

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_optimize_portfolio_allocation_max_sharpe(self, mock_validate, analysis_service):
        """測試投資組合優化 - 最大夏普比率"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_portfolio = {
            "inventory": [
                {"stock_no": "2330", "market_value": 100000, "quantity": 1000},
                {"stock_no": "2454", "market_value": 50000, "quantity": 500},
            ]
        }

        with patch.object(analysis_service, "_get_portfolio_data", return_value=mock_portfolio):
            result = analysis_service.optimize_portfolio_allocation(
                {"account": "1234567", "optimization_method": "max_sharpe"}
            )

        assert result["status"] == "success"
        assert "current_weights" in result["data"]
        assert "optimized_weights" in result["data"]
        assert result["data"]["optimization_method"] == "max_sharpe"
        assert "expected_annual_return" in result["data"]
        assert "expected_volatility" in result["data"]
        assert "sharpe_ratio" in result["data"]
        assert "成功執行max_sharpe投資組合優化" in result["message"]

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_calculate_performance_attribution(self, mock_validate, analysis_service):
        """測試績效歸因分析"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_portfolio = {"inventory": [{"stock_no": "2330", "market_value": 100000, "quantity": 1000}]}

        with patch.object(analysis_service, "_get_portfolio_data", return_value=mock_portfolio):
            result = analysis_service.calculate_performance_attribution(
                {"account": "1234567", "benchmark": "TWII", "period": "3M"}
            )

        assert result["status"] == "success"
        assert "total_portfolio_return" in result["data"]
        assert "benchmark_return" in result["data"]
        assert "excess_return" in result["data"]
        assert "attribution_breakdown" in result["data"]
        assert result["data"]["benchmark"] == "TWII"
        assert result["data"]["period"] == "3M"
        assert "成功計算3M期間相對於TWII的績效歸因" in result["message"]

    def test_detect_arbitrage_opportunities_cash_futures(self, analysis_service):
        """測試套利機會偵測 - 現貨vs期貨"""
        result = analysis_service.detect_arbitrage_opportunities({"symbols": ["2330"], "arbitrage_types": ["cash_futures"]})

        assert result["status"] == "success"
        assert "opportunities_found" in result["data"]
        assert "total_opportunities" in result["data"]
        assert "scan_timestamp" in result["data"]
        assert "成功掃描套利機會" in result["message"]

    def test_detect_arbitrage_opportunities_statistical(self, analysis_service):
        """測試套利機會偵測 - 統計套利"""
        result = analysis_service.detect_arbitrage_opportunities({"symbols": ["2330"], "arbitrage_types": ["statistical"]})

        assert result["status"] == "success"
        assert result["data"]["arbitrage_types"] == ["statistical"]

    @patch("fubon_api_mcp_server.analysis_service.indicators")
    def test_generate_market_sentiment_index_with_data(self, mock_indicators, analysis_service):
        """測試生成市場情緒指數 - 有數據"""
        # 模擬技術指標計算結果
        mock_rsi = pd.Series([45.0, 55.0, 65.0])
        mock_macd = pd.DataFrame({"histogram": [0.5, -0.2, 1.0]})
        mock_bb = pd.DataFrame({"upper": [110, 112, 115], "lower": [90, 88, 85]})
        mock_vol_rate = pd.Series([1.2, 0.8, 1.5])
        mock_obv = pd.Series([1000, 1200, 1100])

        mock_indicators.calculate_rsi.return_value = mock_rsi
        mock_indicators.calculate_macd.return_value = mock_macd
        mock_indicators.calculate_bollinger_bands.return_value = mock_bb
        mock_indicators.calculate_volume_rate.return_value = mock_vol_rate
        mock_indicators.calculate_obv.return_value = mock_obv

        # 模擬本地數據
        mock_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                "close": [100, 105, 110],
                "high": [105, 110, 115],
                "low": [95, 100, 105],
                "volume": [1000, 1100, 1200],
            }
        )

        with patch.object(analysis_service, "_read_local_stock_data", return_value=mock_df):
            result = analysis_service.generate_market_sentiment_index(
                {"index_components": ["technical", "volume"], "lookback_period": 30}
            )

        assert result["status"] == "success"
        assert "overall_sentiment_index" in result["data"]
        assert "sentiment_level" in result["data"]
        assert "risk_level" in result["data"]
        assert "components" in result["data"]
        assert "technical" in result["data"]["components"]
        assert "volume" in result["data"]["components"]
        assert "成功生成市場情緒指數" in result["message"]

    def test_generate_market_sentiment_index_no_data(self, analysis_service):
        """測試生成市場情緒指數 - 無數據"""
        with patch.object(analysis_service, "_read_local_stock_data", return_value=None):
            result = analysis_service.generate_market_sentiment_index(
                {"index_components": ["technical"], "lookback_period": 30}
            )

        assert result["status"] == "success"
        assert "overall_sentiment_index" in result["data"]
        assert result["data"]["data_source"] == "simulated"

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_calculate_portfolio_var_no_portfolio_data(self, mock_validate, analysis_service):
        """測試計算VaR - 無投資組合數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        with patch.object(analysis_service, "_get_portfolio_data", return_value=None):
            result = analysis_service.calculate_portfolio_var({"account": "1234567"})

        assert result["status"] == "error"
        assert "無法獲取投資組合數據" in result["message"]

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_run_portfolio_stress_test_no_portfolio_data(self, mock_validate, analysis_service):
        """測試壓力測試 - 無投資組合數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        with patch.object(analysis_service, "_get_portfolio_data", return_value=None):
            result = analysis_service.run_portfolio_stress_test({"account": "1234567", "scenarios": [{"name": "test"}]})

        assert result["status"] == "error"
        assert "無法獲取投資組合數據" in result["message"]

    def test_calculate_portfolio_volatility_empty_positions(self, analysis_service):
        """測試計算投資組合波動率 - 空持倉"""
        volatility = analysis_service._calculate_portfolio_volatility([])
        assert volatility == 0.15  # 默認波動率

    def test_calculate_portfolio_volatility_with_data(self, analysis_service):
        """測試計算投資組合波動率 - 有數據"""
        positions = [{"stock_no": "2330", "market_value": 100000}]

        mock_df = pd.DataFrame({"close": [100, 101, 102, 103, 104] * 5})  # 25個數據點

        with patch.object(analysis_service, "_read_local_stock_data", return_value=mock_df):
            volatility = analysis_service._calculate_portfolio_volatility(positions, 1)
            assert isinstance(volatility, float)
            assert volatility >= 0.05  # 最小波動率

    def test_calculate_market_crash_sensitivity_no_data(self, analysis_service):
        """測試計算市場崩盤敏感度 - 無數據"""
        with patch.object(analysis_service, "_read_local_stock_data", return_value=None):
            sensitivity = analysis_service._calculate_market_crash_sensitivity("2330")
            assert sensitivity == 1.0  # 默認敏感度

    def test_calculate_rate_sensitivity_no_data(self, analysis_service):
        """測試計算利率敏感度 - 無數據"""
        with patch.object(analysis_service, "_read_local_stock_data", return_value=None):
            sensitivity = analysis_service._calculate_rate_sensitivity("2330")
            assert sensitivity == 0.8  # 默認敏感度

    def test_read_local_stock_data_success(self, analysis_service):
        """測試讀取本地股票數據 - 成功"""
        mock_df = pd.DataFrame({"symbol": ["2330"], "date": ["2024-01-01"], "close": [100]})

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_connect.return_value.__exit__.return_value = None

            with patch("fubon_api_mcp_server.analysis_service.pd.read_sql_query", return_value=mock_df):
                with patch("fubon_api_mcp_server.analysis_service.pd.to_datetime") as mock_to_datetime:
                    mock_to_datetime.return_value = pd.to_datetime(["2024-01-01"])
                    result = analysis_service._read_local_stock_data("2330")

        assert result is not None
        assert len(result) == 1

    def test_read_local_stock_data_error(self, analysis_service):
        """測試讀取本地股票數據 - 錯誤"""
        with patch("sqlite3.connect") as mock_connect:
            mock_connect.side_effect = Exception("Database error")
            result = analysis_service._read_local_stock_data("2330")
            assert result is None

    def test_analyze_stock_success(self, analysis_service):
        """測試股票分析 - 成功"""
        # Create sample data (100 days)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        # Make close price trend up to trigger bullish signal
        close_prices = np.linspace(100, 150, 100) + np.random.randn(100)

        data = {
            "date": dates,
            "open": close_prices - 1,
            "high": close_prices + 2,
            "low": close_prices - 2,
            "close": close_prices,
            "volume": np.random.randint(1000, 10000, 100),
            "price_change": np.random.randn(100),
            "change_ratio": np.random.randn(100),
        }
        df = pd.DataFrame(data)

        with patch.object(analysis_service, "_read_local_stock_data", return_value=df):
            result = analysis_service.analyze_stock({"symbol": "2330"})

        assert result["status"] == "success"
        assert "trend" in result["data"]
        assert "analysis" in result["data"]
        assert "plan" in result["data"]["analysis"]
        # Check if indicators are calculated
        assert "rsi" in result["data"]["indicators"]
        assert "macd" in result["data"]["indicators"]

    def test_analyze_stock_insufficient_data(self, analysis_service):
        """測試股票分析 - 數據不足"""
        # Create sample data (only 10 days)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=10)
        data = {
            "date": dates,
            "close": np.random.randn(10) + 100,
            "high": np.random.randn(10) + 105,
            "low": np.random.randn(10) + 95,
            "volume": np.random.randint(1000, 10000, 10),
            "price_change": np.random.randn(10),
            "change_ratio": np.random.randn(10),
        }
        df = pd.DataFrame(data)

        with patch.object(analysis_service, "_read_local_stock_data", return_value=df):
            # Mock reststock to be None so it doesn't try to fetch
            analysis_service.reststock = None
            result = analysis_service.analyze_stock({"symbol": "2330"})

        assert result["status"] == "error"
        assert "數據不足" in result["message"]

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_calculate_portfolio_var_no_portfolio_data(self, mock_validate, analysis_service):
        """測試計算VaR - 無投資組合數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        with patch.object(analysis_service, "_get_portfolio_data", return_value=None):
            result = analysis_service.calculate_portfolio_var({"account": "1234567"})

        assert result["status"] == "error"
        assert "無法獲取投資組合數據" in result["message"]

    @patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
    def test_run_portfolio_stress_test_no_portfolio_data(self, mock_validate, analysis_service):
        """測試壓力測試 - 無投資組合數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        with patch.object(analysis_service, "_get_portfolio_data", return_value=None):
            result = analysis_service.run_portfolio_stress_test({"account": "1234567", "scenarios": [{"name": "test"}]})

        assert result["status"] == "error"
        assert "無法獲取投資組合數據" in result["message"]

    def test_calculate_portfolio_volatility_empty_positions(self, analysis_service):
        """測試計算投資組合波動率 - 空持倉"""
        volatility = analysis_service._calculate_portfolio_volatility([])
        assert volatility == 0.15  # 默認波動率

    def test_calculate_portfolio_volatility_with_data(self, analysis_service):
        """測試計算投資組合波動率 - 有數據"""
        positions = [{"stock_no": "2330", "market_value": 100000}]

        mock_df = pd.DataFrame({"close": [100, 101, 102, 103, 104] * 5})  # 25個數據點

        with patch.object(analysis_service, "_read_local_stock_data", return_value=mock_df):
            volatility = analysis_service._calculate_portfolio_volatility(positions, 1)
            assert isinstance(volatility, float)
            assert volatility >= 0.05  # 最小波動率

    def test_calculate_market_crash_sensitivity_no_data(self, analysis_service):
        """測試計算市場崩盤敏感度 - 無數據"""
        with patch.object(analysis_service, "_read_local_stock_data", return_value=None):
            sensitivity = analysis_service._calculate_market_crash_sensitivity("2330")
            assert sensitivity == 1.0  # 默認敏感度

    def test_calculate_rate_sensitivity_no_data(self, analysis_service):
        """測試計算利率敏感度 - 無數據"""
        with patch.object(analysis_service, "_read_local_stock_data", return_value=None):
            sensitivity = analysis_service._calculate_rate_sensitivity("2330")
            assert sensitivity == 0.8  # 默認敏感度

    def test_read_local_stock_data_success(self, analysis_service):
        """測試讀取本地股票數據 - 成功"""
        mock_df = pd.DataFrame({"symbol": ["2330"], "date": ["2024-01-01"], "close": [100]})

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_connect.return_value.__exit__.return_value = None

            with patch("fubon_api_mcp_server.analysis_service.pd.read_sql_query", return_value=mock_df):
                with patch("fubon_api_mcp_server.analysis_service.pd.to_datetime") as mock_to_datetime:
                    mock_to_datetime.return_value = pd.to_datetime(["2024-01-01"])
                    result = analysis_service._read_local_stock_data("2330")

        assert result is not None
        assert len(result) == 1

    def test_read_local_stock_data_error(self, analysis_service):
        """測試讀取本地股票數據 - 錯誤"""
        with patch("sqlite3.connect") as mock_connect:
            mock_connect.side_effect = Exception("Database error")
            result = analysis_service._read_local_stock_data("2330")
            assert result is None

    def test_analyze_stock_success(self, analysis_service):
        """測試股票分析 - 成功"""
        # Create sample data (100 days)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        # Make close price trend up to trigger bullish signal
        close_prices = np.linspace(100, 150, 100) + np.random.randn(100)

        data = {
            "date": dates,
            "open": close_prices - 1,
            "high": close_prices + 2,
            "low": close_prices - 2,
            "close": close_prices,
            "volume": np.random.randint(1000, 10000, 100),
            "price_change": np.random.randn(100),
            "change_ratio": np.random.randn(100),
        }
        df = pd.DataFrame(data)

        with patch.object(analysis_service, "_read_local_stock_data", return_value=df):
            result = analysis_service.analyze_stock({"symbol": "2330"})

        assert result["status"] == "success"
        assert "trend" in result["data"]
        assert "analysis" in result["data"]
        assert "plan" in result["data"]["analysis"]
        # Check if indicators are calculated
        assert "rsi" in result["data"]["indicators"]
        assert "macd" in result["data"]["indicators"]

    def test_analyze_stock_insufficient_data(self, analysis_service):
        """測試股票分析 - 數據不足"""
        # Create sample data (only 10 days)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=10)
        data = {
            "date": dates,
            "close": np.random.randn(10) + 100,
            "high": np.random.randn(10) + 105,
            "low": np.random.randn(10) + 95,
            "volume": np.random.randint(1000, 10000, 10),
            "price_change": np.random.randn(10),
            "change_ratio": np.random.randn(10),
        }
        df = pd.DataFrame(data)

        with patch.object(analysis_service, "_read_local_stock_data", return_value=df):
            # Mock reststock to be None so it doesn't try to fetch
            analysis_service.reststock = None
            result = analysis_service.analyze_stock({"symbol": "2330"})

        assert result["status"] == "error"
        assert "數據不足" in result["message"]


class TestAnalysisServiceIntegration:
    """整合測試 - 使用真實 API（需要環境變數）"""

    @pytest.fixture
    def real_analysis_service(self):
        """使用真實憑證建立 AnalysisService"""
        import os

        from dotenv import load_dotenv
        from fubon_neo.sdk import FubonSDK
        from mcp.server.fastmcp import FastMCP

        # 檢查環境變數
        load_dotenv()
        required_env = ["FUBON_USERNAME", "FUBON_PASSWORD", "FUBON_PFX_PATH"]
        if not all(os.getenv(env) for env in required_env):
            pytest.skip("需要真實 API 憑證才能運行整合測試")

        # 初始化真實 SDK
        sdk = FubonSDK()
        accounts = sdk.login(
            os.getenv("FUBON_USERNAME"),
            os.getenv("FUBON_PASSWORD"),
            os.getenv("FUBON_PFX_PATH"),
            os.getenv("FUBON_PFX_PASSWORD", ""),
        )

        if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
            pytest.skip("SDK 登入失敗")

        # 創建服務實例
        mock_mcp = Mock(spec=FastMCP)
        reststock = sdk.marketdata.rest_client.stock if hasattr(sdk, "marketdata") else None
        restfutopt = sdk.marketdata.rest_client.futopt if hasattr(sdk, "marketdata") else None

        return AnalysisService(mock_mcp, sdk, [a.account for a in accounts.data], reststock, restfutopt)

    def test_calculate_portfolio_var_integration(self, real_analysis_service):
        """整合測試：計算投資組合VaR"""
        if not real_analysis_service.accounts:
            pytest.skip("沒有可用帳戶")

        result = real_analysis_service.calculate_portfolio_var(
            {"account": real_analysis_service.accounts[0], "confidence_level": 0.95, "time_horizon": 1, "method": "historical"}
        )

        assert result["status"] == "success"
        assert "var_estimate" in result["data"]
        assert "var_percentage" in result["data"]

    def test_run_portfolio_stress_test_integration(self, real_analysis_service):
        """整合測試：執行壓力測試"""
        if not real_analysis_service.accounts:
            pytest.skip("沒有可用帳戶")

        result = real_analysis_service.run_portfolio_stress_test(
            {"account": real_analysis_service.accounts[0], "scenarios": [{"name": "market_crash", "equity_drop": -0.2}]}
        )

        # Allow both success and error status if portfolio is empty
        assert result["status"] in ["success", "error"]
        if result["status"] == "success":
            assert "stress_test_results" in result["data"]
        else:
            # If error, it should be due to no portfolio data
            assert "無法獲取投資組合數據" in result.get("message", "")

    def test_generate_market_sentiment_index_integration(self, real_analysis_service):
        """整合測試：生成市場情緒指數"""
        result = real_analysis_service.generate_market_sentiment_index(
            {"index_components": ["technical", "volume"], "lookback_period": 30}
        )

        assert result["status"] == "success"
        assert "overall_sentiment_index" in result["data"]
        assert "sentiment_level" in result["data"]
