#!/usr/bin/env python3
"""
Market Data Service 擴展測試

測試 market_data_service.py 中未覆蓋的部分，特別是:
1. 期貨/選擇權報價查詢
2. 不同時間範圍的歷史數據
3. SQLite 數據庫錯誤處理
4. API 錯誤處理
5. 數據正規化
"""

import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from mcp.server.fastmcp import FastMCP

from fubon_api_mcp_server.market_data_service import MarketDataService


class TestMarketDataServiceExtended:
    """Market Data Service 擴展測試"""

    @pytest.fixture
    def mock_mcp(self):
        """模擬 MCP 實例"""
        return Mock(spec=FastMCP)

    @pytest.fixture
    def mock_sdk(self):
        """模擬 SDK 實例"""
        return Mock()

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
    def market_data_service(self, mock_mcp, base_data_dir, mock_reststock, mock_restfutopt, mock_sdk):
        """建立 MarketDataService 實例"""
        return MarketDataService(mock_mcp, base_data_dir, mock_reststock, mock_restfutopt, mock_sdk)

    # ==================== 數據庫錯誤處理測試 ====================

    def test_create_tables_success(self, market_data_service):
        """測試數據庫表創建成功"""
        assert market_data_service.db_path.exists()

        # 驗證表存在
        with sqlite3.connect(market_data_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_historical_data'")
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "stock_historical_data"

    def test_create_tables_db_exists(self, market_data_service):
        """測試數據庫檔案存在"""
        assert market_data_service.db_path.exists()
        assert market_data_service.db_path.name == "stock_data.db"

    # ==================== 期貨/選擇權報價測試 ====================

    def test_get_futopt_intraday_quote_success(self, market_data_service):
        """測試期貨/選擇權即時報價查詢成功"""
        # 期貨API直接返回字典格式
        mock_result = {
            "symbol": "TXFB5",
            "price": 16000,
            "volume": 1000,
            "bid_price": 15999,
            "ask_price": 16001,
        }
        market_data_service.restfutopt.intraday.quote = Mock(return_value=mock_result)

        result = market_data_service.get_intraday_futopt_quote({"symbol": "TXFB5"})

        assert result["status"] == "success"
        assert "data" in result

    def test_get_futopt_intraday_quote_failure(self, market_data_service):
        """測試期貨/選擇權即時報價查詢失敗"""
        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：商品代碼不存在"
        market_data_service.restfutopt.intraday.quote = Mock(return_value=mock_result)

        result = market_data_service.get_intraday_futopt_quote({"symbol": "INVALID"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    def test_get_futopt_intraday_quote_not_initialized(self, mock_mcp, base_data_dir, mock_sdk):
        """測試期貨/選擇權服務未初始化"""
        service = MarketDataService(mock_mcp, base_data_dir, None, None, mock_sdk)

        result = service.get_intraday_futopt_quote({"symbol": "TXFB5"})

        assert result["status"] == "error"
        assert "未初始化" in result["message"]

    # ==================== 歷史數據查詢測試 ====================

    def test_get_intraday_candles_success(self, market_data_service):
        """測試查詢即時 K 線數據成功"""
        # reststock.intraday.candles 直接返回列表
        mock_result = [
            {"date": "2025-11-25 09:00:00", "open": 500, "high": 505, "low": 498, "close": 502, "volume": 1000},
            {"date": "2025-11-25 09:01:00", "open": 502, "high": 506, "low": 500, "close": 504, "volume": 1200},
        ]
        market_data_service.reststock.intraday.candles = Mock(return_value=mock_result)

        result = market_data_service.get_intraday_candles({"symbol": "2330", "timeframe": "1"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)

    # ==================== 股票報價測試 ====================

    def test_get_intraday_quote_success(self, market_data_service):
        """測試股票即時報價查詢成功"""
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"symbol": "2330", "price": 500, "volume": 10000, "change": 5.0, "change_percent": 1.01}
        market_data_service.reststock.intraday.quote = Mock(return_value=mock_result)

        result = market_data_service.get_intraday_quote({"symbol": "2330"})

        assert result["status"] == "success"
        assert "data" in result

    # ==================== 數據正規化測試 ====================

    def test_normalize_result_with_dict(self, market_data_service):
        """測試正規化字典數據"""
        data = {"symbol": "2330", "price": 500, "volume": 1000}
        result = market_data_service._normalize_result(data)

        assert result == data

    def test_normalize_result_with_object(self, market_data_service):
        """測試正規化物件數據"""
        mock_obj = Mock()
        mock_obj.symbol = "2330"
        mock_obj.price = 500
        mock_obj.volume = 1000

        result = market_data_service._normalize_result(mock_obj)

        assert isinstance(result, dict)

    def test_normalize_result_with_nested_data(self, market_data_service):
        """測試正規化巢狀數據"""
        data = {"quote": {"symbol": "2330", "price": 500}, "details": [{"time": "09:00", "volume": 100}]}

        result = market_data_service._normalize_result(data)

        assert isinstance(result, dict)
        assert "quote" in result

    # ==================== SQLite 數據儲存測試 ====================

    def test_save_historical_data_to_db(self, market_data_service):
        """測試將歷史數據儲存到 SQLite"""
        data = [
            {"date": "2025-11-25", "open": 500.0, "high": 510.0, "low": 495.0, "close": 505.0, "volume": 10000},
            {"date": "2025-11-24", "open": 495.0, "high": 505.0, "low": 490.0, "close": 500.0, "volume": 9000},
        ]

        # 儲存數據
        with sqlite3.connect(market_data_service.db_path) as conn:
            cursor = conn.cursor()
            for row in data:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO stock_historical_data 
                    (symbol, date, open, high, low, close, volume, vol_value, price_change, change_ratio)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        "2330",
                        row["date"],
                        row["open"],
                        row["high"],
                        row["low"],
                        row["close"],
                        row["volume"],
                        None,
                        None,
                        None,
                    ),
                )
            conn.commit()

        # 驗證數據已儲存
        with sqlite3.connect(market_data_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM stock_historical_data WHERE symbol = ?", ("2330",))
            count = cursor.fetchone()[0]
            assert count == 2

    def test_query_historical_data_from_db(self, market_data_service):
        """測試從 SQLite 查詢歷史數據"""
        # 先插入測試數據
        with sqlite3.connect(market_data_service.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO stock_historical_data 
                (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                ("2330", "2025-11-25", 500.0, 510.0, 495.0, 505.0, 10000),
            )
            conn.commit()

        # 查詢數據
        with sqlite3.connect(market_data_service.db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM stock_historical_data WHERE symbol = ?", conn, params=("2330",))

        assert len(df) == 1
        assert df.iloc[0]["symbol"] == "2330"
        assert df.iloc[0]["close"] == 505.0

    # ==================== 期貨/選擇權產品列表測試 ====================

    def test_get_futopt_products_success(self, market_data_service):
        """測試查詢期貨/選擇權產品列表成功"""
        # API返回字典格式,包含data鍵
        mock_result = {
            "type": "futures",
            "exchange": "TAIFEX",
            "data": [
                {"symbol": "TXFA5", "name": "臺指期", "underlyingSymbol": "TXF"},
                {"symbol": "TXFB5", "name": "臺指期", "underlyingSymbol": "TXF"},
            ],
        }
        market_data_service.restfutopt.intraday.products = Mock(return_value=mock_result)

        result = market_data_service.get_intraday_futopt_products({"type": "F", "exchange": "TAIFEX"})

        assert result["status"] == "success"
        assert "data" in result
        assert len(result["data"]) == 2

    def test_get_futopt_products_failure(self, market_data_service):
        """測試查詢期貨/選擇權產品列表失敗"""
        market_data_service.restfutopt.intraday.products = Mock(side_effect=Exception("API 連線錯誤"))

        result = market_data_service.get_intraday_futopt_products({"type": "F", "exchange": "TAIFEX"})

        assert result["status"] == "error"

    def test_get_futopt_products_not_initialized(self, mock_mcp, base_data_dir, mock_sdk):
        """測試期貨/選擇權服務未初始化時查詢產品列表"""
        service = MarketDataService(mock_mcp, base_data_dir, None, None, mock_sdk)

        result = service.get_intraday_futopt_products({"type": "F", "exchange": "TAIFEX"})

        assert result["status"] == "error"

    # ==================== 期貨/選擇權代碼列表測試 ====================

    def test_get_futopt_tickers_success(self, market_data_service):
        """測試查詢期貨/選擇權代碼列表成功"""
        # API返回字典格式,包含data鍵
        mock_result = {
            "type": "futures",
            "exchange": "TAIFEX",
            "data": [{"symbol": "TXFA5"}, {"symbol": "TXFB5"}],
        }
        market_data_service.restfutopt.intraday.tickers = Mock(return_value=mock_result)

        result = market_data_service.get_intraday_futopt_tickers({"type": "F", "symbol": "TXF"})

        assert result["status"] == "success"
        assert "data" in result
        assert len(result["data"]) == 2

    def test_get_futopt_tickers_failure(self, market_data_service):
        """測試查詢期貨/選擇權代碼列表失敗"""
        market_data_service.restfutopt.intraday.tickers = Mock(side_effect=Exception("查詢逾時"))

        result = market_data_service.get_intraday_futopt_tickers({"type": "F", "symbol": "TXF"})

        assert result["status"] == "error"

    # ==================== 資料儲存與讀取整合測試 ====================

    def test_save_and_read_historical_data_integration(self, market_data_service):
        """測試儲存和讀取歷史數據的完整流程"""
        symbol = "2454"
        data = [
            {"date": "2025-11-25", "open": 800.0, "high": 820.0, "low": 790.0, "close": 810.0, "volume": 5000},
            {"date": "2025-11-24", "open": 790.0, "high": 810.0, "low": 785.0, "close": 800.0, "volume": 4800},
        ]

        # 儲存數據
        with sqlite3.connect(market_data_service.db_path) as conn:
            cursor = conn.cursor()
            for row in data:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO stock_historical_data 
                    (symbol, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (symbol, row["date"], row["open"], row["high"], row["low"], row["close"], row["volume"]),
                )
            conn.commit()

        # 讀取數據
        with sqlite3.connect(market_data_service.db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM stock_historical_data WHERE symbol = ? ORDER BY date DESC", conn, params=(symbol,))

        assert len(df) == 2
        assert df.iloc[0]["date"] == "2025-11-25"
        assert df.iloc[1]["date"] == "2025-11-24"

    # ==================== 錯誤處理測試 ====================

    def test_get_intraday_candles_exception_handling(self, market_data_service):
        """測試即時數據查詢異常處理"""
        market_data_service.reststock.intraday.candles = Mock(side_effect=Exception("網路連線中斷"))

        result = market_data_service.get_intraday_candles({"symbol": "2330", "timeframe": "1"})

        assert result["status"] == "error"

    def test_get_intraday_quote_exception_handling(self, market_data_service):
        """測試股票報價查詢異常處理"""
        market_data_service.reststock.intraday.quote = Mock(side_effect=Exception("伺服器錯誤"))

        result = market_data_service.get_intraday_quote({"symbol": "2330"})

        assert result["status"] == "error"
