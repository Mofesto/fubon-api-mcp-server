"""
Test account service functions from server.py.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from fubon_api_mcp_server.server import (
    _get_account_financial_info,
    _get_all_accounts_basic_info,
    _get_basic_account_info,
    get_account_info,
    get_bank_balance,
    get_inventory,
    get_settlement_info,
    get_unrealized_pnl,
)


class TestGetAccountInfo:
    """Test get_account_info function."""

    def test_get_account_info_basic_only(self, mock_accounts, mock_server_globals):
        """Test get_account_info with basic info only."""
        result = get_account_info({"account": ""})

        assert result["status"] == "success"
        assert "data" in result
        assert "message" in result

    def test_get_account_info_detailed_success(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test get_account_info with detailed info success."""
        # Mock SDK responses
        mock_sdk.accounting.bank_remain.return_value = Mock(is_success=True, data="bank_data")
        mock_sdk.accounting.unrealized_gains_and_loses.return_value = Mock(is_success=True, data="pnl_data")
        mock_sdk.accounting.query_settlement.return_value = Mock(is_success=True, data="settlement_data")

        result = get_account_info({"account": "123456"})

        assert result["status"] == "success"
        assert "basic_info" in result["data"]
        assert "bank_balance" in result["data"]
        assert result["message"] == "成功獲取帳戶 123456 詳細資訊"

    def test_get_account_info_validation_failed(self, mock_server_globals):
        """Test get_account_info with validation failure."""
        result = get_account_info({"account": "999999"})

        assert result["status"] == "error"
        assert result["message"] == "找不到帳戶 999999"


