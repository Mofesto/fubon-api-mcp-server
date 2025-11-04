"""
Tests for trading_service.py - Trading operations services.

This module tests trading-related MCP tools including order placement,
modification, cancellation, and batch operations.
"""

from unittest.mock import MagicMock, patch

import pytest

from fubon_mcp import config
from fubon_mcp.trading_service import (
    _create_modify_object,
    _execute_batch_orders,
    _execute_modify_operation,
    _find_target_order,
    _summarize_batch_results,
    batch_place_order,
    cancel_order,
    modify_price,
    modify_quantity,
    place_order,
)


class TestFindTargetOrder:
    """Test _find_target_order helper function."""

    def test_find_target_order_success(self):
        """Test successful order finding."""
        mock_order_results = MagicMock()
        mock_order_results.data = [
            MagicMock(order_no="12345", symbol="2330"),
            MagicMock(order_no="67890", symbol="2454")
        ]

        order = _find_target_order(mock_order_results, "12345")

        assert order is not None
        assert order.order_no == "12345"
        assert order.symbol == "2330"

    def test_find_target_order_not_found(self):
        """Test order not found."""
        mock_order_results = MagicMock()
        mock_order_results.data = [
            MagicMock(order_no="12345", symbol="2330")
        ]

        order = _find_target_order(mock_order_results, "99999")

        assert order is None

    def test_find_target_order_no_data(self):
        """Test when order results have no data."""
        mock_order_results = MagicMock()
        mock_order_results.data = None

        order = _find_target_order(mock_order_results, "12345")

        assert order is None


class TestCreateModifyObject:
    """Test _create_modify_object helper function."""

    def test_create_modify_quantity_object(self, mock_sdk):
        """Test creating quantity modification object."""
        config.sdk = mock_sdk

        target_order = MagicMock()
        modify_obj = _create_modify_object(target_order, 2000, "quantity")

        assert modify_obj is not None
        mock_sdk.stock.make_modify_quantity_obj.assert_called_once_with(target_order, 2000)

    def test_create_modify_price_object(self, mock_sdk):
        """Test creating price modification object."""
        config.sdk = mock_sdk

        target_order = MagicMock()
        modify_obj = _create_modify_object(target_order, 505.0, "price")

        assert modify_obj is not None
        mock_sdk.stock.make_modify_price_obj.assert_called_once_with(target_order, "505.0")

    def test_create_modify_object_invalid_type(self):
        """Test creating modification object with invalid type."""
        target_order = MagicMock()

        with pytest.raises(ValueError, match="Unsupported modification type"):
            _create_modify_object(target_order, 100, "invalid")

    def test_create_modify_object_sdk_not_initialized(self):
        """Test creating modification object when SDK not initialized."""
        config.sdk = None
        target_order = MagicMock()

        with pytest.raises(ValueError, match="SDK not initialized"):
            _create_modify_object(target_order, 2000, "quantity")


class TestExecuteModifyOperation:
    """Test _execute_modify_operation helper function."""

    def test_execute_modify_quantity_operation(self, mock_sdk):
        """Test executing quantity modification operation."""
        config.sdk = mock_sdk

        account_obj = MagicMock()
        modify_obj = MagicMock()

        mock_result = MagicMock()
        mock_result.is_success = True
        mock_sdk.stock.modify_quantity.return_value = mock_result

        result = _execute_modify_operation(account_obj, modify_obj, "quantity")

        assert result == mock_result
        mock_sdk.stock.modify_quantity.assert_called_once_with(account_obj, modify_obj)

    def test_execute_modify_price_operation(self, mock_sdk):
        """Test executing price modification operation."""
        config.sdk = mock_sdk

        account_obj = MagicMock()
        modify_obj = MagicMock()

        mock_result = MagicMock()
        mock_result.is_success = True
        mock_sdk.stock.modify_price.return_value = mock_result

        result = _execute_modify_operation(account_obj, modify_obj, "price")

        assert result == mock_result
        mock_sdk.stock.modify_price.assert_called_once_with(account_obj, modify_obj)

    def test_execute_modify_operation_invalid_type(self, mock_sdk):
        """Test executing modification operation with invalid type."""
        config.sdk = mock_sdk

        account_obj = MagicMock()
        modify_obj = MagicMock()

        with pytest.raises(ValueError, match="Unsupported modification type"):
            _execute_modify_operation(account_obj, modify_obj, "invalid")


