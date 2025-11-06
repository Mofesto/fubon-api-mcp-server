"""
Additional tests for server.py condition order and advanced trading functions.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, call, patch

import pandas as pd
import pytest

from fubon_api_mcp_server.server import (
    cancel_condition_order,
    get_condition_history,
    get_condition_order,
    get_condition_order_by_id,
    get_maintenance,
    get_realized_pnl,
    get_realized_pnl_summary,
    get_time_slice_order,
    get_trail_history,
    get_trail_order,
    get_unrealized_pnl,
    place_condition_order,
    place_daytrade_condition_order,
    place_daytrade_multi_condition_order,
    place_multi_condition_order,
    place_time_slice_order,
    place_trail_profit,
)


class TestConditionOrderFunctions:
    """Test condition order related functions."""

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_place_condition_order_success(self, mock_sdk, mock_validate):
        """Test successful condition order placement."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data.guid = "test-guid-123"
        mock_sdk.stock.single_condition.return_value = mock_result

        result = place_condition_order(
            {
                "account": "123456",
                "start_date": "20241106",
                "end_date": "20241107",
                "stop_sign": "Full",
                "condition": {
                    "market_type": "Reference",
                    "symbol": "2330",
                    "trigger": "MatchedPrice",
                    "trigger_value": "850",
                    "comparison": "GreaterThan",
                },
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2330",
                    "price": "850",
                    "quantity": 1000,
                    "market_type": "Common",
                    "price_type": "Limit",
                    "time_in_force": "ROD",
                    "order_type": "Stock",
                },
                "tpsl": {
                    "stop_sign": "Full",
                    "tp": {
                        "target_price": "900",
                        "price": "900",
                        "time_in_force": "ROD",
                        "price_type": "Limit",
                        "order_type": "Stock",
                    },
                    "sl": {
                        "target_price": "800",
                        "price": "800",
                        "time_in_force": "ROD",
                        "price_type": "Limit",
                        "order_type": "Stock",
                    },
                    "end_date": "20241108",
                    "intraday": False,
                },
            }
        )

        assert result["status"] == "success"
        assert result["data"]["guid"] == "test-guid-123"
        assert result["data"]["has_tpsl"] is True

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_place_condition_order_without_tpsl(self, mock_sdk, mock_validate):
        """Test condition order placement without TPSL."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data.guid = "test-guid-456"
        mock_sdk.stock.single_condition.return_value = mock_result

        result = place_condition_order(
            {
                "account": "123456",
                "start_date": "20241106",
                "end_date": "20241107",
                "stop_sign": "Full",
                "condition": {
                    "market_type": "Reference",
                    "symbol": "2330",
                    "trigger": "MatchedPrice",
                    "trigger_value": "850",
                    "comparison": "GreaterThan",
                },
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2330",
                    "price": "850",
                    "quantity": 1000,
                    "market_type": "Common",
                    "price_type": "Limit",
                    "time_in_force": "ROD",
                    "order_type": "Stock",
                },
            }
        )

        assert result["status"] == "success"
        assert result["data"]["has_tpsl"] is False

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_place_multi_condition_order_success(self, mock_sdk, mock_validate):
        """Test successful multi-condition order placement."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data.guid = "multi-guid-123"
        mock_sdk.stock.multi_condition.return_value = mock_result

        result = place_multi_condition_order(
            {
                "account": "123456",
                "start_date": "20241106",
                "end_date": "20241107",
                "stop_sign": "Full",
                "conditions": [
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "MatchedPrice",
                        "trigger_value": "850",
                        "comparison": "GreaterThan",
                    },
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "TotalQuantity",
                        "trigger_value": "10000",
                        "comparison": "GreaterThan",
                    },
                ],
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2330",
                    "price": "850",
                    "quantity": 1000,
                    "market_type": "Common",
                    "price_type": "Limit",
                    "time_in_force": "ROD",
                    "order_type": "Stock",
                },
            }
        )

        assert result["status"] == "success"
        assert result["data"]["conditions_count"] == 2

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_place_daytrade_condition_order_success(self, mock_sdk, mock_validate):
        """Test successful daytrade condition order placement."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data.guid = "daytrade-guid-123"
        mock_sdk.stock.single_condition_day_trade.return_value = mock_result

        result = place_daytrade_condition_order(
            {
                "account": "123456",
                "stop_sign": "Full",
                "end_time": "130000",
                "condition": {
                    "market_type": "Reference",
                    "symbol": "2330",
                    "trigger": "MatchedPrice",
                    "trigger_value": "850",
                    "comparison": "GreaterThan",
                },
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2330",
                    "price": "850",
                    "quantity": 1000,
                    "market_type": "Common",
                    "price_type": "Limit",
                    "time_in_force": "ROD",
                    "order_type": "Stock",
                },
                "daytrade": {"day_trade_end_time": "131500", "auto_cancel": True, "price": "", "price_type": "Market"},
                "fix_session": True,
            }
        )

        assert result["status"] == "success"
        assert result["data"]["guid"] == "daytrade-guid-123"

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_place_daytrade_multi_condition_order_success(self, mock_sdk, mock_validate):
        """Test successful daytrade multi-condition order placement."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data.guid = "daytrade-multi-guid-123"
        mock_sdk.stock.multi_condition_day_trade.return_value = mock_result

        result = place_daytrade_multi_condition_order(
            {
                "account": "123456",
                "stop_sign": "Full",
                "end_time": "130000",
                "conditions": [
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "MatchedPrice",
                        "trigger_value": "850",
                        "comparison": "GreaterThan",
                    },
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "TotalQuantity",
                        "trigger_value": "10000",
                        "comparison": "GreaterThan",
                    },
                ],
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2330",
                    "price": "850",
                    "quantity": 1000,
                    "market_type": "Common",
                    "price_type": "Limit",
                    "time_in_force": "ROD",
                    "order_type": "Stock",
                },
                "daytrade": {"day_trade_end_time": "131500", "auto_cancel": True, "price": "", "price_type": "Market"},
                "tpsl": {
                    "stop_sign": "Full",
                    "tp": {
                        "target_price": "900",
                        "price": "900",
                        "time_in_force": "ROD",
                        "price_type": "Limit",
                        "order_type": "Stock",
                    },
                    "sl": {
                        "target_price": "800",
                        "price": "800",
                        "time_in_force": "ROD",
                        "price_type": "Limit",
                        "order_type": "Stock",
                    },
                    "end_date": "20241108",
                    "intraday": False,
                },
                "fix_session": True,
            }
        )

        assert result["status"] == "success"
        assert result["data"]["guid"] == "daytrade-multi-guid-123"
        assert result["data"]["conditions_count"] == 2
        assert result["data"]["has_tpsl"] is True


