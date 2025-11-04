"""
Market data service module for Fubon API MCP Server.

This module contains MCP tools for retrieving market data including
real-time quotes, historical data, intraday data, and snapshots.
"""

from typing import Any, Dict

from .config import mcp, reststock, sdk
from . import config
from .models import (
    GetHistoricalStatsArgs,
    GetIntradayCandlesArgs,
    GetIntradayQuoteArgs,
    GetIntradayTickerArgs,
    GetIntradayTickersArgs,
    GetIntradayTradesArgs,
    GetIntradayVolumesArgs,
    GetRealtimeQuotesArgs,
    GetSnapshotActivesArgs,
    GetSnapshotMoversArgs,
    GetSnapshotQuotesArgs,
)

# =============================================================================
# MCP Market Data Tools
# =============================================================================


@mcp.tool()
def get_realtime_quotes(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get real-time quotes

    Args:
        symbol (str): Stock symbol
    """
    try:
        validated_args = GetRealtimeQuotesArgs(**args)
        symbol = validated_args.symbol

        # Check if SDK is initialized
        if config.sdk is None:
            return {"status": "error", "data": None, "message": "SDK not initialized"}

        # Use realtime API
        quotes = config.sdk.marketdata.realtime.quote(symbol)
        return {"status": "success", "data": quotes, "message": f"Successfully retrieved real-time quotes for {symbol}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get real-time quotes: {str(e)}"}


@mcp.tool()
def get_intraday_tickers(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock/index list (query by conditions)

    Args:
        market (str): Market type, e.g., TSE, OTC
    """
    try:
        validated_args = GetIntradayTickersArgs(**args)
        market = validated_args.market

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.intraday.tickers(market=market)
        return {"status": "success", "data": result, "message": f"Successfully retrieved stock list for {market} market"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get stock list: {str(e)}"}


@mcp.tool()
def get_intraday_ticker(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock basic information (query by symbol)

    Args:
        symbol (str): Stock symbol
    """
    try:
        validated_args = GetIntradayTickerArgs(**args)
        symbol = validated_args.symbol

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.intraday.ticker(symbol)
        return {"status": "success", "data": result, "message": f"Successfully retrieved basic info for {symbol}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get basic info: {str(e)}"}


@mcp.tool()
def get_intraday_quote(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock real-time quote (query by symbol)

    Args:
        symbol (str): Stock symbol
    """
    try:
        validated_args = GetIntradayQuoteArgs(**args)
        symbol = validated_args.symbol

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.intraday.quote(symbol=symbol)
        return {"status": "success", "data": result, "message": f"Successfully retrieved real-time quote for {symbol}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get real-time quote: {str(e)}"}


@mcp.tool()
def get_intraday_candles(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock price K-line (query by symbol)

    Args:
        symbol (str): Stock symbol
    """
    try:
        validated_args = GetIntradayCandlesArgs(**args)
        symbol = validated_args.symbol

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.intraday.candles(symbol)
        return {"status": "success", "data": result, "message": f"Successfully retrieved intraday K-line for {symbol}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get intraday K-line: {str(e)}"}


@mcp.tool()
def get_intraday_trades(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock trade details (query by symbol)

    Args:
        symbol (str): Stock symbol
    """
    try:
        validated_args = GetIntradayTradesArgs(**args)
        symbol = validated_args.symbol

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.intraday.trades(symbol)
        return {"status": "success", "data": result, "message": f"Successfully retrieved trade details for {symbol}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get trade details: {str(e)}"}


@mcp.tool()
def get_intraday_volumes(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock price-volume table (query by symbol)

    Args:
        symbol (str): Stock symbol
    """
    try:
        validated_args = GetIntradayVolumesArgs(**args)
        symbol = validated_args.symbol

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.intraday.volumes(symbol)
        return {"status": "success", "data": result, "message": f"Successfully retrieved price-volume table for {symbol}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get price-volume table: {str(e)}"}


@mcp.tool()
def get_snapshot_quotes(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock market snapshot (by market type)

    Args:
        market (str): Market type, e.g., TSE, OTC
    """
    try:
        validated_args = GetSnapshotQuotesArgs(**args)
        market = validated_args.market

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.snapshot.quotes(market)
        return {"status": "success", "data": result, "message": f"Successfully retrieved market snapshot for {market}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get market snapshot: {str(e)}"}


@mcp.tool()
def get_snapshot_movers(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock price change rankings (by market type)

    Args:
        market (str): Market type, e.g., TSE, OTC
    """
    try:
        validated_args = GetSnapshotMoversArgs(**args)
        market = validated_args.market

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.snapshot.movers(market)
        return {"status": "success", "data": result, "message": f"Successfully retrieved price change rankings for {market}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get price change rankings: {str(e)}"}


@mcp.tool()
def get_snapshot_actives(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get stock trading volume rankings (by market type)

    Args:
        market (str): Market type, e.g., TSE, OTC
    """
    try:
        validated_args = GetSnapshotActivesArgs(**args)
        market = validated_args.market

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.snapshot.actives(market=market, trade="volume")

        # API returns dictionary format with 'data' key
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            if isinstance(data, list):
                # Limit to first 50 records to avoid large responses
                limited_data = data[:50] if len(data) > 50 else data
                return {
                    "status": "success",
                    "data": limited_data,
                    "total_count": len(data),
                    "returned_count": len(limited_data),
                    "message": f"Successfully retrieved trading volume rankings for {market} (showing first {len(limited_data)} of {len(data)} records)",
                }
            else:
                return {"status": "error", "data": None, "message": "API returned 'data' field that is not a list"}
        else:
            # If not expected dictionary format
            return {
                "status": "success",
                "data": result,
                "message": f"Successfully retrieved trading volume rankings for {market}",
            }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get trading volume rankings: {str(e)}"}


@mcp.tool()
def get_historical_stats(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get 52-week stock price data (query by symbol)

    Args:
        symbol (str): Stock symbol
    """
    try:
        validated_args = GetHistoricalStatsArgs(**args)
        symbol = validated_args.symbol

        # Check if reststock is initialized
        if config.reststock is None:
            return {"status": "error", "data": None, "message": "REST client not initialized"}

        result = config.reststock.historical.stats(symbol)
        return {"status": "success", "data": result, "message": f"Successfully retrieved 52-week data for {symbol}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get historical stats: {str(e)}"}
