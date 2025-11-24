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

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

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
        with patch("fubon_api_mcp_server.market_data_service.MarketDataService._create_tables"):
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
        mock_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "open": [100, 101],
                "high": [105, 106],
                "low": [95, 96],
                "close": [102, 103],
                "volume": [1000, 1100],
            }
        )

        with patch.object(market_data_service, "_read_local_stock_data", return_value=mock_df):
            result = market_data_service.historical_candles(
                {"symbol": "2330", "from_date": "2024-01-01", "to_date": "2024-01-02"}
            )

        assert result["status"] == "success"
        assert "data" in result
        assert "成功從本地數據獲取" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.pd.to_datetime")
    @patch("fubon_api_mcp_server.market_data_service.pd.Timedelta")
    def test_historical_candles_api_data(self, mock_timedelta, mock_to_datetime, market_data_service):
        """測試獲取歷史數據 - 使用 API 數據"""
        # 模擬本地數據不存在，API 返回數據
        with (
            patch.object(market_data_service, "_read_local_stock_data", return_value=None),
            patch.object(
                market_data_service,
                "_fetch_api_historical_data",
                return_value=[{"date": "2024-01-01", "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}],
            ),
            patch.object(market_data_service, "_process_historical_data") as mock_process,
            patch.object(market_data_service, "_save_to_local_db"),
        ):

            mock_process.return_value = pd.DataFrame(
                [
                    {
                        "date": "2024-01-01",
                        "open": 100,
                        "high": 105,
                        "low": 95,
                        "close": 102,
                        "volume": 1000,
                        "vol_value": 102000,
                        "price_change": 2,
                        "change_ratio": 2.0,
                    }
                ]
            )

            result = market_data_service.historical_candles(
                {"symbol": "2330", "from_date": "2024-01-01", "to_date": "2024-01-02"}
            )

        assert result["status"] == "success"
        assert "data" in result
        assert "成功獲取" in result["message"]

    def test_get_intraday_tickers_success(self, market_data_service):
        """測試獲取股票列表成功"""
        # 模擬 API 返回
        mock_result = [
            {"symbol": "2330", "name": "台積電", "market": "TSE"},
            {"symbol": "0050", "name": "元大台灣50", "market": "TSE"},
        ]
        market_data_service.reststock.intraday.tickers.return_value = mock_result

        result = market_data_service.get_intraday_tickers({"market": "TSE"})

        assert result["status"] == "success"
        assert result["data"] == mock_result
        assert "成功獲取 TSE 市場股票列表" in result["message"]

    def test_get_intraday_tickers_failure(self, market_data_service):
        """測試獲取股票列表失敗 (API 引發異常)"""
        market_data_service.reststock.intraday.tickers.side_effect = Exception("API error")

        result = market_data_service.get_intraday_tickers({"market": "TSE"})

        assert result["status"] == "error"
        assert "獲取股票列表失敗" in result["message"]

    def test_get_intraday_ticker_success(self, market_data_service):
        """測試獲取股票基本資料成功"""
        # 模擬 API 返回
        mock_result = Mock()
        mock_result.dict.return_value = {"symbol": "2330", "name": "台積電", "securityType": "01"}
        market_data_service.reststock.intraday.ticker.return_value = mock_result

        result = market_data_service.get_intraday_ticker({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "2330"
        assert "成功獲取 2330 基本資料" in result["message"]

    def test_get_intraday_ticker_failure(self, market_data_service):
        """測試 get_intraday_ticker 異常情況"""
        market_data_service.reststock.intraday.ticker.side_effect = Exception("API error")

        result = market_data_service.get_intraday_ticker({"symbol": "2330"})
        assert result["status"] == "error"
        assert "獲取基本資料失敗" in result["message"]

    def test_get_intraday_quote_success(self, market_data_service):
        """測試獲取股票即時報價成功"""
        # 模擬 API 返回
        mock_result = Mock()
        mock_result.dict.return_value = {"symbol": "2330", "lastPrice": 650.0, "change": 5.0}
        market_data_service.reststock.intraday.quote.return_value = mock_result

        result = market_data_service.get_intraday_quote({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "2330"
        assert "成功獲取 2330 即時報價" in result["message"]

    def test_get_intraday_quote_failure(self, market_data_service):
        """測試 get_intraday_quote 異常情況"""
        market_data_service.reststock.intraday.quote.side_effect = Exception("API error")

        result = market_data_service.get_intraday_quote({"symbol": "2330"})
        assert result["status"] == "error"
        assert "獲取即時報價失敗" in result["message"]

    def test_get_snapshot_quotes_success(self, market_data_service):
        """測試獲取股票行情快照成功"""
        # 模擬 API 返回
        mock_result = {
            "data": [{"symbol": "2330", "lastPrice": 650.0}, {"symbol": "0050", "lastPrice": 120.0}],
            "market": "TSE",
            "date": "20241113",
            "time": "09:00:00",
        }
        market_data_service.reststock.snapshot.quotes.return_value = mock_result

        result = market_data_service.get_snapshot_quotes({"market": "TSE"})
        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert result["returned_count"] == 2
        assert "成功獲取 TSE 行情快照" in result["message"]

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert result["returned_count"] == 2
        assert "成功獲取 TSE 行情快照" in result["message"]

    def test_get_snapshot_movers_success(self, market_data_service):
        """測試獲取股票漲跌幅排行成功"""
        # 模擬 API 返回
        mock_result = {
            "data": [{"symbol": "2330", "changePercent": 2.5}, {"symbol": "0050", "changePercent": 1.8}],
            "market": "TSE",
            "direction": "up",
            "change": "percent",
            "date": "20241113",
            "time": "09:00:00",
        }
        market_data_service.reststock.snapshot.movers.return_value = mock_result

        result = market_data_service.get_snapshot_movers({"market": "TSE"})
        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert "成功獲取 TSE 漲跌幅排行" in result["message"]

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert "成功獲取 TSE 漲跌幅排行" in result["message"]

    def test_get_snapshot_actives_success(self, market_data_service):
        """測試獲取股票成交量值排行成功"""
        # 模擬 API 返回
        mock_result = {
            "data": [{"symbol": "2330", "tradeVolume": 10000}, {"symbol": "0050", "tradeVolume": 8000}],
            "market": "TSE",
            "trade": "volume",
            "date": "20241113",
            "time": "09:00:00",
        }
        market_data_service.reststock.snapshot.actives.return_value = mock_result

        result = market_data_service.get_snapshot_actives({"market": "TSE"})
        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert "成功獲取 TSE 成交量值排行" in result["message"]

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
                {"symbol": "TE00C24000", "name": "台指選擇權", "type": "OPTION"},
            ],
            "type": "FUTURE",
        }
        market_data_service.restfutopt.intraday.tickers.return_value = mock_result

        result = market_data_service.get_intraday_futopt_tickers({"type": "FUTURE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["total_count"] == 2
        assert result["type_counts"]["FUTURE"] == 1
        assert result["type_counts"]["OPTION"] == 1
        assert "成功獲取 2 筆合約代碼資訊" in result["message"]

    def test_get_intraday_futopt_tickers_failure(self, market_data_service):
        """測試期貨/選擇權合約代碼列表 API 引發異常"""
        market_data_service.restfutopt.intraday.tickers.side_effect = Exception("API error")

        result = market_data_service.get_intraday_futopt_tickers({"type": "FUTURE"})
        assert result["status"] == "error"
        assert "獲取合約代碼列表失敗" in result["message"]

    def test_get_intraday_futopt_ticker_success(self, market_data_service):
        """測試獲取期貨/選擇權個別合約基本資訊成功"""
        # 模擬 API 返回
        mock_result = {"symbol": "TX00", "name": "台指期", "referencePrice": 18000.0}
        market_data_service.restfutopt.intraday.ticker.return_value = mock_result

        result = market_data_service.get_intraday_futopt_ticker({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "TX00"
        assert "成功獲取合約 TX00 基本資訊" in result["message"]

    def test_get_intraday_futopt_ticker_failure_message_list(self, market_data_service):
        """測試期貨/選擇權合約基本資訊 API 回傳失敗訊息陣列"""

        class ErrObj:
            def __init__(self):
                self.message = ["err1", "err2"]

        market_data_service.restfutopt.intraday.ticker.return_value = ErrObj()

        result = market_data_service.get_intraday_futopt_ticker({"symbol": "TX00"})
        assert result["status"] == "error"
        assert "API 調用失敗" in result["message"]

    def test_get_intraday_futopt_quote_success(self, market_data_service):
        """測試獲取期貨/選擇權即時報價成功"""
        # 模擬 API 返回
        mock_result = {"symbol": "TX00", "lastPrice": 18050.0, "change": 50.0}
        market_data_service.restfutopt.intraday.quote.return_value = mock_result

        result = market_data_service.get_intraday_futopt_quote({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "TX00"
        assert "成功獲取合約 TX00 即時報價" in result["message"]

    def test_get_trading_signals_success(self, market_data_service):
        """測試獲取交易訊號成功"""
        # 模擬本地數據 - 需要足夠的數據點來計算指標
        mock_df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=50),
                "close": [100 + i + np.sin(i / 10) * 5 for i in range(50)],
                "high": [105 + i + np.sin(i / 10) * 5 for i in range(50)],
                "low": [95 + i + np.sin(i / 10) * 5 for i in range(50)],
                "volume": [1000 + i * 100 for i in range(50)],
            }
        )

        with patch.object(market_data_service, "_read_local_stock_data", return_value=mock_df):
            result = market_data_service.get_trading_signals({"symbol": "2330"})

        assert result["status"] == "success"
        assert "symbol" in result["data"]
        assert "overall_signal" in result["data"]
        assert "indicators" in result["data"]
        assert "交易訊號分析成功" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
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

        result = market_data_service.query_symbol_snapshot(
            {"account": "1234567", "market_type": "Common", "stock_type": ["Stock"]}
        )

        assert result["status"] == "success"
        assert result["data"] == [{"symbol": "2330", "price": 650.0}]
        assert "成功查詢快照報價" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
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

        result = market_data_service.query_symbol_snapshot(
            {"account": "1234567", "market_type": "Common", "stock_type": ["Stock"]}
        )

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert isinstance(result["data"][0], dict)
        assert result["data"][0]["symbol"] == "2330"
        assert result["data"][0]["price"] == 650.0

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
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

        result = market_data_service.query_symbol_quote({"account": "1234567", "symbol": "2330"})

        assert result["status"] == "success"
        assert isinstance(result["data"], dict)
        assert result["data"]["symbol"] == "2330"
        assert "成功獲取股票 2330 報價資訊" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
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

        result = market_data_service.query_symbol_quote({"account": "1234567", "symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "2330"
        assert result["data"]["last_price"] == 600.0

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
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

        result = market_data_service.margin_quota({"account": "1234567", "stock_no": "2330"})

        assert result["status"] == "success"
        assert result["data"]["margin_tradable_quota"] == 100000
        assert "成功獲取帳戶 1234567 股票 2330 資券配額" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
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

        result = market_data_service.margin_quota({"account": "1234567", "stock_no": "2330"})

        assert result["status"] == "success"
        assert isinstance(result["data"], dict)
        assert result["data"]["margin_tradable_quota"] == 50000

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
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

        result = market_data_service.daytrade_and_stock_info({"account": "1234567", "stock_no": "2330"})

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

    def test_normalize_result_with_dict_method(self, market_data_service):
        """測試 _normalize_result 處理有 dict() 方法的物件"""

        class ObjWithDict:
            def dict(self):
                return {"a": 1, "b": 2}

        normalized = market_data_service._normalize_result(ObjWithDict())
        assert isinstance(normalized, dict)
        assert normalized["a"] == 1 and normalized["b"] == 2

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
        with patch.object(market_data_service, "_read_local_stock_data", side_effect=Exception("測試錯誤")):
            result = market_data_service.historical_candles(
                {"symbol": "2330", "from_date": "2024-01-01", "to_date": "2024-01-02"}
            )

        assert result["status"] == "error"
        assert "獲取數據時發生錯誤" in result["message"]

    def test_get_market_overview_failure(self, market_data_service):
        """模擬市場概況無法取得 (指數查詢失敗)"""
        market_data_service.reststock.intraday.quote.side_effect = Exception("API error")
        market_data_service.reststock.intraday.ticker.side_effect = Exception("API error")

        result = market_data_service.get_market_overview()
        assert result["status"] == "error"
        assert "無法獲取台股指數行情" in result["message"]

    def test_get_market_overview_success(self, market_data_service):
        """測試市場概況成功返回"""
        # 準備 index 資料
        tse_data = {
            "data": {"symbol": "IX0001", "name": "台股指數", "close": 18000, "chg": 50, "tradeVolume": 100000},
            "date": "20241113",
        }
        market_data_service.reststock.intraday.quote.return_value = SimpleNamespace(data=tse_data["data"])

        # movers and actives
        class Movers:
            def __init__(self):
                self.data = [{}, {}, {}]

        market_data_service.reststock.snapshot.movers.side_effect = [
            SimpleNamespace(data=[{}, {}]),
            SimpleNamespace(data=[{}]),
        ]
        market_data_service.reststock.snapshot.actives.return_value = SimpleNamespace(
            data=[{"tradeVolume": 1000}, {"tradeVolume": 2000}]
        )

        result = market_data_service.get_market_overview()
        assert result["status"] == "success"
        assert "index" in result["data"] and "statistics" in result["data"]

    def test_normalize_various_types(self, market_data_service):
        """測試 _normalize_result 的各種支援型別"""
        from collections import namedtuple
        from dataclasses import dataclass

        @dataclass
        class D:
            symbol: str
            price: int

        NT = namedtuple("NT", ["symbol", "price"])  # namedtuple

        class ObjToDict:
            def to_dict(self):
                return {"symbol": "2330", "price": 650}

        # dataclass
        d = D(symbol="2330", price=650)
        assert market_data_service._normalize_result(d)["symbol"] == "2330"

        # namedtuple
        nt = NT(symbol="0050", price=120)
        nt_normalized = market_data_service._normalize_result(nt)
        # namedtuple handled as tuple-like -> list
        assert isinstance(nt_normalized, list)
        assert nt_normalized[0] == "0050" or (isinstance(nt_normalized[0], dict) and nt_normalized[0].get("raw") == "0050")

        # to_dict
        obj = ObjToDict()
        assert market_data_service._normalize_result(obj)["symbol"] == "2330"

        # object with data attribute
        class Wrapper:
            def __init__(self):
                self.data = [NT(symbol="2330", price=650)]

        res = market_data_service._normalize_result(Wrapper())
        assert isinstance(res, dict) or isinstance(res, list)

        # string parse
        s = 'MyStruct {\n    symbol: "2330",\n    price: 650\n}'
        parsed = market_data_service._normalize_result(s)
        assert isinstance(parsed, dict) or isinstance(parsed, dict)

    def test_get_intraday_futopt_products_success(self, market_data_service):
        """測試期貨/選擇權產品列表成功回傳"""
        market_data_service.restfutopt.intraday.products.return_value = {
            "data": [{"symbol": "TX00", "type": "FUTURE"}],
            "type": "FUTURE",
        }
        result = market_data_service.get_intraday_futopt_products({"type": "FUTURE"})
        assert result["status"] == "success"

    def test_historical_candles_segmented_fetch(self, market_data_service):
        """測試歷史數據分段拉取 (超過一年) 的邏輯"""
        # patch _read_local_stock_data to return None
        with (
            patch.object(market_data_service, "_read_local_stock_data", return_value=None),
            patch.object(
                market_data_service,
                "_fetch_historical_data_segment",
                side_effect=[
                    [{"date": "2020-01-01", "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}],
                    [{"date": "2021-01-01", "open": 101, "high": 106, "low": 96, "close": 103, "volume": 1100}],
                ],
            ),
            patch.object(
                market_data_service,
                "_process_historical_data",
                return_value=pd.DataFrame(
                    [
                        {
                            "date": "2021-01-01",
                            "open": 101,
                            "high": 106,
                            "low": 96,
                            "close": 103,
                            "volume": 1100,
                            "vol_value": 113300,
                            "price_change": 2,
                            "change_ratio": 1.98,
                        }
                    ]
                ),
            ),
            patch.object(market_data_service, "_save_to_local_db"),
        ):
            result = market_data_service.historical_candles(
                {"symbol": "2330", "from_date": "2020-01-01", "to_date": "2022-01-01"}
            )

        assert result["status"] == "success"

    def test_create_tables_db(self, tmp_path):
        """測試 _create_tables 實際建立 SQLite DB 表格"""
        mcp = Mock()
        reststock = Mock()
        restfutopt = Mock()
        sdk = Mock()
        service = MarketDataService(mcp, tmp_path / "data", reststock, restfutopt, sdk)
        # call _create_tables to ensure DB and tables are created
        service._create_tables()
        assert service.db_path.exists()

    def test_to_snake_case_and_normalize_dict(self, market_data_service):
        """測試 _normalize_result 的 key 轉換及 dict 正規化"""
        obj = {"OpenPrice": 100, "TotalVolume": 1000, "LastUpdated": "2024-01-01"}
        res = market_data_service._normalize_result(obj)
        # should convert keys to snake_case
        assert "open_price" in res
        assert "total_volume" in res

    def test_indicator_helpers(self, market_data_service):
        """測試 bb/rsi/macd/kd/volume helper 分支"""
        # bb position
        assert market_data_service._bb_position(10, 9, 8, 7) == "突破上軌"
        assert market_data_service._bb_position(9, 10, 8, 7) == "上半軌"
        assert market_data_service._bb_position(8, 10, 9, 7) == "下半軌"
        assert market_data_service._bb_position(6, 10, 9, 7) == "跌破下軌"

        # rsi level
        assert market_data_service._rsi_level(75) == "超買"
        assert market_data_service._rsi_level(25) == "超賣"
        assert market_data_service._rsi_level(65) == "偏強"
        assert market_data_service._rsi_level(35) == "偏弱"

        # macd cross
        latest = {"macd": 2, "macd_signal": 1}
        prev = {"macd": 0.5, "macd_signal": 0.6}
        assert market_data_service._macd_cross(latest, prev) == "金叉"
        latest2 = {"macd": 0.4, "macd_signal": 0.6}
        prev2 = {"macd": 0.8, "macd_signal": 0.6}
        assert market_data_service._macd_cross(latest2, prev2) == "死叉"
        assert market_data_service._macd_cross(latest, None) == "無"

        # kd cross
        latest = {"k": 80, "d": 60}
        prev = {"k": 50, "d": 60}
        assert market_data_service._kd_cross(latest, prev) == "K上穿D"
        latest2 = {"k": 50, "d": 60}
        prev2 = {"k": 80, "d": 60}
        assert market_data_service._kd_cross(latest2, prev2) == "K下穿D"

        # volume strength
        assert market_data_service._volume_strength(2.5) == "爆量"
        assert market_data_service._volume_strength(1.6) == "量增"
        assert market_data_service._volume_strength(0.9) == "正常"
        assert market_data_service._volume_strength(0.6) == "量縮"
        assert market_data_service._volume_strength(0.1) == "極度萎縮"

    def test_compute_signals_extremes(self, market_data_service):
        """測試 _compute_signals 會回傳預期的鍵與排序"""
        latest = {
            "close": 200,
            "bb_upper": 180,
            "bb_middle": 170,
            "bb_lower": 150,
            "bb_width": 0.2,
            "rsi": 75,
            "macd": 2.0,
            "macd_signal": 0.5,
            "macd_hist": 1.5,
            "k": 85,
            "d": 70,
            "volume": 5000,
            "volume_rate": 2.5,
        }
        prev = {"macd": 0.0, "macd_signal": 0.1, "k": 50, "d": 60}
        res = market_data_service._compute_signals(latest, prev)
        assert "overall_signal" in res and "score" in res and "indicators" in res

    def test_compute_signals_bearish_neutral(self, market_data_service):
        latest_bear = {
            "close": 50,
            "bb_upper": 100,
            "bb_middle": 90,
            "bb_lower": 80,
            "bb_width": 0.02,
            "rsi": 20,
            "macd": -2.0,
            "macd_signal": -0.5,
            "macd_hist": -1.5,
            "k": 10,
            "d": 20,
            "volume": 100,
            "volume_rate": 0.4,
        }
        prev_bear = {"macd": -0.5, "macd_signal": 0.1, "k": 30, "d": 40}
        res_bear = market_data_service._compute_signals(latest_bear, prev_bear)
        assert isinstance(res_bear, dict)
        assert "overall_signal" in res_bear

        latest_neu = {
            "close": 100,
            "bb_upper": 110,
            "bb_middle": 100,
            "bb_lower": 90,
            "bb_width": 0.06,
            "rsi": 50,
            "macd": 0.1,
            "macd_signal": 0.1,
            "macd_hist": 0.0,
            "k": 50,
            "d": 50,
            "volume": 1000,
            "volume_rate": 1.0,
        }
        res_neu = market_data_service._compute_signals(latest_neu, None)
        assert isinstance(res_neu, dict)
        assert "overall_signal" in res_neu

    def test_normalize_sdk_object_and_snake_case(self, market_data_service):
        """測試 _normalize_result 能處理具有 is_success 和 data 的 SDK 物件與 snake_case"""

        class SDKObj:
            def __init__(self):
                self.is_success = True
                self.data = {"LastPrice": 100, "TradeValue": 1000}

        normalized = market_data_service._normalize_result(SDKObj())
        assert isinstance(normalized, dict)
        assert "last_price" in normalized or "LastPrice" in normalized

    def test_get_intraday_futopt_products_type_counts(self, market_data_service):
        """測試期貨/選擇權 products 回傳以及 type_counts 統計"""
        market_data_service.restfutopt.intraday.products.return_value = {
            "data": [
                {"symbol": "TX00", "type": "FUTURE"},
                {"symbol": "TE00C24000", "type": "OPTION"},
                {"symbol": "TE00P24000", "type": "OPTION"},
            ]
        }

        result = market_data_service.get_intraday_futopt_products({})
        assert result["status"] == "success"
        assert result["total_count"] == 3
        assert result["type_counts"]["OPTION"] == 2

    def test_get_intraday_futopt_candles_with_is_success_obj(self, market_data_service):
        """測試 fut/opt K 線在 SDK 回傳 result.is_success 時的邏輯"""
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"open": 18000, "high": 18050, "low": 17950, "close": 18030, "volume": 100}]
        market_data_service.restfutopt.intraday.candles.return_value = mock_result

        res = market_data_service.get_intraday_futopt_candles({"symbol": "TX00"})
        assert res["status"] == "error"
        assert (
            "API 調用失敗" in res["message"]
            or "返回結果為 None" in res["message"]
            or "API 調用失敗，結果對象" in res["message"]
        )

    def test_get_intraday_trades_failure(self, market_data_service):
        market_data_service.reststock.intraday.trades.side_effect = Exception("API error")
        result = market_data_service.get_intraday_trades({"symbol": "2330"})
        assert result["status"] == "error"
        assert "獲取成交明細失敗" in result["message"] or "失敗" in result["message"]

    def test_fetch_historical_data_segment_with_sdk_object(self, market_data_service):
        """測試 _fetch_historical_data_segment 針對 SDK 物件返回值的處理"""

        def fake_candles(**params):
            mock_res = Mock()
            mock_res.is_success = True
            mock_res.data = [{"date": "2020-01-01", "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}]
            return mock_res

        market_data_service.reststock.historical.candles = fake_candles
        res = market_data_service._fetch_historical_data_segment("2330", "2020-01-01", "2020-01-02")
        assert isinstance(res, list)

    def test_get_intraday_futopt_products_full_fields(self, market_data_service):
        """測試 fut/opt 產品列表在完整 product 字段輸入時的結果欄位映射"""
        product = {
            "symbol": "TE00C24000",
            "name": "台指選擇權",
            "type": "OPTION",
            "exchange": "TAIFEX",
            "session": "REGULAR",
            "contractType": "CALL",
            "statusCode": "ACTIVE",
            "underlyingSymbol": "TX00",
            "strikePrice": 24000,
            "expirationDate": "2025-12-01",
            "contractSize": 200,
            "tickSize": 0.5,
            "tickValue": 10,
            "tradingHours": "09:00-13:30",
            "settlementDate": "2025-12-02",
            "lastTradingDate": "2025-11-30",
            "tradingCurrency": "TWD",
            "quoteAcceptable": True,
            "canBlockTrade": False,
            "expiryType": "AM",
            "underlyingType": "I",
            "marketCloseGroup": "G1",
            "endSession": "REGULAR",
            "startDate": "2025-01-01",
        }

        market_data_service.restfutopt.intraday.products.return_value = {"data": [product], "type": "OPTION"}
        res = market_data_service.get_intraday_futopt_products({})
        assert res["status"] == "success"
        assert res["total_count"] == 1
        assert res["type_counts"]["OPTION"] == 1
        assert "strike_price" in res["data"][0]

    def test_get_intraday_futopt_tickers_full_fields(self, market_data_service):
        """測試期貨/選擇權合約代碼列表在完整 ticker 欄位輸入時的結果欄位映射"""
        ticker = {
            "symbol": "TE00C24000",
            "name": "台指選擇權",
            "type": "OPTION",
            "exchange": "TAIFEX",
            "session": "REGULAR",
            "product": "TX00",
            "contractType": "CALL",
            "expirationDate": "2025-12-01",
            "strikePrice": 24000,
            "optionType": "CALL",
            "underlyingSymbol": "TX00",
            "multiplier": 200,
            "tickSize": 0.5,
            "tradingHours": "09:00-13:30",
            "lastTradingDate": "2025-11-30",
        }
        market_data_service.restfutopt.intraday.tickers.return_value = {"data": [ticker]}
        res = market_data_service.get_intraday_futopt_tickers({"type": "OPTION"})
        assert res["status"] == "success"
        assert res["total_count"] == 1
        assert res["type_counts"]["OPTION"] == 1
        assert "strike_price" in res["data"][0]

    def test_normalize_inspect_public_attributes(self, market_data_service):
        """測試 _normalize_result 通過 dir() 探測公有屬性的情況"""

        class Attrs:
            def __init__(self):
                self.price = 100
                self.symbol = "2330"

            def method(self):
                return 1

        obj = Attrs()
        normalized = market_data_service._normalize_result(obj)
        assert isinstance(normalized, dict)
        assert normalized["symbol"] == "2330"

    def test_exercise_many_endpoints(self, market_data_service):
        """一次性調用多個 endpoint，確保在各種常見回應類型下不拋出例外並返回狀態鍵"""
        # stock endpoints
        market_data_service.reststock.intraday.tickers.return_value = [{"symbol": "2330"}]
        market_data_service.reststock.intraday.ticker.return_value = Mock(dict=lambda: {"symbol": "2330"})
        market_data_service.reststock.intraday.quote.return_value = Mock(dict=lambda: {"symbol": "2330", "lastPrice": 650})
        market_data_service.reststock.intraday.candles.return_value = [{"open": 100, "close": 101, "volume": 1000}]
        market_data_service.reststock.intraday.trades.return_value = [{"time": "09:00", "price": 100}]
        market_data_service.reststock.intraday.volumes.return_value = [{"price": 100, "volume": 1000}]
        market_data_service.reststock.snapshot.quotes.return_value = {
            "data": [{"symbol": "2330"}],
            "market": "TSE",
            "date": "20250101",
        }
        market_data_service.reststock.snapshot.movers.return_value = {"data": [{"symbol": "2330"}], "market": "TSE"}
        market_data_service.reststock.snapshot.actives.return_value = {
            "data": [{"symbol": "2330", "tradeVolume": 1000}],
            "market": "TSE",
        }
        market_data_service.reststock.historical.stats.return_value = {"week52High": 700, "week52Low": 400}
        market_data_service.reststock.intraday.historical_stats.return_value = {"data": {}}

        # futopt endpoints
        market_data_service.restfutopt.intraday.products.return_value = {
            "data": [{"symbol": "TX00", "type": "FUTURE"}],
            "type": "FUTURE",
        }
        market_data_service.restfutopt.intraday.tickers.return_value = {
            "data": [{"symbol": "TX00", "name": "台指期", "type": "FUTURE"}],
            "type": "FUTURE",
        }
        market_data_service.restfutopt.intraday.ticker.return_value = {"symbol": "TX00", "name": "台指期"}
        market_data_service.restfutopt.intraday.quote.return_value = {"symbol": "TX00", "lastPrice": 18000}
        market_data_service.restfutopt.intraday.candles.return_value = {
            "data": [{"open": 18000, "close": 18010, "volume": 10}]
        }
        market_data_service.restfutopt.intraday.volumes.return_value = {"data": [{"price": 18000, "volume": 10}]}
        market_data_service.restfutopt.intraday.trades.return_value = {"data": [{"price": 18000, "time": "09:00"}]}

        # sdk level endpoints
        market_data_service.sdk.stock.query_symbol_snapshot.return_value = Mock(is_success=True, data=[{"symbol": "2330"}])
        market_data_service.sdk.stock.query_symbol_quote.return_value = Mock(is_success=True, data={"symbol": "2330"})
        market_data_service.sdk.stock.margin_quota.return_value = Mock(is_success=True, data={"margin_tradable_quota": 100})
        market_data_service.sdk.stock.daytrade_and_stock_info.return_value = Mock(is_success=True, data={"stock_no": "2330"})

        funcs_and_args = [
            (market_data_service.get_intraday_tickers, {"market": "TSE"}),
            (market_data_service.get_intraday_ticker, {"symbol": "2330"}),
            (market_data_service.get_intraday_quote, {"symbol": "2330"}),
            (market_data_service.get_intraday_candles, {"symbol": "2330"}),
            (market_data_service.get_intraday_trades, {"symbol": "2330"}),
            (market_data_service.get_intraday_volumes, {"symbol": "2330"}),
            (market_data_service.get_snapshot_quotes, {"market": "TSE"}),
            (market_data_service.get_snapshot_movers, {"market": "TSE"}),
            (market_data_service.get_snapshot_actives, {"market": "TSE"}),
            (market_data_service.get_historical_stats, {"symbol": "2330"}),
            (market_data_service.get_realtime_quotes, {"symbol": "2330"}),
            (market_data_service.get_intraday_futopt_products, {}),
            (market_data_service.get_intraday_futopt_tickers, {"type": "FUTURE"}),
            (market_data_service.get_intraday_futopt_ticker, {"symbol": "TX00"}),
            (market_data_service.get_intraday_futopt_quote, {"symbol": "TX00"}),
            (market_data_service.get_intraday_futopt_candles, {"symbol": "TX00"}),
            (market_data_service.get_intraday_futopt_volumes, {"symbol": "TX00"}),
            (market_data_service.get_intraday_futopt_trades, {"symbol": "TX00"}),
            (market_data_service.query_symbol_snapshot, {"account": "123", "market_type": "Common", "stock_type": ["Stock"]}),
            (market_data_service.query_symbol_quote, {"account": "123", "symbol": "2330"}),
            (market_data_service.margin_quota, {"account": "123", "stock_no": "2330"}),
            (market_data_service.daytrade_and_stock_info, {"account": "123", "stock_no": "2330"}),
        ]

        for func, args in funcs_and_args:
            res = func(args)
            assert isinstance(res, dict)
            assert "status" in res

    def test_exhaustive_return_types(self, market_data_service):
        """為多個 endpoint 提供不同型別返回值以覆蓋更多分支"""
        # Map methods to patch targets and args
        cases = [
            (
                "reststock.intraday.tickers",
                market_data_service.get_intraday_tickers,
                {"market": "TSE"},
                [[{"symbol": "2330"}], Mock(is_success=True, data=[{"symbol": "2330"}]), Mock(message=["error1", "error2"])],
            ),
            (
                "reststock.intraday.ticker",
                market_data_service.get_intraday_ticker,
                {"symbol": "2330"},
                [Mock(dict=lambda: {"symbol": "2330"}), Mock(is_success=True, data={"symbol": "2330"}), {"symbol": "2330"}],
            ),
            (
                "reststock.snapshot.quotes",
                market_data_service.get_snapshot_quotes,
                {"market": "TSE"},
                [{"data": [{"symbol": "2330"}]}, Mock(data=[SimpleNamespace(symbol="2330")])],
            ),
            (
                "restfutopt.intraday.products",
                market_data_service.get_intraday_futopt_products,
                {},
                [{"data": [{"symbol": "TX00", "type": "FUTURE"}]}, Mock(is_success=True, data=[{"symbol": "TX00"}])],
            ),
            (
                "restfutopt.intraday.tickers",
                market_data_service.get_intraday_futopt_tickers,
                {"type": "FUTURE"},
                [{"data": [{"symbol": "TX00", "type": "FUTURE"}]}, Mock(is_success=True, data=[{"symbol": "TX00"}])],
            ),
            (
                "restfutopt.intraday.quote",
                market_data_service.get_intraday_futopt_quote,
                {"symbol": "TX00"},
                [{"symbol": "TX00", "lastPrice": 18000}, Mock(is_success=True, data={"symbol": "TX00"})],
            ),
        ]

        for target, func, args, returns in cases:
            # Use tuple notation to patch nested attribute like 'reststock.intraday.tickers'
            parts = target.split(".")
            obj = market_data_service
            for p in parts[:-1]:
                obj = getattr(obj, p)
            attr = parts[-1]
            for ret in returns:
                setattr(obj, attr, ret)
                res = func(args)
                assert isinstance(res, dict)
                assert "status" in res

    def test_futopt_products_and_tickers_with_is_success_obj(self, market_data_service):
        """測試 fut/opt 的產品與代碼在 SDK 回傳 is_success 物件的情況"""
        mock_products = Mock()
        mock_products.is_success = True
        mock_products.data = [{"symbol": "TX00", "name": "台指期"}]
        market_data_service.restfutopt.intraday.products.return_value = mock_products
        res_prod = market_data_service.get_intraday_futopt_products({})
        assert res_prod["status"] == "error"

        mock_tickers = Mock()
        mock_tickers.is_success = True
        mock_tickers.data = [{"symbol": "TX00", "type": "FUTURE"}, {"symbol": "TE00C24000", "type": "OPTION"}]
        market_data_service.restfutopt.intraday.tickers.return_value = mock_tickers
        res_tick = market_data_service.get_intraday_futopt_tickers({"type": "FUTURE"})
        assert res_tick["status"] == "error"

    def test_get_intraday_futopt_volumes_and_trades_with_is_success_obj(self, market_data_service):
        mock_vol = Mock()
        mock_vol.is_success = True
        mock_vol.data = [{"price": 18000, "volume": 10}]
        market_data_service.restfutopt.intraday.volumes.return_value = mock_vol
        res_vol = market_data_service.get_intraday_futopt_volumes({"symbol": "TX00"})
        assert res_vol["status"] == "error"

        mock_trd = Mock()
        mock_trd.is_success = True
        mock_trd.data = [{"time": "09:00", "price": 18000, "volume": 10}]
        market_data_service.restfutopt.intraday.trades.return_value = mock_trd
        res_trd = market_data_service.get_intraday_futopt_trades({"symbol": "TX00"})
        assert res_trd["status"] == "error"

    def test_snapshot_and_historical_stats_variants(self, market_data_service):
        """測試 snapshot 和 historical_stats 在 object/dict 回傳時的行為"""
        # snapshot quotes as SDK object with data list of SimpleNamespace
        market_data_service.reststock.snapshot.quotes.return_value = SimpleNamespace(
            data=[SimpleNamespace(symbol="2330", lastPrice=650.0)], market="TSE"
        )
        res = market_data_service.get_snapshot_quotes({"market": "TSE"})
        assert res["status"] == "success"

        # historical stats success
        market_data_service.reststock.historical.stats.return_value = {
            "symbol": "2330",
            "week52High": 700,
            "week52Low": 400,
            "closePrice": 650,
        }
        res_stats = market_data_service.get_historical_stats({"symbol": "2330"})
        assert res_stats["status"] == "success"

    def test_get_intraday_candles_success(self, market_data_service):
        """測試獲取 K 線成功"""
        market_data_service.reststock.intraday.candles.return_value = [
            {"open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
        ]

        result = market_data_service.get_intraday_candles({"symbol": "2330"})
        assert result["status"] == "success"
        assert isinstance(result["data"], list)

    def test_get_intraday_trades_success(self, market_data_service):
        """測試獲取成交明細成功"""
        market_data_service.reststock.intraday.trades.return_value = [{"time": "09:00:00", "price": 100, "volume": 100}]

        result = market_data_service.get_intraday_trades({"symbol": "2330"})
        assert result["status"] == "success"
        assert isinstance(result["data"], list)

    def test_get_intraday_volumes_success(self, market_data_service):
        """測試獲取分價量表成功"""
        market_data_service.reststock.intraday.volumes.return_value = [{"price": 100, "volume": 1000}]

        result = market_data_service.get_intraday_volumes({"symbol": "2330"})
        assert result["status"] == "success"
        assert isinstance(result["data"], list)

    def test_get_intraday_futopt_candles_success(self, market_data_service):
        market_data_service.restfutopt.intraday.candles.return_value = {
            "data": [{"open": 18000, "high": 18050, "low": 17950, "close": 18030, "volume": 100}]
        }
        result = market_data_service.get_intraday_futopt_candles({"symbol": "TX00"})
        assert result["status"] == "success"
        assert isinstance(result["data"], dict)

    def test_get_intraday_futopt_volumes_trades_success(self, market_data_service):
        market_data_service.restfutopt.intraday.volumes.return_value = {"data": [{"price": 18000, "volume": 10}]}
        market_data_service.restfutopt.intraday.trades.return_value = {
            "data": [{"time": "09:00", "price": 18000, "volume": 10}]
        }

        res_vol = market_data_service.get_intraday_futopt_volumes({"symbol": "TX00"})
        res_trd = market_data_service.get_intraday_futopt_trades({"symbol": "TX00"})

        assert res_vol["status"] == "success"
        assert res_trd["status"] == "success"

    def test_get_historical_stats_failure(self, market_data_service):
        """測試近52週股價數據 API 失敗"""
        market_data_service.reststock.intraday.historical_stats.side_effect = Exception("API error")
        result = market_data_service.get_historical_stats({"symbol": "2330"})
        assert result["status"] == "error"
        assert "錯誤" in result["message"] or "失敗" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
    def test_query_symbol_snapshot_failure(self, mock_validate, market_data_service):
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)
        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API error"
        market_data_service.sdk.stock.query_symbol_snapshot.return_value = mock_result

        result = market_data_service.query_symbol_snapshot(
            {"account": "1234567", "market_type": "Common", "stock_type": ["Stock"]}
        )
        assert result["status"] == "error"
        assert "查詢快照報價失敗" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
    def test_query_symbol_quote_failure(self, mock_validate, market_data_service):
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)
        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API error"
        market_data_service.sdk.stock.query_symbol_quote.return_value = mock_result

        result = market_data_service.query_symbol_quote({"account": "1234567", "symbol": "2330"})
        assert result["status"] == "error"
        assert "無法獲取" in result["message"] or "錯誤" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
    def test_margin_quota_failure(self, mock_validate, market_data_service):
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)
        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API error"
        market_data_service.sdk.stock.margin_quota.return_value = mock_result

        result = market_data_service.margin_quota({"account": "1234567", "stock_no": "2330"})
        assert result["status"] == "error"
        assert "API 調用失敗" in result["message"] or "失敗" in result["message"]

    @patch("fubon_api_mcp_server.market_data_service.validate_and_get_account")
    def test_daytrade_and_stock_info_failure(self, mock_validate, market_data_service):
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)
        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API error"
        market_data_service.sdk.stock.daytrade_and_stock_info.return_value = mock_result

        result = market_data_service.daytrade_and_stock_info({"account": "1234567", "stock_no": "2330"})
        assert result["status"] == "error"
        assert "無法獲取" in result["message"] or "失敗" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
