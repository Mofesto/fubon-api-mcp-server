#!/usr/bin/env python3
"""
富邦 API MCP Server - Market Data Service 單元測試

此測試檔案使用 pytest 框架測試 market_data_service 的所有功能。
測試分為兩類：
1. 模擬測試：使用 mock 物件測試邏輯
2. 整合測試：使用真實 API 測試（需要環境變數）

使用方法：
# 運行所有測試
pytest tests/test_market_data_service.py -v

# 只運行模擬測試
pytest tests/test_market_data_service.py::TestMarketDataServiceMock -v

# 只運行整合測試（需要真實憑證）
pytest tests/test_market_data_service.py::TestMarketDataServiceIntegration -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pandas as pd
import numpy as np

from fubon_api_mcp_server.market_data_service import MarketDataService


class TestMarketDataServiceMock:
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
    def mock_reststock(self):
        """模擬股票 REST 客戶端"""
        reststock = Mock()
        return reststock

    @pytest.fixture
    def mock_restfutopt(self):
        """模擬期貨/選擇權 REST 客戶端"""
        restfutopt = Mock()
        return restfutopt

    @pytest.fixture
    def base_data_dir(self, tmp_path):
        """臨時數據目錄"""
        return tmp_path / "data"

    @pytest.fixture
    def market_data_service(self, mock_mcp, base_data_dir, mock_reststock, mock_restfutopt, mock_sdk):
        """建立 MarketDataService 實例"""
        with patch('fubon_api_mcp_server.market_data_service.MarketDataService._create_tables'):
            service = MarketDataService(mock_mcp, base_data_dir, mock_reststock, mock_restfutopt, mock_sdk)
        return service

    def test_initialization(self, market_data_service):
        """測試 MarketDataService 初始化"""
        assert market_data_service.mcp is not None
        assert market_data_service.base_data_dir is not None
        assert market_data_service.reststock is not None
        assert market_data_service.restfutopt is not None
        assert market_data_service.sdk is not None

    def test_historical_candles_local_data(self, market_data_service):
        """測試獲取歷史數據 - 使用本地數據"""
        # 模擬本地數據存在
        mock_df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'open': [100, 101],
            'high': [105, 106],
            'low': [95, 96],
            'close': [102, 103],
            'volume': [1000, 1100]
        })

        with patch.object(market_data_service, '_read_local_stock_data', return_value=mock_df):
            result = market_data_service.historical_candles({
                "symbol": "2330",
                "from_date": "2024-01-01",
                "to_date": "2024-01-02"
            })

        assert result["status"] == "success"
        assert "data" in result
        assert "成功從本地數據獲取" in result["message"]

    @patch('fubon_api_mcp_server.market_data_service.pd.to_datetime')
    @patch('fubon_api_mcp_server.market_data_service.pd.Timedelta')
    def test_historical_candles_api_data(self, mock_timedelta, mock_to_datetime, market_data_service):
        """測試獲取歷史數據 - 使用 API 數據"""
        # 模擬本地數據不存在，API 返回數據
        with patch.object(market_data_service, '_read_local_stock_data', return_value=None), \
             patch.object(market_data_service, '_fetch_api_historical_data', return_value=[
                 {'date': '2024-01-01', 'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': 1000}
             ]), \
             patch.object(market_data_service, '_process_historical_data') as mock_process, \
             patch.object(market_data_service, '_save_to_local_db'):

            mock_process.return_value = pd.DataFrame([{
                'date': '2024-01-01', 'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': 1000,
                'vol_value': 102000, 'price_change': 2, 'change_ratio': 2.0
            }])

            result = market_data_service.historical_candles({
                "symbol": "2330",
                "from_date": "2024-01-01",
                "to_date": "2024-01-02"
            })

        assert result["status"] == "success"
        assert "data" in result
        assert "成功獲取" in result["message"]

    def test_get_intraday_tickers_success(self, market_data_service):
        """測試獲取股票列表成功"""
        # 模擬 API 返回
        mock_result = [
            {"symbol": "2330", "name": "台積電", "market": "TSE"},
            {"symbol": "0050", "name": "元大台灣50", "market": "TSE"}
        ]
        market_data_service.reststock.intraday.tickers.return_value = mock_result

        result = market_data_service.get_intraday_tickers({"market": "TSE"})

        assert result["status"] == "success"
        assert result["data"] == mock_result
        assert "成功獲取 TSE 市場股票列表" in result["message"]

    def test_get_intraday_ticker_success(self, market_data_service):
        """測試獲取股票基本資料成功"""
        # 模擬 API 返回
        mock_result = Mock()
        mock_result.dict.return_value = {
            "symbol": "2330",
            "name": "台積電",
            "securityType": "01"
        }
        market_data_service.reststock.intraday.ticker.return_value = mock_result

        result = market_data_service.get_intraday_ticker({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "2330"
        assert "成功獲取 2330 基本資料" in result["message"]

    def test_get_intraday_quote_success(self, market_data_service):
        """測試獲取股票即時報價成功"""
        # 模擬 API 返回
        mock_result = Mock()
        mock_result.dict.return_value = {
            "symbol": "2330",
            "lastPrice": 650.0,
            "change": 5.0
        }
        market_data_service.reststock.intraday.quote.return_value = mock_result

        result = market_data_service.get_intraday_quote({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "2330"
        assert "成功獲取 2330 即時報價" in result["message"]

    def test_get_snapshot_quotes_success(self, market_data_service):
        """測試獲取股票行情快照成功"""
        # 模擬 API 返回
        mock_result = {
            "data": [
                {"symbol": "2330", "lastPrice": 650.0},
                {"symbol": "0050", "lastPrice": 120.0}
            ],
            "market": "TSE",
            "date": "20241113",
            "time": "09:00:00"
        }
        market_data_service.reststock.snapshot.quotes.return_value = mock_result

        result = market_data_service.get_snapshot_quotes({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert result["returned_count"] == 2
        assert "成功獲取 TSE 行情快照" in result["message"]

    def test_get_snapshot_movers_success(self, market_data_service):
        """測試獲取股票漲跌幅排行成功"""
        # 模擬 API 返回
        mock_result = {
            "data": [
                {"symbol": "2330", "changePercent": 2.5},
                {"symbol": "0050", "changePercent": 1.8}
            ],
            "market": "TSE",
            "direction": "up",
            "change": "percent",
            "date": "20241113",
            "time": "09:00:00"
        }
        market_data_service.reststock.snapshot.movers.return_value = mock_result

        result = market_data_service.get_snapshot_movers({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert "成功獲取 TSE 漲跌幅排行" in result["message"]

    def test_get_snapshot_actives_success(self, market_data_service):
        """測試獲取股票成交量值排行成功"""
        # 模擬 API 返回
        mock_result = {
            "data": [
                {"symbol": "2330", "tradeVolume": 10000},
                {"symbol": "0050", "tradeVolume": 8000}
            ],
            "market": "TSE",
            "trade": "volume",
            "date": "20241113",
            "time": "09:00:00"
        }
        market_data_service.reststock.snapshot.actives.return_value = mock_result

        result = market_data_service.get_snapshot_actives({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert "成功獲取 TSE 成交量值排行" in result["message"]

    def test_get_intraday_futopt_tickers_success(self, market_data_service):
        """測試獲取期貨/選擇權合約代碼列表成功"""
        # 模擬 API 返回
        mock_result = {
            "data": [
                {"symbol": "TX00", "name": "台指期", "type": "FUTURE"},
                {"symbol": "TE00C24000", "name": "台指選擇權", "type": "OPTION"}
            ],
            "type": "FUTURE"
        }
        market_data_service.restfutopt.intraday.tickers.return_value = mock_result

        result = market_data_service.get_intraday_futopt_tickers({"type": "FUTURE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert result["type_counts"]["FUTURE"] == 1
        assert result["type_counts"]["OPTION"] == 1
        assert "成功獲取 2 筆合約代碼資訊" in result["message"]

    def test_get_intraday_futopt_ticker_success(self, market_data_service):
        """測試獲取期貨/選擇權個別合約基本資訊成功"""
        # 模擬 API 返回
        mock_result = {
            "symbol": "TX00",
            "name": "台指期",
            "referencePrice": 18000.0
        }
        market_data_service.restfutopt.intraday.ticker.return_value = mock_result

        result = market_data_service.get_intraday_futopt_ticker({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "TX00"
        assert "成功獲取合約 TX00 基本資訊" in result["message"]

    def test_get_intraday_futopt_quote_success(self, market_data_service):
        """測試獲取期貨/選擇權即時報價成功"""
        # 模擬 API 返回
        mock_result = {
            "symbol": "TX00",
            "lastPrice": 18050.0,
            "change": 50.0
        }
        market_data_service.restfutopt.intraday.quote.return_value = mock_result

        result = market_data_service.get_intraday_futopt_quote({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "TX00"
        assert "成功獲取合約 TX00 即時報價" in result["message"]

    def test_get_trading_signals_success(self, market_data_service):
        """測試獲取交易訊號成功"""
        # 模擬本地數據 - 需要足夠的數據點來計算指標
        mock_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=50),
            'close': [100 + i + np.sin(i/10)*5 for i in range(50)],
            'high': [105 + i + np.sin(i/10)*5 for i in range(50)],
            'low': [95 + i + np.sin(i/10)*5 for i in range(50)],
            'volume': [1000 + i*100 for i in range(50)]
        })

        with patch.object(market_data_service, '_read_local_stock_data', return_value=mock_df):
            result = market_data_service.get_trading_signals({"symbol": "2330"})

        assert result["status"] == "success"
        assert "symbol" in result["data"]
        assert "overall_signal" in result["data"]
        assert "indicators" in result["data"]
        assert "交易訊號分析成功" in result["message"]

    @patch('fubon_api_mcp_server.market_data_service.validate_and_get_account')
    def test_query_symbol_snapshot_success(self, mock_validate, market_data_service):
        """測試查詢股票快照報價成功"""
        # 模擬帳戶驗證
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"symbol": "2330", "price": 650.0}]
        market_data_service.sdk.stock.query_symbol_snapshot.return_value = mock_result

        result = market_data_service.query_symbol_snapshot({
            "account": "1234567",
            "market_type": "Common",
            "stock_type": ["Stock"]
        })

        assert result["status"] == "success"
        assert result["data"] == [{"symbol": "2330", "price": 650.0}]
        assert "成功查詢快照報價" in result["message"]

    @patch('fubon_api_mcp_server.market_data_service.validate_and_get_account')
    def test_query_symbol_snapshot_with_object_return(self, mock_validate, market_data_service):
        """測試 query_symbol_snapshot 在 SDK 回傳物件（非 dict）時仍能正規化"""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        from types import SimpleNamespace
        item = SimpleNamespace(symbol="2330", price=650.0)
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [item]
        market_data_service.sdk.stock.query_symbol_snapshot.return_value = mock_result

        result = market_data_service.query_symbol_snapshot({
            "account": "1234567",
            "market_type": "Common",
            "stock_type": ["Stock"]
        })

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert isinstance(result["data"][0], dict)
        assert result["data"][0]["symbol"] == "2330"
        assert result["data"][0]["price"] == 650.0

    @patch('fubon_api_mcp_server.market_data_service.validate_and_get_account')
    def test_query_symbol_quote_success(self, mock_validate, market_data_service):
        """測試查詢商品漲跌幅報表成功"""
        # 模擬帳戶驗證
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"symbol": "2330", "last_price": 650.0}
        market_data_service.sdk.stock.query_symbol_quote.return_value = mock_result

        result = market_data_service.query_symbol_quote({
            "account": "1234567",
            "symbol": "2330"
        })

        assert result["status"] == "success"
        assert isinstance(result["data"], dict)
        assert result["data"]["symbol"] == "2330"
        assert "成功獲取股票 2330 報價資訊" in result["message"]

    @patch('fubon_api_mcp_server.market_data_service.validate_and_get_account')
    def test_query_symbol_quote_object_return(self, mock_validate, market_data_service):
        """測試 query_symbol_quote 在 SDK 回傳物件（非 dict）時仍能正規化"""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        from types import SimpleNamespace
        data_obj = SimpleNamespace(symbol="2330", last_price=600.0)
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = data_obj
        market_data_service.sdk.stock.query_symbol_quote.return_value = mock_result

        result = market_data_service.query_symbol_quote({
            "account": "1234567",
            "symbol": "2330"
        })

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "2330"
        assert result["data"]["last_price"] == 600.0

    @patch('fubon_api_mcp_server.market_data_service.validate_and_get_account')
    def test_margin_quota_success(self, mock_validate, market_data_service):
        """測試查詢資券配額成功"""
        # 模擬帳戶驗證
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"margin_tradable_quota": 100000}
        market_data_service.sdk.stock.margin_quota.return_value = mock_result

        result = market_data_service.margin_quota({
            "account": "1234567",
            "stock_no": "2330"
        })

        assert result["status"] == "success"
        assert result["data"]["margin_tradable_quota"] == 100000
        assert "成功獲取帳戶 1234567 股票 2330 資券配額" in result["message"]

    @patch('fubon_api_mcp_server.market_data_service.validate_and_get_account')
    def test_margin_quota_with_object_return(self, mock_validate, market_data_service):
        """測試資券配額在 SDK 回傳物件（非 dict）時仍能正規化"""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        # 物件風格回傳（沒有 dict() 方法）
        from types import SimpleNamespace
        data_obj = SimpleNamespace(margin_tradable_quota=50000)
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = data_obj
        market_data_service.sdk.stock.margin_quota.return_value = mock_result

        result = market_data_service.margin_quota({
            "account": "1234567",
            "stock_no": "2330"
        })

        assert result["status"] == "success"
        assert isinstance(result["data"], dict)
        assert result["data"]["margin_tradable_quota"] == 50000

    @patch('fubon_api_mcp_server.market_data_service.validate_and_get_account')
    def test_daytrade_and_stock_info_object_return(self, mock_validate, market_data_service):
        """測試 daytrade_and_stock_info 在 SDK 回傳物件（非 dict）時仍能正規化"""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        from types import SimpleNamespace
        data_obj = SimpleNamespace(stock_no="2330", daytrade_tradable_quota=3000)
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = data_obj
        market_data_service.sdk.stock.daytrade_and_stock_info.return_value = mock_result

        result = market_data_service.daytrade_and_stock_info({
            "account": "1234567",
            "stock_no": "2330"
        })

        assert result["status"] == "success"
        assert isinstance(result["data"], dict)
        assert result["data"]["stock_no"] == "2330"
        assert result["data"]["daytrade_tradable_quota"] == 3000

    def test_normalize_result_handles_mock_object(self, market_data_service):
        """直接測試 _normalize_result 能夠處理 Mock 物件並回傳 dict"""
        from types import SimpleNamespace
        item = SimpleNamespace(symbol="2330", price=650.0)
        normalized = market_data_service._normalize_result(item)
        assert isinstance(normalized, dict)
        assert normalized["symbol"] == "2330"
        assert normalized["price"] == 650.0


    def test_get_intraday_futopt_service_not_initialized(self, market_data_service):
        """測試期貨/選擇權服務未初始化"""
        # 設置 restfutopt 為 None
        market_data_service.restfutopt = None

        result = market_data_service.get_intraday_futopt_tickers({"type": "FUTURE"})

        assert result["status"] == "error"
        assert "期貨/選擇權行情服務未初始化" in result["message"]

    def test_get_realtime_quotes_service_not_initialized(self, market_data_service):
        """測試股票行情服務未初始化"""
        # 設置 reststock 為 None
        market_data_service.reststock = None

        result = market_data_service.get_realtime_quotes({"symbol": "2330"})

        assert result["status"] == "error"
        assert "股票行情服務未初始化" in result["message"]

    def test_historical_candles_exception(self, market_data_service):
        """測試歷史數據獲取異常"""
        with patch.object(market_data_service, '_read_local_stock_data', side_effect=Exception("測試錯誤")):
            result = market_data_service.historical_candles({
                "symbol": "2330",
                "from_date": "2024-01-01",
                "to_date": "2024-01-02"
            })

        assert result["status"] == "error"
        assert "獲取數據時發生錯誤" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])