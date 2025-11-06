"""
Tests for basic trading and account functions in server.py

This module tests the core trading functionality including:
- Basic order placement and management
- Account information retrieval
- Bank balance and inventory queries
- Order status and results
"""

from unittest.mock import MagicMock, patch

import pytest

from fubon_api_mcp_server.server import (
    batch_place_order,
    cancel_order,
    get_account_info,
    get_bank_balance,
    get_inventory,
    get_order_results,
    get_order_results_detail,
    modify_price,
    modify_quantity,
    place_order,
)


class TestBasicTradingFunctions:
    """Test basic trading operations"""

    @pytest.fixture
    def mock_globals(self):
        """Mock global variables and SDK"""
        mock_accounts = MagicMock()
        mock_accounts.is_success = True
        mock_accounts.data = [MagicMock(account="123456", name="Test User", branch_no="001", account_type="Stock")]

        with (
            patch("fubon_api_mcp_server.server.accounts", mock_accounts),
            patch("fubon_api_mcp_server.server.sdk") as mock_sdk,
        ):
            yield mock_sdk

    def test_place_order_success(self, mock_globals):
        """Test successful order placement"""
        mock_sdk = mock_globals
        # Setup
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.data = {"order_no": "12345"}
        mock_sdk.stock.place_order.return_value = mock_result

        # Test
        result = place_order(
            {
                "account": "123456",
                "symbol": "2330",
                "quantity": 1000,
                "price": 500.0,
                "buy_sell": "Buy",
                "market_type": "Common",
                "price_type": "Limit",
                "time_in_force": "ROD",
                "order_type": "Stock",
            }
        )

        # Assert
        assert result["status"] == "success"
        assert "成功" in result["message"]
        mock_sdk.stock.place_order.assert_called_once()

    def test_place_order_failure(self, mock_globals):
        """Test order placement failure"""
        mock_sdk = mock_globals
        # Setup
        mock_result = MagicMock()
        mock_result.is_success = False
        mock_result.message = "Insufficient funds"
        mock_sdk.stock.place_order.return_value = mock_result

        # Test
        result = place_order({"account": "123456", "symbol": "2330", "quantity": 1000, "price": 500.0, "buy_sell": "Buy"})

        # Assert
        assert result["status"] == "error"
        assert "下單失敗" in result["message"]

    def test_cancel_order_success(self, mock_globals):
        """Test successful order cancellation"""
        mock_sdk = mock_globals
        # Setup
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="12345")]

        mock_cancel_result = MagicMock()
        mock_cancel_result.is_success = True

        mock_sdk.stock.get_order_results.return_value = mock_order_results
        mock_sdk.stock.cancel_order.return_value = mock_cancel_result

        # Test
        result = cancel_order({"account": "123456", "order_no": "12345"})

        # Assert
        assert result["status"] == "success"
        assert "成功取消" in result["message"]

    def test_cancel_order_not_found(self, mock_globals):
        """Test cancelling non-existent order"""
        mock_sdk = mock_globals
        # Setup
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="99999")]  # Different order number

        mock_sdk.stock.get_order_results.return_value = mock_order_results

        # Test
        result = cancel_order({"account": "123456", "order_no": "12345"})

        # Assert
        assert result["status"] == "error"
        assert "找不到委託單號" in result["message"]

    def test_modify_price_success(self, mock_globals):
        """Test successful price modification"""
        mock_sdk = mock_globals
        # Setup
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="12345")]

        mock_modify_result = MagicMock()
        mock_modify_result.is_success = True

        mock_sdk.stock.get_order_results.return_value = mock_order_results
        mock_sdk.stock.make_modify_price_obj.return_value = MagicMock()
        mock_sdk.stock.modify_price.return_value = mock_modify_result

        # Test
        result = modify_price({"account": "123456", "order_no": "12345", "new_price": 510.0})

        # Assert
        assert result["status"] == "success"
        assert "成功修改" in result["message"]

    def test_modify_quantity_success(self, mock_globals):
        """Test successful quantity modification"""
        mock_sdk = mock_globals
        # Setup
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="12345")]

        mock_modify_result = MagicMock()
        mock_modify_result.is_success = True

        mock_sdk.stock.get_order_results.return_value = mock_order_results
        mock_sdk.stock.make_modify_quantity_obj.return_value = MagicMock()
        mock_sdk.stock.modify_quantity.return_value = mock_modify_result

        # Test
        result = modify_quantity({"account": "123456", "order_no": "12345", "new_quantity": 2000})

        # Assert
        assert result["status"] == "success"
        assert "成功修改" in result["message"]


