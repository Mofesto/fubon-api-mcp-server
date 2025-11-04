"""
Unit tests for utils.py module.
"""

from unittest.mock import Mock, patch

from fubon_mcp.utils import _safe_api_call, get_order_by_no, handle_exceptions, validate_and_get_account


class TestHandleExceptions:
    """Test the handle_exceptions decorator."""

    def test_handle_exceptions_success(self):
        """Test that decorator doesn't interfere with successful function calls."""

        @handle_exceptions
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"

    def test_handle_exceptions_with_exception(self):
        """Test that decorator handles exceptions properly."""

        @handle_exceptions
        def test_func():
            raise ValueError("test error")

        with patch("sys.stderr") as mock_stderr:
            result = test_func()
            assert result is None
            # Check that error was written to stderr
            mock_stderr.write.assert_called()


class TestValidateAndGetAccount:
    """Test account validation functions."""

    @patch("fubon_mcp.utils.config_module.accounts")
    def test_validate_and_get_account_success(self, mock_accounts):
        """Test successful account validation."""
        # Mock successful accounts response
        mock_account_obj = Mock()
        mock_account_obj.account = "123456"
        mock_accounts.is_success = True
        mock_accounts.data = [mock_account_obj]

        result, error = validate_and_get_account("123456")
        assert result == mock_account_obj
        assert error is None

    @patch("fubon_mcp.utils.config_module.accounts")
    def test_validate_and_get_account_no_accounts(self, mock_accounts):
        """Test validation when accounts are not available."""
        mock_accounts.is_success = False

        result, error = validate_and_get_account("123456")
        assert result is None
        assert "Account authentication failed" in error

    @patch("fubon_mcp.utils.config_module.accounts")
    def test_validate_and_get_account_not_found(self, mock_accounts):
        """Test validation when account is not found."""
        mock_account_obj = Mock()
        mock_account_obj.account = "999999"
        mock_accounts.is_success = True
        mock_accounts.data = [mock_account_obj]

        result, error = validate_and_get_account("123456")
        assert result is None
        assert "Account 123456 not found" in error


class TestGetOrderByNo:
    """Test order retrieval functions."""

    @patch("fubon_mcp.utils.config_module.sdk")
    def test_get_order_by_no_success(self, mock_sdk):
        """Test successful order retrieval."""
        mock_order = Mock()
        mock_order.order_no = "ORDER123"
        mock_order_results = Mock()
        mock_order_results.is_success = True
        mock_order_results.data = [mock_order]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        mock_account = Mock()
        result, error = get_order_by_no(mock_account, "ORDER123")
        assert result == mock_order
        assert error is None

    @patch("fubon_mcp.utils.config_module.sdk")
    def test_get_order_by_no_api_failure(self, mock_sdk):
        """Test order retrieval when API fails."""
        mock_order_results = Mock()
        mock_order_results.is_success = False
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        mock_account = Mock()
        result, error = get_order_by_no(mock_account, "ORDER123")
        assert result is None
        assert "Unable to get account order results" in error

    @patch("fubon_mcp.utils.config_module.sdk")
    def test_get_order_by_no_not_found(self, mock_sdk):
        """Test order retrieval when order is not found."""
        mock_order = Mock()
        mock_order.order_no = "ORDER999"
        mock_order_results = Mock()
        mock_order_results.is_success = True
        mock_order_results.data = [mock_order]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        mock_account = Mock()
        result, error = get_order_by_no(mock_account, "ORDER123")
        assert result is None
        assert "Order number ORDER123 not found" in error

    @patch("fubon_mcp.utils.config_module.sdk")
    def test_get_order_by_no_exception(self, mock_sdk):
        """Test order retrieval when exception occurs."""
        mock_sdk.stock.get_order_results.side_effect = Exception("API error")

        mock_account = Mock()
        result, error = get_order_by_no(mock_account, "ORDER123")
        assert result is None
        assert "Error getting order results: API error" in error


class TestSafeApiCall:
    """Test the _safe_api_call helper function."""

    def test_safe_api_call_success(self):
        """Test successful API call."""
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = "test_data"

        def api_func():
            return mock_result

        result = _safe_api_call(api_func, "Test error")
        assert result == "test_data"

    def test_safe_api_call_failure(self):
        """Test failed API call."""
        mock_result = Mock()
        mock_result.is_success = False

        def api_func():
            return mock_result

        result = _safe_api_call(api_func, "Test error")
        assert result is None

    def test_safe_api_call_exception(self):
        """Test API call with exception."""

        def api_func():
            raise Exception("API error")

        result = _safe_api_call(api_func, "Test error")
        assert result == "Test error: API error"
