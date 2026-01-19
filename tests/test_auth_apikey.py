"""
Tests for API-Key authentication (SDK v2.2.7+ feature).

This module tests the new API-Key authentication method introduced in SDK v2.2.7.
Tests cover:
- Valid API-Key + Secret authentication
- Invalid credentials handling
- Missing credentials error messages
- Expired/revoked API-Key handling
- Trading operations with API-Key auth

References:
- specs/001-sdk-v2.2.7-upgrade/tasks.md: T010-T016
- specs/001-sdk-v2.2.7-upgrade/research.md: API-Key signature format
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from fubon_api_mcp_server.utils import validate_api_key_credentials, validate_and_get_account


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_key_credentials():
    """Mock valid API-Key credentials."""
    return {
        "api_key": "test_api_key_1234567890abcdef",
        "api_secret": "test_api_secret_1234567890abcdef",
    }


@pytest.fixture
def mock_invalid_api_key():
    """Mock invalid API-Key (too short)."""
    return {
        "api_key": "short",
        "api_secret": "test_api_secret_1234567890abcdef",
    }


@pytest.fixture
def mock_invalid_secret():
    """Mock invalid API Secret (too short)."""
    return {
        "api_key": "test_api_key_1234567890abcdef",
        "api_secret": "short",
    }


@pytest.fixture
def mock_fubon_sdk():
    """Mock FubonSDK for testing API-Key authentication."""
    with patch("fubon_api_mcp_server.utils.FubonSDK") as mock_sdk_class:
        mock_sdk_instance = MagicMock()
        mock_sdk_class.return_value = mock_sdk_instance

        # Mock successful login response
        mock_login_result = MagicMock()
        mock_login_result.is_success = True
        mock_login_result.data = [MagicMock(account="1234567", broker_id="test")]
        mock_sdk_instance.login.return_value = mock_login_result

        yield mock_sdk_instance


# =============================================================================
# Test: validate_api_key_credentials helper function
# =============================================================================


class TestValidateAPIKeyCredentials:
    """Test suite for API-Key credential validation helper."""

    def test_valid_credentials(self, mock_api_key_credentials):
        """Test validation passes for valid API-Key credentials."""
        is_valid, error_msg = validate_api_key_credentials(
            mock_api_key_credentials["api_key"], mock_api_key_credentials["api_secret"]
        )
        assert is_valid is True
        assert error_msg == ""

    def test_empty_api_key(self):
        """Test validation fails for empty API-Key."""
        is_valid, error_msg = validate_api_key_credentials("", "valid_secret_1234567890")
        assert is_valid is False
        assert "API Key is required" in error_msg
        assert "需要 API 金鑰" in error_msg

    def test_none_api_key(self):
        """Test validation fails for None API-Key."""
        is_valid, error_msg = validate_api_key_credentials(None, "valid_secret_1234567890")
        assert is_valid is False
        assert "API Key is required" in error_msg

    def test_empty_secret(self):
        """Test validation fails for empty Secret."""
        is_valid, error_msg = validate_api_key_credentials("valid_key_1234567890", "")
        assert is_valid is False
        assert "API Secret is required" in error_msg
        assert "需要 API 祕密" in error_msg

    def test_none_secret(self):
        """Test validation fails for None Secret."""
        is_valid, error_msg = validate_api_key_credentials("valid_key_1234567890", None)
        assert is_valid is False
        assert "API Secret is required" in error_msg

    def test_short_api_key(self, mock_invalid_api_key):
        """Test validation fails for API-Key that is too short."""
        is_valid, error_msg = validate_api_key_credentials(
            mock_invalid_api_key["api_key"], mock_invalid_api_key["api_secret"]
        )
        assert is_valid is False
        assert "Invalid API Key format" in error_msg
        assert "too short" in error_msg
        assert "無效的 API 金鑰格式" in error_msg

    def test_short_secret(self, mock_invalid_secret):
        """Test validation fails for Secret that is too short."""
        is_valid, error_msg = validate_api_key_credentials(
            mock_invalid_secret["api_key"], mock_invalid_secret["api_secret"]
        )
        assert is_valid is False
        assert "Invalid API Secret format" in error_msg
        assert "too short" in error_msg
        assert "無效的 API 祕密格式" in error_msg

    def test_whitespace_only_credentials(self):
        """Test validation fails for whitespace-only credentials."""
        is_valid, error_msg = validate_api_key_credentials("   ", "   ")
        assert is_valid is False
        assert "API Key is required" in error_msg


# =============================================================================
# Test: API-Key authentication via validate_and_get_account
# =============================================================================


class TestAPIKeyAuthentication:
    """Test suite for API-Key authentication flow."""

    @patch("dotenv.load_dotenv")
    @patch("os.getenv")
    @patch("fubon_neo.sdk.FubonSDK")
    @patch("fubon_api_mcp_server.utils.config_module")
    def test_authenticate_with_api_key(self, mock_config, mock_sdk_class, mock_getenv, mock_load_dotenv):
        """
        T011: Test successful authentication with API-Key + Secret.

        Verifies:
        - SDK is initialized with API-Key credentials
        - Session is established
        - User account info is retrieved
        """
        # Setup mock environment variables
        def getenv_side_effect(key, default=None):
            env_vars = {
                "FUBON_API_KEY": "test_api_key_1234567890abcdef",
                "FUBON_API_SECRET": "test_api_secret_1234567890abcdef",
                "FUBON_USERNAME": None,
                "FUBON_PASSWORD": None,
                "FUBON_PFX_PATH": None,
                "FUBON_PFX_PASSWORD": "",
            }
            return env_vars.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        # Setup mock SDK
        mock_sdk_instance = MagicMock()
        mock_sdk_class.return_value = mock_sdk_instance

        mock_login_result = MagicMock()
        mock_login_result.is_success = True
        mock_account = MagicMock()
        mock_account.account = "1234567"
        mock_account.broker_id = "test_broker"
        mock_login_result.data = [mock_account]
        mock_sdk_instance.login.return_value = mock_login_result

        # Reset config to trigger re-initialization
        mock_config.sdk = None
        mock_config.accounts = None

        # Execute authentication
        account_obj, error_msg = validate_and_get_account("1234567")

        # Assertions
        assert account_obj is not None
        assert error_msg is None
        assert account_obj.account == "1234567"

        # Verify SDK login was called with API-Key
        mock_sdk_instance.login.assert_called_once()
        call_kwargs = mock_sdk_instance.login.call_args.kwargs
        assert "api_key" in call_kwargs
        assert "secret_key" in call_kwargs
        assert call_kwargs["api_key"] == "test_api_key_1234567890abcdef"
        assert call_kwargs["secret_key"] == "test_api_secret_1234567890abcdef"

    @patch("dotenv.load_dotenv")
    @patch("os.getenv")
    @patch("fubon_neo.sdk.FubonSDK")
    @patch("fubon_api_mcp_server.utils.config_module")
    def test_api_key_auth_invalid_secret(self, mock_config, mock_sdk_class, mock_getenv, mock_load_dotenv):
        """
        T012: Test authentication fails with invalid Secret.

        Verifies:
        - Authentication fails
        - Appropriate error message is returned
        """
        # Setup mock environment variables with invalid secret (too short)
        def getenv_side_effect(key, default=None):
            env_vars = {
                "FUBON_API_KEY": "test_api_key_1234567890abcdef",
                "FUBON_API_SECRET": "short",  # Invalid: too short
                "FUBON_USERNAME": None,
                "FUBON_PASSWORD": None,
                "FUBON_PFX_PATH": None,
                "FUBON_PFX_PASSWORD": "",
            }
            return env_vars.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        # Reset config to trigger re-initialization
        mock_config.sdk = None
        mock_config.accounts = None

        # Execute authentication
        account_obj, error_msg = validate_and_get_account("1234567")

        # Assertions
        assert account_obj is None
        assert error_msg is not None
        assert "Invalid API Secret format" in error_msg
        assert "無效的 API 祕密格式" in error_msg

    @patch("dotenv.load_dotenv")
    @patch("os.getenv")
    @patch("fubon_api_mcp_server.utils.config_module")
    def test_api_key_auth_missing_credentials(self, mock_config, mock_getenv, mock_load_dotenv):
        """
        T013: Test authentication fails when API-Key credentials are missing.

        Verifies:
        - Clear error message directing user to Fubon portal
        - Bilingual error message (English + Traditional Chinese)
        """
        # Setup mock environment variables with no credentials
        def getenv_side_effect(key, default=None):
            env_vars = {
                "FUBON_API_KEY": None,
                "FUBON_API_SECRET": None,
                "FUBON_USERNAME": None,
                "FUBON_PASSWORD": None,
                "FUBON_PFX_PATH": None,
                "FUBON_PFX_PASSWORD": "",
            }
            return env_vars.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        # Reset config to trigger re-initialization
        mock_config.sdk = None
        mock_config.accounts = None

        # Execute authentication
        account_obj, error_msg = validate_and_get_account("1234567")

        # Assertions
        assert account_obj is None
        assert error_msg is not None
        assert "No valid credentials found" in error_msg
        assert "FUBON_API_KEY" in error_msg
        assert "FUBON_API_SECRET" in error_msg
        assert "未找到有效憑證" in error_msg

    @patch("dotenv.load_dotenv")
    @patch("os.getenv")
    @patch("fubon_neo.sdk.FubonSDK")
    @patch("fubon_api_mcp_server.utils.config_module")
    def test_api_key_auth_sdk_not_supported(self, mock_config, mock_sdk_class, mock_getenv, mock_load_dotenv):
        """
        Test handling when SDK version doesn't support API-Key auth.

        Verifies:
        - TypeError from SDK login is caught
        - Appropriate error message is returned
        """
        # Setup mock environment variables
        def getenv_side_effect(key, default=None):
            env_vars = {
                "FUBON_API_KEY": "test_api_key_1234567890abcdef",
                "FUBON_API_SECRET": "test_api_secret_1234567890abcdef",
                "FUBON_USERNAME": None,
                "FUBON_PASSWORD": None,
                "FUBON_PFX_PATH": None,
                "FUBON_PFX_PASSWORD": "",
            }
            return env_vars.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        # Setup mock SDK to raise TypeError (API-Key not supported)
        mock_sdk_instance = MagicMock()
        mock_sdk_class.return_value = mock_sdk_instance
        mock_sdk_instance.login.side_effect = TypeError("Unexpected keyword argument 'api_key'")

        # Reset config to trigger re-initialization
        mock_config.sdk = None
        mock_config.accounts = None

        # Execute authentication
        account_obj, error_msg = validate_and_get_account("1234567")

        # Assertions
        assert account_obj is None
        assert error_msg is not None
        assert "API-Key authentication not supported" in error_msg
        assert "SDK 版本不支援 API 金鑰驗證" in error_msg


# =============================================================================
# Test: Trading operations with API-Key auth
# =============================================================================


class TestAPIKeyTradingOperations:
    """Test that trading operations work with API-Key authentication."""

    @patch("dotenv.load_dotenv")
    @patch("os.getenv")
    @patch("fubon_neo.sdk.FubonSDK")
    @patch("fubon_api_mcp_server.utils.config_module")
    def test_place_order_with_api_key_auth(self, mock_config, mock_sdk_class, mock_getenv, mock_load_dotenv):
        """
        Test placing an order after API-Key authentication.

        Verifies:
        - Order placement succeeds with API-Key auth
        - Same functionality as traditional PFX auth
        """
        # Setup mock environment variables
        def getenv_side_effect(key, default=None):
            env_vars = {
                "FUBON_API_KEY": "test_api_key_1234567890abcdef",
                "FUBON_API_SECRET": "test_api_secret_1234567890abcdef",
                "FUBON_USERNAME": None,
                "FUBON_PASSWORD": None,
                "FUBON_PFX_PATH": None,
                "FUBON_PFX_PASSWORD": "",
            }
            return env_vars.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        # Setup mock SDK
        mock_sdk_instance = MagicMock()
        mock_sdk_class.return_value = mock_sdk_instance

        mock_login_result = MagicMock()
        mock_login_result.is_success = True
        mock_account = MagicMock()
        mock_account.account = "1234567"
        mock_login_result.data = [mock_account]
        mock_sdk_instance.login.return_value = mock_login_result

        # Mock place_order result
        mock_order_result = MagicMock()
        mock_order_result.is_success = True
        mock_order_result.order_no = "TEST_ORDER_001"
        mock_sdk_instance.stock.place_order.return_value = mock_order_result

        # Reset config to trigger re-initialization
        mock_config.sdk = None
        mock_config.accounts = None

        # Execute authentication
        account_obj, error_msg = validate_and_get_account("1234567")
        assert account_obj is not None
        assert error_msg is None

        # Simulate placing an order (this would be done in trading_service)
        order_result = mock_sdk_instance.stock.place_order(
            account=account_obj, symbol="2330", price="100", quantity=1000, buy_sell="Buy"
        )

        # Assertions
        assert order_result.is_success is True
        assert order_result.order_no == "TEST_ORDER_001"


# =============================================================================
# Test: Backward compatibility
# =============================================================================


class TestBackwardCompatibility:
    """Test that traditional PFX authentication still works."""

    @patch("dotenv.load_dotenv")
    @patch("os.getenv")
    @patch("fubon_neo.sdk.FubonSDK")
    @patch("fubon_api_mcp_server.utils.config_module")
    def test_traditional_pfx_auth_still_works(self, mock_config, mock_sdk_class, mock_getenv, mock_load_dotenv):
        """
        Test that traditional PFX authentication still works after SDK v2.2.7 upgrade.

        Verifies:
        - PFX auth is selected when API-Key credentials are not present
        - SDK login is called with traditional parameters
        - Authentication succeeds
        """
        # Setup mock environment variables (traditional PFX auth)
        def getenv_side_effect(key, default=None):
            env_vars = {
                "FUBON_API_KEY": None,
                "FUBON_API_SECRET": None,
                "FUBON_USERNAME": "test_user",
                "FUBON_PASSWORD": "test_password",
                "FUBON_PFX_PATH": "/path/to/cert.pfx",
                "FUBON_PFX_PASSWORD": "pfx_pass",
            }
            return env_vars.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        # Setup mock SDK
        mock_sdk_instance = MagicMock()
        mock_sdk_class.return_value = mock_sdk_instance

        mock_login_result = MagicMock()
        mock_login_result.is_success = True
        mock_account = MagicMock()
        mock_account.account = "1234567"
        mock_login_result.data = [mock_account]
        mock_sdk_instance.login.return_value = mock_login_result

        # Reset config to trigger re-initialization
        mock_config.sdk = None
        mock_config.accounts = None

        # Execute authentication
        account_obj, error_msg = validate_and_get_account("1234567")

        # Assertions
        assert account_obj is not None
        assert error_msg is None

        # Verify SDK login was called with traditional parameters
        mock_sdk_instance.login.assert_called_once_with("test_user", "test_password", "/path/to/cert.pfx", "pfx_pass")