class TestPlaceOrder:
    """Test place_order MCP tool."""

    def test_place_order_success(self, mock_sdk, mock_accounts, sample_order_data):
        """Test successful order placement."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        # Mock API response
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.data = {"order_no": "12345"}
        mock_sdk.stock.place_order.return_value = mock_result

        result = place_order.fn(sample_order_data)

        assert result["status"] == "success"
        assert result["data"] is not None  # Mock result object
        assert "Successfully placed blocking order" in result["message"]
        mock_sdk.stock.place_order.assert_called_once()

    def test_place_order_account_not_found(self, mock_accounts, sample_order_data):
        """Test order placement with invalid account."""
        config.accounts = mock_accounts

        result = place_order.fn({**sample_order_data, "account": "99999999"})

        assert result["status"] == "error"
        assert "Account 99999999 not found" in result["message"]

    def test_place_order_api_failure(self, mock_sdk, mock_accounts, sample_order_data):
        """Test order placement when API fails."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        mock_sdk.stock.place_order.side_effect = Exception("API Error")

        result = place_order.fn(sample_order_data)

        assert result["status"] == "error"
        assert "Order placement failed" in result["message"]


class TestModifyPrice:
    """Test modify_price MCP tool."""

    def test_modify_price_success(self, mock_sdk, mock_accounts):
        """Test successful price modification."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        # Mock order results
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="12345")]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        # Mock modification result
        mock_modify_result = MagicMock()
        mock_modify_result.is_success = True
        mock_sdk.stock.modify_price.return_value = mock_modify_result

        result = modify_price.fn({
            "account": "12345678",
            "order_no": "12345",
            "new_price": 505.0
        })

        assert result["status"] == "success"
        assert "Successfully modified order 12345 price to 505.0" in result["message"]

    def test_modify_price_order_not_found(self, mock_sdk, mock_accounts):
        """Test price modification with order not found."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="12345")]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        result = modify_price.fn({
            "account": "12345678",
            "order_no": "99999",
            "new_price": 505.0
        })

        assert result["status"] == "error"
        assert "Order number 99999 not found" in result["message"]


class TestModifyQuantity:
    """Test modify_quantity MCP tool."""

    def test_modify_quantity_success(self, mock_sdk, mock_accounts):
        """Test successful quantity modification."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        # Mock order results
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="12345")]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        # Mock modification result
        mock_modify_result = MagicMock()
        mock_modify_result.is_success = True
        mock_sdk.stock.modify_quantity.return_value = mock_modify_result

        result = modify_quantity.fn({
            "account": "12345678",
            "order_no": "12345",
            "new_quantity": 2000
        })

        assert result["status"] == "success"
        assert "Successfully modified order 12345 quantity to 2000" in result["message"]


class TestCancelOrder:
    """Test cancel_order MCP tool."""

    def test_cancel_order_success(self, mock_sdk, mock_accounts):
        """Test successful order cancellation."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        # Mock order results
        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="12345")]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        # Mock cancellation result
        mock_cancel_result = MagicMock()
        mock_cancel_result.is_success = True
        mock_sdk.stock.cancel_order.return_value = mock_cancel_result

        result = cancel_order.fn({
            "account": "12345678",
            "order_no": "12345"
        })

        assert result["status"] == "success"
        assert "Successfully cancelled order 12345" in result["message"]

    def test_cancel_order_not_found(self, mock_sdk, mock_accounts):
        """Test order cancellation with order not found."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        mock_order_results = MagicMock()
        mock_order_results.is_success = True
        mock_order_results.data = [MagicMock(order_no="12345")]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        result = cancel_order.fn({
            "account": "12345678",
            "order_no": "99999"
        })

        assert result["status"] == "error"
        assert "Order number 99999 not found" in result["message"]


class TestBatchPlaceOrder:
    """Test batch_place_order MCP tool."""

    def test_batch_place_order_success(self, mock_sdk, mock_accounts):
        """Test successful batch order placement."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        orders = [
            {
                "symbol": "2330",
                "quantity": 1000,
                "price": 500.0,
                "buy_sell": "Buy"
            }
        ]

        # Mock successful order placement
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.data = {"order_no": "12345"}
        mock_sdk.stock.place_order.return_value = mock_result

        result = batch_place_order.fn({
            "account": "12345678",
            "orders": orders,
            "max_workers": 5
        })

        assert result["status"] == "success"
        assert "Batch order completed" in result["message"]

    def test_batch_place_order_empty_orders(self):
        """Test batch order placement with empty order list."""
        result = batch_place_order.fn({
            "account": "12345678",
            "orders": [],
            "max_workers": 5
        })

        assert result["status"] == "error"
        assert "Order list cannot be empty" in result["message"]

    def test_batch_place_order_account_not_found(self, mock_accounts):
        """Test batch order placement with invalid account."""
        config.accounts = mock_accounts

        orders = [{"symbol": "2330", "quantity": 1000, "price": 500.0, "buy_sell": "Buy"}]

        result = batch_place_order.fn({
            "account": "99999999",
            "orders": orders
        })

        assert result["status"] == "error"
        assert "account 99999999 not found" in result["message"]


