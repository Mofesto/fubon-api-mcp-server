"""
Tests for indicators_service module.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fubon_api_mcp_server.indicators_service import (
    analyze_momentum,
    analyze_stock_trend,
    analyze_trend,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    calculate_stochastic_oscillator,
    calculate_technical_indicators,
    calculate_volume_indicators,
)


@pytest.fixture
def sample_price_data():
    """Create sample price data for testing"""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    data = pd.DataFrame(
        {
            "date": dates,
            "open": [100 + i * 0.5 for i in range(100)],
            "high": [102 + i * 0.5 for i in range(100)],
            "low": [98 + i * 0.5 for i in range(100)],
            "close": [100 + i * 0.5 for i in range(100)],
            "volume": [1000000 + i * 10000 for i in range(100)],
        }
    )
    return data


@pytest.fixture
def insufficient_data():
    """Create insufficient data for testing edge cases"""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    data = pd.DataFrame(
        {
            "date": dates,
            "open": [100, 101, 102, 103, 104],
            "high": [102, 103, 104, 105, 106],
            "low": [98, 99, 100, 101, 102],
            "close": [100, 101, 102, 103, 104],
            "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
        }
    )
    return data


# =============================================================================
# Calculation Function Tests
# =============================================================================


def test_calculate_sma_basic(sample_price_data):
    """Test simple moving average calculation"""
    result = calculate_sma(sample_price_data, period=20)
    assert isinstance(result, pd.Series)
    assert len(result) == len(sample_price_data)
    # First 19 values should be NaN
    assert pd.isna(result.iloc[0])
    # After period, should have valid values
    assert not pd.isna(result.iloc[-1])


def test_calculate_ema_basic(sample_price_data):
    """Test exponential moving average calculation"""
    result = calculate_ema(sample_price_data, period=20)
    assert isinstance(result, pd.Series)
    assert len(result) == len(sample_price_data)
    assert not pd.isna(result.iloc[-1])


def test_calculate_ema_insufficient_data(insufficient_data):
    """Test EMA with insufficient data"""
    result = calculate_ema(insufficient_data, period=20)
    assert isinstance(result, pd.Series)
    assert all(pd.isna(result))


def test_calculate_rsi_basic(sample_price_data):
    """Test RSI calculation"""
    result = calculate_rsi(sample_price_data, period=14)
    assert isinstance(result, pd.Series)
    assert len(result) == len(sample_price_data)
    # RSI should be between 0 and 100
    valid_values = result.dropna()
    assert all((valid_values >= 0) & (valid_values <= 100))


def test_calculate_macd_basic(sample_price_data):
    """Test MACD calculation"""
    result = calculate_macd(sample_price_data, fast_period=12, slow_period=26, signal_period=9)
    assert isinstance(result, dict)
    assert "macd" in result
    assert "signal" in result
    assert "histogram" in result
    assert len(result["macd"]) == len(sample_price_data)


def test_calculate_macd_insufficient_data(insufficient_data):
    """Test MACD with insufficient data"""
    result = calculate_macd(insufficient_data, fast_period=12, slow_period=26, signal_period=9)
    assert isinstance(result, dict)
    assert all(pd.isna(result["macd"]))
    assert all(pd.isna(result["signal"]))


def test_calculate_bollinger_bands_basic(sample_price_data):
    """Test Bollinger Bands calculation"""
    result = calculate_bollinger_bands(sample_price_data, period=20, std_dev=2.0)
    assert isinstance(result, dict)
    assert "upper" in result
    assert "middle" in result
    assert "lower" in result
    # Upper should be above middle, middle above lower
    valid_indices = ~result["middle"].isna()
    assert all(result["upper"][valid_indices] >= result["middle"][valid_indices])
    assert all(result["middle"][valid_indices] >= result["lower"][valid_indices])


def test_calculate_stochastic_oscillator_basic(sample_price_data):
    """Test Stochastic Oscillator calculation"""
    result = calculate_stochastic_oscillator(sample_price_data, k_period=14, d_period=3)
    assert isinstance(result, dict)
    assert "%K" in result
    assert "%D" in result
    # Values should be between 0 and 100
    valid_k = result["%K"].dropna()
    valid_d = result["%D"].dropna()
    assert all((valid_k >= 0) & (valid_k <= 100))
    assert all((valid_d >= 0) & (valid_d <= 100))


def test_calculate_volume_indicators_basic(sample_price_data):
    """Test volume indicators calculation"""
    result = calculate_volume_indicators(sample_price_data)
    assert isinstance(result, dict)
    assert "volume_sma" in result
    assert "volume_ratio" in result
    assert len(result["volume_sma"]) == len(sample_price_data)


# =============================================================================
# Analysis Function Tests
# =============================================================================


def test_analyze_trend_bullish(sample_price_data):
    """Test trend analysis with bullish trend"""
    result = analyze_trend(sample_price_data, short_period=20, long_period=50)
    assert isinstance(result, dict)
    assert "trend_direction" in result
    assert "trend_strength" in result
    assert "support_resistance" in result
    assert result["trend_direction"] in ["bullish", "bearish", "insufficient_data"]


def test_analyze_trend_insufficient_data(insufficient_data):
    """Test trend analysis with insufficient data"""
    result = analyze_trend(insufficient_data, short_period=20, long_period=50)
    assert result["trend_direction"] == "insufficient_data"


def test_analyze_momentum_basic(sample_price_data):
    """Test momentum analysis"""
    result = analyze_momentum(sample_price_data)
    assert isinstance(result, dict)
    assert "momentum_score" in result
    assert "momentum_signals" in result
    assert "rsi_value" in result
    assert "macd_value" in result
    assert isinstance(result["momentum_score"], (int, float))


def test_analyze_momentum_insufficient_data(insufficient_data):
    """Test momentum analysis with insufficient data"""
    result = analyze_momentum(insufficient_data)
    assert "momentum_score" in result
    assert "momentum_signals" in result


# =============================================================================
# MCP Tool Tests
# =============================================================================


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_calculate_technical_indicators_success(mock_read_data, sample_price_data):
    """Test calculate_technical_indicators MCP tool"""
    mock_read_data.return_value = sample_price_data

    # Import the MCP function
    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.calculate_technical_indicators
    result = (
        fn.fn(symbol="2330", indicators=["sma", "ema", "rsi"], periods=None)
        if hasattr(fn, "fn")
        else fn(symbol="2330", indicators=["sma", "ema", "rsi"], periods=None)
    )

    assert result["status"] == "success"
    assert "data" in result
    assert result["data"]["symbol"] == "2330"
    assert "indicators" in result["data"]
    assert "latest_values" in result["data"]


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_calculate_technical_indicators_no_data(mock_read_data):
    """Test calculate_technical_indicators with no data"""
    mock_read_data.return_value = None

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.calculate_technical_indicators
    result = (
        fn.fn({"symbol": "9999", "indicators": None, "periods": None})
        if hasattr(fn, "fn")
        else fn(symbol="9999", indicators=None, periods=None)
    )

    assert result["status"] == "error"
    assert "No historical data found" in result["message"]


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_calculate_technical_indicators_insufficient_data(mock_read_data, insufficient_data):
    """Test calculate_technical_indicators with insufficient data"""
    mock_read_data.return_value = insufficient_data

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.calculate_technical_indicators
    result = (
        fn.fn({"symbol": "2330", "indicators": None, "periods": None})
        if hasattr(fn, "fn")
        else fn(symbol="2330", indicators=None, periods=None)
    )

    assert result["status"] == "error"
    assert "Insufficient data" in result["message"]


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_calculate_technical_indicators_all_indicators(mock_read_data, sample_price_data):
    """Test calculate_technical_indicators with all indicators"""
    mock_read_data.return_value = sample_price_data

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.calculate_technical_indicators
    result = (
        fn.fn(symbol="2330", indicators=["sma", "ema", "rsi", "macd", "bb", "stoch", "volume"], periods=None)
        if hasattr(fn, "fn")
        else fn(symbol="2330", indicators=["sma", "ema", "rsi", "macd", "bb", "stoch", "volume"], periods=None)
    )

    assert result["status"] == "success"
    data = result["data"]
    # Check if indicators were calculated (keys exist)
    assert "sma" in data["indicators"] or "ema" in data["indicators"]


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_calculate_technical_indicators_custom_periods(mock_read_data, sample_price_data):
    """Test calculate_technical_indicators with custom periods"""
    mock_read_data.return_value = sample_price_data

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.calculate_technical_indicators
    custom_periods = {"sma": 10, "rsi": 7}
    result = (
        fn.fn({"symbol": "2330", "indicators": ["sma", "rsi"], "periods": custom_periods})
        if hasattr(fn, "fn")
        else fn(symbol="2330", indicators=["sma", "rsi"], periods=custom_periods)
    )

    assert result["status"] == "success"


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_analyze_stock_trend_comprehensive(mock_read_data, sample_price_data):
    """Test analyze_stock_trend MCP tool with comprehensive analysis"""
    mock_read_data.return_value = sample_price_data

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.analyze_stock_trend
    result = (
        fn.fn(symbol="2330", analysis_type="comprehensive")
        if hasattr(fn, "fn")
        else fn(symbol="2330", analysis_type="comprehensive")
    )

    assert result["status"] == "success"
    data = result["data"]
    assert data["symbol"] == "2330"
    assert "trend_analysis" in data or "momentum_analysis" in data
    assert "trading_signals" in data
    assert "recommendation" in data
    assert data["recommendation"] in ["BUY", "SELL", "HOLD"]


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_analyze_stock_trend_only_trend(mock_read_data, sample_price_data):
    """Test analyze_stock_trend with only trend analysis"""
    mock_read_data.return_value = sample_price_data

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.analyze_stock_trend
    result = fn.fn(symbol="2330", analysis_type="trend") if hasattr(fn, "fn") else fn(symbol="2330", analysis_type="trend")

    assert result["status"] == "success"
    data = result["data"]
    assert "trend_analysis" in data


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_analyze_stock_trend_only_momentum(mock_read_data, sample_price_data):
    """Test analyze_stock_trend with only momentum analysis"""
    mock_read_data.return_value = sample_price_data

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.analyze_stock_trend
    result = (
        fn.fn(symbol="2330", analysis_type="momentum") if hasattr(fn, "fn") else fn(symbol="2330", analysis_type="momentum")
    )

    assert result["status"] == "success"
    data = result["data"]
    assert "momentum_analysis" in data


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_analyze_stock_trend_no_data(mock_read_data):
    """Test analyze_stock_trend with no data"""
    mock_read_data.return_value = None

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.analyze_stock_trend
    result = (
        fn.fn({"symbol": "9999", "analysis_type": "comprehensive"})
        if hasattr(fn, "fn")
        else fn(symbol="9999", analysis_type="comprehensive")
    )

    assert result["status"] == "error"
    assert "No historical data found" in result["message"]


@patch("fubon_api_mcp_server.indicators_service.read_local_stock_data")
def test_analyze_stock_trend_insufficient_data(mock_read_data, insufficient_data):
    """Test analyze_stock_trend with insufficient data"""
    mock_read_data.return_value = insufficient_data

    from fubon_api_mcp_server import indicators_service

    fn = indicators_service.analyze_stock_trend
    result = (
        fn.fn({"symbol": "2330", "analysis_type": "comprehensive"})
        if hasattr(fn, "fn")
        else fn(symbol="2330", analysis_type="comprehensive")
    )

    assert result["status"] == "error"
    assert "Insufficient data for analysis" in result["message"]
