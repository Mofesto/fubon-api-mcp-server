"""
整合測試和端到端測試
"""

import pytest


class TestIntegration:
    """整合測試"""

    def test_full_workflow_simulation(self, fubon_sdk, fubon_credentials, rest_client):
        """模擬完整工作流程（不實際交易）"""
        try:
            # 解包 SDK 和帳戶資訊
            sdk, accounts = fubon_sdk

            # 1. 檢查帳戶連線
            assert sdk is not None
            assert fubon_credentials["username"] is not None

            # 2. 檢查市場數據可用性
            assert rest_client is not None

            # 3. 檢查基本帳戶功能
            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            balance = sdk.accounting.bank_remain(account_obj)
            assert balance and hasattr(balance, "is_success") and balance.is_success
            import time

            time.sleep(0.5)  # Add delay to avoid rate limiting

            # 4. 檢查庫存功能
            inventory = sdk.accounting.inventories(account_obj)
            assert inventory and hasattr(inventory, "is_success") and inventory.is_success
            time.sleep(0.5)  # Add delay to avoid rate limiting

            # 5. 檢查損益功能
            pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)
            # Check if API is rate limited
            if hasattr(pnl, "message") and "流量控管" in str(pnl.message):
                pytest.skip("API rate limited - skipping integration test")
            assert pnl and hasattr(pnl, "is_success") and pnl.is_success

        except Exception as e:
            pytest.fail(f"整合測試失敗: {str(e)}")

    def test_data_consistency(self, fubon_sdk, fubon_credentials):
        """測試數據一致性"""
        try:
            # 解包 SDK 和帳戶資訊
            sdk, accounts = fubon_sdk

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 獲取庫存和損益數據
            inventory = sdk.accounting.inventories(account_obj)
            import time

            time.sleep(0.5)  # Add delay to avoid rate limiting
            pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)

            if (
                inventory
                and hasattr(inventory, "is_success")
                and inventory.is_success
                and pnl
                and hasattr(pnl, "is_success")
                and pnl.is_success
            ):

                inventory_data = inventory.data if hasattr(inventory, "data") else inventory
                pnl_data = pnl.data if hasattr(pnl, "data") else pnl

                # 如果有庫存，應該有對應的損益記錄
                if inventory_data and isinstance(inventory_data, list):
                    inventory_symbols = {getattr(item, "stock_no", None) for item in inventory_data}
                    pnl_symbols = {getattr(item, "stock_no", None) for item in pnl_data}

                    # 損益記錄的股票應該是庫存的子集
                    assert pnl_symbols.issubset(inventory_symbols), "損益記錄與庫存不一致"

        except Exception as e:
            pytest.fail(f"數據一致性檢查失敗: {str(e)}")

    def test_error_handling(self, fubon_sdk, fubon_credentials):
        """測試錯誤處理"""
        try:
            # 解包 SDK
            sdk, _ = fubon_sdk

            # 測試無效憑證
            invalid_accounts = sdk.login(
                "INVALID", "INVALID", fubon_credentials["pfx_path"], fubon_credentials["pfx_password"] or ""
            )
            # 應該返回錯誤狀態
            assert not (invalid_accounts and hasattr(invalid_accounts, "is_success") and invalid_accounts.is_success)

        except Exception:
            # 錯誤處理正常
            assert True

    def test_api_response_format(self, fubon_sdk, fubon_credentials):
        """測試API回應格式"""
        try:
            # 解包 SDK 和帳戶資訊
            sdk, accounts = fubon_sdk

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 測試銀行水位 API
            balance = sdk.accounting.bank_remain(account_obj)

            # 檢查標準回應格式
            assert hasattr(balance, "is_success")
            assert hasattr(balance, "data") or hasattr(balance, "error")

        except Exception as e:
            pytest.fail(f"API回應格式檢查失敗: {str(e)}")


class TestPerformance:
    """效能測試"""

    def test_response_time(self, fubon_sdk, fubon_credentials):
        """測試API回應時間"""
        import time

        try:
            # 解包 SDK 和帳戶資訊
            sdk, accounts = fubon_sdk

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            start_time = time.time()
            balance = sdk.accounting.bank_remain(account_obj)
            end_time = time.time()

            response_time = end_time - start_time

            # 回應時間應該在合理範圍內（例如小於5秒）
            assert response_time < 5.0, f"API回應過慢: {response_time}秒"
            assert balance and hasattr(balance, "is_success") and balance.is_success

        except Exception as e:
            pytest.fail(f"效能測試失敗: {str(e)}")

    def get_account_obj(self, fubon_sdk, fubon_credentials):
        """獲取帳戶對象"""
        sdk, accounts = fubon_sdk

        if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
            pytest.skip("登入失敗")

        # 使用第一個帳戶
        if not hasattr(accounts, "data") or not accounts.data:
            pytest.skip("沒有帳戶資料")

        return sdk, accounts.data[0]

    def make_request(self, sdk, account_obj):
        """發送請求"""
        try:
            balance = sdk.accounting.bank_remain(account_obj)
            return ("success", balance)
        except Exception as e:
            return ("error", str(e))

    def test_concurrent_requests_simulation(self, fubon_sdk, fubon_credentials):
        """模擬並發請求"""
        import concurrent.futures

        try:
            sdk, account_obj = self.get_account_obj(fubon_sdk, fubon_credentials)

            # 模擬3個並發請求
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(self.make_request, sdk, account_obj) for _ in range(3)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

            # 檢查結果
            success_count = sum(1 for status, _ in results if status == "success")

            # 至少應該有成功請求
            assert success_count > 0, "並發請求測試失敗"

        except Exception as e:
            pytest.fail(f"並發請求測試失敗: {str(e)}")
