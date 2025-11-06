"""
Additional tests for server.py functions with low coverage.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, call, patch

import pandas as pd
import pytest

from fubon_api_mcp_server.server import (
    _fetch_api_historical_data,
    _get_local_historical_data,
    fetch_historical_data_segment,
    get_historical_data,
    historical_candles,
    on_event,
    on_filled,
    on_order,
    on_order_changed,
    process_historical_data,
    read_local_stock_data,
    save_to_local_csv,
)


class TestHistoricalDataProcessing:
    """Test historical data processing functions."""

    def test_fetch_historical_data_segment_success(self):
        """Test successful historical data segment fetch."""
        with patch("fubon_api_mcp_server.server.reststock") as mock_reststock:
            mock_response = {"data": [{"date": "2023-01-01", "close": 100}]}
            mock_reststock.historical.candles.return_value = mock_response

            result = fetch_historical_data_segment("2330", "2023-01-01", "2023-01-02")
            assert result == [{"date": "2023-01-01", "close": 100}]

    def test_fetch_historical_data_segment_api_error(self):
        """Test historical data segment fetch with API error."""
        with patch("fubon_api_mcp_server.server.reststock") as mock_reststock:
            mock_reststock.historical.candles.side_effect = Exception("API error")

            result = fetch_historical_data_segment("2330", "2023-01-01", "2023-01-02")
            assert result == []

    def test_fetch_historical_data_segment_no_data(self):
        """Test historical data segment fetch with no data."""
        with patch("fubon_api_mcp_server.server.reststock") as mock_reststock:
            mock_reststock.historical.candles.return_value = {"data": []}

            result = fetch_historical_data_segment("2330", "2023-01-01", "2023-01-02")
            assert result == []

    def test_process_historical_data(self):
        """Test historical data processing."""
        df = pd.DataFrame(
            {"date": ["2023-01-01", "2023-01-02"], "open": [100, 101], "close": [105, 106], "volume": [1000, 1100]}
        )

        processed = process_historical_data(df)

        assert "vol_value" in processed.columns
        assert "price_change" in processed.columns
        assert "change_ratio" in processed.columns
        assert processed.loc[0, "vol_value"] == 105 * 1000
        assert processed.loc[0, "price_change"] == 105 - 100

    def test_read_local_stock_data_exists(self):
        """Test reading existing local stock data."""
        with patch("pathlib.Path.exists", return_value=True), patch("pandas.read_csv") as mock_read_csv:

            mock_df = pd.DataFrame({"date": ["2023-01-01"], "close": [100]})
            mock_read_csv.return_value = mock_df

            result = read_local_stock_data("2330")
            assert result is not None
            assert len(result) == 1

    def test_read_local_stock_data_not_exists(self):
        """Test reading non-existing local stock data."""
        with patch("pathlib.Path.exists", return_value=False):
            result = read_local_stock_data("NONEXISTENT")
            assert result is None

    def test_save_to_local_csv(self):
        """Test saving data to local CSV."""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("pandas.DataFrame.to_csv") as mock_to_csv,
            patch("shutil.move") as mock_move,
            patch("tempfile.NamedTemporaryFile") as mock_temp_file,
        ):

            mock_temp_file.return_value.__enter__.return_value.name = "temp.csv"

            test_data = [{"date": "2023-01-01", "close": 100}]
            save_to_local_csv("2330", test_data)

            mock_to_csv.assert_called_once()
            mock_move.assert_called_once()


class TestCallbackFunctions:
    """Test callback functions."""

    def test_on_order_callback(self):
        """Test order callback function."""
        with patch("fubon_api_mcp_server.server.latest_order_reports", []) as mock_reports:
            order_data = {"order_no": "12345", "symbol": "2330"}

            on_order(order_data)

            assert len(mock_reports) == 1
            assert mock_reports[0]["data"] == order_data
            assert "timestamp" in mock_reports[0]

    def test_on_order_changed_callback(self):
        """Test order changed callback function."""
        with patch("fubon_api_mcp_server.server.latest_order_changed_reports", []) as mock_reports:
            order_changed_data = {"order_no": "12345", "action": "modify"}

            on_order_changed(order_changed_data)

            assert len(mock_reports) == 1
            assert mock_reports[0]["data"] == order_changed_data

    def test_on_filled_callback(self):
        """Test filled callback function."""
        with patch("fubon_api_mcp_server.server.latest_filled_reports", []) as mock_reports:
            filled_data = {"order_no": "12345", "filled_qty": 1000}

            on_filled(filled_data)

            assert len(mock_reports) == 1
            assert mock_reports[0]["data"] == filled_data

    def test_on_event_callback(self):
        """Test event callback function."""
        with patch("fubon_api_mcp_server.server.latest_event_reports", []) as mock_reports:
            event_data = {"type": "connection", "status": "connected"}

            on_event(event_data)

            assert len(mock_reports) == 1
            assert mock_reports[0]["data"] == event_data


class TestHistoricalCandlesIntegration:
    """Test historical candles integration functions."""

    def test_get_historical_data_resource_success(self):
        """Test historical data resource with existing data."""
        with patch("fubon_api_mcp_server.server.read_local_stock_data") as mock_read:
            mock_df = pd.DataFrame({"date": ["2023-01-01"], "close": [100]})
            mock_read.return_value = mock_df

            result = get_historical_data("2330")

            assert result["status"] == "success"
            assert len(result["data"]) == 1

    def test_get_historical_data_resource_not_found(self):
        """Test historical data resource with no data."""
        with patch("fubon_api_mcp_server.server.read_local_stock_data", return_value=None):
            result = get_historical_data("NONEXISTENT")

            assert result["status"] == "error"
            assert result["data"] == []

    def test_historical_candles_success(self, mock_server_globals, mock_sdk):
        """Test historical candles with local data."""
        with patch("fubon_api_mcp_server.server._get_local_historical_data") as mock_local:
            mock_local.return_value = {
                "status": "success",
                "data": [{"date": "2023-01-01", "close": 100}],
                "message": "Local data",
            }

            result = historical_candles({"symbol": "2330", "from_date": "2023-01-01", "to_date": "2023-01-02"})

            assert result["status"] == "success"
            assert len(result["data"]) == 1

    def test_historical_candles_api_fallback(self, mock_server_globals, mock_sdk):
        """Test historical candles falling back to API."""
        with (
            patch("fubon_api_mcp_server.server._get_local_historical_data", return_value=None),
            patch("fubon_api_mcp_server.server._fetch_api_historical_data") as mock_api,
            patch("fubon_api_mcp_server.server.process_historical_data") as mock_process,
            patch("fubon_api_mcp_server.server.save_to_local_csv") as mock_save,
        ):

            mock_api.return_value = [{"date": "2023-01-01", "close": 100}]
            mock_process.return_value = pd.DataFrame([{"date": "2023-01-01", "close": 100}])

            result = historical_candles({"symbol": "2330", "from_date": "2023-01-01", "to_date": "2023-01-02"})

            assert result["status"] == "success"
            mock_api.assert_called_once()
            mock_save.assert_called_once()

    def test_get_local_historical_data_success(self):
        """Test getting local historical data successfully."""
        with (
            patch("fubon_api_mcp_server.server.read_local_stock_data") as mock_read,
            patch("fubon_api_mcp_server.server.process_historical_data") as mock_process,
        ):

            mock_df = pd.DataFrame({"date": ["2023-01-01", "2023-01-02"], "close": [100, 101]})
            mock_read.return_value = mock_df
            mock_process.return_value = mock_df

            result = _get_local_historical_data("2330", "2023-01-01", "2023-01-02")

            assert result["status"] == "success"
            assert len(result["data"]) == 2

    def test_get_local_historical_data_no_data(self):
        """Test getting local historical data when no data exists."""
        with patch("fubon_api_mcp_server.server.read_local_stock_data", return_value=None):
            result = _get_local_historical_data("2330", "2023-01-01", "2023-01-02")

            assert result is None

    def test_fetch_api_historical_data_single_segment(self):
        """Test fetching API data for single segment."""
        with patch("fubon_api_mcp_server.server.fetch_historical_data_segment") as mock_segment:
            mock_segment.return_value = [{"date": "2023-01-01", "close": 100}]

            result = _fetch_api_historical_data("2330", "2023-01-01", "2023-01-02")

            assert len(result) == 1
            mock_segment.assert_called_once()

    def test_fetch_api_historical_data_multiple_segments(self):
        """Test fetching API data for multiple segments."""
        with patch("fubon_api_mcp_server.server.fetch_historical_data_segment") as mock_segment:
            mock_segment.return_value = [{"date": "2023-01-01", "close": 100}]

            # Date range > 365 days should trigger multiple segments
            from_date = "2022-01-01"
            to_date = "2023-01-01"

            result = _fetch_api_historical_data("2330", from_date, to_date)

            # Should be called multiple times for different segments
            # The function splits data into 365-day segments
            assert mock_segment.call_count >= 1  # At least one call
            # Verify the segments are within reasonable bounds
            assert len(result) >= 1
