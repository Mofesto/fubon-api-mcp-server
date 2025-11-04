"""
Unit tests for historical_data_service.py module.
"""

from unittest.mock import Mock, patch

import pandas as pd

from fubon_mcp.historical_data_service import _fetch_api_historical_data, _get_local_historical_data, historical_candles


class TestGetLocalHistoricalData:
    """Test _get_local_historical_data function."""

    @patch("fubon_mcp.historical_data_service.read_local_stock_data")
    @patch("fubon_mcp.historical_data_service.process_historical_data")
    def test_get_local_historical_data_success(self, mock_process, mock_read):
        """Test successful local data retrieval."""
        mock_df = pd.DataFrame(
            {"date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]), "close": [100.0, 101.0, 102.0]}
        )
        mock_read.return_value = mock_df

        mock_processed_df = Mock()
        mock_processed_df.to_dict.return_value = [{"date": "2023-01-01", "close": 100.0}]
        mock_process.return_value = mock_processed_df

        result = _get_local_historical_data("2330", "2023-01-01", "2023-01-02")
        assert result is not None
        assert result["status"] == "success"
        assert "Successfully retrieved 2330 data from local cache" in result["message"]

    @patch("fubon_mcp.historical_data_service.read_local_stock_data")
    def test_get_local_historical_data_no_data(self, mock_read):
        """Test when no local data is available."""
        mock_read.return_value = None

        result = _get_local_historical_data("2330", "2023-01-01", "2023-01-02")
        assert result is None

    @patch("fubon_mcp.historical_data_service.read_local_stock_data")
    def test_get_local_historical_data_empty_filtered(self, mock_read):
        """Test when local data exists but date filter returns empty."""
        mock_df = pd.DataFrame({"date": pd.to_datetime(["2023-01-01"]), "close": [100.0]})
        mock_read.return_value = mock_df

        result = _get_local_historical_data("2330", "2023-02-01", "2023-02-02")
        assert result is None


class TestFetchApiHistoricalData:
    """Test _fetch_api_historical_data function."""

    @patch("fubon_mcp.historical_data_service.fetch_historical_data_segment")
    def test_fetch_api_historical_data_short_period(self, mock_fetch):
        """Test API data fetching for short period."""
        mock_fetch.return_value = [{"date": "2023-01-01", "close": 100.0}]

        result = _fetch_api_historical_data("2330", "2023-01-01", "2023-01-02")
        assert len(result) == 1
        mock_fetch.assert_called_once_with("2330", "2023-01-01", "2023-01-02")

    @patch("fubon_mcp.historical_data_service.fetch_historical_data_segment")
    def test_fetch_api_historical_data_long_period(self, mock_fetch):
        """Test API data fetching for long period (segmented)."""
        # Mock segment returns
        mock_fetch.side_effect = [[{"date": "2023-01-01", "close": 100.0}], [{"date": "2024-01-01", "close": 110.0}]]

        result = _fetch_api_historical_data("2330", "2023-01-01", "2024-06-01")
        assert len(result) == 2
        assert mock_fetch.call_count == 2


class TestHistoricalCandles:
    """Test historical_candles function."""

    @patch("fubon_mcp.historical_data_service._get_local_historical_data")
    def test_historical_candles_from_cache(self, mock_local):
        """Test historical candles retrieval from local cache."""
        mock_local.return_value = {
            "status": "success",
            "data": [{"date": "2023-01-01", "close": 100.0}],
            "message": "From cache",
        }

        result = historical_candles({"symbol": "2330", "from_date": "2023-01-01", "to_date": "2023-01-02"})
        assert result["status"] == "success"
        assert result["data"] == [{"date": "2023-01-01", "close": 100.0}]

    @patch("fubon_mcp.historical_data_service._get_local_historical_data")
    @patch("fubon_mcp.historical_data_service._fetch_api_historical_data")
    @patch("fubon_mcp.historical_data_service.save_to_local_csv")
    @patch("fubon_mcp.historical_data_service.process_historical_data")
    def test_historical_candles_from_api(self, mock_process, mock_save, mock_api, mock_local):
        """Test historical candles retrieval from API."""
        mock_local.return_value = None
        mock_api.return_value = [{"date": "2023-01-01", "close": 100.0}]

        mock_df = Mock()
        mock_df.to_dict.return_value = [{"date": "2023-01-01", "close": 100.0, "vol_value": 10000.0}]
        mock_process.return_value = mock_df

        result = historical_candles({"symbol": "2330", "from_date": "2023-01-01", "to_date": "2023-01-02"})
        assert result["status"] == "success"
        assert "Successfully retrieved 2330 data from API" in result["message"]
        mock_save.assert_called_once()

    @patch("fubon_mcp.historical_data_service._get_local_historical_data")
    @patch("fubon_mcp.historical_data_service._fetch_api_historical_data")
    def test_historical_candles_no_data(self, mock_api, mock_local):
        """Test historical candles when no data is available."""
        mock_local.return_value = None
        mock_api.return_value = []

        result = historical_candles({"symbol": "2330", "from_date": "2023-01-01", "to_date": "2023-01-02"})
        assert result["status"] == "error"
        assert result["data"] == []
        assert "Unable to retrieve 2330 historical data" in result["message"]

    def test_historical_candles_invalid_args(self):
        """Test historical candles with invalid arguments."""
        result = historical_candles({})
        assert result["status"] == "error"
        assert result["data"] == []
        assert "Error retrieving data" in result["message"]

    def test_historical_candles_exception(self):
        """Test historical candles with exception."""
        result = historical_candles({"symbol": "", "from_date": "invalid", "to_date": "2023-01-01"})
        assert result["status"] == "error"
        assert result["data"] == []
        assert "Error retrieving data" in result["message"]
