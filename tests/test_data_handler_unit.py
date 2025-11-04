"""
Unit tests for data_handler.py module.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from fubon_mcp.data_handler import (
    fetch_historical_data_segment,
    process_historical_data,
    read_local_stock_data,
    save_to_local_csv,
)


class TestReadLocalStockData:
    """Test reading local stock data."""

    @patch("fubon_mcp.data_handler.BASE_DATA_DIR", Path(tempfile.gettempdir()) / "test_data")
    def test_read_local_stock_data_success(self):
        """Test successful reading of local stock data."""
        # Create test data directory
        test_dir = Path(tempfile.gettempdir()) / "test_data"
        test_dir.mkdir(exist_ok=True)

        # Create test CSV file
        test_file = test_dir / "2330.csv"
        test_data = pd.DataFrame(
            {"date": ["2023-01-01", "2023-01-02"], "close": [100.0, 101.0], "open": [99.0, 100.0], "volume": [1000, 1100]}
        )
        test_data.to_csv(test_file, index=False)

        try:
            result = read_local_stock_data("2330")
            assert result is not None
            assert len(result) == 2
            # Should be sorted descending by date
            assert result.iloc[0]["date"] > result.iloc[1]["date"]
        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
            if test_dir.exists():
                test_dir.rmdir()

    @patch("fubon_mcp.data_handler.BASE_DATA_DIR", Path(tempfile.gettempdir()) / "test_data")
    def test_read_local_stock_data_file_not_exists(self):
        """Test reading when file doesn't exist."""
        result = read_local_stock_data("NONEXISTENT")
        assert result is None

    @patch("fubon_mcp.data_handler.BASE_DATA_DIR", Path(tempfile.gettempdir()) / "test_data")
    def test_read_local_stock_data_corrupted_file(self):
        """Test reading corrupted CSV file."""
        test_dir = Path(tempfile.gettempdir()) / "test_data"
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "corrupted.csv"

        # Create corrupted CSV
        with open(test_file, "w") as f:
            f.write("invalid,csv,data\n")

        try:
            result = read_local_stock_data("corrupted")
            assert result is None
        finally:
            if test_file.exists():
                test_file.unlink()
            if test_dir.exists():
                test_dir.rmdir()


class TestSaveToLocalCsv:
    """Test saving data to local CSV."""

    @patch("fubon_mcp.data_handler.BASE_DATA_DIR", Path(tempfile.gettempdir()) / "test_data")
    def test_save_to_local_csv_new_file(self):
        """Test saving to a new CSV file."""
        test_dir = Path(tempfile.gettempdir()) / "test_data"
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "2330.csv"

        new_data = [
            {"date": "2023-01-01", "close": 100.0, "open": 99.0, "volume": 1000},
            {"date": "2023-01-02", "close": 101.0, "open": 100.0, "volume": 1100},
        ]

        try:
            save_to_local_csv("2330", new_data)

            # Verify file was created and contains data
            assert test_file.exists()
            df = pd.read_csv(test_file)
            assert len(df) == 2
            assert df.iloc[0]["date"] == "2023-01-02"  # Should be sorted descending
        finally:
            if test_file.exists():
                test_file.unlink()
            if test_dir.exists():
                test_dir.rmdir()

    @patch("fubon_mcp.data_handler.BASE_DATA_DIR", Path(tempfile.gettempdir()) / "test_data")
    def test_save_to_local_csv_merge_existing(self):
        """Test merging with existing CSV file."""
        test_dir = Path(tempfile.gettempdir()) / "test_data"
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "2330.csv"

        # Create existing data
        existing_data = pd.DataFrame({"date": ["2023-01-01"], "close": [100.0], "open": [99.0], "volume": [1000]})
        existing_data.to_csv(test_file, index=False)

        # New data with one overlapping date
        new_data = [
            {"date": "2023-01-01", "close": 100.5, "open": 99.5, "volume": 1050},  # Updated
            {"date": "2023-01-02", "close": 101.0, "open": 100.0, "volume": 1100},  # New
        ]

        try:
            save_to_local_csv("2330", new_data)

            # Verify merged data
            df = pd.read_csv(test_file)
            assert len(df) == 2
            # Should have the updated data for 2023-01-01
            row_0101 = df[df["date"] == "2023-01-01"].iloc[0]
            assert row_0101["close"] == 100.5
        finally:
            if test_file.exists():
                test_file.unlink()
            if test_dir.exists():
                test_dir.rmdir()


class TestProcessHistoricalData:
    """Test historical data processing."""

    def test_process_historical_data(self):
        """Test processing historical data with calculated columns."""
        test_data = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
                "close": [100.0, 101.0],
                "open": [99.0, 100.0],
                "volume": [1000, 1100],
            }
        )

        result = process_historical_data(test_data)

        # Check that new columns were added
        assert "vol_value" in result.columns
        assert "price_change" in result.columns
        assert "change_ratio" in result.columns

        # Check calculations (after sorting by date descending, so first row is latest date)
        assert result.iloc[0]["vol_value"] == 101.0 * 1100  # close * volume for latest date
        assert result.iloc[0]["price_change"] == 101.0 - 100.0  # close - open for latest date
        assert result.iloc[0]["change_ratio"] == (101.0 - 100.0) / 100.0 * 100  # (close - open) / open * 100 for latest date

        # Check second row (earlier date)
        assert result.iloc[1]["vol_value"] == 100.0 * 1000  # close * volume for earlier date

        # Should be sorted descending by date
        assert result.iloc[0]["date"] > result.iloc[1]["date"]


class TestFetchHistoricalDataSegment:
    """Test fetching historical data segments."""

    @patch("fubon_mcp.data_handler.reststock")
    def test_fetch_historical_data_segment_success(self, mock_reststock):
        """Test successful data fetching."""
        mock_response = {"data": [{"date": "2023-01-01", "close": 100.0}, {"date": "2023-01-02", "close": 101.0}]}
        mock_reststock.historical.candles.return_value = mock_response

        result = fetch_historical_data_segment("2330", "2023-01-01", "2023-01-02")
        assert len(result) == 2
        assert result[0]["date"] == "2023-01-01"

    @patch("fubon_mcp.data_handler.reststock")
    def test_fetch_historical_data_segment_no_data(self, mock_reststock):
        """Test fetching when API returns no data."""
        mock_response = {"data": []}
        mock_reststock.historical.candles.return_value = mock_response

        result = fetch_historical_data_segment("2330", "2023-01-01", "2023-01-02")
        assert result == []

    @patch("fubon_mcp.data_handler.reststock")
    def test_fetch_historical_data_segment_exception(self, mock_reststock):
        """Test fetching when exception occurs."""
        mock_reststock.historical.candles.side_effect = Exception("API error")

        result = fetch_historical_data_segment("2330", "2023-01-01", "2023-01-02")
        assert result == []

    @patch("fubon_mcp.data_handler.reststock")
    def test_fetch_historical_data_segment_invalid_response(self, mock_reststock):
        """Test fetching with invalid API response format."""
        mock_reststock.historical.candles.return_value = "invalid response"

        result = fetch_historical_data_segment("2330", "2023-01-01", "2023-01-02")
        assert result == []
