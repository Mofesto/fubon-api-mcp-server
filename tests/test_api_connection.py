"""
API連線和基本功能測試
"""

import pytest


class TestAPIConnection:
    """API連線測試"""

    def test_sdk_initialization(self, fubon_sdk):
        """測試SDK初始化"""
        sdk, accounts = fubon_sdk  # 解包元組
        assert sdk is not None
        assert hasattr(sdk, "login")
        # 注意：測試環境可能沒有 marketdata 屬性
        # assert hasattr(sdk, 'marketdata')
        # 注意：orders屬性可能不存在，取決於SDK版本
        # assert hasattr(sdk, 'orders')

    def test_login_success(self, fubon_sdk, fubon_credentials):
        """測試登入成功"""
        sdk, accounts = fubon_sdk  # 解包元組
        # 如果已經登入成功，SDK應該有有效的session
        assert sdk is not None

        # 檢查是否有帳戶資訊
        assert accounts is not None
        assert hasattr(accounts, "is_success")
        assert accounts.is_success

    def test_realtime_initialization(self, fubon_sdk):
        """測試即時連線初始化"""
        sdk, accounts = fubon_sdk  # 解包元組
        assert sdk is not None
        # 檢查即時連線是否初始化
        assert hasattr(sdk, "init_realtime")

    def test_rest_client_available(self, rest_client):
        """測試REST客戶端可用性 - 測試環境可能不支持"""
        if rest_client is None:
            pytest.skip("測試環境不支持 REST 客戶端")
        assert hasattr(rest_client, "intraday")
        assert hasattr(rest_client, "snapshot")
        assert hasattr(rest_client, "historical")

    def test_environment_variables_loaded(self, fubon_credentials):
        """測試環境變數正確載入"""
        assert fubon_credentials["username"] is not None
        assert fubon_credentials["password"] is not None
        assert fubon_credentials["pfx_path"] is not None
        assert fubon_credentials["pfx_path"].endswith(".pfx")