class TestTrailProfitFunctions:
    """Test trail profit related functions."""

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_place_trail_profit_success(self, mock_sdk, mock_validate):
        """Test successful trail profit placement."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data.guid = "trail-guid-123"
        mock_sdk.stock.trail_profit.return_value = mock_result

        result = place_trail_profit(
            {
                "account": "123456",
                "start_date": "20241106",
                "end_date": "20241107",
                "stop_sign": "Full",
                "trail": {
                    "symbol": "2330",
                    "price": "850",
                    "direction": "Up",
                    "percentage": 5,
                    "buysell": "Buy",
                    "quantity": 1000,
                    "price_type": "MatchedPrice",
                    "diff": 5,
                    "time_in_force": "ROD",
                    "order_type": "Stock",
                },
            }
        )

        assert result["status"] == "success"
        assert result["data"]["guid"] == "trail-guid-123"

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_trail_order_success(self, mock_sdk, mock_validate):
        """Test successful trail order retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"guid": "trail-1", "symbol": "2330"}]
        mock_sdk.stock.get_trail_order.return_value = mock_result

        result = get_trail_order({"account": "123456"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_trail_history_success(self, mock_sdk, mock_validate):
        """Test successful trail history retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"guid": "trail-1", "symbol": "2330", "status": "Completed"}]
        mock_sdk.stock.get_trail_history.return_value = mock_result

        result = get_trail_history({"account": "123456", "start_date": "20241101", "end_date": "20241107"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1


class TestTimeSliceOrderFunctions:
    """Test time slice order related functions."""

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_place_time_slice_order_success(self, mock_sdk, mock_validate):
        """Test successful time slice order placement."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        # Create mock SmartOrderResponse
        mock_smart_order_response = Mock()
        mock_smart_order_response.guid = "timeslice-guid-123"

        # Create mock data as dict with SmartOrderResponse
        mock_data = {"SmartOrderResponse": mock_smart_order_response}

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = mock_data
        mock_sdk.stock.time_slice_order.return_value = mock_result

        result = place_time_slice_order(
            {
                "account": "123456",
                "start_date": "20241106",
                "end_date": "20241107",
                "stop_sign": "Full",
                "split": {
                    "method": "Type1",
                    "interval": 30,
                    "single_quantity": 1000,
                    "total_quantity": 5000,
                    "start_time": "090000",
                },
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2330",
                    "price": "850",
                    "quantity": 5000,
                    "market_type": "Common",
                    "price_type": "Limit",
                    "time_in_force": "ROD",
                    "order_type": "Stock",
                },
            }
        )

        assert result["status"] == "success"
        assert result["data"]["guid"] == "timeslice-guid-123"

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_time_slice_order_success(self, mock_sdk, mock_validate):
        """Test successful time slice order retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"batch_no": "TS001", "symbol": "2330"}]
        mock_sdk.stock.get_time_slice_order.return_value = mock_result

        result = get_time_slice_order({"account": "123456", "batch_no": "TS001"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1


class TestConditionOrderManagement:
    """Test condition order management functions."""

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_cancel_condition_order_success(self, mock_sdk, mock_validate):
        """Test successful condition order cancellation."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data.advisory = "Order cancelled successfully"
        mock_sdk.stock.cancel_condition_orders.return_value = mock_result

        result = cancel_condition_order({"account": "123456", "guid": "condition-guid-123"})

        assert result["status"] == "success"
        assert "advisory" in result["data"]

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_condition_order_success(self, mock_sdk, mock_validate):
        """Test successful condition order retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"guid": "cond-1", "symbol": "2330"}]
        mock_sdk.stock.get_condition_order.return_value = mock_result

        result = get_condition_order({"account": "123456"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_condition_order_by_id_success(self, mock_sdk, mock_validate):
        """Test successful condition order retrieval by ID."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"guid": "cond-1", "symbol": "2330", "status": "Active"}
        mock_sdk.stock.get_condition_order_by_id.return_value = mock_result

        result = get_condition_order_by_id({"account": "123456", "guid": "cond-1"})

        assert result["status"] == "success"
        assert result["data"]["guid"] == "cond-1"

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_condition_history_success(self, mock_sdk, mock_validate):
        """Test successful condition history retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [{"guid": "hist-1", "symbol": "2330"}]
        mock_sdk.stock.get_condition_history.return_value = mock_result

        result = get_condition_history({"account": "123456", "start_date": "20241101", "end_date": "20241107"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1


class TestPnLAndMaintenanceFunctions:
    """Test P&L and maintenance related functions."""

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_realized_pnl_success(self, mock_sdk, mock_validate):
        """Test successful realized P&L retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_item = Mock()
        mock_item.date = "20241106"
        mock_item.stock_no = "2330"
        mock_item.buy_sell = "Buy"
        mock_item.filled_qty = 1000
        mock_item.realized_profit = 5000
        mock_item.realized_loss = 0

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [mock_item]
        mock_sdk.accounting.realized_gains_and_loses.return_value = mock_result

        result = get_realized_pnl({"account": "123456"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["realized_profit"] == 5000

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_realized_pnl_summary_success(self, mock_sdk, mock_validate):
        """Test successful realized P&L summary retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_item = Mock()
        mock_item.start_date = "20241101"
        mock_item.end_date = "20241106"
        mock_item.stock_no = "2330"
        mock_item.buy_sell = "Buy"
        mock_item.filled_qty = 1000
        mock_item.filled_avg_price = 850.0
        mock_item.realized_profit_and_loss = 5000

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [mock_item]
        mock_sdk.accounting.realized_gains_and_loses_summary.return_value = mock_result

        result = get_realized_pnl_summary({"account": "123456"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["realized_profit_and_loss"] == 5000

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_unrealized_pnl_success(self, mock_sdk, mock_validate):
        """Test successful unrealized P&L retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_item = Mock()
        mock_item.stock_no = "2330"
        mock_item.unrealized_profit = 3000
        mock_item.unrealized_loss = 0

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [mock_item]
        mock_sdk.accounting.unrealized_gains_and_loses.return_value = mock_result

        result = get_unrealized_pnl({"account": "123456"})

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["unrealized_profit"] == 3000

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    @patch("fubon_api_mcp_server.server.sdk")
    def test_get_maintenance_success(self, mock_sdk, mock_validate):
        """Test successful maintenance information retrieval."""
        mock_account = Mock()
        mock_validate.return_value = (mock_account, None)

        mock_summary = Mock()
        mock_summary.total_market_value = 1000000.0
        mock_summary.total_equity = 800000.0

        mock_detail = Mock()
        mock_detail.stock_no = "2330"
        mock_detail.market_value = 500000.0

        mock_data = Mock()
        mock_data.maintenance_ratio = 1.5
        mock_data.summary = mock_summary
        mock_data.details = [mock_detail]

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = mock_data
        mock_sdk.accounting.get_maintenance.return_value = mock_result

        result = get_maintenance({"account": "123456"})

        assert result["status"] == "success"
        assert result["data"]["maintenance_ratio"] == 1.5
        assert len(result["data"]["details"]) == 1
