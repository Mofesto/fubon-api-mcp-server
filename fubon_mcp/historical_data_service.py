"""
Historical data service module for Fubon API MCP Server.

This module contains MCP tools for retrieving and managing historical
stock data, with local caching capabilities.
"""

from typing import Any, Dict, Optional

import pandas as pd

from .config import mcp
from .data_handler import fetch_historical_data_segment, process_historical_data, read_local_stock_data, save_to_local_csv
from .models import HistoricalCandlesArgs

# =============================================================================
# Historical Data Helper Functions
# =============================================================================


def _get_local_historical_data(symbol: str, from_date: str, to_date: str) -> Optional[Dict[str, Any]]:
    """Get historical data from local cache"""
    local_data = read_local_stock_data(symbol)
    if local_data is None:
        return None

    df = local_data
    mask = (df["date"] >= from_date) & (df["date"] <= to_date)
    df = df[mask]

    if df.empty:
        return None

    df = process_historical_data(df)
    return {
        "status": "success",
        "data": df.to_dict("records"),
        "message": f"Successfully retrieved {symbol} data from local cache for {from_date} to {to_date}",
    }


def _fetch_api_historical_data(symbol: str, from_date: str, to_date: str) -> list:
    """Fetch historical data from API"""
    from_datetime = pd.to_datetime(from_date)
    to_datetime = pd.to_datetime(to_date)
    date_diff = (to_datetime - from_datetime).days

    all_data = []

    if date_diff > 365:
        # Fetch data in segments
        current_from = from_datetime
        while current_from < to_datetime:
            current_to = min(current_from + pd.Timedelta(days=365), to_datetime)
            segment_data = fetch_historical_data_segment(
                symbol, current_from.strftime("%Y-%m-%d"), current_to.strftime("%Y-%m-%d")
            )
            all_data.extend(segment_data)
            current_from = current_to + pd.Timedelta(days=1)
    else:
        # Fetch data directly
        all_data = fetch_historical_data_segment(symbol, from_date, to_date)

    return all_data


# =============================================================================
# MCP Historical Data Tools
# =============================================================================


@mcp.tool()
def historical_candles(args: Dict) -> Dict:
    """
    Get historical data, prioritizing local data, then API if not available

    Args:
        symbol (str): Stock symbol, e.g., '2330', '00878'
        from_date (str): Start date, format: YYYY-MM-DD
        to_date (str): End date, format: YYYY-MM-DD
    """
    try:
        # Validate using HistoricalCandlesArgs
        validated_args = HistoricalCandlesArgs(**args)
        symbol = validated_args.symbol
        from_date = validated_args.from_date
        to_date = validated_args.to_date

        # Try to get from local data first
        local_result = _get_local_historical_data(symbol, from_date, to_date)
        if local_result:
            return local_result

        # If no local data, fetch from API
        api_data = _fetch_api_historical_data(symbol, from_date, to_date)
        if api_data:
            # Process and save data
            df = pd.DataFrame(api_data)
            df = process_historical_data(df)
            save_to_local_csv(symbol, api_data)
            return {
                "status": "success",
                "data": df.to_dict("records"),
                "message": f"Successfully retrieved {symbol} data from API for {from_date} to {to_date}",
            }

        return {"status": "error", "data": [], "message": f"Unable to retrieve {symbol} historical data"}

    except Exception as e:
        return {"status": "error", "data": [], "message": f"Error retrieving data: {str(e)}"}
