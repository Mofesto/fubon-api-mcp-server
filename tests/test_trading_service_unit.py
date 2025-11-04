"""
Unit tests for trading service module.

This module contains unit tests for the trading service functions,
testing them directly without MCP tool wrappers.
"""

from unittest.mock import Mock, patch

import pytest

from fubon_mcp.trading_service import (
    _convert_order_data_to_enums,
    _create_modify_object,
    _create_order_object,
    _execute_batch_orders,
    _execute_modify_operation,
    _find_target_order,
    _modify_order,
    _place_single_order,
    _summarize_batch_results,
)


class TestTradingService:
    """Unit tests for trading service functions"""

    def test_find_target_order_found(self):
        """Test finding target order - order found"""
        mock_order_results = Mock()
        mock_order1 = Mock()
        mock_order1.order_no = "12345"
        mock_order2 = Mock()
        mock_order2.order_no = "67890"

        mock_order_results.data = [mock_order1, mock_order2]

        result = _find_target_order(mock_order_results, "67890")

        assert result == mock_order2

    def test_find_target_order_not_found(self):
        """Test finding target order - order not found"""
        mock_order_results = Mock()
        mock_order1 = Mock()
        mock_order1.order_no = "12345"

        mock_order_results.data = [mock_order1]

        result = _find_target_order(mock_order_results, "99999")

        assert result is None

    @patch("fubon_mcp.trading_service.sdk")
    def test_create_modify_object_quantity(self, mock_sdk):
        """Test creating modify object for quantity"""
        mock_target_order = Mock()
        mock_modify_obj = Mock()
        mock_sdk.stock.make_modify_quantity_obj.return_value = mock_modify_obj

        result = _create_modify_object(mock_target_order, 2000, "quantity")

        mock_sdk.stock.make_modify_quantity_obj.assert_called_once_with(mock_target_order, 2000)
        assert result == mock_modify_obj

    @patch("fubon_mcp.trading_service.sdk")
    def test_create_modify_object_price(self, mock_sdk):
        """Test creating modify object for price"""
        mock_target_order = Mock()
        mock_modify_obj = Mock()
        mock_sdk.stock.make_modify_price_obj.return_value = mock_modify_obj

        result = _create_modify_object(mock_target_order, 150.5, "price")

        mock_sdk.stock.make_modify_price_obj.assert_called_once_with(mock_target_order, "150.5")
        assert result == mock_modify_obj

    def test_create_modify_object_invalid_type(self):
        """Test creating modify object with invalid type"""
        mock_target_order = Mock()

        with pytest.raises(ValueError, match="Unsupported modification type"):
            _create_modify_object(mock_target_order, 100, "invalid")

    @patch("fubon_mcp.trading_service.sdk")
    def test_execute_modify_operation_quantity(self, mock_sdk):
        """Test executing modify operation for quantity"""
        mock_modify_obj = Mock()
        mock_result = Mock()
        mock_sdk.stock.modify_quantity.return_value = mock_result

        result = _execute_modify_operation(None, mock_modify_obj, "quantity")

        mock_sdk.stock.modify_quantity.assert_called_once()
        assert result == mock_result

    @patch("fubon_mcp.trading_service.sdk")
    def test_execute_modify_operation_price(self, mock_sdk):
        """Test executing modify operation for price"""
        mock_modify_obj = Mock()
        mock_result = Mock()
        mock_sdk.stock.modify_price.return_value = mock_result

        result = _execute_modify_operation(None, mock_modify_obj, "price")

        mock_sdk.stock.modify_price.assert_called_once()
        assert result == mock_result

    def test_execute_modify_operation_invalid_type(self):
        """Test executing modify operation with invalid type"""
        mock_modify_obj = Mock()

        with pytest.raises(ValueError, match="Unsupported modification type"):
            _execute_modify_operation(None, mock_modify_obj, "invalid")

    @patch("fubon_mcp.trading_service.validate_and_get_account")
    @patch("fubon_mcp.trading_service.sdk")
    def test_modify_order_success_quantity(self, mock_sdk, mock_validate):
        """Test successful order modification for quantity"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_order_results = Mock()
        mock_order_results.is_success = True
        mock_target_order = Mock()
        mock_target_order.order_no = "12345"
        mock_order_results.data = [mock_target_order]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        mock_modify_obj = Mock()
        mock_sdk.stock.make_modify_quantity_obj.return_value = mock_modify_obj

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = "modified_data"
        mock_sdk.stock.modify_quantity.return_value = mock_result

        result = _modify_order("account1", "12345", 2000, "quantity")

        assert result["status"] == "success"
        assert result["data"] == "modified_data"
        assert "quantity to 2000" in result["message"]

    @patch("fubon_mcp.trading_service.validate_and_get_account")
    @patch("fubon_mcp.trading_service.sdk")
    def test_modify_order_success_price(self, mock_sdk, mock_validate):
        """Test successful order modification for price"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_order_results = Mock()
        mock_order_results.is_success = True
        mock_target_order = Mock()
        mock_target_order.order_no = "12345"
        mock_order_results.data = [mock_target_order]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        mock_modify_obj = Mock()
        mock_sdk.stock.make_modify_price_obj.return_value = mock_modify_obj

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = "modified_data"
        mock_sdk.stock.modify_price.return_value = mock_result

        result = _modify_order("account1", "12345", 150.5, "price")

        assert result["status"] == "success"
        assert result["data"] == "modified_data"
        assert "price to 150.5" in result["message"]

    @patch("fubon_mcp.trading_service.validate_and_get_account")
    def test_modify_order_account_validation_error(self, mock_validate):
        """Test order modification with account validation error"""
        mock_validate.return_value = (None, "Account error")

        result = _modify_order("invalid_account", "12345", 2000, "quantity")

        assert result["status"] == "error"
        assert result["message"] == "Account error"

    @patch("fubon_mcp.trading_service.validate_and_get_account")
    @patch("fubon_mcp.trading_service.sdk")
    def test_modify_order_get_order_results_failed(self, mock_sdk, mock_validate):
        """Test order modification when getting order results fails"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_order_results = Mock()
        mock_order_results.is_success = False
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        result = _modify_order("account1", "12345", 2000, "quantity")

        assert result["status"] == "error"
        assert "Unable to get order results" in result["message"]

    @patch("fubon_mcp.trading_service.validate_and_get_account")
    @patch("fubon_mcp.trading_service.sdk")
    def test_modify_order_not_found(self, mock_sdk, mock_validate):
        """Test order modification when order not found"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_order_results = Mock()
        mock_order_results.is_success = True
        mock_order_results.data = []
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        result = _modify_order("account1", "12345", 2000, "quantity")

        assert result["status"] == "error"
        assert "Order number 12345 not found" in result["message"]

    @patch("fubon_mcp.trading_service.validate_and_get_account")
    @patch("fubon_mcp.trading_service.sdk")
    def test_modify_order_modify_failed(self, mock_sdk, mock_validate):
        """Test order modification when modify operation fails"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_order_results = Mock()
        mock_order_results.is_success = True
        mock_target_order = Mock()
        mock_target_order.order_no = "12345"
        mock_order_results.data = [mock_target_order]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        mock_modify_obj = Mock()
        mock_sdk.stock.make_modify_quantity_obj.return_value = mock_modify_obj

        mock_result = Mock()
        mock_result.is_success = False
        mock_sdk.stock.modify_quantity.return_value = mock_result

        result = _modify_order("account1", "12345", 2000, "quantity")

        assert result["status"] == "error"
        assert "Failed to modify order 12345 quantity" in result["message"]

    @patch("fubon_mcp.trading_service.validate_and_get_account")
    @patch("fubon_mcp.trading_service.sdk")
    def test_modify_order_exception(self, mock_sdk, mock_validate):
        """Test order modification with exception"""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_sdk.stock.get_order_results.side_effect = Exception("SDK error")

        result = _modify_order("account1", "12345", 2000, "quantity")

        assert result["status"] == "error"
        assert "Error modifying quantity: SDK error" in result["message"]

    def test_convert_order_data_to_enums_default(self):
        """Test converting order data to enums with default values"""
        order_data = {}

        result = _convert_order_data_to_enums(order_data)

        # Check that the function returns a dict with the expected keys
        assert isinstance(result, dict)
        assert "buy_sell" in result
        assert "market_type" in result
        assert "price_type" in result
        assert "time_in_force" in result
        assert "order_type" in result

    def test_convert_order_data_to_enums_custom(self):
        """Test converting order data to enums with custom values"""
        order_data = {
            "buy_sell": "Sell",
            "market_type": "AfterHour",
            "price_type": "Market",
            "time_in_force": "IOC",
            "order_type": "Odd",
        }

        result = _convert_order_data_to_enums(order_data)

        # Check that the function returns a dict with the expected keys
        assert isinstance(result, dict)
        assert "buy_sell" in result
        assert "market_type" in result
        assert "price_type" in result
        assert "time_in_force" in result
        assert "order_type" in result

    @patch("fubon_neo.sdk.Order")
    def test_create_order_object(self, mock_order_class):
        """Test creating order object"""
        order_data = {"symbol": "2330", "price": 500.0, "quantity": 1000, "user_def": "test_user"}
        enums = {
            "buy_sell": Mock(),
            "market_type": Mock(),
            "price_type": Mock(),
            "time_in_force": Mock(),
            "order_type": Mock(),
        }

        mock_order_instance = Mock()
        mock_order_class.return_value = mock_order_instance

        result = _create_order_object(order_data, enums)

        mock_order_class.assert_called_once_with(
            buy_sell=enums["buy_sell"],
            symbol="2330",
            price="500.0",
            quantity=1000,
            market_type=enums["market_type"],
            price_type=enums["price_type"],
            time_in_force=enums["time_in_force"],
            order_type=enums["order_type"],
            user_def="test_user",
        )
        assert result == mock_order_instance

    @patch("fubon_mcp.trading_service.sdk")
    @patch("fubon_mcp.trading_service._convert_order_data_to_enums")
    @patch("fubon_mcp.trading_service._create_order_object")
    def test_place_single_order_success(self, mock_create_order, mock_convert_enums, mock_sdk):
        """Test successful single order placement"""
        order_data = {"symbol": "2330", "quantity": 1000, "price": 500.0}
        mock_account_obj = Mock()

        mock_enums = Mock()
        mock_convert_enums.return_value = mock_enums

        mock_order = Mock()
        mock_create_order.return_value = mock_order

        mock_result = Mock()
        mock_sdk.stock.place_order.return_value = mock_result

        result = _place_single_order(mock_account_obj, order_data)

        assert result["success"] is True
        assert result["order_data"] == order_data
        assert result["result"] == mock_result
        assert result["error"] is None
        mock_sdk.stock.place_order.assert_called_once_with(mock_account_obj, mock_order, False)

    @patch("fubon_mcp.trading_service.sdk")
    @patch("fubon_mcp.trading_service._convert_order_data_to_enums")
    @patch("fubon_mcp.trading_service._create_order_object")
    def test_place_single_order_non_blocking(self, mock_create_order, mock_convert_enums, mock_sdk):
        """Test single order placement with non-blocking mode"""
        order_data = {"symbol": "2330", "quantity": 1000, "price": 500.0, "is_non_blocking": True}
        mock_account_obj = Mock()

        mock_enums = Mock()
        mock_convert_enums.return_value = mock_enums

        mock_order = Mock()
        mock_create_order.return_value = mock_order

        mock_result = Mock()
        mock_sdk.stock.place_order.return_value = mock_result

        result = _place_single_order(mock_account_obj, order_data)

        assert result["success"] is True
        mock_sdk.stock.place_order.assert_called_once_with(mock_account_obj, mock_order, True)

    @patch("fubon_mcp.trading_service._convert_order_data_to_enums")
    def test_place_single_order_exception(self, mock_convert_enums):
        """Test single order placement with exception"""
        order_data = {"symbol": "2330", "quantity": 1000, "price": 500.0}
        mock_account_obj = Mock()

        mock_convert_enums.side_effect = Exception("Conversion error")

        result = _place_single_order(mock_account_obj, order_data)

        assert result["success"] is False
        assert result["order_data"] == order_data
        assert result["result"] is None
        assert result["error"] == "Conversion error"

    @patch("fubon_mcp.trading_service._place_single_order")
    def test_execute_batch_orders(self, mock_place_single):
        """Test executing batch orders"""
        mock_account_obj = Mock()
        orders = [{"symbol": "2330"}, {"symbol": "2454"}]
        max_workers = 2

        mock_result1 = {"success": True}
        mock_result2 = {"success": False}
        mock_place_single.side_effect = [mock_result1, mock_result2]

        results = _execute_batch_orders(mock_account_obj, orders, max_workers)

        assert len(results) == 2
        assert mock_result1 in results
        assert mock_result2 in results
        assert mock_place_single.call_count == 2

    def test_summarize_batch_results(self):
        """Test summarizing batch order results"""
        results = [
            {"success": True, "order_data": {"symbol": "2330"}},
            {"success": True, "order_data": {"symbol": "2454"}},
            {"success": False, "order_data": {"symbol": "3008"}, "error": "Failed"},
        ]

        summary = _summarize_batch_results(results)

        assert summary["total_orders"] == 3
        assert summary["successful_orders"] == 2
        assert summary["failed_orders"] == 1
        assert summary["results"] == results
