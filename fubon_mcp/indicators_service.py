"""
Quantitative indicators service module for Fubon API MCP Server.

This module provides technical analysis indicators for quantitative trading,
including moving averages, RSI, MACD, and other common indicators.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from .config import mcp
from .data_handler import read_local_stock_data

# =============================================================================
# Technical Indicator Calculations
# =============================================================================


def calculate_sma(data: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
    """
    Calculate Simple Moving Average (SMA)

    Args:
        data (pd.DataFrame): Historical price data
        period (int): Period for SMA calculation
        column (str): Column to calculate SMA on

    Returns:
        pd.Series: SMA values
    """
    return data[column].rolling(window=period).mean()


def calculate_ema(data: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA)

    Args:
        data (pd.DataFrame): Historical price data
        period (int): Period for EMA calculation
        column (str): Column to calculate EMA on

    Returns:
        pd.Series: EMA values
    """
    if len(data) < period:
        # Return NaN series if insufficient data
        return pd.Series([pd.NA] * len(data), index=data.index)

    return data[column].ewm(span=period, adjust=False).mean()


def calculate_rsi(data: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """
    Calculate Relative Strength Index (RSI)

    Args:
        data (pd.DataFrame): Historical price data
        period (int): Period for RSI calculation
        column (str): Column to calculate RSI on

    Returns:
        pd.Series: RSI values (0-100)
    """
    delta = data[column].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()  # type: ignore[operator]
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()  # type: ignore[operator]
    rs = gain / loss
    rsi: pd.Series = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(
    data: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, column: str = "close"
) -> Dict[str, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence)

    Args:
        data (pd.DataFrame): Historical price data
        fast_period (int): Fast EMA period
        slow_period (int): Slow EMA period
        signal_period (int): Signal line EMA period
        column (str): Column to calculate MACD on

    Returns:
        dict: MACD line, signal line, and histogram
    """
    if len(data) < slow_period:
        # Return NaN series if insufficient data
        nan_series = pd.Series([pd.NA] * len(data), index=data.index)
        return {"macd": nan_series, "signal": nan_series, "histogram": nan_series}

    fast_ema = calculate_ema(data, fast_period, column)
    slow_ema = calculate_ema(data, slow_period, column)
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def calculate_bollinger_bands(
    data: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = "close"
) -> Dict[str, pd.Series]:
    """
    Calculate Bollinger Bands

    Args:
        data (pd.DataFrame): Historical price data
        period (int): Period for moving average
        std_dev (float): Standard deviation multiplier
        column (str): Column to calculate BB on

    Returns:
        dict: Upper band, middle band (SMA), lower band
    """
    sma = calculate_sma(data, period, column)
    std = data[column].rolling(window=period).std()

    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)

    return {"upper": upper_band, "middle": sma, "lower": lower_band}


def calculate_stochastic_oscillator(data: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
    """
    Calculate Stochastic Oscillator

    Args:
        data (pd.DataFrame): Historical price data
        k_period (int): Period for %K calculation
        d_period (int): Period for %D calculation (SMA of %K)

    Returns:
        dict: %K and %D values
    """
    lowest_low = data["low"].rolling(window=k_period).min()
    highest_high = data["high"].rolling(window=k_period).max()

    k_percent = 100 * ((data["close"] - lowest_low) / (highest_high - lowest_low))
    d_percent = k_percent.rolling(window=d_period).mean()

    return {"%K": k_percent, "%D": d_percent}


def calculate_volume_indicators(data: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Calculate volume-based indicators

    Args:
        data (pd.DataFrame): Historical price data with volume column

    Returns:
        dict: Volume indicators (volume SMA, volume ratio, etc.)
    """
    volume_sma_20 = data["volume"].rolling(window=20).mean()
    volume_ratio = data["volume"] / volume_sma_20

    return {"volume_sma": volume_sma_20, "volume_ratio": volume_ratio}


# =============================================================================
# Indicator Analysis Functions
# =============================================================================


def analyze_trend(data: pd.DataFrame, short_period: int = 20, long_period: int = 50) -> Dict:
    """
    Analyze price trend using moving averages

    Args:
        data (pd.DataFrame): Historical price data
        short_period (int): Short-term MA period
        long_period (int): Long-term MA period

    Returns:
        dict: Trend analysis results
    """
    short_ma = calculate_sma(data, short_period)
    long_ma = calculate_ema(data, long_period)

    latest_short = short_ma.iloc[-1] if not short_ma.empty else None
    latest_long = long_ma.iloc[-1] if not long_ma.empty else None

    if pd.notna(latest_short) and pd.notna(latest_long):
        if latest_short > latest_long:
            trend = "bullish"
            strength = (latest_short - latest_long) / latest_long * 100
        else:
            trend = "bearish"
            strength = (latest_long - latest_short) / latest_long * 100
    else:
        trend = "insufficient_data"
        strength = 0

    return {
        "trend_direction": trend,
        "trend_strength": strength,
        "support_resistance": {"short_ma": latest_short, "long_ma": latest_long},
    }


def analyze_momentum(data: pd.DataFrame) -> Dict:
    """
    Analyze price momentum using RSI and MACD

    Args:
        data (pd.DataFrame): Historical price data

    Returns:
        dict: Momentum analysis results
    """
    rsi = calculate_rsi(data)
    macd_data = calculate_macd(data)

    latest_rsi = rsi.iloc[-1] if not rsi.empty else None
    latest_macd = macd_data["macd"].iloc[-1] if not macd_data["macd"].empty else None
    latest_signal = macd_data["signal"].iloc[-1] if not macd_data["signal"].empty else None

    # RSI analysis
    if latest_rsi:
        if latest_rsi > 70:
            rsi_signal = "overbought"
        elif latest_rsi < 30:
            rsi_signal = "oversold"
        else:
            rsi_signal = "neutral"
    else:
        rsi_signal = "insufficient_data"

    # MACD analysis
    if pd.notna(latest_macd) and pd.notna(latest_signal):
        if latest_macd > latest_signal:
            macd_signal = "bullish"
        else:
            macd_signal = "bearish"
    else:
        macd_signal = "insufficient_data"

    # Calculate momentum score (simplified)
    momentum_score = 0
    if rsi_signal == "oversold":
        momentum_score += 1
    elif rsi_signal == "overbought":
        momentum_score -= 1

    if macd_signal == "bullish":
        momentum_score += 1
    elif macd_signal == "bearish":
        momentum_score -= 1

    return {
        "momentum_score": momentum_score,
        "momentum_signals": [rsi_signal, macd_signal],
        "divergence_signals": [],  # Placeholder for future implementation
        "rsi_value": latest_rsi,
        "rsi_signal": rsi_signal,
        "macd_value": latest_macd,
        "macd_signal": macd_signal,
        "signal_value": latest_signal,
    }


# =============================================================================
# MCP Indicator Tools
# =============================================================================


@mcp.tool()
def calculate_technical_indicators(
    symbol: str, indicators: Optional[List[str]] = None, periods: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """# noqa: C901
    Calculate technical indicators for a stock

    Args:
        symbol (str): Stock symbol
        indicators (List[str]): List of indicators to calculate. Options:
            ['sma', 'ema', 'rsi', 'macd', 'bb', 'stoch', 'volume']
        periods (Dict): Custom periods for indicators, e.g., {'sma': 20, 'rsi': 14}

    Returns:
        dict: Calculated indicators with latest values
    """
    try:
        # Set default indicators if none specified
        if indicators is None:
            indicators = ["sma", "ema", "rsi", "macd"]

        # Set default periods
        default_periods = {
            "sma": 20,
            "ema": 20,
            "rsi": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "bb": 20,
            "stoch_k": 14,
            "stoch_d": 3,
        }
        if periods:
            default_periods.update(periods)

        # Get historical data
        data = read_local_stock_data(symbol)
        if data is None:
            return {"status": "error", "data": None, "message": f"No historical data found for {symbol}"}

        # Ensure we have enough data
        if len(data) < 50:
            return {"status": "error", "data": None, "message": f"Insufficient data for {symbol} (need at least 50 records)"}

        results: Dict[str, Any] = {}
        latest_values = {}

        # Calculate requested indicators
        for indicator in indicators:
            try:
                if indicator == "sma":
                    sma = calculate_sma(data, default_periods["sma"])
                    results["sma"] = sma.fillna(0).tolist()
                    latest_values["sma"] = sma.iloc[-1] if not sma.empty else None

                elif indicator == "ema":
                    ema = calculate_ema(data, default_periods["ema"])
                    results["ema"] = ema.fillna(0).tolist()
                    latest_values["ema"] = ema.iloc[-1] if not ema.empty else None

                elif indicator == "rsi":
                    rsi = calculate_rsi(data, default_periods["rsi"])
                    results["rsi"] = rsi.fillna(50).tolist()  # Neutral RSI value for NaN
                    latest_values["rsi"] = rsi.iloc[-1] if not rsi.empty else None

                elif indicator == "macd":
                    macd_data = calculate_macd(
                        data, default_periods["macd_fast"], default_periods["macd_slow"], default_periods["macd_signal"]
                    )
                    results["macd"] = {
                        "macd": macd_data["macd"].fillna(0).tolist(),
                        "signal": macd_data["signal"].fillna(0).tolist(),
                        "histogram": macd_data["histogram"].fillna(0).tolist(),
                    }
                    latest_values["macd"] = {
                        "macd": macd_data["macd"].iloc[-1] if not macd_data["macd"].empty else None,
                        "signal": macd_data["signal"].iloc[-1] if not macd_data["signal"].empty else None,
                        "histogram": macd_data["histogram"].iloc[-1] if not macd_data["histogram"].empty else None,
                    }

                elif indicator == "bb":
                    bb_data = calculate_bollinger_bands(data, default_periods["bb"])
                    results["bollinger_bands"] = {
                        "upper": bb_data["upper"].fillna(0).tolist(),
                        "middle": bb_data["middle"].fillna(0).tolist(),
                        "lower": bb_data["lower"].fillna(0).tolist(),
                    }
                    latest_values["bollinger_bands"] = {
                        "upper": bb_data["upper"].iloc[-1] if not bb_data["upper"].empty else None,
                        "middle": bb_data["middle"].iloc[-1] if not bb_data["middle"].empty else None,
                        "lower": bb_data["lower"].iloc[-1] if not bb_data["lower"].empty else None,
                    }

                elif indicator == "stoch":
                    stoch_data = calculate_stochastic_oscillator(data, default_periods["stoch_k"], default_periods["stoch_d"])
                    results["stochastic"] = {
                        "%K": stoch_data["%K"].fillna(50).tolist(),
                        "%D": stoch_data["%D"].fillna(50).tolist(),
                    }
                    latest_values["stochastic"] = {
                        "%K": stoch_data["%K"].iloc[-1] if not stoch_data["%K"].empty else None,
                        "%D": stoch_data["%D"].iloc[-1] if not stoch_data["%D"].empty else None,
                    }

                elif indicator == "volume":
                    volume_data = calculate_volume_indicators(data)
                    results["volume_indicators"] = {
                        "volume_sma": volume_data["volume_sma"].fillna(0).tolist(),
                        "volume_ratio": volume_data["volume_ratio"].fillna(1).tolist(),
                    }
                    latest_values["volume_indicators"] = {
                        "volume_sma": (volume_data["volume_sma"].iloc[-1] if not volume_data["volume_sma"].empty else None),
                        "volume_ratio": (
                            volume_data["volume_ratio"].iloc[-1] if not volume_data["volume_ratio"].empty else None
                        ),
                    }

            except Exception as e:
                results[indicator] = f"Error calculating {indicator}: {str(e)}"
                latest_values[indicator] = None

        return {
            "status": "success",
            "data": {"symbol": symbol, "indicators": results, "latest_values": latest_values, "data_points": len(data)},
            "message": f"Successfully calculated {len(indicators)} indicators for {symbol}",
        }

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to calculate indicators: {str(e)}"}


@mcp.tool()
def analyze_stock_trend(symbol: str, analysis_type: str = "comprehensive") -> Dict:
    """# noqa: C901
    Perform comprehensive trend and momentum analysis for a stock

    Args:
        symbol (str): Stock symbol
        analysis_type (str): Type of analysis - "trend", "momentum", or "comprehensive"

    Returns:
        dict: Analysis results with signals and recommendations
    """
    try:
        # Get historical data
        data = read_local_stock_data(symbol)
        if data is None:
            return {"status": "error", "data": None, "message": f"No historical data found for {symbol}"}

        if len(data) < 100:
            return {
                "status": "error",
                "data": None,
                "message": "Insufficient data for analysis (need at least 100 records)",
            }

        results: Dict[str, Any] = {
            "symbol": symbol,
            "analysis_type": analysis_type,
            "current_price": data["close"].iloc[-1] if not data.empty else None,
        }

        if analysis_type in ["trend", "comprehensive"]:
            trend_analysis = analyze_trend(data)
            results["trend_analysis"] = trend_analysis

        if analysis_type in ["momentum", "comprehensive"]:
            momentum_analysis = analyze_momentum(data)
            results["momentum_analysis"] = momentum_analysis

        # Generate trading signals based on analysis
        signals = []

        if analysis_type in ["trend", "comprehensive"]:
            trend_direction = results["trend_analysis"]["trend_direction"]
            if trend_direction == "bullish":
                signals.append("BUY_SIGNAL: Short-term MA above long-term MA")
            elif trend_direction == "bearish":
                signals.append("SELL_SIGNAL: Short-term MA below long-term MA")

        if analysis_type in ["momentum", "comprehensive"]:
            rsi_signal = results["momentum_analysis"]["rsi_signal"]
            macd_signal = results["momentum_analysis"]["macd_signal"]

            if rsi_signal == "oversold":
                signals.append("BUY_SIGNAL: RSI indicates oversold condition")
            elif rsi_signal == "overbought":
                signals.append("SELL_SIGNAL: RSI indicates overbought condition")

            if macd_signal == "bullish":
                signals.append("BUY_SIGNAL: MACD shows bullish momentum")
            elif macd_signal == "bearish":
                signals.append("SELL_SIGNAL: MACD shows bearish momentum")

        results["trading_signals"] = signals

        # Overall recommendation
        buy_signals = len([s for s in signals if "BUY_SIGNAL" in s])
        sell_signals = len([s for s in signals if "SELL_SIGNAL" in s])

        if buy_signals > sell_signals:
            recommendation = "BUY"
        elif sell_signals > buy_signals:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"

        results["recommendation"] = recommendation
        results["signal_summary"] = f"{buy_signals} buy signals, {sell_signals} sell signals"

        return {
            "status": "success",
            "data": results,
            "message": f"Successfully completed {analysis_type} analysis for {symbol}",
        }

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to analyze stock trend: {str(e)}"}
