"""
Tests for market data service functions in server.py.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from fubon_api_mcp_server.server import (
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


class TestGetRealtimeQuotes:
    """Test get_realtime_quotes function."""

    def test_get_realtime_quotes_success(self, mock_server_globals, mock_sdk):
        """Test get_realtime_quotes success."""
        mock_response = Mock()
        mock_response.dict.return_value = {"price": 500.0}
        mock_sdk.marketdata.rest_client.stock.intraday.quote.return_value = mock_response

        result = get_realtime_quotes({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"] == {"price": 500.0}
        assert "成功獲取 2330 即時行情" in result["message"]

    def test_get_realtime_quotes_exception(self, mock_server_globals, mock_sdk):
        """Test get_realtime_quotes with exception."""
        mock_sdk.marketdata.rest_client.stock.intraday.quote.side_effect = Exception("API error")

        result = get_realtime_quotes({"symbol": "2330"})

        assert result["status"] == "error"
        assert "獲取即時行情失敗" in result["message"]


class TestGetIntradayTickers:
    """Test get_intraday_tickers function."""

    def test_get_intraday_tickers_success(self, mock_server_globals, mock_sdk):
        """Test get_intraday_tickers success."""
        mock_sdk.marketdata.rest_client.stock.intraday.tickers.return_value = [{"symbol": "2330", "name": "台積電"}]

        result = get_intraday_tickers({"market": "TSE"})

        assert result["status"] == "success"
        assert result["data"] == [{"symbol": "2330", "name": "台積電"}]
        assert "成功獲取 TSE 市場股票列表" in result["message"]

    def test_get_intraday_tickers_exception(self, mock_server_globals, mock_sdk):
        """Test get_intraday_tickers with exception."""
        mock_sdk.marketdata.rest_client.stock.intraday.tickers.side_effect = Exception("API error")

        result = get_intraday_tickers({"market": "TSE"})

        assert result["status"] == "error"
        assert "獲取股票列表失敗" in result["message"]


class TestGetIntradayTicker:
    """Test get_intraday_ticker function."""

    def test_get_intraday_ticker_success(self, mock_server_globals, mock_sdk):
        """Test get_intraday_ticker success."""
        mock_response = Mock()
        mock_response.dict.return_value = {
            "symbol": "2330", 
            "name": "台積電",
            "securityType": "01"
        }
        mock_sdk.marketdata.rest_client.stock.intraday.ticker.return_value = mock_response

        result = get_intraday_ticker({"symbol": "2330"})

        assert result["status"] == "success"
        expected_data = {
            "symbol": "2330", 
            "name": "台積電",
            "securityType": "01",
            "securityTypeName": "一般股票"
        }
        assert result["data"] == expected_data
        assert "成功獲取 2330 基本資料" in result["message"]

    def test_get_intraday_quote_success(self, mock_server_globals, mock_sdk):
        """Test get_intraday_quote success."""
        mock_response = Mock()
        mock_response.dict.return_value = {"price": 500.0, "volume": 10000}
        mock_sdk.marketdata.rest_client.stock.intraday.quote.return_value = mock_response

        result = get_intraday_quote({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"] == {"price": 500.0, "volume": 10000}
        assert "成功獲取 2330 即時報價" in result["message"]


class TestGetIntradayCandles:
    """Test get_intraday_candles function."""

    def test_get_intraday_candles_success(self, mock_server_globals, mock_sdk):
        """Test get_intraday_candles success."""
        mock_sdk.marketdata.rest_client.stock.intraday.candles.return_value = [{"time": "09:00", "open": 500.0}]

        result = get_intraday_candles({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"] == [{"time": "09:00", "open": 500.0}]
        assert "成功獲取 2330 盤中 K 線" in result["message"]


class TestGetIntradayTrades:
    """Test get_intraday_trades function."""

    def test_get_intraday_trades_success(self, mock_server_globals, mock_sdk):
        """Test get_intraday_trades success."""
        mock_sdk.marketdata.rest_client.stock.intraday.trades.return_value = [{"time": "09:00", "price": 500.0, "volume": 100}]

        result = get_intraday_trades({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"] == [{"time": "09:00", "price": 500.0, "volume": 100}]
        assert "成功獲取 2330 成交明細" in result["message"]


class TestGetIntradayVolumes:
    """Test get_intraday_volumes function."""

    def test_get_intraday_volumes_success(self, mock_server_globals, mock_sdk):
        """Test get_intraday_volumes success."""
        mock_sdk.marketdata.rest_client.stock.intraday.volumes.return_value = [{"price": 500.0, "volume": 1000}]

        result = get_intraday_volumes({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"] == [{"price": 500.0, "volume": 1000}]
        assert "成功獲取 2330 分價量表" in result["message"]


class TestGetSnapshotQuotes:
    """Test get_snapshot_quotes function."""

    def test_get_snapshot_quotes_success(self, mock_server_globals, mock_sdk):
        """Test get_snapshot_quotes success."""
        mock_sdk.marketdata.rest_client.stock.snapshot.quotes.return_value = [{"symbol": "2330", "price": 500.0}]

        result = get_snapshot_quotes({"market": "TSE"})

        assert result["status"] == "success"
        assert result["data"] == [{"symbol": "2330", "price": 500.0}]
        assert "成功獲取 TSE 行情快照" in result["message"]


class TestGetSnapshotMovers:
    """Test get_snapshot_movers function."""

    def test_get_snapshot_movers_success(self, mock_server_globals, mock_sdk):
        """Test get_snapshot_movers success."""
        mock_response = {
            "data": [{"symbol": "2330", "change": 5.0}],
            "market": "TSE",
            "direction": "up",
            "change": "percent",
            "date": "2023-01-01",
            "time": "09:00",
        }
        mock_sdk.marketdata.rest_client.stock.snapshot.movers.return_value = mock_response

        result = get_snapshot_movers({"market": "TSE"})

        assert result["status"] == "success"
        assert result["data"] == [{"symbol": "2330", "change": 5.0}]
        assert "成功獲取 TSE 漲跌幅排行" in result["message"]


class TestGetSnapshotActives:
    """Test get_snapshot_actives function."""

    def test_get_snapshot_actives_success(self, mock_server_globals, mock_sdk):
        """Test get_snapshot_actives success."""
        mock_data = [{"symbol": "2330", "volume": 10000}] * 60  # More than 50
        mock_sdk.marketdata.rest_client.stock.snapshot.actives.return_value = {"data": mock_data}

        result = get_snapshot_actives({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 50  # Limited to 50
        assert result["total_count"] == 60
        assert result["returned_count"] == 50
        assert "成交量值排行" in result["message"]

    def test_get_snapshot_actives_small_data(self, mock_server_globals, mock_sdk):
        """Test get_snapshot_actives with small data set."""
        mock_data = [{"symbol": "2330", "volume": 10000}] * 10
        mock_sdk.marketdata.rest_client.stock.snapshot.actives.return_value = {"data": mock_data}

        result = get_snapshot_actives({"market": "TSE"})

        assert result["status"] == "success"
        assert len(result["data"]) == 10
        assert result["total_count"] == 10

    def test_get_historical_stats_success(self, mock_server_globals, mock_sdk):
        """Test get_historical_stats success."""
        mock_response = {
            "week52High": 600.0,
            "week52Low": 400.0,
            "symbol": "2330",
            "name": "台積電",
            "closePrice": 500.0,
            "change": 5.0,
            "changePercent": 1.0,
            "date": "2023-01-01",
        }
        mock_sdk.marketdata.rest_client.stock.historical.stats.return_value = mock_response

        result = get_historical_stats({"symbol": "2330"})

        assert result["status"] == "success"
        assert result["data"] == {
            "symbol": "2330",
            "name": "台積電",
            "52_week_high": 600.0,
            "52_week_low": 400.0,
            "current_price": 500.0,
            "change": 5.0,
            "change_percent": 1.0,
            "date": "2023-01-01",
        }
        assert "成功獲取 2330 近 52 週統計" in result["message"]

    def test_get_historical_stats_exception(self, mock_server_globals, mock_sdk):
        """Test get_historical_stats with exception."""
        mock_sdk.marketdata.rest_client.stock.historical.stats.side_effect = Exception("API error")

        result = get_historical_stats({"symbol": "2330"})

        assert result["status"] == "error"
        assert "獲取歷史統計失敗" in result["message"]
