"""
Tests for account_service.py - Account management services.

This module tests account-related functions including basic account info retrieval.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from fubon_api_mcp_server import config
from fubon_api_mcp_server.account_service import (
    _get_account_financial_info,
    _get_all_accounts_basic_info,
    _get_basic_account_info,
    get_account_info,
    get_bank_balance,
    get_inventory,
    get_settlement_info,
    get_unrealized_pnl,
)


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
        import fubon_api_mcp_server.account_service as account_module

        # Check for expected functions
        expected_functions = ["_get_all_accounts_basic_info"]

        for func_name in expected_functions:
            assert hasattr(account_module, func_name), f"Account service module missing function: {func_name}"

        # Test that the function is callable
        assert callable(_get_all_accounts_basic_info)


class TestBasicAccountInfo:
    """Test _get_basic_account_info function."""

    def test_get_basic_account_info_success(self):
        """Test successful retrieval of basic account info."""
        mock_account = MagicMock()
        mock_account.name = "Test User"
        mock_account.branch_no = "001"
        mock_account.account = "12345678"
        mock_account.account_type = "S"

        result = _get_basic_account_info(mock_account)

        assert result["basic_info"]["account"] == "12345678"
        assert result["basic_info"]["account_type"] == "S"
        assert result["basic_info"]["branch_no"] == "001"
        assert result["basic_info"]["name"] == "Test User"


class TestAccountFinancialInfo:
    """Test _get_account_financial_info function."""

    def test_get_account_financial_info_success(self):
        """Test successful retrieval of account financial info."""
        mock_account = MagicMock()

        result = _get_account_financial_info(mock_account)

        # Should contain the expected keys
        assert "bank_balance" in result
        assert "unrealized_pnl" in result
        assert "settlement_today" in result

    def test_get_account_financial_info_with_exception(self):
        """Test account financial info with SDK not initialized."""
        # Mock config.sdk to be None
        with patch(""fubon_api_mcp_server.account_service.config_module.sdk", None):
            mock_account = MagicMock()
            result = _get_account_financial_info(mock_account)

            assert "error" in result
            assert "SDK not initialized" in result["error"]


class TestGetAccountInfo:
    """Test get_account_info function."""

    @patch("fubon_api_mcp_server.account_service._get_all_accounts_basic_info")
    def test_get_account_info_success(self, mock_get_all):
        """Test successful account info retrieval."""
        mock_get_all.return_value = {"status": "success", "data": [{"account": "12345678"}]}

        # Call the underlying function tool if present, otherwise call the function directly
        result = get_account_info.fn({}) if hasattr(get_account_info, "fn") else get_account_info({})

        assert result["status"] == "success"
        assert len(result["data"]) == 1

    @patch("fubon_api_mcp_server.account_service._get_all_accounts_basic_info")
    def test_get_account_info_error(self, mock_get_all):
        """Test account info retrieval with error."""
        mock_get_all.return_value = {"status": "error", "data": None}

        result = get_account_info.fn({}) if hasattr(get_account_info, "fn") else get_account_info({})

        assert result["status"] == "error"


class TestGetInventory:
    """Test get_inventory function."""

    def test_get_inventory_success(self, mock_accounts):
        """Test successful inventory retrieval."""
        config.accounts = mock_accounts

        # Mock the SDK accounting call
        mock_inventory_result = MagicMock()
        mock_inventory_result.is_success = True
        mock_inventory_result.data = [{"symbol": "2330", "quantity": 1000}]
        config.sdk.accounting.inventories.return_value = mock_inventory_result
        # Call the underlying function tool if present, otherwise call the function directly
        result = (
            get_inventory.fn({"account": "12345678"})
            if hasattr(get_inventory, "fn")
            else get_inventory({"account": "12345678"})
        )

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["symbol"] == "2330"

    def test_get_inventory_no_accounts(self):
        """Test inventory retrieval with no accounts."""
        config.accounts = None

        result = (
            get_inventory.fn({"account": "12345678"})
            if hasattr(get_inventory, "fn")
            else get_inventory({"account": "12345678"})
        )

        assert result["status"] == "error"
        assert "Account authentication failed" in result["message"]


class TestGetUnrealizedPnL:
    """Test get_unrealized_pnl function."""

    def test_get_unrealized_pnl_success(self, mock_accounts):
        """Test successful unrealized PnL retrieval."""
        config.accounts = mock_accounts

        # Mock the SDK accounting call
        mock_pnl_result = MagicMock()
        mock_pnl_result.is_success = True
        mock_pnl_result.data = {"total_pnl": 5000, "positions": []}
        config.sdk.accounting.unrealized_gains_and_loses.return_value = mock_pnl_result

        result = (
            get_unrealized_pnl.fn({"account": "12345678"})
            if hasattr(get_unrealized_pnl, "fn")
            else get_unrealized_pnl({"account": "12345678"})
        )

        assert result["status"] == "success"
        assert result["data"]["total_pnl"] == 5000

    def test_get_unrealized_pnl_no_accounts(self):
        """Test unrealized PnL retrieval with no accounts."""
        config.accounts = None

        result = (
            get_unrealized_pnl.fn({"account": "12345678"})
            if hasattr(get_unrealized_pnl, "fn")
            else get_unrealized_pnl({"account": "12345678"})
        )

        assert result["status"] == "error"


class TestGetSettlementInfo:
    """Test get_settlement_info function."""

    def test_get_settlement_info_success(self, mock_accounts):
        """Test successful settlement info retrieval."""
        config.accounts = mock_accounts

        # Mock the SDK accounting call
        mock_settlement_result = MagicMock()
        mock_settlement_result.is_success = True
        # Mock the SDK accounting call
        mock_settlement_result = MagicMock()
        mock_settlement_result.is_success = True
        mock_settlement_result.data = {"settlement_date": "2023-01-01"}
        config.sdk.accounting.query_settlement.return_value = mock_settlement_result
        # Call the underlying function tool if present, otherwise call the function directly
        result = (
            get_settlement_info.fn({"account": "12345678"})
            if hasattr(get_settlement_info, "fn")
            else get_settlement_info({"account": "12345678"})
        )

        assert result["status"] == "success"
        assert result["data"]["settlement_date"] == "2023-01-01"
        config.accounts = None

        result = (
            get_settlement_info.fn({"account": "12345678"})
            if hasattr(get_settlement_info, "fn")
            else get_settlement_info({"account": "12345678"})
        )

        assert result["status"] == "error"


class TestGetBankBalance:
    """Test get_bank_balance function."""

    def test_get_bank_balance_success(self, mock_accounts):
        """Test successful bank balance retrieval."""
        config.accounts = mock_accounts

        # Mock the SDK accounting call
        mock_balance_result = MagicMock()
        mock_balance_result.is_success = True
        mock_balance_result.data = {"bank_balance": 50000, "available_balance": 45000}
        config.sdk.accounting.bank_remain.return_value = mock_balance_result

        # Call the underlying function tool if present, otherwise call the function directly
        result = (
            get_bank_balance.fn({"account": "12345678"})
            if hasattr(get_bank_balance, "fn")
            else get_bank_balance({"account": "12345678"})
        )

        assert result["status"] == "success"
        assert result["data"]["bank_balance"] == 50000
        assert result["data"]["available_balance"] == 45000

    def test_get_bank_balance_no_accounts(self):
        """Test bank balance retrieval with no accounts."""
        config.accounts = None

        result = (
            get_bank_balance.fn({"account": "12345678"})
            if hasattr(get_bank_balance, "fn")
            else get_bank_balance({"account": "12345678"})
        )

        assert result["status"] == "error"
        assert "Account authentication failed" in result["message"]
