"""
Unit tests for account_service.py helper functions.
"""

import sys
from unittest.mock import MagicMock, Mock, patch

# Mock the problematic fubon_neo import before importing our modules
sys.modules["fubon_neo"] = MagicMock()
sys.modules["fubon_neo.sdk"] = MagicMock()

from fubon_mcp.account_service import (  # noqa: E402 - Import after sys.modules setup
    _get_account_financial_info,
    _get_all_accounts_basic_info,
    _get_basic_account_info,
)


class TestGetAllAccountsBasicInfo:
    """Test _get_all_accounts_basic_info function."""

    @patch("fubon_mcp.config.accounts")
    def test_get_all_accounts_basic_info_success(self, mock_accounts):
        """Test successful retrieval of all accounts basic info."""
        mock_account1 = Mock()
        mock_account1.account = "123456"
        mock_account1.name = "Test User 1"
        mock_account1.account_type = "stock"

        mock_account2 = Mock()
        mock_account2.account = "789012"
        mock_account2.name = "Test User 2"
        mock_account2.account_type = "future"

        mock_accounts.is_success = True
        mock_accounts.data = [mock_account1, mock_account2]

        result = _get_all_accounts_basic_info()
        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["data"][0]["account"] == "123456"
        assert result["data"][1]["account"] == "789012"

    @patch("fubon_mcp.config.accounts")
    def test_get_all_accounts_basic_info_no_accounts(self, mock_accounts):
        """Test when no accounts are available."""
        mock_accounts.is_success = False

        result = _get_all_accounts_basic_info()
        assert result["status"] == "error"
        assert "Account authentication failed" in result["message"]


class TestGetBasicAccountInfo:
    """Test _get_basic_account_info function."""

    @patch("fubon_mcp.config.sdk")
    def test_get_basic_account_info_success(self, mock_sdk):
        """Test successful retrieval of basic account info."""
        mock_account_obj = Mock()
        mock_account_obj.account = "123456"
        mock_account_obj.name = "Test User"
        mock_account_obj.branch_no = "2020"
        mock_account_obj.account_type = "stock"

        result = _get_basic_account_info(mock_account_obj)

        assert "basic_info" in result
        assert result["basic_info"]["account"] == "123456"
        assert result["basic_info"]["name"] == "Test User"
        assert result["basic_info"]["branch_no"] == "2020"
        assert result["basic_info"]["account_type"] == "stock"

    def test_get_basic_account_info_with_missing_attributes(self):
        """Test basic account info with missing attributes."""
        mock_account_obj = Mock()
        # Missing some attributes - Mock will return new Mock objects for missing attributes
        mock_account_obj.account = "123456"
        # Remove attributes to simulate missing ones
        del mock_account_obj.name
        del mock_account_obj.branch_no
        del mock_account_obj.account_type

        result = _get_basic_account_info(mock_account_obj)

        assert "basic_info" in result
        assert result["basic_info"]["account"] == "123456"
        # Since we're using Mock objects, getattr will return Mock objects for missing attributes
        # The function should handle this gracefully


class TestGetAccountFinancialInfo:
    """Test _get_account_financial_info function."""

    @patch("fubon_mcp.config.sdk")
    def test_get_account_financial_info_success(self, mock_sdk):
        """Test successful retrieval of account financial info."""
        mock_account_obj = Mock()

        mock_balance_result = Mock()
        mock_balance_result.is_success = True
        mock_balance_result.data = {"balance": 100000.0, "available": 95000.0}
        mock_sdk.accounting.bank_remain.return_value = mock_balance_result

        mock_inventory_result = Mock()
        mock_inventory_result.is_success = True
        mock_inventory_result.data = [{"stock": "2330", "quantity": 1000}]
        mock_sdk.accounting.inventories.return_value = mock_inventory_result

        mock_pnl_result = Mock()
        mock_pnl_result.is_success = True
        mock_pnl_result.data = [{"stock": "2330", "pnl": 5000.0}]
        mock_sdk.accounting.unrealized_gains_and_loses.return_value = mock_pnl_result

        mock_settlement_result = Mock()
        mock_settlement_result.is_success = True
        mock_settlement_result.data = {"receivables": 1000.0, "payables": 500.0}
        mock_sdk.accounting.query_settlement.return_value = mock_settlement_result

        result = _get_account_financial_info(mock_account_obj)

        assert "bank_balance" in result
        assert "unrealized_pnl" in result
        assert "settlement_today" in result
        assert result["bank_balance"]["balance"] == 100000.0
        assert result["unrealized_pnl"][0]["pnl"] == 5000.0
        assert result["settlement_today"]["receivables"] == 1000.0

    @patch("fubon_mcp.config.sdk")
    def test_get_account_financial_info_partial_failure(self, mock_sdk):
        """Test financial info when some APIs fail."""
        mock_account_obj = Mock()

        # Balance succeeds
        mock_balance_result = Mock()
        mock_balance_result.is_success = True
        mock_balance_result.data = {"balance": 100000.0}
        mock_sdk.accounting.bank_remain.return_value = mock_balance_result

        # Inventory fails (not used in this function)
        mock_inventory_result = Mock()
        mock_inventory_result.is_success = False
        mock_sdk.accounting.inventories.return_value = mock_inventory_result

        # PnL succeeds
        mock_pnl_result = Mock()
        mock_pnl_result.is_success = True
        mock_pnl_result.data = [{"pnl": 5000.0}]
        mock_sdk.accounting.unrealized_gains_and_loses.return_value = mock_pnl_result

        # Settlement fails
        mock_settlement_result = Mock()
        mock_settlement_result.is_success = False
        mock_sdk.accounting.query_settlement.return_value = mock_settlement_result

        result = _get_account_financial_info(mock_account_obj)

        assert "bank_balance" in result
        assert "unrealized_pnl" in result
        assert "settlement_today" in result
        assert result["bank_balance"]["balance"] == 100000.0
        assert result["unrealized_pnl"][0]["pnl"] == 5000.0
        assert result["settlement_today"] is None  # Failed API returns None

    @patch("fubon_mcp.config.sdk")
    def test_get_account_financial_info_all_failures(self, mock_sdk):
        """Test financial info when all APIs fail."""
        mock_account_obj = Mock()

        # All APIs fail
        mock_balance_result = Mock()
        mock_balance_result.is_success = False
        mock_sdk.accounting.bank_remain.return_value = mock_balance_result
        mock_sdk.accounting.unrealized_gains_and_loses.return_value = mock_balance_result
        mock_sdk.accounting.query_settlement.return_value = mock_balance_result

        result = _get_account_financial_info(mock_account_obj)

        assert "bank_balance" in result
        assert "unrealized_pnl" in result
        assert "settlement_today" in result
        assert result["bank_balance"] is None  # Failed API returns None
        assert result["unrealized_pnl"] is None  # Failed API returns None
        assert result["settlement_today"] is None  # Failed API returns None
