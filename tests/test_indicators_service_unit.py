"""
Unit tests for indicators_service.py module.
"""

from unittest.mock import patch

import pandas as pd

from fubon_mcp.indicators_service import (
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


class TestCalculateSMA:
    """Test calculate_sma function."""

    def test_calculate_sma_basic(self):
        """Test basic SMA calculation."""
        data = pd.DataFrame(
            {
                "close": [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                    117,
                    118,
                    119,
                    120,
                ]
            }
        )

        result = calculate_sma(data, period=5)
        assert len(result) == len(data)
        assert pd.isna(result.iloc[0:4]).all()  # First 4 should be NaN
        assert result.iloc[4] == 102.0  # Average of first 5 values
        assert result.iloc[-1] == 118.0  # Average of last 5 values

    def test_calculate_sma_insufficient_data(self):
        """Test SMA with insufficient data."""
        data = pd.DataFrame({"close": [100, 101, 102]})

        result = calculate_sma(data, period=5)
        assert pd.isna(result).all()

    def test_calculate_sma_different_column(self):
        """Test SMA with different column."""
        data = pd.DataFrame({"close": [100, 101, 102, 103, 104], "volume": [1000, 1100, 1200, 1300, 1400]})

        result = calculate_sma(data, period=3, column="volume")
        assert result.iloc[2] == 1100.0  # Average of first 3 volume values


class TestCalculateEMA:
    """Test calculate_ema function."""

    def test_calculate_ema_basic(self):
        """Test basic EMA calculation."""
        data = pd.DataFrame({"close": [100, 101, 102, 103, 104, 105]})

        result = calculate_ema(data, period=3)
        assert len(result) == len(data)
        assert result.iloc[0] == 100.0  # First value should be the first data point
        assert not pd.isna(result.iloc[1])  # Subsequent values should not be NaN

    def test_calculate_ema_insufficient_data(self):
        """Test EMA with insufficient data."""
        data = pd.DataFrame({"close": [100]})

        result = calculate_ema(data, period=3)
        assert pd.isna(result.iloc[0])


class TestCalculateRSI:
    """Test calculate_rsi function."""

    def test_calculate_rsi_basic(self):
        """Test basic RSI calculation."""
        # Create data with clear up/down movements
        data = pd.DataFrame(
            {"close": [100, 102, 98, 103, 97, 105, 95, 107, 93, 109, 91, 111, 89, 113, 87, 115, 85, 117, 83, 119]}
        )

        result = calculate_rsi(data, period=14)
        assert len(result) == len(data)
        # RSI should be between 0 and 100
        valid_rsi = result.dropna()
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()

    def test_calculate_rsi_insufficient_data(self):
        """Test RSI with insufficient data."""
        data = pd.DataFrame({"close": [100, 101, 102]})

        result = calculate_rsi(data, period=14)
        assert pd.isna(result).all()


class TestCalculateMACD:
    """Test calculate_macd function."""

    def test_calculate_macd_basic(self):
        """Test basic MACD calculation."""
        data = pd.DataFrame({"close": list(range(100, 150))})  # 50 data points

        result = calculate_macd(data)
        assert isinstance(result, dict)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

        # All series should have same length
        assert len(result["macd"]) == len(result["signal"]) == len(result["histogram"]) == len(data)

    def test_calculate_macd_insufficient_data(self):
        """Test MACD with insufficient data."""
        data = pd.DataFrame({"close": [100, 101, 102]})

        result = calculate_macd(data)
        assert pd.isna(result["macd"]).all()
        assert pd.isna(result["signal"]).all()
        assert pd.isna(result["histogram"]).all()


class TestCalculateBollingerBands:
    """Test calculate_bollinger_bands function."""

    def test_calculate_bollinger_bands_basic(self):
        """Test basic Bollinger Bands calculation."""
        data = pd.DataFrame({"close": [100] * 25})  # Constant values for predictable results

        result = calculate_bollinger_bands(data, period=20, std_dev=2.0)
        assert isinstance(result, dict)
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result

        # With constant data, all bands should be equal to the constant value
        valid_upper = result["upper"].dropna()
        valid_middle = result["middle"].dropna()
        valid_lower = result["lower"].dropna()

        assert (valid_upper == 100).all()
        assert (valid_middle == 100).all()
        assert (valid_lower == 100).all()


class TestCalculateStochasticOscillator:
    """Test calculate_stochastic_oscillator function."""

    def test_calculate_stochastic_oscillator_basic(self):
        """Test basic Stochastic Oscillator calculation."""
        # Create data with clear high/low patterns
        data = pd.DataFrame(
            {
                "high": [105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124],
                "low": [95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
                "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119],
            }
        )

        result = calculate_stochastic_oscillator(data)
        assert isinstance(result, dict)
        assert "%K" in result
        assert "%D" in result

        # Values should be between 0 and 100
        valid_k = result["%K"].dropna()
        valid_d = result["%D"].dropna()
        assert (valid_k >= 0).all() and (valid_k <= 100).all()
        assert (valid_d >= 0).all() and (valid_d <= 100).all()


class TestCalculateVolumeIndicators:
    """Test calculate_volume_indicators function."""

    def test_calculate_volume_indicators_basic(self):
        """Test basic volume indicators calculation."""
        data = pd.DataFrame(
            {
                "volume": [
                    1000,
                    1100,
                    1200,
                    1300,
                    1400,
                    1500,
                    1600,
                    1700,
                    1800,
                    1900,
                    2000,
                    2100,
                    2200,
                    2300,
                    2400,
                    2500,
                    2600,
                    2700,
                    2800,
                    2900,
                ]
            }
        )

        result = calculate_volume_indicators(data)
        assert isinstance(result, dict)
        assert "volume_sma" in result
        assert "volume_ratio" in result

        # Check that volume SMA is calculated
        assert not pd.isna(result["volume_sma"].iloc[-1])


class TestAnalyzeTrend:
    """Test analyze_trend function."""

    def test_analyze_trend_basic(self):
        """Test basic trend analysis."""
        data = pd.DataFrame({"close": list(range(100, 150))})  # Upward trend

        result = analyze_trend(data)
        assert isinstance(result, dict)
        assert "trend_direction" in result
        assert "trend_strength" in result
        assert "support_resistance" in result

    def test_analyze_trend_insufficient_data(self):
        """Test trend analysis with insufficient data."""
        data = pd.DataFrame({"close": [100, 101, 102]})

        result = analyze_trend(data)
        assert result["trend_direction"] == "insufficient_data"


class TestAnalyzeMomentum:
    """Test analyze_momentum function."""

    def test_analyze_momentum_basic(self):
        """Test basic momentum analysis."""
        data = pd.DataFrame(
            {"close": [100, 102, 98, 103, 97, 105, 95, 107, 93, 109, 91, 111, 89, 113, 87, 115, 85, 117, 83, 119]}
        )

        result = analyze_momentum(data)
        assert isinstance(result, dict)
        assert "momentum_score" in result
        assert "momentum_signals" in result
        assert "divergence_signals" in result


class TestCalculateTechnicalIndicators:
    """Test calculate_technical_indicators function."""

    @patch("fubon_mcp.indicators_service.read_local_stock_data")
    def test_calculate_technical_indicators_success(self, mock_read_data):
        """Test successful technical indicators calculation."""
        # Create mock data as DataFrame with sufficient data (50+ points)
        dates = [f"2023-01-{i:02d}" for i in range(1, 51)]  # 50 data points
        mock_data = pd.DataFrame(
            {
                "date": dates,
                "close": [100.0 + i for i in range(50)],
                "high": [105.0 + i for i in range(50)],
                "low": [95.0 + i for i in range(50)],
                "volume": [1000 + i * 10 for i in range(50)],
            }
        )
        mock_read_data.return_value = mock_data

        result = calculate_technical_indicators("2330", ["SMA", "RSI"])
        assert result["status"] == "success"
        assert "data" in result
        assert "indicators" in result["data"]

    @patch("fubon_mcp.indicators_service.read_local_stock_data")
    def test_calculate_technical_indicators_api_failure(self, mock_read_data):
        """Test technical indicators when API fails."""
        mock_read_data.return_value = None

        result = calculate_technical_indicators("2330")
        assert result["status"] == "error"


class TestAnalyzeStockTrend:
    """Test analyze_stock_trend function."""

    @patch("fubon_mcp.indicators_service.read_local_stock_data")
    def test_analyze_stock_trend_success(self, mock_read_data):
        """Test successful stock trend analysis."""
        # Create mock data as DataFrame with sufficient data for analysis
        mock_data = pd.DataFrame(
            {
                "close": [100.0] * 150,  # 150 data points for sufficient analysis
                "high": [105.0] * 150,
                "low": [95.0] * 150,
                "volume": [1000] * 150,
            }
        )
        mock_read_data.return_value = mock_data

        result = analyze_stock_trend("2330", "comprehensive")
        assert result["status"] == "success"
        assert "data" in result

    @patch("fubon_mcp.indicators_service.read_local_stock_data")
    def test_analyze_stock_trend_api_failure(self, mock_read_data):
        """Test stock trend analysis when API fails."""
        mock_read_data.return_value = None

        result = analyze_stock_trend("2330")
        assert result["status"] == "error"
