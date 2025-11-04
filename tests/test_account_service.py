"""
Tests for account_service.py - Account management services.

This module tests account-related functions including basic account info retrieval.
"""

from unittest.mock import MagicMock

import pytest

from fubon_mcp import config
from fubon_mcp.account_service import _get_all_accounts_basic_info


class TestGetAllAccountsBasicInfo:
    """Test _get_all_accounts_basic_info function."""

    def test_get_all_accounts_basic_info_success(self, mock_accounts):
        """Test successful retrieval of all accounts basic info."""
        config.accounts = mock_accounts

        result = _get_all_accounts_basic_info()

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["data"][0]["account"] == "12345678"
        assert result["data"][1]["account"] == "87654321"
        assert "Successfully retrieved 2 accounts" in result["message"]

    def test_get_all_accounts_basic_info_no_accounts(self):
        """Test retrieval when no accounts available."""
        config.accounts = None

        result = _get_all_accounts_basic_info()

        assert result["status"] == "error"
        assert result["data"] is None
        assert "Account authentication failed" in result["message"]

    def test_get_all_accounts_basic_info_auth_failed(self):
        """Test retrieval when authentication failed."""
        mock_failed_accounts = MagicMock()
        mock_failed_accounts.is_success = False
        config.accounts = mock_failed_accounts

        result = _get_all_accounts_basic_info()

        assert result["status"] == "error"
        assert result["data"] is None
        assert "Account authentication failed" in result["message"]


class TestAccountServiceIntegration:
    """Test account service integration."""

    def test_account_service_module_structure(self):
        """Test account_service module has expected structure."""
        import fubon_mcp.account_service as account_module

        # Check for expected functions
        expected_functions = [
            '_get_all_accounts_basic_info'
        ]

        for func_name in expected_functions:
            assert hasattr(account_module, func_name), f"Account service module missing function: {func_name}"

        # Test that the function is callable
        assert callable(_get_all_accounts_basic_info)