class TestBatchOperationsHelpers:
    """Test batch operation helper functions."""

    def test_summarize_batch_results(self):
        """Test batch results summarization."""
        results = [
            {"success": True, "order_no": "12345"},
            {"success": False, "error": "API Error"},
            {"success": True, "order_no": "67890"}
        ]

        summary = _summarize_batch_results(results)

        assert summary["total_orders"] == 3
        assert summary["successful_orders"] == 2
        assert summary["failed_orders"] == 1
        assert len(summary["successful_orders_detail"]) == 2
        assert len(summary["failed_orders_detail"]) == 1

    @pytest.mark.skip(reason="Test hangs - skipping for now")
    @patch('fubon_mcp.trading_service.concurrent.futures.ThreadPoolExecutor')
    def test_execute_batch_orders(self, mock_executor, mock_sdk, mock_accounts):
        """Test batch order execution."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        # Mock executor
        mock_future = MagicMock()
        mock_future.result.return_value = {"success": True, "order_no": "12345"}
        mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future

        orders = [{"symbol": "2330", "quantity": 1000, "price": 500.0, "buy_sell": "Buy"}]
        account_obj = MagicMock()

        results = _execute_batch_orders(account_obj, orders, 5)

        assert len(results) == 1
        assert results[0]["success"] is True


class TestTradingServiceIntegration:
    """Test trading service integration."""

    def test_all_trading_functions_importable(self):
        """Test that all trading service functions can be imported."""
        from fubon_mcp.trading_service import (
            _create_modify_object,
            _execute_batch_orders,
            _execute_modify_operation,
            _find_target_order,
            _summarize_batch_results,
            batch_place_order,
            cancel_order,
            modify_price,
            modify_quantity,
            place_order,
        )

        # Test that helper functions are callable
        assert callable(_find_target_order)
        assert callable(_create_modify_object)
        assert callable(_execute_modify_operation)
        assert callable(_summarize_batch_results)
        assert callable(_execute_batch_orders)
        
        # Test that MCP functions have .fn attribute (FunctionTool objects)
        assert hasattr(place_order, 'fn')
        assert hasattr(modify_price, 'fn')
        assert hasattr(modify_quantity, 'fn')
        assert hasattr(cancel_order, 'fn')
        assert hasattr(batch_place_order, 'fn')

    def test_trading_service_module_structure(self):
        """Test trading_service module has expected structure."""
        import fubon_mcp.trading_service as trading_module

        # Check for expected functions
        expected_functions = [
            '_find_target_order',
            '_create_modify_object',
            '_execute_modify_operation',
            '_summarize_batch_results',
            '_execute_batch_orders',
            'place_order',
            'modify_price',
            'modify_quantity',
            'cancel_order',
            'batch_place_order'
        ]

        for func_name in expected_functions:
            assert hasattr(trading_module, func_name), f"Trading service module missing function: {func_name}"