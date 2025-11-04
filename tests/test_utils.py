"""
Tests for utils.py - Utility functions.

This module tests utility functions including error handling,
account validation, and API call helpers.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from fubon_mcp import config
from fubon_mcp.utils import _safe_api_call, get_order_by_no, handle_exceptions, validate_and_get_account


class TestHandleExceptions:
    """Test exception handling decorator."""

    def test_handle_exceptions_success(self):
        """Test that decorator doesn't interfere with successful execution."""
        @handle_exceptions
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_handle_exceptions_with_exception(self, capsys):
        """Test that decorator handles exceptions properly."""
        @handle_exceptions
        def failing_function():
            raise ValueError("Test error")

        # Function should not raise exception
        failing_function()

        # Check that error was printed to stderr
        captured = capsys.readouterr()
        assert "failing_function exception: Test error" in captured.err
        assert "Traceback" in captured.err

    def test_handle_exceptions_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""
        @handle_exceptions
        def test_function():
            """Test docstring."""
            pass

        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test docstring."


class TestValidateAndGetAccount:
    """Test account validation functions."""

    def test_validate_and_get_account_success(self, mock_accounts):
        """Test successful account validation."""
        config.accounts = mock_accounts

        account_obj, error = validate_and_get_account("12345678")

        assert account_obj is not None
        assert error is None
        assert account_obj.account == "12345678"

    def test_validate_and_get_account_no_accounts(self):
        """Test account validation when no accounts available."""
        config.accounts = None

        account_obj, error = validate_and_get_account("12345678")

        assert account_obj is None
        assert error == "Account authentication failed, please check if credentials have expired"

    def test_validate_and_get_account_failed_auth(self):
        """Test account validation when authentication failed."""
        mock_failed_accounts = MagicMock()
        mock_failed_accounts.is_success = False
        config.accounts = mock_failed_accounts

        account_obj, error = validate_and_get_account("12345678")

        assert account_obj is None
        assert error == "Account authentication failed, please check if credentials have expired"

    def test_validate_and_get_account_not_found(self, mock_accounts):
        """Test account validation when account not found."""
        config.accounts = mock_accounts

        account_obj, error = validate_and_get_account("99999999")

        assert account_obj is None
        assert error == "account 99999999 not found"


class TestGetOrderByNo:
    """Test order retrieval functions."""

    def test_get_order_by_no_success(self, mock_sdk):
        """Test successful order retrieval."""
        config.sdk = mock_sdk

        # Mock order results
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [
            MagicMock(order_no="12345", symbol="2330"),
            MagicMock(order_no="67890", symbol="2454")
        ]

        mock_sdk.stock.get_order_results.return_value = mock_order_results

        order_obj, error = get_order_by_no(MagicMock(), "12345")

        assert order_obj is not None
        assert error is None
        assert order_obj.order_no == "12345"

    def test_get_order_by_no_sdk_not_initialized(self):
        """Test order retrieval when SDK not initialized."""
        config.sdk = None

        order_obj, error = get_order_by_no(MagicMock(), "12345")

        assert order_obj is None
        assert error == "SDK not initialized or stock module not available"

    def test_get_order_by_no_api_failure(self, mock_sdk):
        """Test order retrieval when API call fails."""
        config.sdk = mock_sdk

        mock_sdk.stock.get_order_results.side_effect = Exception("API Error")

        order_obj, error = get_order_by_no(MagicMock(), "12345")

        assert order_obj is None
        assert "Error getting order results: API Error" in error

    def test_get_order_by_no_not_found(self, mock_sdk):
        """Test order retrieval when order not found."""
        config.sdk = mock_sdk

        # Clear any side effects from previous tests
        mock_sdk.stock.get_order_results.side_effect = None
        
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [
            MagicMock(order_no="12345", symbol="2330")
        ]

        mock_sdk.stock.get_order_results.return_value = mock_order_results

        order_obj, error = get_order_by_no(MagicMock(), "99999")

        assert order_obj is None
        assert error == "Order number 99999 not found"


class TestSafeApiCall:
    """Test safe API call helper."""

    def test_safe_api_call_success(self):
        """Test successful API call."""
        def mock_api():
            result = MagicMock()
            result.is_success = True
            result.data = {"key": "value"}
            return result

        data = _safe_api_call(mock_api, "Test API")

        assert data == {"key": "value"}

    def test_safe_api_call_failure(self):
        """Test failed API call."""
        def mock_api():
            result = MagicMock()
            result.is_success = False
            return result

        data = _safe_api_call(mock_api, "Test API")

        assert data is None

    def test_safe_api_call_exception(self):
        """Test API call with exception."""
        def mock_api():
            raise Exception("Test exception")

        data = _safe_api_call(mock_api, "Test API")

        assert data == "Test API: Test exception"


class TestUtilsIntegration:
    """Test utility functions integration."""

    def test_all_utils_functions_importable(self):
        """Test that all utility functions can be imported."""
        from fubon_mcp.utils import (
            _safe_api_call,
            get_order_by_no,
            handle_exceptions,
            validate_and_get_account,
        )

        # Test that functions are callable
        assert callable(handle_exceptions)
        assert callable(validate_and_get_account)
        assert callable(get_order_by_no)
        assert callable(_safe_api_call)

    def test_utils_module_structure(self):
        """Test utils module has expected structure."""
        import fubon_mcp.utils as utils_module

        # Check for expected functions
        expected_functions = [
            'handle_exceptions',
            'validate_and_get_account',
            'get_order_by_no',
            '_safe_api_call'
        ]

        for func_name in expected_functions:
            assert hasattr(utils_module, func_name), f"Utils module missing function: {func_name}"
            assert callable(getattr(utils_module, func_name)), f"{func_name} is not callable"