class TestAccountInformationFunctions:
    """Test account information retrieval functions"""

    @pytest.fixture
    def mock_globals(self):
        """Mock global variables and SDK"""
        mock_accounts = MagicMock()
        mock_accounts.is_success = True
        mock_accounts.data = [MagicMock(account="123456", name="Test User", branch_no="001", account_type="Stock")]

        with (
            patch("fubon_api_mcp_server.server.accounts", mock_accounts),
            patch("fubon_api_mcp_server.server.sdk") as mock_sdk,
        ):
            yield mock_sdk

    def test_get_account_info_success(self, mock_globals):
        """Test successful account info retrieval"""
        mock_sdk = mock_globals
        # Setup
        mock_bank_balance = MagicMock()
        mock_bank_balance.is_success = True
        mock_bank_balance.data = {"balance": 100000}

        mock_unrealized_pnl = MagicMock()
        mock_unrealized_pnl.is_success = True
        mock_unrealized_pnl.data = {"pnl": 5000}

        mock_settlement = MagicMock()
        mock_settlement.is_success = True
        mock_settlement.data = {"amount": 0}

        mock_sdk.accounting.bank_remain.return_value = mock_bank_balance
        mock_sdk.accounting.unrealized_gains_and_loses.return_value = mock_unrealized_pnl
        mock_sdk.accounting.query_settlement.return_value = mock_settlement

        # Test
        result = get_account_info({"account": "123456"})

        # Assert
        assert result["status"] == "success"
        assert "basic_info" in result["data"]
        assert "bank_balance" in result["data"]
        assert result["data"]["basic_info"]["account"] == "123456"

    def test_get_inventory_success(self, mock_globals):
        """Test successful inventory retrieval"""
        mock_sdk = mock_globals
        # Setup
        mock_inventory = MagicMock()
        mock_inventory.is_success = True
        mock_inventory.data = [{"stock_no": "2330", "quantity": 1000}, {"stock_no": "2454", "quantity": 500}]

        mock_sdk.accounting.inventories.return_value = mock_inventory

        # Test
        result = get_inventory({"account": "123456"})

        # Assert
        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["data"][0]["stock_no"] == "2330"

    def test_get_bank_balance_success(self, mock_globals):
        """Test successful bank balance retrieval"""
        mock_sdk = mock_globals
        # Setup
        mock_balance = MagicMock()
        mock_balance.is_success = True
        mock_balance.data = {"available_balance": 50000}

        mock_sdk.accounting.bank_remain.return_value = mock_balance

        # Test
        result = get_bank_balance({"account": "123456"})

        # Assert
        assert result["status"] == "success"
        assert result["data"]["available_balance"] == 50000


class TestOrderManagementFunctions:
    """Test order status and results functions"""

    @pytest.fixture
    def mock_globals(self):
        """Mock global variables and SDK"""
        mock_accounts = MagicMock()
        mock_accounts.is_success = True
        mock_accounts.data = [MagicMock(account="123456", name="Test User", branch_no="001", account_type="Stock")]

        with (
            patch("fubon_api_mcp_server.server.accounts", mock_accounts),
            patch("fubon_api_mcp_server.server.sdk") as mock_sdk,
        ):
            yield mock_sdk

    def test_get_order_results_success(self, mock_globals):
        """Test successful order results retrieval"""
        mock_sdk = mock_globals
        # Setup
        mock_results = MagicMock()
        mock_results.is_success = True
        mock_results.data = [
            {"order_no": "12345", "symbol": "2330", "status": "Filled"},
            {"order_no": "12346", "symbol": "2454", "status": "Pending"},
        ]

        mock_sdk.stock.get_order_results.return_value = mock_results

        # Test
        result = get_order_results({"account": "123456"})

        # Assert
        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["data"][0]["order_no"] == "12345"

    def test_get_order_results_detail_success(self, mock_globals):
        """Test successful detailed order results retrieval"""
        mock_sdk = mock_globals
        # Setup
        mock_results = MagicMock()
        mock_results.is_success = True
        mock_results.data = [
            {
                "order_no": "12345",
                "symbol": "2330",
                "details": [{"modified_time": "2024-01-01", "before_qty": 1000, "after_qty": 500}],
            }
        ]

        mock_sdk.stock.get_order_results_detail.return_value = mock_results

        # Test
        result = get_order_results_detail({"account": "123456"})

        # Assert
        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert "details" in result["data"][0]


class TestBatchOperations:
    """Test batch operation functions"""

    @pytest.fixture
    def mock_globals(self):
        """Mock global variables and SDK"""
        mock_accounts = MagicMock()
        mock_accounts.is_success = True
        mock_accounts.data = [MagicMock(account="123456", name="Test User", branch_no="001", account_type="Stock")]

        with (
            patch("fubon_api_mcp_server.server.accounts", mock_accounts),
            patch("fubon_api_mcp_server.server.sdk") as mock_sdk,
        ):
            yield mock_sdk

    def test_batch_place_order_success(self, mock_globals):
        """Test successful batch order placement"""
        mock_sdk = mock_globals
        # Setup
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_sdk.stock.place_order.return_value = mock_result

        orders = [
            {"symbol": "2330", "quantity": 1000, "price": 500.0, "buy_sell": "Buy"},
            {"symbol": "2454", "quantity": 500, "price": 100.0, "buy_sell": "Sell"},
        ]

        # Test
        result = batch_place_order({"account": "123456", "orders": orders, "max_workers": 5})

        # Assert
        assert result["status"] == "success"
        assert result["data"]["total_orders"] == 2
        assert result["data"]["successful_orders"] == 2
        assert result["data"]["failed_orders"] == 0

    def test_batch_place_order_partial_failure(self, mock_globals):
        """Test batch order placement with partial failures"""
        mock_sdk = mock_globals

        # Create mock results: first succeeds, second fails
        success_result = MagicMock()
        success_result.is_success = True

        fail_result = MagicMock()
        fail_result.is_success = False
        fail_result.message = "Insufficient funds"

        # Set up side_effect to return different results
        mock_sdk.stock.place_order.side_effect = [success_result, fail_result]

        orders = [
            {"symbol": "2330", "quantity": 1000, "price": 500.0, "buy_sell": "Buy"},
            {"symbol": "2454", "quantity": 500, "price": 100.0, "buy_sell": "Sell"},
        ]

        # Test
        result = batch_place_order({"account": "123456", "orders": orders, "max_workers": 5})

        # Assert
        assert result["status"] == "success"
        assert result["data"]["total_orders"] == 2
        assert result["data"]["successful_orders"] == 1
        assert result["data"]["failed_orders"] == 1
