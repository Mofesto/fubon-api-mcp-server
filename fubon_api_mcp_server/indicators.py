"""
Technical Indicators Module

提供常用技術指標計算函式,支援動能交易分析。
僅使用 pandas 與 numpy,避免外部二進位依賴。

指標包含:
- SMA/EMA: 移動平均
- Bollinger Bands: 布林通道
- RSI: 相對強弱指標
- MACD: 指數平滑異同移動平均
- KD: 隨機指標 (Stochastic)
- Volume Rate: 量比 (相對成交量)

所有函式皆回傳 pandas Series 或 dict(包含多個 Series)。
"""

from typing import Dict

import numpy as np
import pandas as pd


def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    """簡單移動平均 (SMA)"""
    return data.rolling(window=period).mean()


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """指數移動平均 (EMA)"""
    return data.ewm(span=period, adjust=False).mean()


def calculate_bollinger_bands(data: pd.Series, period: int = 20, stddev: float = 2.0) -> Dict[str, pd.Series]:
    """布林通道 (Bollinger Bands) 上/中/下軌 + 寬度"""
    middle = calculate_sma(data, period)
    deviation = data.rolling(window=period).std()
    upper = middle + deviation * stddev
    lower = middle - deviation * stddev
    width = (upper - lower) / middle.replace(0, np.nan)
    return {"upper": upper, "middle": middle, "lower": lower, "width": width}


def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """RSI (Relative Strength Index)"""
    if len(data) < period + 1:
        return pd.Series([np.nan] * len(data), index=data.index)

    delta = data.diff()
    gains = delta.clip(lower=0)
    losses = (-delta.clip(upper=0)).abs()
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()

    # Handle division by zero: when avg_loss is 0, RSI should be 100
    rs = avg_gain / avg_loss.replace(0, 1e-10)  # Use small value instead of NaN for division
    rsi = 100 - (100 / (1 + rs))

    # Set RSI to 100 when avg_loss was originally 0 (perfect uptrend)
    rsi = rsi.where(avg_loss != 0, 100)

    return rsi


def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """MACD 線/Signal 線/Histogram"""
    if len(data) < slow:
        nan_series = pd.Series([np.nan] * len(data), index=data.index)
        return {"macd": nan_series, "signal": nan_series, "histogram": nan_series}

    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def calculate_kd(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9, smooth_k: int = 3, smooth_d: int = 3
) -> Dict[str, pd.Series]:
    """KD (Stochastic) 指標 %K / %D"""
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan) * 100
    k = rsv.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    return {"k": k, "d": d}


def calculate_volume_rate(volume: pd.Series, period: int = 20) -> pd.Series:
    """量比 = 當期成交量 / 過去 period 日平均成交量"""
    vol_ma = volume.rolling(window=period).mean()
    return volume / vol_ma.replace(0, np.nan)
