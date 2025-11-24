"""
Technical Indicators Module

提供常用技術指標計算函式,使用 TA-Lib 套件進行運算。

指標包含:
- 移動平均: SMA, EMA, WMA
- 波段指標: Bollinger Bands
- 動量指標: RSI, MACD, KD, Williams %R, CCI, ROC
- 趨勢指標: ADX
- 波動率指標: ATR
- 成交量指標: OBV, Volume Rate

所有函式皆回傳 pandas Series 或 dict(包含多個 Series)。
"""

from typing import Dict

import numpy as np
import pandas as pd
import talib


def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    """簡單移動平均 (SMA)"""
    return pd.Series(talib.SMA(data.values.astype(float), timeperiod=period), index=data.index)


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """指數移動平均 (EMA)"""
    return pd.Series(talib.EMA(data.values.astype(float), timeperiod=period), index=data.index)


def calculate_bollinger_bands(data: pd.Series, period: int = 20, stddev: float = 2.0) -> Dict[str, pd.Series]:
    """布林通道 (Bollinger Bands) 上/中/下軌 + 寬度"""
    upper, middle, lower = talib.BBANDS(data.values.astype(float), timeperiod=period, nbdevup=stddev, nbdevdn=stddev, matype=0)
    width = (upper - lower) / pd.Series(middle, index=data.index).replace(0, np.nan)
    return {
        "upper": pd.Series(upper, index=data.index),
        "middle": pd.Series(middle, index=data.index),
        "lower": pd.Series(lower, index=data.index),
        "width": pd.Series(width, index=data.index),
    }


def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """RSI (Relative Strength Index)"""
    return pd.Series(talib.RSI(data.values.astype(float), timeperiod=period), index=data.index)


def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """MACD 線/Signal 線/Histogram"""
    macd, macdsignal, macdhist = talib.MACD(data.values.astype(float), fastperiod=fast, slowperiod=slow, signalperiod=signal)
    return {
        "macd": pd.Series(macd, index=data.index),
        "signal": pd.Series(macdsignal, index=data.index),
        "histogram": pd.Series(macdhist, index=data.index),
    }


def calculate_kd(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9, smooth_k: int = 3, smooth_d: int = 3
) -> Dict[str, pd.Series]:
    """KD (Stochastic) 指標 %K / %D"""
    slowk, slowd = talib.STOCH(
        high.values.astype(float),
        low.values.astype(float),
        close.values.astype(float),
        fastk_period=period,
        slowk_period=smooth_k,
        slowd_period=smooth_d,
    )
    return {"k": pd.Series(slowk, index=high.index), "d": pd.Series(slowd, index=high.index)}


def calculate_volume_rate(volume: pd.Series, period: int = 20) -> pd.Series:
    """量比 = 當期成交量 / 過去 period 日平均成交量
    注意: 此為手動計算,非 TA-Lib 標準指標
    """
    vol_ma = volume.rolling(window=period).mean()
    return volume / vol_ma.replace(0, np.nan)


def calculate_wma(data: pd.Series, period: int) -> pd.Series:
    """加權移動平均 (WMA)"""
    return pd.Series(talib.WMA(data.values.astype(float), timeperiod=period), index=data.index)


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """平均真實波幅 (ATR) - 衡量價格波動性"""
    return pd.Series(
        talib.ATR(high.values.astype(float), low.values.astype(float), close.values.astype(float), timeperiod=period),
        index=high.index,
    )


def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """平均趨向指標 (ADX) - 衡量趨勢強度"""
    return pd.Series(
        talib.ADX(high.values.astype(float), low.values.astype(float), close.values.astype(float), timeperiod=period),
        index=high.index,
    )


def calculate_williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R - 類似於 Stochastic，但使用不同的計算方式"""
    return pd.Series(
        talib.WILLR(high.values.astype(float), low.values.astype(float), close.values.astype(float), timeperiod=period),
        index=high.index,
    )


def calculate_cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """順勢指標 (CCI) - 用於識別超買超賣區域"""
    return pd.Series(
        talib.CCI(high.values.astype(float), low.values.astype(float), close.values.astype(float), timeperiod=period),
        index=high.index,
    )


def calculate_roc(data: pd.Series, period: int = 10) -> pd.Series:
    """變化率 (ROC) - 衡量價格變化速度"""
    return pd.Series(talib.ROC(data.values.astype(float), timeperiod=period), index=data.index)


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """能量潮指標 (OBV) - 根據成交量確認趨勢"""
    return pd.Series(talib.OBV(close.values.astype(float), volume.values.astype(float)), index=close.index)
