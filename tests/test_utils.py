#!/usr/bin/env python3
"""
測試 utils.py 模組的輔助函數
"""
import os
from unittest.mock import Mock, MagicMock, patch, PropertyMock

import pytest

from fubon_api_mcp_server import config as config_module
from fubon_api_mcp_server.utils import (
    handle_exceptions,
    validate_and_get_account,
    get_order_by_no,
    _safe_api_call,
    normalize_item,
)


class TestHandleExceptions:
    """測試 handle_exceptions 裝飾器"""

    def test_function_success(self):
        """測試函數正常執行"""

        @handle_exceptions
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"

    def test_function_with_exception(self, caplog):
        """測試函數拋出異常時的處理"""

        @handle_exceptions
        def test_func():
            raise ValueError("test error")

        with caplog.at_level("ERROR"):
            result = test_func()
            assert result is None
            assert "test_func exception" in caplog.text


class TestValidateAndGetAccount:
    """測試 validate_and_get_account 函數"""

    @pytest.fixture(autouse=True)
    def reset_config(self):
        """每個測試前重置 config 模組"""
        original_sdk = config_module.sdk
        original_accounts = config_module.accounts
        yield
        config_module.sdk = original_sdk
        config_module.accounts = original_accounts

    def test_account_not_found(self):
        """測試帳號不存在的情況"""
        # 設置 mock SDK 和 accounts
        mock_sdk = Mock()
        mock_account = Mock()
        mock_account.account = "9999999"

        mock_accounts = Mock()
        mock_accounts.data = [mock_account]

        config_module.sdk = mock_sdk
        config_module.accounts = mock_accounts

        account_obj, error = validate_and_get_account("1234567")
        assert account_obj is None
        assert "not found" in error

    def test_account_found_success(self):
        """測試成功找到帳號"""
        # 設置 mock SDK 和 accounts
        mock_sdk = Mock()
        mock_account = Mock()
        mock_account.account = "1234567"

        mock_accounts = Mock()
        mock_accounts.data = [mock_account]

        config_module.sdk = mock_sdk
        config_module.accounts = mock_accounts

        account_obj, error = validate_and_get_account("1234567")
        assert account_obj is not None
        assert error is None
        assert account_obj.account == "1234567"

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_credentials(self):
        """測試缺少認證資訊的情況"""
        config_module.sdk = None
        config_module.accounts = None

        account_obj, error = validate_and_get_account("1234567")
        assert account_obj is None
        # 可能是認證失敗或帳號未找到,兩者都是合理的錯誤
        assert error is not None and len(error) > 0

    @patch("dotenv.load_dotenv")
    @patch("fubon_neo.sdk.FubonSDK")
    @patch.dict(
        os.environ,
        {
            "FUBON_USERNAME": "testuser",
            "FUBON_PASSWORD": "testpass",
            "FUBON_PFX_PATH": "test.pfx",
            "FUBON_PFX_PASSWORD": "pfxpass",
        },
    )
    def test_sdk_initialization_success(self, mock_sdk_class, mock_load_dotenv):
        """測試 SDK 初始化成功"""
        config_module.sdk = None
        config_module.accounts = None

        # Setup mock SDK
        mock_sdk_instance = Mock()
        mock_sdk_class.return_value = mock_sdk_instance

        # Setup mock account
        mock_account = Mock()
        mock_account.account = "1234567"

        # Setup mock login response
        mock_accounts = Mock()
        mock_accounts.is_success = True
        mock_accounts.data = [mock_account]
        mock_sdk_instance.login.return_value = mock_accounts

        account_obj, error = validate_and_get_account("1234567")

        assert account_obj is not None
        assert error is None
        assert account_obj.account == "1234567"
        mock_sdk_instance.login.assert_called_once_with("testuser", "testpass", "test.pfx", "pfxpass")

    @patch("dotenv.load_dotenv")
    @patch("fubon_neo.sdk.FubonSDK")
    @patch.dict(
        os.environ,
        {"FUBON_USERNAME": "testuser", "FUBON_PASSWORD": "testpass", "FUBON_PFX_PATH": "test.pfx"},
    )
    def test_sdk_initialization_failure(self, mock_sdk_class, mock_load_dotenv):
        """測試 SDK 初始化失敗"""
        config_module.sdk = None
        config_module.accounts = None

        # Setup mock SDK
        mock_sdk_instance = Mock()
        mock_sdk_class.return_value = mock_sdk_instance

        # Setup failed login response
        mock_accounts = Mock()
        mock_accounts.is_success = False
        mock_sdk_instance.login.return_value = mock_accounts

        account_obj, error = validate_and_get_account("1234567")

        assert account_obj is None
        assert "authentication failed" in error.lower()


