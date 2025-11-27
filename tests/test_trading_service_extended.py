#!/usr/bin/env python3
"""
Trading Service 擴展測試 - 提升覆蓋率

此測試檔案針對 trading_service.py 中未覆蓋的部分進行測試，特別是：
1. 錯誤處理路徑
2. 條件單的各種錯誤情況
3. 修改訂單的錯誤處理
4. 移動鎖利單的錯誤處理
5. 分時分量單的錯誤處理
6. 多條件單的錯誤處理
7. 當沖條件單的錯誤處理
8. 停損停利的錯誤處理
9. 歷史查詢的無數據情況
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from fubon_api_mcp_server.trading_service import TradingService


class TestTradingServiceExtended:
    """Trading Service 擴展測試 - 覆蓋錯誤處理和邊界情況"""

    @pytest.fixture
    def mock_mcp(self):
        """模擬 MCP 實例"""
        return Mock(spec=FastMCP)

    @pytest.fixture
    def mock_sdk(self):
        """模擬 SDK 實例"""
        sdk = Mock()
        mock_account = Mock()
        mock_account.account = "1234567"
        mock_account.name = "測試用戶"

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

    # ==================== 帳號驗證錯誤測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_order_account_validation_error(self, mock_validate, trading_service):
        """測試下單時帳號驗證失敗"""
        mock_validate.return_value = (None, "帳號驗證失敗：帳號不存在")

        result = trading_service.place_order(
            {"account": "invalid", "buy_sell": "Buy", "symbol": "2330", "price": "500.0", "quantity": 1000}
        )

        assert result["status"] == "error"
        assert "帳號驗證失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_cancel_order_account_validation_error(self, mock_validate, trading_service):
        """測試取消訂單時帳號驗證失敗"""
        mock_validate.return_value = (None, "帳號驗證失敗")

        result = trading_service.cancel_order({"account": "invalid", "order_no": "12345678"})

        assert result["status"] == "error"
        assert "帳號驗證失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_modify_price_account_validation_error(self, mock_validate, trading_service):
        """測試改價時帳號驗證失敗"""
        mock_validate.return_value = (None, "帳號驗證失敗")

        result = trading_service.modify_price({"account": "invalid", "order_no": "12345678", "new_price": 505.0})

        assert result["status"] == "error"
        assert "帳號驗證失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_modify_quantity_account_validation_error(self, mock_validate, trading_service):
        """測試改量時帳號驗證失敗"""
        mock_validate.return_value = (None, "帳號驗證失敗")

        result = trading_service.modify_quantity({"account": "invalid", "order_no": "12345678", "new_quantity": 500})

        assert result["status"] == "error"
        assert "帳號驗證失敗" in result["message"]

    # ==================== SDK 錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_order_sdk_exception(self, mock_validate, trading_service):
        """測試下單時 SDK 拋出異常"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        trading_service.sdk.stock.place_order = Mock(side_effect=Exception("SDK 連線錯誤"))

        result = trading_service.place_order(
            {"account": "1234567", "buy_sell": "Buy", "symbol": "2330", "price": "500.0", "quantity": 1000}
        )

        assert result["status"] == "error"
        assert "SDK 連線錯誤" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_cancel_order_sdk_failure(self, mock_validate, trading_service):
        """測試取消訂單失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # Mock get_order_results to return the order
        mock_get_results = Mock()
        mock_get_results.is_success = True
        mock_get_results.data = [{"order_no": "12345678"}]
        trading_service.sdk.stock.get_order_results = Mock(return_value=mock_get_results)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "取消失敗：訂單已成交"
        trading_service.sdk.stock.cancel_order = Mock(return_value=mock_result)

        result = trading_service.cancel_order({"account": "1234567", "order_no": "12345678"})

        assert result["status"] == "error"
        assert "取消失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_modify_price_sdk_failure(self, mock_validate, trading_service):
        """測試改價失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # Mock get_order_results to return the order
        mock_get_results = Mock()
        mock_get_results.is_success = True
        mock_get_results.data = [{"order_no": "12345678"}]
        trading_service.sdk.stock.get_order_results = Mock(return_value=mock_get_results)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "改價失敗：價格超出漲跌幅限制"
        trading_service.sdk.stock.modify_price = Mock(return_value=mock_result)
        trading_service.sdk.stock.make_modify_price_obj = Mock(return_value={"order_no": "12345678"})

        result = trading_service.modify_price({"account": "1234567", "order_no": "12345678", "new_price": 999.0})

        assert result["status"] == "error"
        assert "改價失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_modify_quantity_sdk_failure(self, mock_validate, trading_service):
        """測試改量失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "改量失敗：數量超過可用庫存"
        trading_service.sdk.stock.modify_quantity = Mock(return_value=mock_result)

        result = trading_service.modify_quantity({"account": "1234567", "order_no": "12345678", "new_quantity": 10000})

        assert result["status"] == "error"
        assert "改量失敗" in result["message"]

    # ==================== 條件單錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_condition_order_failure(self, mock_validate, trading_service):
        """測試建立條件單失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "條件單建立失敗：參數錯誤"
        trading_service.sdk.single_condition = Mock(return_value=mock_result)
        trading_service.sdk.stock.single_condition = trading_service.sdk.single_condition

        result = trading_service.place_condition_order(
            {
                "account": "1234567",
                "start_date": "20250101",
                "end_date": "20251231",
                "stop_sign": "Full",
                "condition": {
                    "market_type": "Reference",
                    "symbol": "2330",
                    "trigger": "MatchedPrice",
                    "trigger_value": "500",
                    "comparison": "LessThan"
                },
                "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000},
            }
        )

        assert result["status"] == "error"
        assert "條件單建立失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_cancel_condition_order_failure(self, mock_validate, trading_service):
        """測試取消條件單失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "取消失敗：條件單已觸發"
        trading_service.sdk.stock.cancel_condition_order = Mock(return_value=mock_result)

        result = trading_service.cancel_condition_order({"account": "1234567", "condition_no": "COND001"})

        assert result["status"] == "error"
        assert "取消失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_condition_order_failure(self, mock_validate, trading_service):
        """測試查詢條件單失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：連線逾時"
        trading_service.sdk.stock.get_condition_order = Mock(return_value=mock_result)

        result = trading_service.get_condition_order({"account": "1234567"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_condition_order_empty_data(self, mock_validate, trading_service):
        """測試查詢條件單無數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        trading_service.sdk.stock.get_condition_order = Mock(return_value=mock_result)

        result = trading_service.get_condition_order({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 0

    # ==================== 移動鎖利單錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_trail_profit_failure(self, mock_validate, trading_service):
        """測試移動鎖利單建立失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "移動鎖利單建立失敗：參數錯誤"
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

        assert result["status"] == "error"
        assert "移動鎖利單建立失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_trail_order_failure(self, mock_validate, trading_service):
        """測試查詢移動鎖利單失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：系統錯誤"
        trading_service.sdk.stock.get_trail_order = Mock(return_value=mock_result)

        result = trading_service.get_trail_order({"account": "1234567"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_trail_order_empty_data(self, mock_validate, trading_service):
        """測試查詢移動鎖利單無數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        trading_service.sdk.stock.get_trail_order = Mock(return_value=mock_result)

        result = trading_service.get_trail_order({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 0

    # ==================== 分時分量單錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_time_slice_order_failure(self, mock_validate, trading_service):
        """測試分時分量單建立失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "分時分量單建立失敗：時間區間錯誤"
        trading_service.sdk.stock.place_time_slice_order = Mock(return_value=mock_result)

        result = trading_service.place_time_slice_order(
            {
                "account": "1234567",
                "start_date": "20250101",
                "end_date": "20250102",
                "stop_sign": "Full",
                "split": {"method": "Type1", "interval": 30, "single_quantity": 1000, "total_quantity": 5000, "start_time": "090000"},
                "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 5000},
            }
        )

        assert result["status"] == "error"
        assert "分時分量單建立失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_time_slice_order_failure(self, mock_validate, trading_service):
        """測試查詢分時分量單失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：批次號不存在"
        trading_service.sdk.stock.get_time_slice_order = Mock(return_value=mock_result)

        result = trading_service.get_time_slice_order({"account": "1234567", "batch_no": "INVALID"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_time_slice_order_empty_data(self, mock_validate, trading_service):
        """測試查詢分時分量單無數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        trading_service.sdk.stock.get_time_slice_order = Mock(return_value=mock_result)

        result = trading_service.get_time_slice_order({"account": "1234567", "batch_no": "BATCH001"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 0

    # ==================== 多條件單錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_multi_condition_order_failure(self, mock_validate, trading_service):
        """測試多條件單建立失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "多條件單建立失敗：條件衝突"
        trading_service.sdk.stock.place_multi_condition_order = Mock(return_value=mock_result)

        result = trading_service.place_multi_condition_order(
            {
                "account": "1234567",
                "start_date": "20250101",
                "end_date": "20251231",
                "stop_sign": "Full",
                "conditions": [
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "MatchedPrice",
                        "trigger_value": "500",
                        "comparison": "Greater",
                    },
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "TotalQuantity",
                        "trigger_value": "10000",
                        "comparison": "Greater",
                    },
                ],
                "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000},
            }
        )

        assert result["status"] == "error"
        assert "多條件單建立失敗" in result["message"]

    # ==================== 當沖條件單錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_daytrade_condition_order_failure(self, mock_validate, trading_service):
        """測試當沖條件單建立失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "當沖條件單建立失敗：不符合當沖條件"
        trading_service.sdk.stock.place_daytrade_condition_order = Mock(return_value=mock_result)

        result = trading_service.place_daytrade_condition_order(
            {
                "account": "1234567",
                "start_date": "20250101",
                "end_date": "20251231",
                "stop_sign": "Full",
                "conditions": [
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "MatchedPrice",
                        "trigger_value": "500",
                        "comparison": "Greater",
                    }
                ],
                "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000, "order_type": "DayTrade"},
            }
        )

        assert result["status"] == "error"
        assert "當沖條件單建立失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_daytrade_multi_condition_order_failure(self, mock_validate, trading_service):
        """測試當沖多條件單建立失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "當沖多條件單建立失敗：時間設定錯誤"
        trading_service.sdk.stock.multi_condition_day_trade = Mock(return_value=mock_result)

        result = trading_service.place_daytrade_multi_condition_order(
            {
                "account": "1234567",
                "stop_sign": "Full",
                "end_time": "130000",
                "conditions": [
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "MatchedPrice",
                        "trigger_value": "500",
                        "comparison": "Greater",
                    }
                ],
                "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000, "order_type": "DayTrade"},
                "daytrade": {"day_trade_end_time": "133000", "auto_cancel": False, "price": "510", "price_type": "Limit"},
            }
        )

        assert result["status"] == "error"
        assert "當沖多條件單建立失敗" in result["message"]

    # ==================== 停損停利錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_tpsl_condition_order_failure(self, mock_validate, trading_service):
        """測試停損停利條件單建立失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "停損停利條件單建立失敗：價格設定錯誤"
        trading_service.sdk.single_condition = Mock(return_value=mock_result)
        trading_service.sdk.stock.single_condition = trading_service.sdk.single_condition

        result = trading_service.place_tpsl_condition_order(
            {
                "account": "1234567",
                "start_date": "20250101",
                "end_date": "20251231",
                "stop_sign": "Full",
                "condition": {
                    "market_type": "Reference",
                    "symbol": "2330",
                    "trigger": "MatchedPrice",
                    "trigger_value": "500",
                    "comparison": "Greater",
                },
                "order": {"buy_sell": "Buy", "symbol": "2330", "price": "500", "quantity": 1000},
                "tpsl": {"stop_sign": "Full", "tp": {"target_price": "550", "price": "550"}, "sl": {"target_price": "450", "price": "450"}},
            }
        )

        assert result["status"] == "error"
        assert "停損停利條件單建立失敗" in result["message"]

    # ==================== 歷史查詢錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_history_failure(self, mock_validate, trading_service):
        """測試查詢歷史委託失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：日期格式錯誤"
        trading_service.sdk.stock.order_history = Mock(return_value=mock_result)

        result = trading_service.get_order_history({"account": "1234567", "start_date": "invalid", "end_date": "20251118"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_history_empty_data(self, mock_validate, trading_service):
        """測試查詢歷史委託無數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        trading_service.sdk.stock.order_history = Mock(return_value=mock_result)

        result = trading_service.get_order_history({"account": "1234567", "start_date": "20251118", "end_date": "20251118"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 0

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_filled_history_failure(self, mock_validate, trading_service):
        """測試查詢歷史成交失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：日期超出範圍"
        trading_service.sdk.stock.filled_history = Mock(return_value=mock_result)

        result = trading_service.get_filled_history({"account": "1234567", "start_date": "19990101"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_filled_history_empty_data(self, mock_validate, trading_service):
        """測試查詢歷史成交無數據"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        trading_service.sdk.stock.filled_history = Mock(return_value=mock_result)

        result = trading_service.get_filled_history({"account": "1234567", "start_date": "20251118"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 0

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_results_failure(self, mock_validate, trading_service):
        """測試獲取委託結果失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：連線中斷"
        trading_service.sdk.stock.get_order_results = Mock(return_value=mock_result)

        result = trading_service.get_order_results({"account": "1234567"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_order_results_detail_failure(self, mock_validate, trading_service):
        """測試獲取委託結果詳細資訊失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：權限不足"
        trading_service.sdk.stock.get_order_results_detail = Mock(return_value=mock_result)

        result = trading_service.get_order_results_detail({"account": "1234567"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    # ==================== 條件單查詢錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_condition_order_by_id_failure(self, mock_validate, trading_service):
        """測試依ID查詢條件單失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：條件單號不存在"
        trading_service.sdk.stock.get_condition_order_by_id = Mock(return_value=mock_result)

        result = trading_service.get_condition_order_by_id({"account": "1234567", "condition_no": "INVALID"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_get_daytrade_condition_by_id_failure(self, mock_validate, trading_service):
        """測試依ID查詢當沖條件單失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "查詢失敗：條件單號不存在"
        trading_service.sdk.stock.get_daytrade_condition_by_id = Mock(return_value=mock_result)

        result = trading_service.get_daytrade_condition_by_id({"account": "1234567", "condition_no": "INVALID"})

        assert result["status"] == "error"
        assert "查詢失敗" in result["message"]

    # ==================== 批量下單錯誤處理測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_batch_place_order_all_failures(self, mock_validate, trading_service):
        """測試批量下單全部失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result_failure = Mock()
        mock_result_failure.is_success = False
        mock_result_failure.message = "下單失敗"

        trading_service.sdk.place_order = Mock(return_value=mock_result_failure)
        trading_service.sdk.stock.place_order = trading_service.sdk.place_order

        orders = [
            {"account": "1234567", "buy_sell": "Buy", "symbol": "2330", "price": "500.0", "quantity": 1000},
            {"account": "1234567", "buy_sell": "Sell", "symbol": "2454", "price": "800.0", "quantity": 500},
        ]

        result = trading_service.batch_place_order({"orders": orders})

        assert result["status"] == "success"
        assert "results" in result["data"]
        assert len(result["data"]["results"]) == 2
        assert all(r["status"] == "error" for r in result["data"]["results"])

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_batch_place_order_exception_in_one(self, mock_validate, trading_service):
        """測試批量下單其中一筆拋出異常"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result_success = Mock()
        mock_result_success.is_success = True
        mock_result_success.data = {"order_no": "12345678"}

        # 第二筆拋出異常
        trading_service.sdk.place_order = Mock(side_effect=[mock_result_success, Exception("網路錯誤")])
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
        assert "網路錯誤" in result["data"]["results"][1]["message"]

    # ==================== 輔助方法測試 ====================

    def test_to_dict_with_none(self, trading_service):
        """測試 _to_dict 處理 None 值"""
        result = trading_service._to_dict(None)
        assert result is None

    def test_to_dict_with_primitives(self, trading_service):
        """測試 _to_dict 處理基本類型"""
        assert trading_service._to_dict("test") == "test"
        assert trading_service._to_dict(123) == 123
        assert trading_service._to_dict(45.67) == 45.67
        assert trading_service._to_dict(True) is True

    def test_to_dict_with_list(self, trading_service):
        """測試 _to_dict 處理列表"""
        result = trading_service._to_dict([1, "test", None, {"key": "value"}])
        assert result == [1, "test", None, {"key": "value"}]

    def test_to_dict_with_dict(self, trading_service):
        """測試 _to_dict 處理字典"""
        input_dict = {"a": 1, "b": "test", "c": None}
        result = trading_service._to_dict(input_dict)
        assert result == input_dict

    def test_to_dict_with_object_vars(self, trading_service):
        """測試 _to_dict 處理物件（使用 vars）"""
        mock_obj = Mock()
        mock_obj.name = "Test Name"
        mock_obj.account = "1234567"
        mock_obj._private = "should be ignored"

        result = trading_service._to_dict(mock_obj)
        assert isinstance(result, dict)
        assert "name" in result or "account" in result  # At least one of the public attrs

    def test_to_dict_with_object_fallback(self, trading_service):
        """測試 _to_dict 使用 fallback 路徑處理物件（模擬 SDK 物件）"""

        # 建立一個類似 SDK 物件的測試物件，vars() 無法正常運作
        class SDKLikeObject:
            """模擬某些 SDK 物件，vars() 會失敗但 dir()/getattr() 可用"""
            __slots__ = ['order_no', 'status', 'price']
            
            def __init__(self):
                self.order_no = "12345678"
                self.status = "Active"
                self.price = 500.0

        obj = SDKLikeObject()
        result = trading_service._to_dict(obj)
        
        # 應該使用 dir()/getattr() fallback 成功提取屬性
        assert isinstance(result, dict)
        assert result.get("order_no") == "12345678"
        assert result.get("status") == "Active"
        assert result.get("price") == 500.0

    def test_normalize_order_result_with_enums(self, trading_service):
        """測試 _normalize_order_result 將 enum 字串正規化"""
        raw_obj = {
            "order_no": "ORD123",
            "buy_sell": "BSAction.Buy",
            "order_type": "OrderType.Stock",
            "price_type": "PriceType.Limit",
            "status": "Status.10",
        }

        result = trading_service._normalize_order_result(raw_obj)
        assert result["order_no"] == "ORD123"
        assert result["buy_sell"] == "Buy"
        assert result["order_type"] == "Stock"
        assert result["price_type"] == "Limit"

    def test_normalize_order_result_with_details(self, trading_service):
        """測試 _normalize_order_result 處理 details 子列表"""
        raw_obj = {
            "order_no": "ORD456",
            "details": [
                {"status": "Status.90", "modified_time": "10:00:00", "price_type": "PriceType.Market"},
                {"status": "Status.10", "modified_time": "11:00:00", "price_type": "PriceType.Limit"},
            ],
        }

        result = trading_service._normalize_order_result(raw_obj)
        assert result["order_no"] == "ORD456"
        assert len(result["details"]) == 2
        assert result["details"][0]["modified_time"] == "10:00:00"
        assert result["details"][1]["modified_time"] == "11:00:00"

    # ==================== 期貨/選擇權訂單測試 ====================

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_place_futopt_order_success(self, mock_validate, trading_service):
        """測試期貨/選擇權下單成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = Mock()
        mock_result.data.order_no = "FUT12345"
        # Also set as dict for _to_dict conversion
        trading_service.sdk.futopt.place_order = Mock(return_value=mock_result)

        result = trading_service.place_order(
            {
                "account": "1234567",
                "buy_sell": "Buy",
                "symbol": "TXFB5",
                "price": "16000",
                "quantity": 1,
                "market_type": "Common",
                "price_type": "Limit",
                "time_in_force": "ROD",
                "order_type": "Fut",
            }
        )

        assert result["status"] == "success"
        # Accept either dict with 'order_no' key or object with order_no attribute
        assert (
            ("order_no" in result["data"])
            or (hasattr(result["data"], "order_no"))
            or (isinstance(result["data"], dict) and len(result["data"]) > 0)
        )

    @patch("fubon_api_mcp_server.trading_service.validate_and_get_account")
    def test_cancel_futopt_order_success(self, mock_validate, trading_service):
        """測試取消期貨/選擇權訂單成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = True
        trading_service.sdk.futopt.cancel_order = Mock(return_value=mock_result)

        result = trading_service.cancel_order({"account": "1234567", "order_res": {"order_no": "FUT12345"}, "unblock": True})

        assert result["status"] == "success"
        assert "取消成功" in result["message"]
