"""
Tests for market data service functions in server.py.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from fubon_api_mcp_server.server import (
    get_historical_stats,
    get_intraday_candles,
    get_intraday_futopt_candles,
    get_intraday_futopt_products,
    get_intraday_futopt_quote,
    get_intraday_futopt_ticker,
    get_intraday_futopt_tickers,
    get_intraday_futopt_trades,
    get_intraday_futopt_volumes,
    get_intraday_quote,
    get_intraday_ticker,
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


class TestGetIntradayTicker:
    """Test get_intraday_ticker function."""

    def test_get_intraday_ticker_success(self, mock_server_globals, mock_sdk):
        """Test get_intraday_ticker success."""
        mock_response = Mock()
        mock_response.dict.return_value = {"symbol": "2330", "name": "台積電", "securityType": "01"}
        mock_sdk.marketdata.rest_client.stock.intraday.ticker.return_value = mock_response

        result = get_intraday_ticker({"symbol": "2330"})

        assert result["status"] == "success"
        expected_data = {"symbol": "2330", "name": "台積電", "securityType": "01", "securityTypeName": "一般股票"}
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


class TestGetIntradayFutOptProducts:
    """Test get_intraday_futopt_products function."""

    def test_get_intraday_futopt_products_success(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_products success."""
        mock_response = {
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "session": "REGULAR",
            "contractType": "I",
            "status": "ACTIVE",
            "data": [
                {
                    "symbol": "TX00",
                    "name": "台指期近月",
                    "type": "FUTURE",
                    "exchange": "TAIFEX",
                    "session": "REGULAR",
                    "contractType": "I",
                    "contractSize": 200,
                    "statusCode": "ACTIVE",
                    "tradingCurrency": "TWD",
                    "quoteAcceptable": True,
                    "startDate": "20240101",
                    "canBlockTrade": True,
                    "expiryType": "MONTHLY",
                    "underlyingType": "INDEX",
                    "marketCloseGroup": "FUTURES",
                    "endSession": "REGULAR",
                    "underlyingSymbol": "TWI",
                },
                {
                    "symbol": "MTX00",
                    "name": "小台指期近月",
                    "type": "FUTURE",
                    "exchange": "TAIFEX",
                    "session": "REGULAR",
                    "contractType": "I",
                    "contractSize": 50,
                    "statusCode": "ACTIVE",
                    "tradingCurrency": "TWD",
                    "quoteAcceptable": True,
                    "startDate": "20240101",
                    "canBlockTrade": True,
                    "expiryType": "MONTHLY",
                    "underlyingType": "INDEX",
                    "marketCloseGroup": "FUTURES",
                    "endSession": "REGULAR",
                    "underlyingSymbol": "MTX",
                },
            ],
        }
        mock_restfutopt.intraday.products.return_value = mock_response

        result = get_intraday_futopt_products({"type": "FUTURE", "contractType": "I"})

        assert result["status"] == "success"
        assert result["type"] == "FUTURE"
        assert result["exchange"] == "TAIFEX"
        assert result["contractType"] == "I"
        assert result["query_status"] == "ACTIVE"
        assert result["total_count"] == 2
        assert result["type_counts"] == {"FUTURE": 2}
        assert len(result["data"]) == 2
        assert result["data"][0]["symbol"] == "TX00"
        assert result["data"][0]["name"] == "台指期近月"
        assert result["data"][1]["symbol"] == "MTX00"
        assert "成功獲取 2 筆合約資訊" in result["message"]

    def test_get_intraday_futopt_products_empty_data(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_products with empty data."""
        mock_response = {"type": None, "exchange": None, "session": None, "contractType": None, "status": None, "data": []}
        mock_restfutopt.intraday.products.return_value = mock_response

        result = get_intraday_futopt_products({})

        assert result["status"] == "success"
        assert result["total_count"] == 0
        assert result["data"] == []
        assert "成功獲取 0 筆合約資訊" in result["message"]

    def test_get_intraday_futopt_products_api_error(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_products with API error."""
        mock_restfutopt.intraday.products.return_value = None

        result = get_intraday_futopt_products({"type": "FUTURE"})

        assert result["status"] == "error"
        assert "API 返回格式錯誤" in result["message"]

    def test_get_intraday_futopt_products_exception(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_products with exception."""
        mock_restfutopt.intraday.products.side_effect = Exception("API connection error")

        result = get_intraday_futopt_products({"type": "FUTURE"})

        assert result["status"] == "error"
        assert "獲取合約列表失敗" in result["message"]


class TestGetIntradayFutOptTickers:
    """Test get_intraday_futopt_tickers function."""

    def test_get_intraday_futopt_tickers_success(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_tickers success."""
        mock_response = {
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "session": "REGULAR",
            "contractType": "I",
            "data": [
                {
                    "symbol": "TX00",
                    "name": "台指期近月",
                    "type": "FUTURE",
                    "exchange": "TAIFEX",
                    "session": "REGULAR",
                    "product": "TX00",
                    "contractType": "I",
                    "expirationDate": "20241220",
                    "strikePrice": None,
                    "optionType": None,
                    "underlyingSymbol": "TWI",
                    "multiplier": 200,
                    "tickSize": 1,
                    "tradingHours": "08:45-15:00",
                    "lastTradingDate": "20241220",
                },
                {
                    "symbol": "MTX00",
                    "name": "小台指期近月",
                    "type": "FUTURE",
                    "exchange": "TAIFEX",
                    "session": "REGULAR",
                    "product": "MTX00",
                    "contractType": "I",
                    "expirationDate": "20241220",
                    "strikePrice": None,
                    "optionType": None,
                    "underlyingSymbol": "MTX",
                    "multiplier": 50,
                    "tickSize": 0.5,
                    "tradingHours": "08:45-15:00",
                    "lastTradingDate": "20241220",
                },
            ],
        }
        mock_restfutopt.intraday.tickers.return_value = mock_response

        result = get_intraday_futopt_tickers({"type": "FUTURE", "contractType": "I"})

        assert result["status"] == "success"
        assert result["total_count"] == 2
        assert result["type_counts"] == {"FUTURE": 2}
        assert result["filters_applied"] == {"type": "FUTURE", "contractType": "I"}
        assert len(result["data"]) == 2
        assert result["data"][0]["symbol"] == "TX00"
        assert result["data"][0]["name"] == "台指期近月"
        assert result["data"][0]["type"] == "FUTURE"
        assert result["data"][0]["contract_type"] == "I"
        assert result["data"][0]["expiration_date"] == "20241220"
        assert result["data"][0]["underlying_symbol"] == "TWI"
        assert result["data"][0]["multiplier"] == 200
        assert result["data"][1]["symbol"] == "MTX00"
        assert "成功獲取 2 筆合約代碼資訊" in result["message"]

    def test_get_intraday_futopt_tickers_empty_data(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_tickers with empty data."""
        mock_response = {"type": "FUTURE", "exchange": "TAIFEX", "session": "REGULAR", "contractType": "I", "data": []}
        mock_restfutopt.intraday.tickers.return_value = mock_response

        result = get_intraday_futopt_tickers({"type": "FUTURE"})

        assert result["status"] == "success"
        assert result["total_count"] == 0
        assert result["data"] == []
        assert result["type_counts"] == {}
        assert "成功獲取 0 筆合約代碼資訊" in result["message"]

    def test_get_intraday_futopt_tickers_with_options(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_tickers with options data."""
        mock_response = {
            "type": "OPTION",
            "exchange": "TAIFEX",
            "session": "REGULAR",
            "contractType": "I",
            "data": [
                {
                    "symbol": "TE00C24000",
                    "name": "台指選擇權看漲24000",
                    "type": "OPTION",
                    "exchange": "TAIFEX",
                    "session": "REGULAR",
                    "product": "TE00",
                    "contractType": "I",
                    "expirationDate": "20241220",
                    "strikePrice": 24000.0,
                    "optionType": "CALL",
                    "underlyingSymbol": "TWI",
                    "multiplier": 50,
                    "tickSize": 1,
                    "tradingHours": "08:45-15:00",
                    "lastTradingDate": "20241220",
                }
            ],
        }
        mock_restfutopt.intraday.tickers.return_value = mock_response

        result = get_intraday_futopt_tickers({"type": "OPTION", "product": "TE00"})

        assert result["status"] == "success"
        assert result["total_count"] == 1
        assert result["type_counts"] == {"OPTION": 1}
        assert len(result["data"]) == 1
        ticker = result["data"][0]
        assert ticker["symbol"] == "TE00C24000"
        assert ticker["type"] == "OPTION"
        assert ticker["contract_type"] == "I"
        assert ticker["strike_price"] == 24000.0
        assert ticker["option_type"] == "CALL"
        assert "成功獲取 1 筆合約代碼資訊" in result["message"]

    def test_get_intraday_futopt_tickers_api_error(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_tickers with API error."""
        mock_restfutopt.intraday.tickers.return_value = None

        result = get_intraday_futopt_tickers({"type": "FUTURE"})

        assert result["status"] == "error"
        assert "API 返回格式錯誤" in result["message"]

    def test_get_intraday_futopt_tickers_invalid_format(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_tickers with invalid response format."""
        mock_restfutopt.intraday.tickers.return_value = {"invalid": "format"}

        result = get_intraday_futopt_tickers({"type": "FUTURE"})

        assert result["status"] == "error"
        assert "API 返回格式錯誤" in result["message"]

    def test_get_intraday_futopt_tickers_service_not_initialized(self, mock_server_globals):
        """Test get_intraday_futopt_tickers when service not initialized."""
        with patch("fubon_api_mcp_server.server.restfutopt", None):
            result = get_intraday_futopt_tickers({"type": "FUTURE"})

        assert result["status"] == "error"
        assert "期貨/選擇權行情服務未初始化" in result["message"]

    def test_get_intraday_futopt_tickers_exception(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_tickers with exception."""
        mock_restfutopt.intraday.tickers.side_effect = Exception("API connection error")

        result = get_intraday_futopt_tickers({"type": "FUTURE"})

        assert result["status"] == "error"
        assert "獲取合約代碼列表失敗" in result["message"]


class TestGetIntradayFutOptTicker:
    """Test get_intraday_futopt_ticker function."""

    def test_get_intraday_futopt_ticker_success(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_ticker success."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "name": "台指期近月",
            "referencePrice": 18000.0,
            "settlementDate": "20241220",
            "startDate": "20240101",
            "endDate": "20241220",
        }
        mock_restfutopt.intraday.ticker.return_value = mock_response

        result = get_intraday_futopt_ticker({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"] == {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "name": "台指期近月",
            "referencePrice": 18000.0,
            "settlementDate": "20241220",
            "startDate": "20240101",
            "endDate": "20241220",
        }
        assert "成功獲取合約 TX00 基本資訊" in result["message"]

    def test_get_intraday_futopt_ticker_with_session(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_ticker with session parameter."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "name": "台指期近月",
            "referencePrice": 18000.0,
        }
        mock_restfutopt.intraday.ticker.return_value = mock_response

        result = get_intraday_futopt_ticker({"symbol": "TX00", "session": "afterhours"})

        assert result["status"] == "success"
        mock_restfutopt.intraday.ticker.assert_called_once_with(symbol="TX00", session="afterhours")

    def test_get_intraday_futopt_ticker_not_found(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_ticker when symbol not found."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = None
        mock_restfutopt.intraday.ticker.return_value = mock_response

        result = get_intraday_futopt_ticker({"symbol": "INVALID"})

        assert result["status"] == "error"
        assert "找不到合約代碼 INVALID" in result["message"]

    def test_get_intraday_futopt_ticker_api_error(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_ticker with API error."""
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.message = "API error"
        mock_restfutopt.intraday.ticker.return_value = mock_response

        result = get_intraday_futopt_ticker({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "API 調用失敗: API error" in result["message"]

    def test_get_intraday_futopt_ticker_service_not_initialized(self, mock_server_globals):
        """Test get_intraday_futopt_ticker when service not initialized."""
        with patch("fubon_api_mcp_server.server.restfutopt", None):
            result = get_intraday_futopt_ticker({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "期貨/選擇權行情服務未初始化" in result["message"]

    def test_get_intraday_futopt_ticker_exception(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_ticker with exception."""
        mock_restfutopt.intraday.ticker.side_effect = Exception("Connection error")

        result = get_intraday_futopt_ticker({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "獲取合約基本資訊失敗" in result["message"]


class TestGetIntradayFutOptQuote:
    """Test get_intraday_futopt_quote function."""

    def test_get_intraday_futopt_quote_success(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_quote success."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "name": "台指期近月",
            "previousClose": 17900.0,
            "openPrice": 18000.0,
            "closePrice": 18100.0,
            "highPrice": 18200.0,
            "lowPrice": 17800.0,
            "lastPrice": 18100.0,
            "change": 200.0,
            "changePercent": 1.12,
            "total": {
                "tradeVolume": 15000,
                "totalBidMatch": 7500,
                "totalAskMatch": 7500,
            },
            "lastTrade": {
                "bid": 18100.0,
                "ask": 18105.0,
                "price": 18100.0,
                "size": 1,
                "time": "14:30:00",
                "serial": 12345,
            },
        }
        mock_restfutopt.intraday.quote.return_value = mock_response

        result = get_intraday_futopt_quote({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"] == {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "name": "台指期近月",
            "previousClose": 17900.0,
            "openPrice": 18000.0,
            "closePrice": 18100.0,
            "highPrice": 18200.0,
            "lowPrice": 17800.0,
            "lastPrice": 18100.0,
            "change": 200.0,
            "changePercent": 1.12,
            "total": {
                "tradeVolume": 15000,
                "totalBidMatch": 7500,
                "totalAskMatch": 7500,
            },
            "lastTrade": {
                "bid": 18100.0,
                "ask": 18105.0,
                "price": 18100.0,
                "size": 1,
                "time": "14:30:00",
                "serial": 12345,
            },
        }
        assert "成功獲取合約 TX00 即時報價" in result["message"]

    def test_get_intraday_futopt_quote_with_session(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_quote with session parameter."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {"symbol": "TX00", "lastPrice": 18100.0}
        mock_restfutopt.intraday.quote.return_value = mock_response

        result = get_intraday_futopt_quote({"symbol": "TX00", "session": "afterhours"})

        assert result["status"] == "success"
        mock_restfutopt.intraday.quote.assert_called_once_with(symbol="TX00", session="afterhours")

    def test_get_intraday_futopt_quote_not_found(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_quote when symbol not found."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = None
        mock_restfutopt.intraday.quote.return_value = mock_response

        result = get_intraday_futopt_quote({"symbol": "INVALID"})

        assert result["status"] == "error"
        assert "找不到合約代碼 INVALID" in result["message"]

    def test_get_intraday_futopt_quote_api_error(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_quote with API error."""
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.message = "Quote not available"
        mock_restfutopt.intraday.quote.return_value = mock_response

        result = get_intraday_futopt_quote({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "API 調用失敗: Quote not available" in result["message"]

    def test_get_intraday_futopt_quote_service_not_initialized(self, mock_server_globals):
        """Test get_intraday_futopt_quote when service not initialized."""
        with patch("fubon_api_mcp_server.server.restfutopt", None):
            result = get_intraday_futopt_quote({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "期貨/選擇權行情服務未初始化" in result["message"]

    def test_get_intraday_futopt_quote_exception(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_quote with exception."""
        mock_restfutopt.intraday.quote.side_effect = Exception("Network timeout")

        result = get_intraday_futopt_quote({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "獲取合約即時報價失敗" in result["message"]


class TestGetIntradayFutOptCandles:
    """Test get_intraday_futopt_candles function."""

    def test_get_intraday_futopt_candles_success(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_candles success."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "timeframe": "1",
            "data": [
                {"open": 18000.0, "high": 18100.0, "low": 17950.0, "close": 18050.0, "volume": 100},
                {"open": 18050.0, "high": 18150.0, "low": 18000.0, "close": 18100.0, "volume": 150},
            ],
        }
        mock_restfutopt.intraday.candles.return_value = mock_response

        result = get_intraday_futopt_candles({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"] == {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "timeframe": "1",
            "data": [
                {"open": 18000.0, "high": 18100.0, "low": 17950.0, "close": 18050.0, "volume": 100},
                {"open": 18050.0, "high": 18150.0, "low": 18000.0, "close": 18100.0, "volume": 150},
            ],
        }
        assert "成功獲取合約 TX00 K 線數據" in result["message"]

    def test_get_intraday_futopt_candles_with_timeframe(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_candles with timeframe parameter."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {"symbol": "TX00", "timeframe": "5", "data": []}
        mock_restfutopt.intraday.candles.return_value = mock_response

        result = get_intraday_futopt_candles({"symbol": "TX00", "timeframe": "5", "session": "regular"})

        assert result["status"] == "success"
        mock_restfutopt.intraday.candles.assert_called_once_with(symbol="TX00", session="regular", timeframe="5")

    def test_get_intraday_futopt_candles_not_found(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_candles when symbol not found."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = None
        mock_restfutopt.intraday.candles.return_value = mock_response

        result = get_intraday_futopt_candles({"symbol": "INVALID"})

        assert result["status"] == "error"
        assert "找不到合約代碼 INVALID" in result["message"]

    def test_get_intraday_futopt_candles_api_error(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_candles with API error."""
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.message = "Candles data unavailable"
        mock_restfutopt.intraday.candles.return_value = mock_response

        result = get_intraday_futopt_candles({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "API 調用失敗: Candles data unavailable" in result["message"]

    def test_get_intraday_futopt_candles_service_not_initialized(self, mock_server_globals):
        """Test get_intraday_futopt_candles when service not initialized."""
        with patch("fubon_api_mcp_server.server.restfutopt", None):
            result = get_intraday_futopt_candles({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "期貨/選擇權行情服務未初始化" in result["message"]

    def test_get_intraday_futopt_candles_exception(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_candles with exception."""
        mock_restfutopt.intraday.candles.side_effect = Exception("Database error")

        result = get_intraday_futopt_candles({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "獲取合約 K 線數據失敗" in result["message"]


class TestGetIntradayFutOptVolumes:
    """Test get_intraday_futopt_volumes function."""

    def test_get_intraday_futopt_volumes_success(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_volumes success."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "data": [
                {"price": 18000.0, "volume": 100},
                {"price": 18050.0, "volume": 150},
                {"price": 18100.0, "volume": 200},
            ],
        }
        mock_restfutopt.intraday.volumes.return_value = mock_response

        result = get_intraday_futopt_volumes({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"] == {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "data": [
                {"price": 18000.0, "volume": 100},
                {"price": 18050.0, "volume": 150},
                {"price": 18100.0, "volume": 200},
            ],
        }
        assert "成功獲取合約 TX00 成交量數據" in result["message"]

    def test_get_intraday_futopt_volumes_with_session(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_volumes with session parameter."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {"symbol": "TX00", "data": []}
        mock_restfutopt.intraday.volumes.return_value = mock_response

        result = get_intraday_futopt_volumes({"symbol": "TX00", "session": "afterhours"})

        assert result["status"] == "success"
        mock_restfutopt.intraday.volumes.assert_called_once_with(symbol="TX00", session="afterhours")

    def test_get_intraday_futopt_volumes_not_found(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_volumes when symbol not found."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = None
        mock_restfutopt.intraday.volumes.return_value = mock_response

        result = get_intraday_futopt_volumes({"symbol": "INVALID"})

        assert result["status"] == "error"
        assert "找不到合約代碼 INVALID" in result["message"]

    def test_get_intraday_futopt_volumes_api_error(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_volumes with API error."""
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.message = "Volume data not available"
        mock_restfutopt.intraday.volumes.return_value = mock_response

        result = get_intraday_futopt_volumes({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "API 調用失敗: Volume data not available" in result["message"]

    def test_get_intraday_futopt_volumes_service_not_initialized(self, mock_server_globals):
        """Test get_intraday_futopt_volumes when service not initialized."""
        with patch("fubon_api_mcp_server.server.restfutopt", None):
            result = get_intraday_futopt_volumes({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "期貨/選擇權行情服務未初始化" in result["message"]

    def test_get_intraday_futopt_volumes_exception(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_volumes with exception."""
        mock_restfutopt.intraday.volumes.side_effect = Exception("Connection timeout")

        result = get_intraday_futopt_volumes({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "獲取合約成交量數據失敗" in result["message"]


class TestGetIntradayFutOptTrades:
    """Test get_intraday_futopt_trades function."""

    def test_get_intraday_futopt_trades_success(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_trades success."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "data": [
                {"time": "09:00:01", "price": 18000.0, "volume": 1, "tick_type": "up"},
                {"time": "09:00:02", "price": 18005.0, "volume": 2, "tick_type": "down"},
                {"time": "09:00:03", "price": 18010.0, "volume": 1, "tick_type": "equal"},
            ],
        }
        mock_restfutopt.intraday.trades.return_value = mock_response

        result = get_intraday_futopt_trades({"symbol": "TX00"})

        assert result["status"] == "success"
        assert result["data"] == {
            "date": "20241220",
            "type": "FUTURE",
            "exchange": "TAIFEX",
            "symbol": "TX00",
            "data": [
                {"time": "09:00:01", "price": 18000.0, "volume": 1, "tick_type": "up"},
                {"time": "09:00:02", "price": 18005.0, "volume": 2, "tick_type": "down"},
                {"time": "09:00:03", "price": 18010.0, "volume": 1, "tick_type": "equal"},
            ],
        }
        assert "成功獲取合約 TX00 成交明細數據" in result["message"]

    def test_get_intraday_futopt_trades_with_pagination(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_trades with pagination parameters."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = {"symbol": "TX00", "data": []}
        mock_restfutopt.intraday.trades.return_value = mock_response

        result = get_intraday_futopt_trades({"symbol": "TX00", "session": "regular", "offset": 10, "limit": 50})

        assert result["status"] == "success"
        mock_restfutopt.intraday.trades.assert_called_once_with(symbol="TX00", session="regular", offset=10, limit=50)

    def test_get_intraday_futopt_trades_not_found(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_trades when symbol not found."""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.data = None
        mock_restfutopt.intraday.trades.return_value = mock_response

        result = get_intraday_futopt_trades({"symbol": "INVALID"})

        assert result["status"] == "error"
        assert "找不到合約代碼 INVALID" in result["message"]

    def test_get_intraday_futopt_trades_api_error(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_trades with API error."""
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.message = "Trade data temporarily unavailable"
        mock_restfutopt.intraday.trades.return_value = mock_response

        result = get_intraday_futopt_trades({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "API 調用失敗: Trade data temporarily unavailable" in result["message"]

    def test_get_intraday_futopt_trades_service_not_initialized(self, mock_server_globals):
        """Test get_intraday_futopt_trades when service not initialized."""
        with patch("fubon_api_mcp_server.server.restfutopt", None):
            result = get_intraday_futopt_trades({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "期貨/選擇權行情服務未初始化" in result["message"]

    def test_get_intraday_futopt_trades_exception(self, mock_server_globals_futopt, mock_restfutopt):
        """Test get_intraday_futopt_trades with exception."""
        mock_restfutopt.intraday.trades.side_effect = Exception("Server overload")

        result = get_intraday_futopt_trades({"symbol": "TX00"})

        assert result["status"] == "error"
        assert "獲取合約成交明細數據失敗" in result["message"]
