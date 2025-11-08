"""
Tests for indicators module.
"""

import numpy as np
import pandas as pd
import pytest

from fubon_api_mcp_server.indicators import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_kd,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    calculate_volume_rate,
)


class TestSMA:
    """Test Simple Moving Average calculations."""

    def test_calculate_sma_basic(self):
        """Test basic SMA calculation."""
        data = pd.Series([1, 2, 3, 4, 5])
        result = calculate_sma(data, period=3)
        expected = pd.Series([np.nan, np.nan, 2.0, 3.0, 4.0])
        pd.testing.assert_series_equal(result, expected)

    def test_calculate_sma_period_larger_than_data(self):
        """Test SMA with period larger than data length."""
        data = pd.Series([1, 2, 3])
        result = calculate_sma(data, period=5)
        expected = pd.Series([np.nan, np.nan, np.nan])
        pd.testing.assert_series_equal(result, expected)

    def test_calculate_sma_empty_data(self):
        """Test SMA with empty data."""
        data = pd.Series([], dtype=float)
        result = calculate_sma(data, period=3)
        expected = pd.Series([], dtype=float)
        pd.testing.assert_series_equal(result, expected)


class TestEMA:
    """Test Exponential Moving Average calculations."""

    def test_calculate_ema_basic(self):
        """Test basic EMA calculation."""
        data = pd.Series([1, 2, 3, 4, 5])
        result = calculate_ema(data, period=3)
        # EMA calculation: first value is the first data point
        # subsequent values use the formula: ema = (data * multiplier) + (prev_ema * (1 - multiplier))
        # where multiplier = 2 / (period + 1)
        expected = pd.Series([1.0, 1.5, 2.25, 3.125, 4.0625])
        pd.testing.assert_series_equal(result, expected, atol=1e-6)

    def test_calculate_ema_single_value(self):
        """Test EMA with single value."""
        data = pd.Series([5.0])
        result = calculate_ema(data, period=3)
        expected = pd.Series([5.0])
        pd.testing.assert_series_equal(result, expected)


class TestBollingerBands:
    """Test Bollinger Bands calculations."""

    def test_calculate_bollinger_bands_basic(self):
        """Test basic Bollinger Bands calculation."""
        data = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
                         20, 21, 22, 23, 24, 25, 26, 27, 28, 29])
        result = calculate_bollinger_bands(data, period=5, stddev=2.0)

        # Check that all required keys are present
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert "width" in result

        # Check that middle band is SMA
        expected_middle = calculate_sma(data, 5)
        pd.testing.assert_series_equal(result["middle"], expected_middle)

        # Check that upper and lower bands are calculated correctly
        std = data.rolling(window=5).std()
        expected_upper = expected_middle + std * 2.0
        expected_lower = expected_middle - std * 2.0
        pd.testing.assert_series_equal(result["upper"], expected_upper)
        pd.testing.assert_series_equal(result["lower"], expected_lower)

    def test_calculate_bollinger_bands_insufficient_data(self):
        """Test Bollinger Bands with insufficient data."""
        data = pd.Series([10, 11, 12])
        result = calculate_bollinger_bands(data, period=5, stddev=2.0)

        # All results should be NaN for insufficient data
        assert result["upper"].isna().all()
        assert result["middle"].isna().all()
        assert result["lower"].isna().all()
        assert result["width"].isna().all()


class TestRSI:
    """Test RSI calculations."""

    def test_calculate_rsi_basic(self):
        """Test basic RSI calculation."""
        # Create a simple uptrend
        data = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
                         20, 21, 22, 23, 24, 25, 26, 27, 28, 29])
        result = calculate_rsi(data, period=14)

        # RSI should be between 0 and 100
        assert result.min() >= 0
        assert result.max() <= 100

        # For an uptrend, RSI should be high
        assert result.iloc[-1] > 70  # Should be overbought

    def test_calculate_rsi_downtrend(self):
        """Test RSI with downtrend."""
        # Create a downtrend
        data = pd.Series([30, 29, 28, 27, 26, 25, 24, 23, 22, 21,
                         20, 19, 18, 17, 16, 15, 14, 13, 12, 11])
        result = calculate_rsi(data, period=14)

        # RSI should be between 0 and 100
        assert result.min() >= 0
        assert result.max() <= 100

        # For a downtrend, RSI should be low
        assert result.iloc[-1] < 30  # Should be oversold

    def test_calculate_rsi_insufficient_data(self):
        """Test RSI with insufficient data."""
        data = pd.Series([10, 11, 12])
        result = calculate_rsi(data, period=14)

        # All results should be NaN for insufficient data
        assert result.isna().all()


