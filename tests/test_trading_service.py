#!/usr/bin/env python3
"""
富邦 API MCP Server - Trading Service 單元測試

此測試檔案使用 pytest 框架測試 trading_service 的所有功能。
測試分為兩類：
1. 模擬測試：使用 mock 物件測試邏輯
2. 整合測試：使用真實 API 測試（需要環境變數）

使用方法：
# 運行所有測試
pytest tests/test_trading_service.py -v

# 只運行模擬測試
pytest tests/test_trading_service.py::TestTradingServiceMock -v

# 只運行整合測試（需要真實憑證）
pytest tests/test_trading_service.py::TestTradingServiceIntegration -v
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from fubon_api_mcp_server.trading_service import TradingService


class TestTradingServiceMock:
    """模擬測試 - 不依賴真實 API"""

    @pytest.fixture
    def mock_mcp(self):
        """模擬 MCP 實例"""
        return Mock(spec=FastMCP)

    @pytest.fixture
    def mock_sdk(self):
        """模擬 SDK 實例"""
        sdk = Mock()
        # 模擬帳戶物件
        mock_account = Mock()
        mock_account.account = "1234567"
        mock_account.name = "測試用戶"

        # 模擬帳戶列表
        mock_accounts = Mock()
        mock_accounts.data = [mock_account]

        sdk.login = Mock(return_value=mock_accounts)
        sdk.init_realtime = Mock()
        return sdk, mock_accounts

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
    def trading_service(self, mock_mcp, mock_sdk, base_data_dir, mock_reststock, mock_restfutopt):
        """建立 TradingService 實例"""
        sdk, accounts = mock_sdk
        return TradingService(
            mock_mcp, sdk, [a.account for a in accounts.data], base_data_dir, mock_reststock, mock_restfutopt
        )

    def test_initialization(self, trading_service):
        """測試 TradingService 初始化"""
        assert trading_service.mcp is not None
        assert trading_service.sdk is not None
        assert trading_service.accounts is not None
        assert trading_service.base_data_dir is not None
        assert trading_service.reststock is not None
        assert trading_service.restfutopt is not None

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_order_success(self, mock_validate, trading_service):
        """測試下單成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 下單成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"order_no": "12345678"}
        trading_service.sdk.stock.place_order = Mock(return_value=mock_result)

        result = trading_service.place_order(
            {
                "account": "1234567",
                "buy_sell": "Buy",
                "symbol": "2330",
                "price": "500.0",
                "quantity": 1000,
                "market_type": "Common",
                "price_type": "Limit",
                "time_in_force": "ROD",
                "order_type": "Stock",
            }
        )

        assert result["status"] == "success"
        assert "order_no" in result["data"]
        assert "委託單下單成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_order_failure(self, mock_validate, trading_service):
        """測試下單失敗"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 下單失敗
        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "下單失敗：資金不足"
        trading_service.sdk.stock.place_order = Mock(return_value=mock_result)

        result = trading_service.place_order(
            {"account": "1234567", "buy_sell": "Buy", "symbol": "2330", "price": "500.0", "quantity": 1000}
        )

        assert result["status"] == "error"
        assert "下單失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_cancel_order_success(self, mock_validate, trading_service):
        """測試取消委託成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 取消成功 (使用 order_no)
        mock_result = Mock()
        mock_result.is_success = True
        trading_service.sdk.stock.cancel_order = Mock(return_value=mock_result)

        # Mock get_order_results to return the order to be cancelled
        mock_get_results = Mock()
        mock_get_results.is_success = True
        mock_get_results.data = [{"order_no": "12345678"}]
        trading_service.sdk.stock.get_order_results = Mock(return_value=mock_get_results)

        result = trading_service.cancel_order({"account": "1234567", "order_no": "12345678"})

        assert result["status"] == "success"
        assert "取消成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_cancel_order_with_order_res_success(self, mock_validate, trading_service):
        """測試取消委託成功（使用 order_res 物件）"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 取消成功
        mock_result = Mock()
        mock_result.is_success = True
        trading_service.sdk.stock.cancel_order = Mock(return_value=mock_result)

        order_res_obj = {"order_no": "12345678"}
        result = trading_service.cancel_order({"account": "1234567", "order_res": order_res_obj, "unblock": True})

        assert result["status"] == "success"
        assert "取消成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_modify_price_success(self, mock_validate, trading_service):
        """測試改價成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 改價成功
        mock_result = Mock()
        mock_result.is_success = True
        # SDK.make_modify_price_obj 應被呼叫以組成 ModifyPriceObj
        trading_service.sdk.stock.make_modify_price_obj = Mock(return_value={"order_no": "12345678"})
        # Mock get_order_results to provide a matching order when using order_no mode
        mock_get_results = Mock()
        mock_get_results.is_success = True
        mock_get_results.data = [{"order_no": "12345678"}]
        trading_service.sdk.stock.get_order_results = Mock(return_value=mock_get_results)
        trading_service.sdk.stock.modify_price = Mock(return_value=mock_result)

        result = trading_service.modify_price({"account": "1234567", "order_no": "12345678", "new_price": 505.0})

        assert result["status"] == "success"
        assert "價格修改成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_modify_quantity_success(self, mock_validate, trading_service):
        """測試改量成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 改量成功
        mock_result = Mock()
        mock_result.is_success = True
        trading_service.sdk.stock.modify_quantity = Mock(return_value=mock_result)

        result = trading_service.modify_quantity({"account": "1234567", "order_no": "12345678", "new_quantity": 500})

        assert result["status"] == "success"
        assert "數量修改成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_batch_place_order_success(self, mock_validate, trading_service):
        """測試批量下單成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 下單成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"order_no": "12345678"}
        trading_service.sdk.stock.place_order = Mock(return_value=mock_result)

        orders = [
            {"account": "1234567", "buy_sell": "Buy", "symbol": "2330", "price": "500.0", "quantity": 1000},
            {"account": "1234567", "buy_sell": "Sell", "symbol": "2454", "price": "800.0", "quantity": 500},
        ]

        result = trading_service.batch_place_order({"orders": orders})

        assert result["status"] == "success"
        assert "results" in result["data"]
        assert len(result["data"]["results"]) == 2
        assert "批量下單完成" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_batch_place_order_partial_failure(self, mock_validate, trading_service):
        """測試批量下單部分失敗"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬第一個下單成功，第二個失敗
        mock_result_success = Mock()
        mock_result_success.is_success = True
        mock_result_success.data = {"order_no": "12345678"}

        mock_result_failure = Mock()
        mock_result_failure.is_success = False
        mock_result_failure.message = "下單失敗"

        trading_service.sdk.place_order = Mock(side_effect=[mock_result_success, mock_result_failure])
        # Also set stock.place_order to the same mock to support both sdk shapes
        trading_service.sdk.stock.place_order = trading_service.sdk.place_order

        orders = [
            {"account": "1234567", "buy_sell": "Buy", "symbol": "2330", "price": "500.0", "quantity": 1000},
            {"account": "1234567", "buy_sell": "Sell", "symbol": "2454", "price": "800.0", "quantity": 500},
        ]

        result = trading_service.batch_place_order({"orders": orders})

        assert result["status"] == "success"
        assert "results" in result["data"]
        assert len(result["data"]["results"]) == 2
        assert result["data"]["results"][0]["status"] == "success"
        assert result["data"]["results"][1]["status"] == "error"
        assert "批量下單完成" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_results_success(self, mock_validate, trading_service):
        """測試獲取委託結果成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 查詢成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "order_no": "12345678",
                "stock_no": "2330",
                "buy_sell": "Buy",
                "quantity": 1000,
                "price": 500.0,
                "status": "Filled",
            }
        ]
        trading_service.sdk.stock.get_order_results = Mock(return_value=mock_result)

        result = trading_service.get_order_results({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert "成功獲取委託結果" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_results_normalize_enum(self, mock_validate, trading_service):
        """測試 get_order_results 能將 SDK 的 enum 字串正規化為簡單名稱 """
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "order_no": "ORD999",
                "stock_no": "2330",
                "buy_sell": "BSAction.Sell",
                "order_type": "OrderType.DayTrade",
                "price_type": "PriceType.Limit",
                "status": "Status.10",
            }
        ]
        trading_service.sdk.stock.get_order_results = Mock(return_value=mock_result)

        result = trading_service.get_order_results({"account": "1234567"})

        assert result["status"] == "success"
        assert result["data"][0]["order_no"] == "ORD999"
        assert result["data"][0]["buy_sell"] == "Sell"
        assert result["data"][0]["order_type"] == "DayTrade"
        assert result["data"][0]["price_type"] == "Limit"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_results_detail_success(self, mock_validate, trading_service):
        """測試獲取委託結果詳細成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 查詢成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "order_no": "12345678",
                "stock_no": "2330",
                "buy_sell": "Buy",
                "quantity": 1000,
                "price": 500.0,
                "status": "Filled",
                "details": [],
            }
        ]
        trading_service.sdk.stock.get_order_results_detail = Mock(return_value=mock_result)

        result = trading_service.get_order_results_detail({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert "成功獲取委託結果詳細資訊" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_results_detail_normalize_enum(self, mock_validate, trading_service):
        """測試 get_order_results_detail 能將 SDK 的 enum 字串正規化為簡單名稱 """
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 回傳 enum 字串
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "order_no": "ORD123",
                "stock_no": "2330",
                "buy_sell": "BSAction.Buy",
                "order_type": "OrderType.Stock",
                "details": [{"status": "Status.90", "modified_time": "10:00:00"}],
            }
        ]
        trading_service.sdk.stock.get_order_results_detail = Mock(return_value=mock_result)

        result = trading_service.get_order_results_detail({"account": "1234567"})

        assert result["status"] == "success"
        assert result["data"][0]["order_no"] == "ORD123"
        assert result["data"][0]["buy_sell"] == "Buy"
        assert result["data"][0]["order_type"] == "Stock"
        assert isinstance(result["data"][0]["details"], list)
        assert result["data"][0]["details"][0]["modified_time"] == "10:00:00"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_condition_order_success(self, mock_validate, trading_service):
        """測試下條件單成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 下條件單成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"condition_no": "COND001"}
        trading_service.sdk.place_condition_order = Mock(return_value=mock_result)
        # Also set stock.place_condition_order to the same mock for compatibility
        trading_service.sdk.stock.place_condition_order = trading_service.sdk.place_condition_order

        result = trading_service.place_condition_order(
            {
                "account": "1234567",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "stop_sign": "Full",
                "condition": {"price": 500.0, "operator": "GreaterThan"},
                "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500.0", "quantity": 1000},
            }
        )

        assert result["status"] == "success"
        assert result["data"]["condition_no"] == "COND001"
        assert "條件單建立成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_cancel_condition_order_success(self, mock_validate, trading_service):
        """測試取消條件單成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 取消條件單成功
        mock_result = Mock()
        mock_result.is_success = True
        trading_service.sdk.stock.cancel_condition_order = Mock(return_value=mock_result)

        result = trading_service.cancel_condition_order({"account": "1234567", "condition_no": "COND001"})

        assert result["status"] == "success"
        assert "取消成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_condition_order_success(self, mock_validate, trading_service):
        """測試查詢條件單成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 查詢條件單成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"condition_no": "COND001", "stock_no": "2330", "status": "Active"}]
        trading_service.sdk.stock.get_condition_order = Mock(return_value=mock_result)

        result = trading_service.get_condition_order({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert "成功獲取條件單清單" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_trail_order_success(self, mock_validate, trading_service):
        """測試查詢移動鎖利單成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 查詢移動鎖利單成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"trail_no": "TRAIL001", "stock_no": "2330", "status": "Active"}]
        trading_service.sdk.stock.get_trail_order = Mock(return_value=mock_result)

        result = trading_service.get_trail_order({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert "成功獲取移動鎖利單清單" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_history_success(self, mock_validate, trading_service):
        """測試查詢歷史委託成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "order_no": "12345678",
                "stock_no": "2330",
                "buy_sell": "Buy",
                "quantity": 1000,
                "price": 500.0,
                "status": 10,
            }
        ]
        trading_service.sdk.stock.order_history = Mock(return_value=mock_result)

        result = trading_service.get_order_history({"account": "1234567", "start_date": "20251118", "end_date": "20251118"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert "查詢成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_history_normalize_enum(self, mock_validate, trading_service):
        """測試 get_order_history 能將 SDK 的 enum 字串正規化為簡單名稱 """
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "order_no": "ORD999",
                "stock_no": "2330",
                "buy_sell": "BSAction.Sell",
                "order_type": "OrderType.DayTrade",
                "price_type": "PriceType.Limit",
                "details": [{"status": "Status.90", "modified_time": "09:00:32.477"}],
            }
        ]
        trading_service.sdk.stock.order_history = Mock(return_value=mock_result)

        result = trading_service.get_order_history({"account": "1234567", "start_date": "20251118"})

        assert result["status"] == "success"
        assert result["data"][0]["order_no"] == "ORD999"
        assert result["data"][0]["buy_sell"] == "Sell"
        assert result["data"][0]["order_type"] == "DayTrade"
        assert result["data"][0]["price_type"] == "Limit"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_filled_history_success(self, mock_validate, trading_service):
        """測試查詢歷史成交成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "date": "2025/11/18",
                "branch_no": "20203",
                "account": "1234567",
                "order_no": "12345678",
                "stock_no": "2330",
                "buy_sell": "Buy",
                "filled_no": "FILL123",
                "filled_avg_price": 500.0,
                "filled_qty": 1000,
                "filled_price": 500.0,
                "order_type": "Stock",
                "filled_time": "10:31:00.931",
            }
        ]
        trading_service.sdk.stock.filled_history = Mock(return_value=mock_result)

        result = trading_service.get_filled_history({"account": "1234567", "start_date": "20251118"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert "查詢成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_filled_history_normalize_enum(self, mock_validate, trading_service):
        """測試 get_filled_history 能將 SDK 的 enum 字串正規化為簡單名稱 """
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "order_no": "ORD777",
                "stock_no": "2330",
                "buy_sell": "BSAction.Sell",
                "order_type": "OrderType.Stock",
                "filled_qty": 500,
                "filled_price": 800.0,
                "filled_time": "11:00:00.000",
            }
        ]
        trading_service.sdk.stock.filled_history = Mock(return_value=mock_result)

        result = trading_service.get_filled_history({"account": "1234567", "start_date": "20251118"})

        assert result["status"] == "success"
        assert result["data"][0]["order_no"] == "ORD777"
        assert result["data"][0]["buy_sell"] == "Sell"
        assert result["data"][0]["order_type"] == "Stock"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_trail_profit_success(self, mock_validate, trading_service):
        """測試移動鎖利條件單建立成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 建立移動鎖利單成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = Mock()
        mock_result.data.guid = "TRAIL_GUID_001"
        trading_service.sdk.stock.trail_profit = Mock(return_value=mock_result)

        result = trading_service.place_trail_profit(
            {
                "account": "1234567",
                "start_date": "20241106",
                "end_date": "20241107",
                "stop_sign": "Full",
                "trail": {
                    "symbol": "2330",
                    "price": "850.00",
                    "direction": "Up",
                    "percentage": 5,
                    "buysell": "Buy",
                    "quantity": 1000,
                    "price_type": "MatchedPrice",
                    "diff": 5,
                    "time_in_force": "ROD",
                    "order_type": "Stock",
                },
            }
        )

        assert result["status"] == "success"
        assert result["data"]["guid"] == "TRAIL_GUID_001"
        assert "移動鎖利條件單已建立" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_time_slice_order_success(self, mock_validate, trading_service):
        """測試分時分量查詢成功"""
        # 模擬驗證成功
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 查詢分時分量成功
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"batch_no": "BATCH001", "symbol": "2330", "status": "Active"}]
        trading_service.sdk.stock.get_time_slice_order = Mock(return_value=mock_result)

        result = trading_service.get_time_slice_order({"account": "1234567", "batch_no": "BATCH001"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert "查詢成功" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_multi_condition_order_success(self, mock_validate, trading_service):
        """測試多條件單建立成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"condition_no": "MULTI001"}
        trading_service.sdk.stock.place_multi_condition_order = Mock(return_value=mock_result)

        result = trading_service.place_multi_condition_order({
            "account": "1234567",
            "start_date": "20250101",
            "end_date": "20251231",
            "stop_sign": "Full",
            "conditions": [
                {"market_type": "Reference", "symbol": "2330", "trigger": "MatchedPrice", "trigger_value": "500", "comparison": "Greater"},
                {"market_type": "Reference", "symbol": "2330", "trigger": "TotalQuantity", "trigger_value": "10000", "comparison": "Greater"}
            ],
            "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000}
        })

        assert result["status"] == "success"
        assert result["data"]["condition_no"] == "MULTI001"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_daytrade_condition_order_success(self, mock_validate, trading_service):
        """測試當沖條件單建立成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"condition_no": "DT001"}
        trading_service.sdk.stock.place_daytrade_condition_order = Mock(return_value=mock_result)

        result = trading_service.place_daytrade_condition_order({
            "account": "1234567",
            "start_date": "20250101",
            "end_date": "20251231",
            "stop_sign": "Full",
            "conditions": [{"market_type": "Reference", "symbol": "2330", "trigger": "MatchedPrice", "trigger_value": "500", "comparison": "Greater"}],
            "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000, "order_type": "DayTrade"}
        })

        assert result["status"] == "success"
        assert result["data"]["condition_no"] == "DT001"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_daytrade_multi_condition_order_success(self, mock_validate, trading_service):
        """測試當沖多條件單建立成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = Mock(guid="DTMULTI001")
        trading_service.sdk.stock.multi_condition_day_trade = Mock(return_value=mock_result)

        result = trading_service.place_daytrade_multi_condition_order({
            "account": "1234567",
            "stop_sign": "Full",
            "end_time": "130000",
            "conditions": [{"market_type": "Reference", "symbol": "2330", "trigger": "MatchedPrice", "trigger_value": "500", "comparison": "Greater"}],
            "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000, "order_type": "DayTrade"},
            "daytrade": {"day_trade_end_time": "133000", "auto_cancel": False, "price": "510", "price_type": "Limit"}
        })

        assert result["status"] == "success"
        assert result["data"]["guid"] == "DTMULTI001"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_time_slice_order_success(self, mock_validate, trading_service):
        """測試分時分量單建立成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"guid": "TS001"}
        trading_service.sdk.stock.place_time_slice_order = Mock(return_value=mock_result)

        result = trading_service.place_time_slice_order({
            "account": "1234567",
            "start_date": "20250101",
            "end_date": "20250102",
            "stop_sign": "Full",
            "split": {"method": "Type1", "interval": 30, "single_quantity": 1000, "total_quantity": 5000, "start_time": "090000"},
            "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 5000}
        })

        assert result["status"] == "success"
        assert result["data"]["guid"] == "TS001"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_tpsl_condition_order_success(self, mock_validate, trading_service):
        """測試停損停利條件單建立成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"condition_no": "TPSL001"}
        trading_service.sdk.stock.place_condition_order = Mock(return_value=mock_result)

        result = trading_service.place_tpsl_condition_order({
            "account": "1234567",
            "start_date": "20250101",
            "end_date": "20251231",
            "stop_sign": "Full",
            "condition": {"market_type": "Reference", "symbol": "2330", "trigger": "MatchedPrice", "trigger_value": "500", "comparison": "Greater"},
            "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000},
            "tpsl": {
                "stop_sign": "Full",
                "tp": {"target_price": "550", "price": "550"},
                "sl": {"target_price": "450", "price": "450"}
            }
        })

        assert result["status"] == "success"
        assert result["data"]["condition_no"] == "TPSL001"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_condition_order_by_id_success(self, mock_validate, trading_service):
        """測試依ID查詢條件單成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"condition_no": "COND001", "status": "Active"}
        trading_service.sdk.stock.get_condition_order_by_id = Mock(return_value=mock_result)

        result = trading_service.get_condition_order_by_id({"account": "1234567", "condition_no": "COND001"})

        assert result["status"] == "success"
        assert result["data"]["condition_no"] == "COND001"

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_daytrade_condition_by_id_success(self, mock_validate, trading_service):
        """測試依ID查詢當沖條件單成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"condition_no": "DT001", "status": "Active"}
        trading_service.sdk.stock.get_daytrade_condition_by_id = Mock(return_value=mock_result)

        result = trading_service.get_daytrade_condition_by_id({"account": "1234567", "condition_no": "DT001"})

        assert result["status"] == "success"
        assert result["data"]["condition_no"] == "DT001"
