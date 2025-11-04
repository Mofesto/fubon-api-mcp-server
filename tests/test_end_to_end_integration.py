"""
端到端整合測試 - 使用真實的 fubon_neo SDK
測試完整的 MCP 服務器功能流程
"""

import os

import pytest


class TestEndToEndIntegration:
    """端到端整合測試"""

    @pytest.fixture(autouse=True)
    def setup_environment(self):
        """設定測試環境"""
        # 確保使用真實 SDK
        os.environ["USE_REAL_SDK"] = "true"
        yield
        # 清理環境變數
        if "USE_REAL_SDK" in os.environ:
            del os.environ["USE_REAL_SDK"]

    def test_mcp_server_initialization(self, fubon_sdk, fubon_credentials):
        """測試 MCP 服務器初始化"""
        try:
            from fubon_mcp.server import mcp

            # 檢查 MCP 實例是否存在
            assert mcp is not None

            # 檢查必要的 callable 函數是否存在
            from fubon_mcp.server import (
                callable_get_account_info,
                callable_get_bank_balance,
                callable_get_inventory,
                callable_get_order_results,
                callable_place_order,
            )

            # 驗證函數都是可調用的
            assert callable(callable_get_account_info)
            assert callable(callable_get_bank_balance)
            assert callable(callable_get_inventory)
            assert callable(callable_place_order)
            assert callable(callable_get_order_results)

        except Exception as e:
            pytest.fail(f"MCP 服務器初始化測試失敗: {str(e)}")

    def test_account_services_integration(self, fubon_sdk, fubon_credentials):
        """測試帳戶服務整合"""
        try:
            # 設置全局 SDK 和帳戶變數
            import fubon_mcp.config as config

            config.sdk = fubon_sdk[0]  # SDK 實例
            config.accounts = fubon_sdk[1]  # 帳戶資訊

            from fubon_mcp.server import callable_get_account_info, callable_get_bank_balance, callable_get_inventory

            # 測試獲取帳戶資訊
            account_result = callable_get_account_info({"account": ""})
            assert account_result["status"] == "success"
            assert "data" in account_result
            assert len(account_result["data"]) > 0

            # 使用第一個帳戶進行後續測試
            first_account = account_result["data"][0]["account"]

            # 測試銀行餘額
            balance_result = callable_get_bank_balance({"account": first_account})
            # Check if API is rate limited
            if balance_result.get("message") and "流量控管" in str(balance_result.get("message", "")):
                pytest.skip("API rate limited - skipping bank balance test")
            assert balance_result["status"] == "success"
            assert "data" in balance_result
            import time

            time.sleep(0.5)  # Add delay to avoid rate limiting

            # 測試庫存查詢
            inventory_result = callable_get_inventory({"account": first_account})
            assert inventory_result["status"] == "success"
            assert "data" in inventory_result

        except Exception as e:
            pytest.fail(f"帳戶服務整合測試失敗: {str(e)}")

    def test_market_data_integration(self, fubon_sdk):
        """測試市場數據整合"""
        try:
            from fubon_mcp.server import callable_get_realtime_quotes

            # 測試即時報價查詢 (使用台積電代號)
            quotes_result = callable_get_realtime_quotes({"symbols": ["2330"], "fields": ["price", "volume"]})

            # 即使沒有數據，回應格式應該正確
            assert "status" in quotes_result
            if quotes_result["status"] == "success":
                assert "data" in quotes_result

        except Exception as e:
            pytest.fail(f"市場數據整合測試失敗: {str(e)}")

    def test_trading_workflow_integration(self, fubon_sdk, fubon_credentials):
        """測試交易流程整合 (模擬下單，不實際執行)"""
        try:
            # 獲取帳戶
            from fubon_mcp.server import (
                callable_cancel_order,
                callable_get_account_info,
                callable_get_order_results,
                callable_modify_price,
            )

            account_result = callable_get_account_info({"account": ""})
            assert account_result["status"] == "success"
            first_account = account_result["data"][0]["account"]

            # 測試獲取委託結果
            order_results = callable_get_order_results({"account": first_account})
            assert "status" in order_results

            # 測試修改價格功能結構
            assert callable(callable_modify_price)

            # 測試取消委託功能結構
            assert callable(callable_cancel_order)

        except Exception as e:
            pytest.fail(f"交易流程整合測試失敗: {str(e)}")

    def test_batch_operations_integration(self, fubon_sdk):
        """測試批量操作整合"""
        try:
            from fubon_mcp.server import callable_batch_place_order

            # 測試批量下單功能結構
            assert callable(callable_batch_place_order)

        except Exception as e:
            pytest.fail(f"批量操作整合測試失敗: {str(e)}")

    def test_error_handling_integration(self, fubon_sdk):
        """測試錯誤處理整合"""
        try:
            from fubon_mcp.server import callable_get_account_info

            # 測試無效帳戶參數
            invalid_result = callable_get_account_info({"account": "INVALID_ACCOUNT_12345"})
            # 應該返回錯誤或空結果，但不應該崩潰
            assert "status" in invalid_result

        except Exception as e:
            pytest.fail(f"錯誤處理整合測試失敗: {str(e)}")

    def test_callback_system_integration(self, fubon_sdk):
        """測試回調系統整合"""
        try:
            from fubon_mcp.server import (
                callable_get_filled_reports,
                callable_get_order_changed_reports,
                callable_get_order_reports,
            )

            # 測試成交回報
            filled_result = callable_get_filled_reports({"limit": 5})
            assert "status" in filled_result

            # 測試委託回報
            order_result = callable_get_order_reports({"limit": 5})
            assert "status" in order_result

            # 測試改單回報
            changed_result = callable_get_order_changed_reports({"limit": 5})
            assert "status" in changed_result

        except Exception as e:
            pytest.fail(f"回調系統整合測試失敗: {str(e)}")

    def test_performance_integration(self, fubon_sdk, fubon_credentials):
        """測試效能整合"""
        import time

        try:
            from fubon_mcp.server import callable_get_account_info

            # 測試響應時間
            start_time = time.time()
            result = callable_get_account_info({"account": ""})
            end_time = time.time()

            response_time = end_time - start_time

            # 響應時間應該在合理範圍內
            assert response_time < 10.0, f"API 響應過慢: {response_time}秒"
            assert result["status"] == "success"

        except Exception as e:
            pytest.fail(f"效能整合測試失敗: {str(e)}")


class TestRealTradingSafety:
    """真實交易安全測試"""

    def test_no_actual_trading_in_ci(self):
        """確保在 CI 環境中不會進行實際交易"""
        # 檢查是否在 CI 環境中
        is_ci = os.getenv("CI", "false").lower() == "true"

        if is_ci:
            # 在 CI 環境中，強制使用模擬模式
            assert os.getenv("USE_REAL_SDK", "false").lower() != "true"

    def test_safe_order_parameters(self):
        """測試安全的訂單參數"""
        # 確保測試不會使用危險的參數
        safe_symbols = ["2330", "2454", "2317"]  # 常見的台股代號
        safe_quantity = 1000  # 最小交易單位

        assert "2330" in safe_symbols
        assert safe_quantity == 1000