class TestGetBankBalance:
    """Test get_bank_balance function."""

    def test_get_bank_balance_success(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test get_bank_balance success."""
        # Mock BankRemain object
        mock_bank_obj = Mock()
        mock_bank_obj.branch_no = "001"
        mock_bank_obj.account = "123456"
        mock_bank_obj.currency = "TWD"
        mock_bank_obj.balance = 100000
        mock_bank_obj.available_balance = 100000
        
        mock_sdk.accounting.bank_remain.return_value = Mock(is_success=True, data=mock_bank_obj)

        result = get_bank_balance({"account": "123456"})

        assert result["status"] == "success"
        assert isinstance(result["data"], dict)
        assert result["data"]["branch_no"] == "001"
        assert result["data"]["account"] == "123456"
        assert result["data"]["currency"] == "TWD"
        assert result["data"]["balance"] == 100000
        assert result["data"]["available_balance"] == 100000
        assert "成功獲取帳戶 123456 銀行水位資訊" in result["message"]

    def test_get_bank_balance_api_failed(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test get_bank_balance with API failure."""
        mock_sdk.accounting.bank_remain.return_value = Mock(is_success=False)

        result = get_bank_balance({"account": "123456"})

        assert result["status"] == "error"
        assert "無法獲取帳戶 123456 銀行水位資訊" in result["message"]


class TestGetInventory:
    """Test get_inventory function."""

    def test_get_inventory_success(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test get_inventory success."""
        # Mock Inventory object
        mock_inventory_obj = Mock()
        mock_inventory_obj.date = "2024-01-01"
        mock_inventory_obj.account = "123456"
        mock_inventory_obj.branch_no = "001"
        mock_inventory_obj.stock_no = "2330"
        mock_inventory_obj.order_type = "Stock"
        mock_inventory_obj.lastday_qty = 1000
        mock_inventory_obj.buy_qty = 0
        mock_inventory_obj.buy_filled_qty = 0
        mock_inventory_obj.buy_value = 0
        mock_inventory_obj.today_qty = 1000
        mock_inventory_obj.tradable_qty = 1000
        mock_inventory_obj.sell_qty = 0
        mock_inventory_obj.sell_filled_qty = 0
        mock_inventory_obj.sell_value = 0
        
        # Mock odd object
        mock_odd = Mock()
        mock_odd.lastday_qty = 0
        mock_odd.buy_qty = 0
        mock_odd.buy_filled_qty = 0
        mock_odd.buy_value = 0
        mock_odd.today_qty = 0
        mock_odd.tradable_qty = 0
        mock_odd.sell_qty = 0
        mock_odd.sell_filled_qty = 0
        mock_odd.sell_value = 0
        mock_inventory_obj.odd = mock_odd
        
        mock_sdk.accounting.inventories.return_value = Mock(is_success=True, data=[mock_inventory_obj])

        result = get_inventory({"account": "123456"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert isinstance(result["data"][0], dict)
        assert result["data"][0]["stock_no"] == "2330"
        assert result["data"][0]["tradable_qty"] == 1000
        assert "成功獲取帳戶 123456 庫存資訊" in result["message"]

    def test_get_inventory_api_failed(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test get_inventory with API failure."""
        mock_sdk.accounting.inventories.return_value = Mock(is_success=False)

        result = get_inventory({"account": "123456"})

        assert result["status"] == "error"
        assert "無法獲取帳戶 123456 庫存資訊" in result["message"]


class TestGetUnrealizedPnL:
    """Test get_unrealized_pnl function."""

    def test_get_unrealized_pnl_success(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test get_unrealized_pnl success."""
        # Mock the API response with data that will be processed
        mock_item = Mock()
        mock_item.date = "2024-01-01"
        mock_item.branch_no = "001"
        mock_item.stock_no = "2330"
        mock_item.buy_sell = Mock()
        mock_item.buy_sell.__str__ = Mock(return_value="BSAction.Buy")
        mock_item.order_type = Mock()
        mock_item.order_type.__str__ = Mock(return_value="OrderType.Stock")
        mock_item.cost_price = 500.0
        mock_item.tradable_qty = 1000
        mock_item.today_qty = 100
        mock_item.unrealized_profit = 5000
        mock_item.unrealized_loss = 0

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [mock_item]
        mock_sdk.accounting.unrealized_gains_and_loses.return_value = mock_result

        result = get_unrealized_pnl({"account": "123456"})

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert result["data"][0]["stock_no"] == "2330"
        assert result["data"][0]["buy_sell"] == "Buy"
        assert result["data"][0]["order_type"] == "Stock"
        assert "成功獲取帳戶 123456 未實現損益" in result["message"]


class TestGetSettlementInfo:
    """Test get_settlement_info function."""

    def test_get_settlement_info_success(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test get_settlement_info success."""
        mock_sdk.accounting.query_settlement.return_value = Mock(is_success=True, data="settlement_data")

        result = get_settlement_info({"account": "123456", "days": "0d"})

        assert result["status"] == "success"
        assert result["data"] == "settlement_data"
        assert "成功獲取帳戶 123456 0d 交割資訊" in result["message"]

    def test_get_settlement_info_api_failed(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test get_settlement_info with API failure."""
        mock_sdk.accounting.query_settlement.return_value = Mock(is_success=False)

        result = get_settlement_info({"account": "123456", "days": "0d"})

        assert result["status"] == "error"
        assert "無法獲取帳戶 123456 交割資訊" in result["message"]


class TestPrivateAccountFunctions:
    """Test private account helper functions."""

    def test_get_all_accounts_basic_info(self, mock_accounts, mock_server_globals):
        """Test _get_all_accounts_basic_info function."""
        result = _get_all_accounts_basic_info()

        assert result["status"] == "success"
        assert "data" in result
        assert len(result["data"]) == 2  # Two mock accounts

    def test_get_basic_account_info(self, mock_accounts):
        """Test _get_basic_account_info function."""
        account_obj = mock_accounts.data[0]
        result = _get_basic_account_info(account_obj)

        assert "basic_info" in result
        assert result["basic_info"]["account"] == "123456"

    def test_get_account_financial_info(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test _get_account_financial_info function."""
        account_obj = mock_accounts.data[0]

        # Mock successful API calls
        mock_sdk.accounting.bank_remain.return_value = Mock(is_success=True, data="bank_data")
        mock_sdk.accounting.unrealized_gains_and_loses.return_value = Mock(is_success=True, data="pnl_data")
        mock_sdk.accounting.query_settlement.return_value = Mock(is_success=True, data="settlement_data")

        result = _get_account_financial_info(account_obj)

        assert "bank_balance" in result
        assert "unrealized_pnl" in result
        assert "settlement_today" in result
