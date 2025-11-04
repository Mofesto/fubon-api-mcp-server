"""
Tests for market_data_service.py - Market data services.

This module tests market data related MCP tools including quotes,
tickers, candles, and market statistics.
"""

from unittest.mock import MagicMock

import pytest

from fubon_mcp import config
from fubon_mcp.market_data_service import (
    get_historical_stats,
    get_intraday_candles,
    get_intraday_quote,
    get_intraday_ticker,
    get_intraday_tickers,
    get_intraday_trades,
    get_intraday_volumes,
    get_realtime_quotes,
    get_snapshot_actives,
    get_snapshot_movers,
    get_snapshot_quotes,
)


class TestMarketDataServices:
    """Test market data service functions."""

    def test_get_intraday_tickers_success(self, mock_reststock):
        """Test successful intraday tickers retrieval."""
        config.reststock = mock_reststock

        # Mock API response
        mock_result = [
            {"symbol": "2330", "price": 500.0},
            {"symbol": "2454", "price": 1000.0}
        ]
        mock_reststock.intraday.tickers.return_value = mock_result

        result = get_intraday_tickers.fn({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["data"][0]["symbol"] == "2330"
        mock_reststock.intraday.tickers.assert_called_once_with(market="TSE")

    def test_get_intraday_ticker_success(self, mock_reststock):
        """Test successful intraday ticker retrieval."""
        config.reststock = mock_reststock

        mock_result = {"symbol": "2330", "price": 500.0, "volume": 1000000}
        mock_reststock.intraday.ticker.return_value = mock_result

        result = get_intraday_ticker.fn({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["symbol"] == "2330"
        mock_reststock.intraday.ticker.assert_called_once_with("2330")

    def test_get_intraday_quote_success(self, mock_reststock):
        """Test successful intraday quote retrieval."""
        config.reststock = mock_reststock

        mock_result = {
            "symbol": "2330",
            "price": 500.0,
            "change": 5.0,
            "change_percent": 1.0
        }
        mock_reststock.intraday.quote.return_value = mock_result

        result = get_intraday_quote.fn({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["price"] == 500.0
        mock_reststock.intraday.quote.assert_called_once_with(symbol="2330")

    def test_get_intraday_candles_success(self, mock_reststock):
        """Test successful intraday candles retrieval."""
        config.reststock = mock_reststock

        mock_result = [
            {"time": "09:00", "open": 495.0, "high": 505.0, "low": 490.0, "close": 500.0},
            {"time": "09:01", "open": 500.0, "high": 510.0, "low": 495.0, "close": 505.0}
        ]
        mock_reststock.intraday.candles.return_value = mock_result

        result = get_intraday_candles.fn({"symbol": "2330"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        mock_reststock.intraday.candles.assert_called_once_with("2330")

    def test_get_intraday_trades_success(self, mock_reststock):
        """Test successful intraday trades retrieval."""
        config.reststock = mock_reststock

        mock_result = [
            {"time": "09:00:01", "price": 500.0, "volume": 100},
            {"time": "09:00:02", "price": 501.0, "volume": 200}
        ]
        mock_reststock.intraday.trades.return_value = mock_result

        result = get_intraday_trades.fn({"symbol": "2330"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        mock_reststock.intraday.trades.assert_called_once_with("2330")

    def test_get_intraday_volumes_success(self, mock_reststock):
        """Test successful intraday volumes retrieval."""
        config.reststock = mock_reststock

        mock_result = [
            {"time": "09:00", "volume": 10000},
            {"time": "09:01", "volume": 15000}
        ]
        mock_reststock.intraday.volumes.return_value = mock_result

        result = get_intraday_volumes.fn({"symbol": "2330"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        mock_reststock.intraday.volumes.assert_called_once_with("2330")

    def test_get_snapshot_quotes_success(self, mock_reststock):
        """Test successful snapshot quotes retrieval."""
        config.reststock = mock_reststock

        mock_result = [
            {"symbol": "2330", "price": 500.0, "change": 5.0},
            {"symbol": "2454", "price": 1000.0, "change": -10.0}
        ]
        mock_reststock.snapshot.quotes.return_value = mock_result

        result = get_snapshot_quotes.fn({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        mock_reststock.snapshot.quotes.assert_called_once_with("TSE")

    def test_get_snapshot_movers_success(self, mock_reststock):
        """Test successful snapshot movers retrieval."""
        config.reststock = mock_reststock

        mock_result = [
            {"symbol": "2330", "change_percent": 5.0},
            {"symbol": "2454", "change_percent": -3.0}
        ]
        mock_reststock.snapshot.movers.return_value = mock_result

        result = get_snapshot_movers.fn({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        mock_reststock.snapshot.movers.assert_called_once_with("TSE")

    def test_get_snapshot_actives_success(self, mock_reststock):
        """Test successful snapshot actives retrieval."""
        config.reststock = mock_reststock

        mock_result = [
            {"symbol": "2330", "volume": 1000000},
            {"symbol": "2454", "volume": 500000}
        ]
        mock_reststock.snapshot.actives.return_value = mock_result

        result = get_snapshot_actives.fn({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        mock_reststock.snapshot.actives.assert_called_once_with(market="TSE", trade="volume")

    def test_get_historical_stats_success(self, mock_reststock):
        """Test successful historical stats retrieval."""
        config.reststock = mock_reststock

        mock_result = {
            "symbol": "2330",
            "high_52w": 600.0,
            "low_52w": 400.0,
            "avg_volume": 1000000
        }
        mock_reststock.historical.stats.return_value = mock_result

        result = get_historical_stats.fn({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["high_52w"] == 600.0
        mock_reststock.historical.stats.assert_called_once_with("2330")

    def test_get_realtime_quotes_success(self, mock_sdk):
        """Test successful realtime quotes retrieval."""
        config.sdk = mock_sdk

        mock_result = {
            "symbol": "2330",
            "price": 500.0,
            "bid": 499.0,
            "ask": 501.0
        }
        mock_sdk.marketdata.realtime.quote.return_value = mock_result

        result = get_realtime_quotes.fn({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"]["price"] == 500.0
        mock_sdk.marketdata.realtime.quote.assert_called_once_with("2330")

    def test_market_data_api_failure(self, mock_reststock):
        """Test market data API failure handling."""
        config.reststock = mock_reststock

        mock_reststock.intraday.ticker.side_effect = Exception("API Error")

        result = get_intraday_ticker.fn({"symbol": "2330"})

        assert result["status"] == "error"
        assert "API Error" in result["message"]

    def test_market_data_no_reststock(self):
        """Test market data when reststock is not initialized."""
        config.reststock = None

        result = get_intraday_ticker.fn({"symbol": "2330"})

        assert result["status"] == "error"
        assert "REST client not initialized" in result["message"]


class TestMarketDataServiceIntegration:
    """Test market data service integration."""

    def test_all_market_data_functions_importable(self):
        """Test that all market data service functions can be imported."""
        from fubon_mcp.market_data_service import (
            get_historical_stats,
            get_intraday_candles,
            get_intraday_quote,
            get_intraday_ticker,
            get_intraday_tickers,
            get_intraday_trades,
            get_intraday_volumes,
            get_realtime_quotes,
            get_snapshot_actives,
            get_snapshot_movers,
            get_snapshot_quotes,
        )

        # Test that functions have .fn attribute (MCP FunctionTool objects)
        assert hasattr(get_intraday_tickers, 'fn')
        assert hasattr(get_intraday_ticker, 'fn')
        assert hasattr(get_intraday_quote, 'fn')
        assert hasattr(get_intraday_candles, 'fn')
        assert hasattr(get_intraday_trades, 'fn')
        assert hasattr(get_intraday_volumes, 'fn')
        assert hasattr(get_snapshot_quotes, 'fn')
        assert hasattr(get_snapshot_movers, 'fn')
        assert hasattr(get_snapshot_actives, 'fn')
        assert hasattr(get_historical_stats, 'fn')
        assert hasattr(get_realtime_quotes, 'fn')

    def test_market_data_service_module_structure(self):
        """Test market_data_service module has expected structure."""
        import fubon_mcp.market_data_service as market_data_module

        # Check for expected functions
        expected_functions = [
            'get_intraday_tickers',
            'get_intraday_ticker',
            'get_intraday_quote',
            'get_intraday_candles',
            'get_intraday_trades',
            'get_intraday_volumes',
            'get_snapshot_quotes',
            'get_snapshot_movers',
            'get_snapshot_actives',
            'get_historical_stats',
            'get_realtime_quotes'
        ]

        for func_name in expected_functions:
            assert hasattr(market_data_module, func_name), f"Market data service module missing function: {func_name}"
