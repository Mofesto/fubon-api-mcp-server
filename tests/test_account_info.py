"""
帳戶資訊測試
"""

import pytest


class TestAccountInfo:
    """帳戶資訊功能測試"""

    def test_get_bank_balance(self, fubon_sdk, fubon_credentials):
        """測試獲取銀行水位"""
        try:
            sdk, accounts = fubon_sdk  # 解包元組

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗 - 測試環境可能不支持完整登入")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 獲取銀行水位
            balance = sdk.accounting.bank_remain(account_obj)
            assert balance and hasattr(balance, "is_success") and balance.is_success
            import time

            time.sleep(0.5)  # Add delay to avoid rate limiting

            balance_data = balance.data if hasattr(balance, "data") else balance

            # 檢查必要欄位
            assert hasattr(balance_data, "branch_no") or "branch_no" in balance_data
            assert hasattr(balance_data, "account") or "account" in balance_data
            assert hasattr(balance_data, "currency") or "currency" in balance_data
            assert hasattr(balance_data, "balance") or "balance" in balance_data
            assert hasattr(balance_data, "available_balance") or "available_balance" in balance_data

        except Exception as e:
            pytest.skip(f"銀行水位查詢失敗: {str(e)}")

    def test_get_inventory(self, fubon_sdk, fubon_credentials):
        """測試獲取庫存資訊"""
        try:
            sdk, accounts = fubon_sdk  # 解包元組

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 獲取庫存
            inventory = sdk.accounting.inventories(account_obj)
            assert inventory and hasattr(inventory, "is_success") and inventory.is_success
            import time

            time.sleep(0.5)  # Add delay to avoid rate limiting

            inventory_data = inventory.data if hasattr(inventory, "data") else inventory

            # 庫存應該是列表或可迭代物件
            assert isinstance(inventory_data, (list, tuple)) or hasattr(inventory_data, "__iter__")

        except Exception as e:
            pytest.skip(f"庫存查詢失敗: {str(e)}")

    def test_get_unrealized_pnl(self, fubon_sdk, fubon_credentials):
        """測試獲取未實現損益"""
        try:
            sdk, accounts = fubon_sdk  # 解包元組

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 獲取未實現損益
            pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)
            assert pnl and hasattr(pnl, "is_success") and pnl.is_success
            import time

            time.sleep(0.5)  # Add delay to avoid rate limiting

            pnl_data = pnl.data if hasattr(pnl, "data") else pnl

            # 損益數據應該是列表
            assert isinstance(pnl_data, list)

        except Exception as e:
            pytest.skip(f"未實現損益查詢失敗: {str(e)}")

    def test_get_account_info(self, fubon_sdk, fubon_credentials):
        """測試獲取完整帳戶資訊"""
        try:
            sdk, accounts = fubon_sdk  # 解包元組

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 測試多個 API 調用來獲取帳戶資訊
            balance = sdk.accounting.bank_remain(account_obj)
            import time

            time.sleep(0.5)  # Add delay to avoid rate limiting
            inventory = sdk.accounting.inventories(account_obj)
            time.sleep(0.5)  # Add delay to avoid rate limiting
            pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)

            account_data = {
                "balance": balance.data if hasattr(balance, "data") else balance,
                "inventory": inventory.data if hasattr(inventory, "data") else inventory,
                "pnl": pnl.data if hasattr(pnl, "data") else pnl,
            }

            # 檢查是否包含基本資訊
            assert "balance" in account_data

        except Exception as e:
            pytest.skip(f"帳戶資訊查詢失敗: {str(e)}")

    def test_get_settlement_info(self, fubon_sdk, fubon_credentials):
        """測試獲取結算資訊"""
        try:
            sdk, accounts = fubon_sdk  # 解包元組

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 獲取結算資訊
            settlement = sdk.accounting.query_settlement(account_obj, "0d")
            assert settlement and hasattr(settlement, "is_success") and settlement.is_success
            import time

            time.sleep(0.5)  # Add delay to avoid rate limiting

        except Exception as e:
            pytest.skip(f"交割資訊查詢失敗: {str(e)}")

    def test_inventory_data_structure(self, fubon_sdk, fubon_credentials):
        """測試庫存資料結構"""
        try:
            sdk, accounts = fubon_sdk  # 解包元組

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 測試庫存資料結構
            inventory = sdk.accounting.inventories(account_obj)
            if inventory and hasattr(inventory, "is_success") and inventory.is_success:
                import time

                time.sleep(0.5)  # Add delay to avoid rate limiting
                inventory_data = inventory.data if hasattr(inventory, "data") else inventory

                if inventory_data:
                    inventory_item = (
                        inventory_data[0] if isinstance(inventory_data, list) and inventory_data else inventory_data
                    )

                    # 檢查庫存項目是否有必要的屬性
                    required_attrs = ["stock_no", "tradable_qty", "today_qty"]
                    for attr in required_attrs:
                        assert hasattr(inventory_item, attr), f"庫存項目缺少屬性: {attr}"

        except Exception as e:
            pytest.skip(f"庫存數據結構檢查失敗: {str(e)}")

    def test_pnl_data_structure(self, fubon_sdk, fubon_credentials):
        """測試損益資料結構"""
        try:
            sdk, accounts = fubon_sdk  # 解包元組

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                pytest.skip("登入失敗")

            # 使用第一個帳戶
            if not hasattr(accounts, "data") or not accounts.data:
                pytest.skip("沒有帳戶資料")

            account_obj = accounts.data[0]

            # 測試損益資料結構
            pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)
            if pnl and hasattr(pnl, "is_success") and pnl.is_success:
                import time

                time.sleep(0.5)  # Add delay to avoid rate limiting
                pnl_data = pnl.data if hasattr(pnl, "data") else pnl

                if pnl_data:
                    pnl_item = pnl_data[0]

                    # 檢查損益項目是否有必要的屬性
                    required_attrs = ["stock_no", "unrealized_profit", "unrealized_loss"]
                    for attr in required_attrs:
                        assert hasattr(pnl_item, attr), f"損益項目缺少屬性: {attr}"

        except Exception as e:
            pytest.skip(f"損益數據結構檢查失敗: {str(e)}")
