"""
Unit tests for account service module.

This module contains unit tests for the account service functions,
testing them directly without MCP tool wrappers.
"""

from unittest.mock import Mock, patch

from fubon_mcp.account_service import (
    _get_account_financial_info,
    _get_all_accounts_basic_info,
    _get_basic_account_info,
)


class TestAccountService:
    """Unit tests for account service functions"""

    @patch("fubon_mcp.config.accounts")
    def test_get_all_accounts_basic_info_success(self, mock_accounts):
        """Test getting basic info for all accounts - success case"""
        # Mock successful accounts
        mock_account1 = Mock()
        mock_account1.name = "Test Account 1"
        mock_account1.branch_no = "001"
        mock_account1.account = "12345678"
        mock_account1.account_type = "Stock"

        mock_account2 = Mock()
        mock_account2.name = "Test Account 2"
        mock_account2.branch_no = "002"
        mock_account2.account = "87654321"
        mock_account2.account_type = "Futures"

        mock_accounts.data = [mock_account1, mock_account2]
        mock_accounts.is_success = True

        result = _get_all_accounts_basic_info()

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["data"][0]["account"] == "12345678"
        assert result["data"][1]["account"] == "87654321"

    @patch("fubon_mcp.config.accounts")
    def test_get_all_accounts_basic_info_failure(self, mock_accounts):
        """Test getting basic info for all accounts - failure case"""
        mock_accounts.is_success = False

        result = _get_all_accounts_basic_info()

        assert result["status"] == "error"
        assert "Account authentication failed" in result["message"]

    def test_get_basic_account_info(self):
        """Test getting basic account information"""
        mock_account = Mock()
        mock_account.name = "Test Account"
        mock_account.branch_no = "001"
        mock_account.account = "12345678"
        mock_account.account_type = "Stock"

        result = _get_basic_account_info(mock_account)

        assert "basic_info" in result
        assert result["basic_info"]["name"] == "Test Account"
        assert result["basic_info"]["account"] == "12345678"

    @patch("fubon_mcp.config.sdk")
    @patch("fubon_mcp.account_service._safe_api_call")
    def test_get_account_financial_info(self, mock_safe_call, mock_sdk):
        """Test getting account financial information"""
        mock_account = Mock()

        # Mock the _safe_api_call responses
        mock_safe_call.side_effect = [
            {"balance": 100000},  # bank_balance
            {"pnl": 5000},  # unrealized_pnl
            {"settlement": 0},  # settlement_today
        ]

        result = _get_account_financial_info(mock_account)

        assert "bank_balance" in result
        assert "unrealized_pnl" in result
        assert "settlement_today" in result

        # Verify _safe_api_call was called 3 times
        assert mock_safe_call.call_count == 3
