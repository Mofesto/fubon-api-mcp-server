"""
Tests for server module.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from fubon_api_mcp_server import server

# =============================================================================
# Callable Wrapper Function Tests
# =============================================================================


def test_callable_get_account_info():
    """Test callable_get_account_info wrapper"""
    with patch("fubon_api_mcp_server.account_service.get_account_info") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_account_info({"account": "123456"})
        assert result["status"] == "success"


def test_callable_get_inventory():
    """Test callable_get_inventory wrapper"""
    with patch("fubon_api_mcp_server.account_service.get_inventory") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_inventory({"account": "123456"})
        assert result["status"] == "success"


def test_callable_get_bank_balance():
    """Test callable_get_bank_balance wrapper"""
    with patch("fubon_api_mcp_server.account_service.get_bank_balance") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_bank_balance({"account": "123456"})
        assert result["status"] == "success"


def test_callable_get_settlement_info():
    """Test callable_get_settlement_info wrapper"""
    with patch("fubon_api_mcp_server.account_service.get_settlement_info") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_settlement_info({"account": "123456"})
        assert result["status"] == "success"


def test_callable_get_unrealized_pnl():
    """Test callable_get_unrealized_pnl wrapper"""
    with patch("fubon_api_mcp_server.account_service.get_unrealized_pnl") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_unrealized_pnl({"account": "123456"})
        assert result["status"] == "success"


def test_callable_place_order():
    """Test callable_place_order wrapper"""
    with patch("fubon_api_mcp_server.trading_service.place_order") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_place_order({"account": "123456"})
        assert result["status"] == "success"


def test_callable_modify_price():
    """Test callable_modify_price wrapper"""
    with patch("fubon_api_mcp_server.trading_service.modify_price") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_modify_price({"account": "123456"})
        assert result["status"] == "success"


def test_callable_modify_quantity():
    """Test callable_modify_quantity wrapper"""
    with patch("fubon_api_mcp_server.trading_service.modify_quantity") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_modify_quantity({"account": "123456"})
        assert result["status"] == "success"


def test_callable_cancel_order():
    """Test callable_cancel_order wrapper"""
    with patch("fubon_api_mcp_server.trading_service.cancel_order") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_cancel_order({"account": "123456"})
        assert result["status"] == "success"


def test_callable_batch_place_order():
    """Test callable_batch_place_order wrapper"""
    with patch("fubon_api_mcp_server.trading_service.batch_place_order") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_batch_place_order({"account": "123456"})
        assert result["status"] == "success"


def test_callable_get_order_results():
    """Test callable_get_order_results wrapper"""
    with patch.object(server.get_order_results, "fn", return_value={"status": "success"}) as mock_fn:
        result = server.callable_get_order_results({"account": "123456"})
        assert result["status"] == "success"
        mock_fn.assert_called_once()


def test_callable_get_order_reports():
    """Test callable_get_order_reports wrapper"""
    with patch.object(server.get_order_reports, "fn", return_value={"status": "success"}) as mock_fn:
        result = server.callable_get_order_reports({})
        assert result["status"] == "success"
        mock_fn.assert_called_once()


def test_callable_get_order_changed_reports():
    """Test callable_get_order_changed_reports wrapper"""
    with patch.object(server.get_order_changed_reports, "fn", return_value={"status": "success"}) as mock_fn:
        result = server.callable_get_order_changed_reports({})
        assert result["status"] == "success"
        mock_fn.assert_called_once()


def test_callable_get_filled_reports():
    """Test callable_get_filled_reports wrapper"""
    with patch.object(server.get_filled_reports, "fn", return_value={"status": "success"}) as mock_fn:
        result = server.callable_get_filled_reports({})
        assert result["status"] == "success"
        mock_fn.assert_called_once()


def test_callable_get_event_reports():
    """Test callable_get_event_reports wrapper"""
    with patch.object(server.get_event_reports, "fn", return_value={"status": "success"}) as mock_fn:
        result = server.callable_get_event_reports({})
        assert result["status"] == "success"
        mock_fn.assert_called_once()


def test_callable_get_all_reports():
    """Test callable_get_all_reports wrapper"""
    with patch.object(server.get_all_reports, "fn", return_value={"status": "success"}) as mock_fn:
        result = server.callable_get_all_reports({})
        assert result["status"] == "success"
        mock_fn.assert_called_once()


def test_callable_get_realtime_quotes():
    """Test callable_get_realtime_quotes wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_realtime_quotes") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_realtime_quotes({"symbols": ["2330"]})
        assert result["status"] == "success"


def test_callable_get_intraday_tickers():
    """Test callable_get_intraday_tickers wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_intraday_tickers") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_intraday_tickers({"date": "2024-01-01"})
        assert result["status"] == "success"


def test_callable_get_intraday_ticker():
    """Test callable_get_intraday_ticker wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_intraday_ticker") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_intraday_ticker({"symbol": "2330"})
        assert result["status"] == "success"


def test_callable_get_intraday_quote():
    """Test callable_get_intraday_quote wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_intraday_quote") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_intraday_quote({"symbol": "2330"})
        assert result["status"] == "success"


def test_callable_get_intraday_candles():
    """Test callable_get_intraday_candles wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_intraday_candles") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_intraday_candles({"symbol": "2330"})
        assert result["status"] == "success"


def test_callable_get_intraday_trades():
    """Test callable_get_intraday_trades wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_intraday_trades") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_intraday_trades({"symbol": "2330"})
        assert result["status"] == "success"


def test_callable_get_intraday_volumes():
    """Test callable_get_intraday_volumes wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_intraday_volumes") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_intraday_volumes({"symbol": "2330"})
        assert result["status"] == "success"


def test_callable_get_snapshot_quotes():
    """Test callable_get_snapshot_quotes wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_snapshot_quotes") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_snapshot_quotes({"symbols": ["2330"]})
        assert result["status"] == "success"


def test_callable_get_snapshot_movers():
    """Test callable_get_snapshot_movers wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_snapshot_movers") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_snapshot_movers({"direction": "up"})
        assert result["status"] == "success"


def test_callable_get_snapshot_actives():
    """Test callable_get_snapshot_actives wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_snapshot_actives") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_snapshot_actives({})
        assert result["status"] == "success"


def test_callable_get_historical_stats():
    """Test callable_get_historical_stats wrapper"""
    with patch("fubon_api_mcp_server.market_data_service.get_historical_stats") as mock_fn:
        mock_fn.return_value = {"status": "success"}
        result = server.callable_get_historical_stats({"symbol": "2330"})
        assert result["status"] == "success"


# =============================================================================
# Main Function Tests
# =============================================================================
# Note: main() function tests are excluded due to complex initialization
# and direct module imports that are difficult to mock reliably.
# The main() function is tested indirectly through integration tests.
