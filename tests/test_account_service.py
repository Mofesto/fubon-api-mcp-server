#!/usr/bin/env python3
"""
富邦 API MCP Server - Account Service 單元測試

此測試檔案使用 pytest 框架測試 account_service 的所有功能。
測試分為兩類：
1. 模擬測試：使用 mock 物件測試邏輯
2. 整合測試：使用真實 API 測試（需要環境變數）

使用方法：
# 運行所有測試
pytest tests/test_account_service.py -v

# 只運行模擬測試
pytest tests/test_account_service.py::TestAccountServiceMock -v

# 只運行整合測試（需要真實憑證）
pytest tests/test_account_service.py::TestAccountServiceIntegration -v
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from fubon_api_mcp_server.account_service import AccountService


class TestAccountServiceMock:
    """模擬測試 - 不依賴真實 API"""

    @pytest.fixture
    def mock_mcp(self):
        """模擬 MCP 實例"""
        return Mock(spec=FastMCP)

    @pytest.fixture
    def mock_sdk(self):
        """模擬 SDK 實例"""
        sdk = Mock()
        # 模擬帳戶物件 (兩個帳號 -> 1234567 與 C04)
        mock_account_1 = Mock()
        mock_account_1.account = "1234567"
        mock_account_1.name = "測試用戶"
        mock_account_1.branch_no = "20203"
        mock_account_1.account_type = "stock"

        mock_account_2 = Mock()
        mock_account_2.account = "C04"
        mock_account_2.name = "測試 C04"
        mock_account_2.branch_no = "99999"
        mock_account_2.account_type = "stock"

        # 模擬帳戶列表 (包含兩筆)
        mock_accounts = Mock()
        mock_accounts.data = [mock_account_1, mock_account_2]

        sdk.accounting = Mock()
        return sdk, mock_accounts

    @pytest.fixture
    def account_service(self, mock_mcp, mock_sdk):
        """建立 AccountService 實例"""
        sdk, accounts = mock_sdk
        return AccountService(mock_mcp, sdk, accounts.data)

    def test_initialization(self, account_service):
        """測試 AccountService 初始化"""
        assert account_service.mcp is not None
        assert account_service.sdk is not None
        assert account_service.accounts is not None

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_account_info_with_account(self, mock_validate, account_service):
        """測試獲取指定帳戶資訊"""
        # 模擬 validate_and_get_account 返回值
        mock_account_obj = Mock()
        mock_account_obj.account = "1234567"
        mock_account_obj.account_name = "測試用戶"
        mock_account_obj.branch_no = "20203"
        mock_account_obj.account_type = "stock"
        mock_account_obj.id_no = "A123456789"
        mock_account_obj.status = "active"
        mock_validate.return_value = (mock_account_obj, None)

        result = account_service.get_account_info({"account": "1234567"})

        assert result["status"] == "success"
        assert result["data"]["account"] == "1234567"
        assert result["data"]["account_name"] == "測試用戶"
        assert "成功獲取帳戶" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_account_info_without_account(self, mock_validate, account_service):
        """測試獲取所有帳戶資訊"""
        # 模擬初始化 SDK 來獲取帳戶列表
        mock_validate.return_value = (None, None)  # 初始化成功但沒有指定帳戶

        # 模擬 config.accounts
        with patch("fubon_api_mcp_server.config.accounts") as mock_accounts:
            mock_accounts.data = account_service.accounts
            result = account_service.get_account_info({})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        # 會返回多個帳戶 (含示例 C04)，確認至少包含測試帳號
        assert any(
            [
                (isinstance(a, dict) and a.get("account") == "1234567")
                or (hasattr(a, "account") and getattr(a, "account") == "1234567")
                for a in result["data"]
            ]
        )
        assert "成功獲取所有帳戶" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_inventory_success(self, mock_validate, account_service):
        """測試獲取庫存成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [Mock(stock_no="0050", quantity=1000, cost_price=50.0, market_price=55.0)]
        account_service.sdk.accounting.inventories.return_value = mock_result

        result = account_service.get_inventory({"account": "1234567"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["stock_no"] == "0050"
        assert "成功獲取帳戶" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_inventory_failure(self, mock_validate, account_service):
        """測試獲取庫存失敗"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 返回失敗
        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API 錯誤"
        account_service.sdk.accounting.inventories.return_value = mock_result

        result = account_service.get_inventory({"account": "1234567"})

        assert result["status"] == "error"
        assert "獲取庫存明細失敗" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_bank_balance_success(self, mock_validate, account_service):
        """測試獲取銀行餘額成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"balance": 100000, "available_balance": 100000}
        account_service.sdk.accounting.bank_remain.return_value = mock_result

        result = account_service.get_bank_balance({"account": "1234567"})

        assert result["status"] == "success"
        assert result["data"]["balance"] == 100000
        assert "成功獲取帳戶" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_maintenance_success(self, mock_validate, account_service):
        """測試獲取維持率成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {
            "maintenance_ratio": 0.0,
            "maintenance_summary": {"margin_value": 0, "shortsell_value": 0},
            "maintenance_detail": [],
        }
        account_service.sdk.accounting.maintenance.return_value = mock_result

        result = account_service.get_maintenance({"account": "1234567"})

        assert result["status"] == "success"
        assert result["data"]["maintenance_ratio"] == 0.0
        assert "成功獲取帳戶" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_settlement_info_success(self, mock_validate, account_service):
        """測試獲取結算資訊成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        account_service.sdk.accounting.query_settlement.return_value = mock_result

        result = account_service.get_settlement_info({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert "成功獲取帳戶" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_realized_pnl_success(self, mock_validate, account_service):
        """測試獲取已實現損益成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        account_service.sdk.accounting.realized_gains_and_loses.return_value = mock_result

        result = account_service.get_realized_pnl({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert "成功獲取已實現損益" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_realized_pnl_summary_success(self, mock_validate, account_service):
        """測試獲取已實現損益摘要成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        account_service.sdk.accounting.realized_gains_and_loses_summary.return_value = mock_result

        result = account_service.get_realized_pnl_summary({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert "成功獲取已實現損益摘要" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_unrealized_pnl_success(self, mock_validate, account_service):
        """測試獲取未實現損益成功"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        # 模擬 SDK 返回
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []
        account_service.sdk.accounting.unrealized_gains_and_loses.return_value = mock_result

        result = account_service.get_unrealized_pnl({"account": "1234567"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert "成功獲取未實現損益" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_account_info_validate_error(self, mock_validate, account_service):
        """測試指定帳戶時 validate_and_get_account 返回錯誤"""
        mock_validate.return_value = (None, "驗證失敗")

        result = account_service.get_account_info({"account": "INVALID"})

        assert result["status"] == "error"
        assert "驗證失敗" in result["message"]

    def test_get_account_info_config_missing(self, account_service):
        """測試沒有 config.accounts 時的行為"""
        # 模擬 initialize (validate_and_get_account 返回成功) 但 config.accounts 缺失
        with patch("fubon_api_mcp_server.account_service.validate_and_get_account", return_value=(None, None)):
            # 模擬 config.accounts 為 None
            with patch("fubon_api_mcp_server.config.accounts", None):
                result = account_service.get_account_info({})

        assert result["status"] == "error"
        assert "帳戶資訊未初始化" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_bank_balance_failure(self, mock_validate, account_service):
        """模擬 bank_remain 返回失敗狀態"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API 錯誤"
        account_service.sdk.accounting.bank_remain.return_value = mock_result

        result = account_service.get_bank_balance({"account": "1234567"})

        assert result["status"] == "error"
        assert "獲取銀行餘額失敗" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_maintenance_failure(self, mock_validate, account_service):
        """模擬 maintenance 返回失敗狀態"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API 錯誤"
        account_service.sdk.accounting.maintenance.return_value = mock_result

        result = account_service.get_maintenance({"account": "1234567"})

        assert result["status"] == "error"
        assert "獲取維持率資訊失敗" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_settlement_info_failure(self, mock_validate, account_service):
        """模擬 query_settlement 返回失敗狀態"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API 錯誤"
        account_service.sdk.accounting.query_settlement.return_value = mock_result

        result = account_service.get_settlement_info({"account": "1234567"})

        assert result["status"] == "error"
        assert "獲取結算資訊失敗" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_realized_pnl_failure(self, mock_validate, account_service):
        """模擬 realized_gains_and_loses 返回失敗狀態"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API 錯誤"
        account_service.sdk.accounting.realized_gains_and_loses.return_value = mock_result

        result = account_service.get_realized_pnl({"account": "1234567"})

        assert result["status"] == "error"
        assert "獲取已實現損益失敗" in result["message"]

    @patch("fubon_api_mcp_server.account_service.validate_and_get_account")
    def test_get_unrealized_pnl_failure(self, mock_validate, account_service):
        """模擬 unrealized_gains_and_loses 返回失敗狀態"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_result = Mock()
        mock_result.is_success = False
        mock_result.message = "API 錯誤"
        account_service.sdk.accounting.unrealized_gains_and_loses.return_value = mock_result

        result = account_service.get_unrealized_pnl({"account": "1234567"})

        assert result["status"] == "error"
        assert "獲取未實現損益失敗" in result["message"]

    def test_to_dict_various_inputs(self, account_service):
        """測試 _to_dict 對不同類型與物件的轉換"""
        # primitives
        assert account_service._to_dict(123) == 123
        assert account_service._to_dict("abc") == "abc"

        # list and dict
        assert account_service._to_dict([1, 2, 3]) == [1, 2, 3]
        assert account_service._to_dict({"a": 1, "b": 2}) == {"a": 1, "b": 2}

        # object with common attributes
        class Obj:
            def __init__(self):
                self.name = "Test"
                self.account = "123"
                self.balance = 1000

        o = Obj()
        d = account_service._to_dict(o)
        assert isinstance(d, dict)
        assert d["name"] == "Test" and d["account"] == "123"

        # nested object in list
        class Inner:
            def __init__(self):
                self.stock_no = "2330"
                self.quantity = 100

        class Outer:
            def __init__(self):
                self.details = [Inner()]

        outer = Outer()
        normalized = account_service._to_dict(outer)
        assert "details" in normalized and isinstance(normalized["details"], list)

    def test_to_dict_vars_raises(self, account_service):
        """測試 vars(obj) 引發例外時，_to_dict 會使用 fallback common_attrs"""

        class BadVars:
            def __init__(self):
                self.name = "Test"
                self.account = "C04"
                self.balance = 500

            def __getattribute__(self, name):
                # emulate vars() raising for __dict__ access
                if name == "__dict__":
                    raise Exception("boom")
                return object.__getattribute__(self, name)

        b = BadVars()
        normalized = account_service._to_dict(b)
        assert isinstance(normalized, dict)
        assert normalized["account"] == "C04"

    def test_multi_account_presence(self, account_service):
        """確認模擬 SDK 帳戶清單有包含 C04"""
        accounts = [a.account if hasattr(a, "account") else a.get("account") for a in account_service.accounts]
        assert "C04" in accounts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