class TestGetOrderByNo:
    """測試 get_order_by_no 函數"""

    def test_sdk_not_initialized(self):
        """測試 SDK 未初始化"""
        config_module.sdk = None
        mock_account = Mock()

        order_obj, error = get_order_by_no(mock_account, "ORDER123")
        assert order_obj is None
        assert "not initialized" in error

    def test_order_not_found(self):
        """測試訂單不存在"""
        # Setup mock SDK
        mock_sdk = Mock()
        mock_stock = Mock()

        mock_order = Mock()
        mock_order.order_no = "OTHER_ORDER"

        mock_results = Mock()
        mock_results.is_success = True
        mock_results.data = [mock_order]

        mock_stock.get_order_results.return_value = mock_results
        mock_sdk.stock = mock_stock
        config_module.sdk = mock_sdk

        mock_account = Mock()

        order_obj, error = get_order_by_no(mock_account, "ORDER123")
        assert order_obj is None
        assert "not found" in error

    def test_order_found_success(self):
        """測試成功找到訂單"""
        # Setup mock SDK
        mock_sdk = Mock()
        mock_stock = Mock()

        mock_order = Mock()
        mock_order.order_no = "ORDER123"

        mock_results = Mock()
        mock_results.is_success = True
        mock_results.data = [mock_order]

        mock_stock.get_order_results.return_value = mock_results
        mock_sdk.stock = mock_stock
        config_module.sdk = mock_sdk

        mock_account = Mock()

        order_obj, error = get_order_by_no(mock_account, "ORDER123")
        assert order_obj is not None
        assert error is None
        assert order_obj.order_no == "ORDER123"

    def test_get_order_results_failure(self):
        """測試獲取訂單結果失敗"""
        # Setup mock SDK
        mock_sdk = Mock()
        mock_stock = Mock()

        mock_results = Mock()
        mock_results.is_success = False

        mock_stock.get_order_results.return_value = mock_results
        mock_sdk.stock = mock_stock
        config_module.sdk = mock_sdk

        mock_account = Mock()

        order_obj, error = get_order_by_no(mock_account, "ORDER123")
        assert order_obj is None
        assert "Unable to get" in error

    def test_get_order_results_exception(self):
        """測試獲取訂單時發生異常"""
        # Setup mock SDK
        mock_sdk = Mock()
        mock_stock = Mock()
        mock_stock.get_order_results.side_effect = Exception("API Error")

        mock_sdk.stock = mock_stock
        config_module.sdk = mock_sdk

        mock_account = Mock()

        order_obj, error = get_order_by_no(mock_account, "ORDER123")
        assert order_obj is None
        assert "Error getting order results" in error


class TestSafeApiCall:
    """測試 _safe_api_call 函數"""

    def test_api_call_success(self):
        """測試 API 調用成功"""

        def mock_api():
            result = Mock()
            result.is_success = True
            result.data = {"key": "value"}
            return result

        result = _safe_api_call(mock_api, "Test Error")
        assert result == {"key": "value"}

    def test_api_call_failure(self):
        """測試 API 調用失敗"""

        def mock_api():
            result = Mock()
            result.is_success = False
            return result

        result = _safe_api_call(mock_api, "Test Error")
        assert result is None

    def test_api_call_exception(self):
        """測試 API 調用拋出異常"""

        def mock_api():
            raise ValueError("API Error")

        result = _safe_api_call(mock_api, "Test Error")
        assert isinstance(result, str)
        assert "Test Error" in result
        assert "API Error" in result

    def test_api_call_no_is_success(self):
        """測試 API 返回對象沒有 is_success 屬性"""

        def mock_api():
            return None

        result = _safe_api_call(mock_api, "Test Error")
        assert result is None


def test_normalize_item_with_dict():
    item = {"stock_no": "2330", "quantity": 10, "cost_price": None}
    nd = normalize_item(item, ["stock_no", "quantity", "cost_price", "stock_name"])  # cost_price None should default to 0

    assert nd["stock_no"] == "2330"
    assert nd["quantity"] == 10
    assert nd["cost_price"] == 0
    assert nd["stock_name"] == ""


def test_normalize_item_with_object():
    class ItemObj:
        def __init__(self):
            self.stock_no = "0050"
            self.market_price = 55.0

    obj = ItemObj()
    nd = normalize_item(obj, ["stock_no", "market_price", "quantity"])  # qty missing -> 0

    assert nd["stock_no"] == "0050"
    assert nd["market_price"] == 55.0
    assert nd["quantity"] == 0


def test_normalize_item_with_none_values():
    item = {"stock_no": None, "quantity": None}
    nd = normalize_item(item, ["stock_no", "quantity"])  # none -> defaults

    assert nd["stock_no"] == ""
    assert nd["quantity"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-q"])

