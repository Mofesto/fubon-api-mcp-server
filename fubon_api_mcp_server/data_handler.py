"""
Data handling module for Fubon API MCP Server.

This module contains functions for processing and managing local
stock data storage, including historical data retrieval and caching.
"""

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from . import config
from .config import BASE_DATA_DIR

# =============================================================================
# Local Data Storage Functions
# =============================================================================


def read_local_stock_data(stock_code: str) -> Optional[pd.DataFrame]:
    """
    Read locally cached stock historical data.

    Reads historical stock data from local CSV file. If the file doesn't exist,
    returns None. Data is sorted in descending order (newest first).

    Args:
        stock_code (str): Stock code used as filename

    Returns:
        pandas.DataFrame or None: Stock historical data DataFrame with date, etc. columns
    """
    try:
        file_path = BASE_DATA_DIR / f"{stock_code}.csv"
        if not file_path.exists():
            return None

        df = pd.read_csv(file_path)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(by="date", ascending=False)
        return df
    except Exception as e:
        print(f"Error reading CSV file: {str(e)}", file=sys.stderr)
        return None


def save_to_local_csv(symbol: str, new_data: List[Dict[str, Any]]) -> None:
    """
    Save new stock data to local CSV file, avoiding duplicates.

    Uses atomic write method (write to temp file then move) to ensure data integrity.
    If file already exists, merges old and new data and removes duplicates.

    Args:
        symbol (str): Stock code used as filename
        new_data (list): List of new stock data dictionaries
    """
    try:
        file_path = BASE_DATA_DIR / f"{symbol}.csv"
        new_df = pd.DataFrame(new_data)
        new_df["date"] = pd.to_datetime(new_df["date"])

        # Create temp file for atomic write
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp_file:
            temp_path = Path(temp_file.name)

            try:
                if file_path.exists():
                    # Read existing data and merge
                    existing_df = pd.read_csv(file_path)
                    existing_df["date"] = pd.to_datetime(existing_df["date"])

                    # Merge data and remove duplicates (by date)
                    combined_df = pd.concat([existing_df, new_df])
                    combined_df = combined_df.drop_duplicates(subset=["date"], keep="last")
                    combined_df = combined_df.sort_values(by="date", ascending=False)
                else:
                    combined_df = new_df.sort_values(by="date", ascending=False)

                # Write merged data to temp file
                combined_df.to_csv(temp_path, index=False)

                # Atomically replace original file
                shutil.move(str(temp_path), str(file_path))
                print(f"Successfully saved data to {file_path}", file=sys.stderr)

            except Exception as e:
                # Ensure temp file is cleaned up
                if temp_path.exists():
                    temp_path.unlink()
                raise e

    except Exception as e:
        print(f"Error saving CSV file: {str(e)}", file=sys.stderr)


# =============================================================================
# Historical Data Processing Functions
# =============================================================================


def process_historical_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process historical data by adding calculated columns.

    Args:
        df (pd.DataFrame): Raw data

    Returns:
        pd.DataFrame: Processed data with additional columns
    """
    df = df.sort_values(by="date", ascending=False)
    # Add more info columns
    df["vol_value"] = df["close"] * df["volume"]  # Trading value
    df["price_change"] = df["close"] - df["open"]  # Price change
    df["change_ratio"] = (df["close"] - df["open"]) / df["open"] * 100  # Change ratio
    return df


def fetch_historical_data_segment(symbol: str, from_date: str, to_date: str) -> List[Dict[str, Any]]:
    """
    Fetch a segment of historical data.

    Args:
        symbol (str): Stock code
        from_date (str): Start date
        to_date (str): End date

    Returns:
        list: Data list, returns empty list if failed
    """
    try:
        # Check if reststock is initialized
        if config.reststock is None:
            print("REST client not initialized", file=sys.stderr)
            return []

        params = {"symbol": symbol, "from": from_date, "to": to_date}
        print(f"Fetching {symbol} data from {params['from']} to {params['to']}...", file=sys.stderr)
        response = config.reststock.historical.candles(**params)
        print(f"API response: {response}", file=sys.stderr)

        if isinstance(response, dict):
            if "data" in response and response["data"]:
                segment_data = response["data"]
                if isinstance(segment_data, list):
                    print(f"Successfully fetched {len(segment_data)} records", file=sys.stderr)
                    return segment_data
                else:
                    print(f"API response data is not a list: {segment_data}", file=sys.stderr)
            else:
                print(f"API response has no data: {response}", file=sys.stderr)
        else:
            print(f"API response format error: {response}", file=sys.stderr)
    except Exception as segment_error:
        print(f"Error fetching segment data: {str(segment_error)}", file=sys.stderr)

    return []
