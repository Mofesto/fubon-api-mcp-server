#!/usr/bin/env python3
"""
富邦 API MCP Server - Indicators 單元測試

此測試檔案使用 pytest 框架測試 indicators 模組的所有技術指標計算功能。
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
    calculate_wma,
)


class TestIndicatorsMock:
    """模擬測試 - 使用預定義數據測試指標計算"""

    @pytest.fixture
    def sample_data(self):
        """生成測試用的樣本數據"""
        np.random.seed(42)  # 固定隨機種子確保測試一致性
        dates = pd.date_range("2024-01-01", periods=100, freq="D")

        # 生成價格數據
        base_price = 100
        prices = []
        highs = []
        lows = []
        volumes = []

        for i in range(100):
            # 生成價格波動
            change = np.random.normal(0, 2)
            price = base_price + change
            prices.append(price)

            # 生成高低價
            high = price + abs(np.random.normal(0, 1))
            low = price - abs(np.random.normal(0, 1))
            highs.append(high)
            lows.append(low)

            # 生成成交量
            volume = np.random.randint(10000, 100000)
            volumes.append(volume)

            base_price = price

        return {
            "close": pd.Series(prices, index=dates),
            "high": pd.Series(highs, index=dates),
            "low": pd.Series(lows, index=dates),
            "volume": pd.Series(volumes, index=dates),
            "dates": dates,
        }

    def test_calculate_sma(self, sample_data):
        """測試簡單移動平均 (SMA)"""
        result = calculate_sma(sample_data["close"], period=20)

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data["close"])
        assert result.index.equals(sample_data["close"].index)

        # 檢查前19個值應該是 NaN（數據不足）
        assert pd.isna(result.iloc[0:19]).all()

        # 檢查最後一個值應該是數值
        assert not pd.isna(result.iloc[-1])
        assert isinstance(result.iloc[-1], (int, float))

    def test_calculate_ema(self, sample_data):
        """測試指數移動平均 (EMA)"""
        result = calculate_ema(sample_data["close"], period=20)

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data["close"])
        assert result.index.equals(sample_data["close"].index)

        # EMA 通常前幾個值也是 NaN
        assert pd.isna(result.iloc[0])
        assert not pd.isna(result.iloc[-1])

    def test_calculate_wma(self, sample_data):
        """測試加權移動平均 (WMA)"""
        result = calculate_wma(sample_data["close"], period=20)

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data["close"])
        assert result.index.equals(sample_data["close"].index)

        # 檢查前19個值應該是 NaN
        assert pd.isna(result.iloc[0:19]).all()
        assert not pd.isna(result.iloc[-1])

    def test_calculate_bollinger_bands(self, sample_data):
        """測試布林通道 (Bollinger Bands)"""
        result = calculate_bollinger_bands(sample_data["close"], period=20, stddev=2.0)

        assert isinstance(result, dict)
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert "width" in result

        for key in ["upper", "middle", "lower", "width"]:
            assert isinstance(result[key], pd.Series)
            assert len(result[key]) == len(sample_data["close"])
            assert result[key].index.equals(sample_data["close"].index)

        # 檢查前19個值應該是 NaN
        for key in ["upper", "middle", "lower"]:
            assert pd.isna(result[key].iloc[0:19]).all()
            assert not pd.isna(result[key].iloc[-1])

    def test_calculate_rsi(self, sample_data):
        """測試 RSI 指標"""
        result = calculate_rsi(sample_data["close"], period=14)

        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data["close"])
        assert result.index.equals(sample_data["close"].index)

        # RSI 值應該在 0-100 之間
        valid_values = result.dropna()
        if len(valid_values) > 0:
            assert (valid_values >= 0).all()
            assert (valid_values <= 100).all()

    def test_calculate_macd(self, sample_data):
        """測試 MACD 指標"""
        result = calculate_macd(sample_data["close"], fast=12, slow=26, signal=9)

        assert isinstance(result, dict)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

        for key in ["macd", "signal", "histogram"]:
            assert isinstance(result[key], pd.Series)
            assert len(result[key]) == len(sample_data["close"])
            assert result[key].index.equals(sample_data["close"].index)

        # MACD 需要足夠的數據，檢查是否有有效值
        valid_count = result["macd"].notna().sum()
        assert valid_count > 0

    def test_calculate_kd(self, sample_data):
        """測試 KD 指標"""
        result = calculate_kd(sample_data["high"], sample_data["low"], sample_data["close"])

        assert isinstance(result, dict)
        assert "k" in result
        assert "d" in result

        for key in ["k", "d"]:
            assert isinstance(result[key], pd.Series)
            assert len(result[key]) == len(sample_data["close"])
            assert result[key].index.equals(sample_data["close"].index)

        # KD 值應該在 0-100 之間
        for key in ["k", "d"]:
            valid_values = result[key].dropna()
            if len(valid_values) > 0:
                assert (valid_values >= 0).all()
                assert (valid_values <= 100).all()

    def test_insufficient_data_sma(self):
        """測試數據不足的情況 - SMA"""
        # 只提供5個數據點，但需要20個周期
        short_data = pd.Series([100, 101, 102, 103, 104])
        result = calculate_sma(short_data, period=20)

        # 所有值都應該是 NaN，因為數據不足
        assert result.isna().all()

    def test_insufficient_data_macd(self):
        """測試數據不足的情況 - MACD"""
        # MACD 需要至少 slow period + signal period - 1 個數據點
        # 預設 slow=26, signal=9，需要至少 26+9-1=34 個數據點
        short_data = pd.Series(range(20))  # 只提供20個數據點
        result = calculate_macd(short_data)

        # 所有值都應該是 NaN，因為數據不足
        for key in ["macd", "signal", "histogram"]:
            assert result[key].isna().all()

    def test_edge_case_identical_values(self):
        """測試邊界情況 - 所有值相同"""
        identical_data = pd.Series([100.0] * 50)
        result = calculate_rsi(identical_data, period=14)

        # 當所有價格相等時，RSI 應該是 0（沒有波動）
        valid_values = result.dropna()
        if len(valid_values) > 0:
            # RSI 在價格無變化時通常是 0 或接近 0
            assert valid_values.iloc[0] == 0.0