class TestMACD:
    """Test MACD calculations."""

    def test_calculate_macd_basic(self):
        """Test basic MACD calculation."""
        data = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
                         20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
                         30, 31, 32, 33, 34, 35, 36, 37, 38, 39])
        result = calculate_macd(data, fast=12, slow=26, signal=9)

        # Check that all required keys are present
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

        # MACD line should be fast EMA - slow EMA
        fast_ema = calculate_ema(data, 12)
        slow_ema = calculate_ema(data, 26)
        expected_macd = fast_ema - slow_ema
        pd.testing.assert_series_equal(result["macd"], expected_macd)

        # Signal line should be EMA of MACD
        expected_signal = calculate_ema(result["macd"], 9)
        pd.testing.assert_series_equal(result["signal"], expected_signal)

        # Histogram should be MACD - signal
        expected_histogram = result["macd"] - result["signal"]
        pd.testing.assert_series_equal(result["histogram"], expected_histogram)

    def test_calculate_macd_insufficient_data(self):
        """Test MACD with insufficient data."""
        data = pd.Series([10, 11, 12])
        result = calculate_macd(data, fast=12, slow=26, signal=9)

        # All results should be NaN for insufficient data
        assert result["macd"].isna().all()
        assert result["signal"].isna().all()
        assert result["histogram"].isna().all()


class TestKD:
    """Test KD (Stochastic) calculations."""

    def test_calculate_kd_basic(self):
        """Test basic KD calculation."""
        high = pd.Series([15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
                         25, 26, 27, 28, 29, 30, 31, 32, 33, 34])
        low = pd.Series([5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
                        15, 16, 17, 18, 19, 20, 21, 22, 23, 24])
        close = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
                          20, 21, 22, 23, 24, 25, 26, 27, 28, 29])

        result = calculate_kd(high, low, close, period=5, smooth_k=3, smooth_d=3)

        # Check that all required keys are present
        assert "k" in result
        assert "d" in result

        # K and D should be between 0 and 100
        assert result["k"].min() >= 0
        assert result["k"].max() <= 100
        assert result["d"].min() >= 0
        assert result["d"].max() <= 100

    def test_calculate_kd_insufficient_data(self):
        """Test KD with insufficient data."""
        high = pd.Series([15, 16, 17])
        low = pd.Series([5, 6, 7])
        close = pd.Series([10, 11, 12])

        result = calculate_kd(high, low, close, period=5, smooth_k=3, smooth_d=3)

        # All results should be NaN for insufficient data
        assert result["k"].isna().all()
        assert result["d"].isna().all()


class TestVolumeRate:
    """Test Volume Rate calculations."""

    def test_calculate_volume_rate_basic(self):
        """Test basic volume rate calculation."""
        volume = pd.Series([100, 200, 150, 300, 250, 400, 350, 500, 450, 600,
                           550, 700, 650, 800, 750, 900, 850, 1000, 950, 1100])
        result = calculate_volume_rate(volume, period=5)

        # Volume rate = current volume / average volume over period
        expected = volume / volume.rolling(window=5).mean()
        pd.testing.assert_series_equal(result, expected)

    def test_calculate_volume_rate_with_zero_volume(self):
        """Test volume rate with zero volume values."""
        volume = pd.Series([0, 100, 200, 0, 300])
        result = calculate_volume_rate(volume, period=3)

        # Should handle zero volumes gracefully
        assert not result.isna().all()

    def test_calculate_volume_rate_insufficient_data(self):
        """Test volume rate with insufficient data."""
        volume = pd.Series([100, 200, 150])
        result = calculate_volume_rate(volume, period=5)

        # All results should be NaN for insufficient data
        assert result.isna().all()


class TestIndicatorsIntegration:
    """Test integration of multiple indicators."""

    def test_all_indicators_with_realistic_data(self):
        """Test all indicators with realistic stock data."""
        # Create realistic stock data
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        np.random.seed(42)  # For reproducible results

        # Generate realistic price data with trend
        base_price = 100
        trend = np.linspace(0, 20, 50)
        noise = np.random.normal(0, 2, 50)
        close = pd.Series(base_price + trend + noise)

        # Generate high/low based on close
        high_noise = np.random.uniform(0, 3, 50)
        low_noise = np.random.uniform(-3, 0, 50)
        high = close + high_noise
        low = close + low_noise

        # Generate volume data
        volume = pd.Series(np.random.uniform(100000, 500000, 50))

        # Test all indicators
        sma = calculate_sma(close, 20)
        ema = calculate_ema(close, 20)
        bb = calculate_bollinger_bands(close, 20, 2.0)
        rsi = calculate_rsi(close, 14)
        macd = calculate_macd(close, 12, 26, 9)
        kd = calculate_kd(high, low, close, 9, 3, 3)
        vol_rate = calculate_volume_rate(volume, 20)

        # Basic sanity checks
        assert len(sma) == len(close)
        assert len(ema) == len(close)
        assert len(bb["upper"]) == len(close)
        assert len(rsi) == len(close)
        assert len(macd["macd"]) == len(close)
        assert len(kd["k"]) == len(close)
        assert len(vol_rate) == len(close)

        # RSI should be in valid range
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()

        # KD should be in valid range
        valid_k = kd["k"].dropna()
        valid_d = kd["d"].dropna()
        if len(valid_k) > 0:
            assert (valid_k >= 0).all() and (valid_k <= 100).all()
        if len(valid_d) > 0:
            assert (valid_d >= 0).all() and (valid_d <= 100).all()

        # Bollinger bands should have upper > middle > lower for valid data
        valid_bb = bb["upper"].dropna()
        valid_middle = bb["middle"].dropna()
        valid_lower = bb["lower"].dropna()
        if len(valid_bb) > 0:
            assert (valid_bb > valid_middle).all()
            assert (valid_middle > valid_lower).all()
