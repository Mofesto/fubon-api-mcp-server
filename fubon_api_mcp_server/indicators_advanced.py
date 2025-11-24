#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
專業交易員風險管理與市場分析工具

此模組包含專業級的風險管理和市場分析功能:
- CVaR (條件風險價值)
- 最大回撤分析
- 尾部風險評估
- 市場廣度指標
- 資金流向分析
- 恐懼貪婪指數

作者: Professional Trading Team
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

# ==================== 風險管理工具 ====================


def calculate_portfolio_returns(positions: List[Dict], lookback_period: int, read_data_func) -> Optional[pd.Series]:
    """
    計算投資組合歷史收益率序列

    Args:
        positions: 持倉列表
        lookback_period: 回顧期(天)
        read_data_func: 讀取數據的函數

    Returns:
        pd.Series: 投資組合收益率序列
    """
    if not positions:
        return None

    total_value = sum(pos.get("market_value", 0) for pos in positions)
    if total_value == 0:
        return None

    portfolio_value_series = None
    valid_positions = 0

    for pos in positions:
        symbol = pos.get("stock_no", "")
        quantity = pos.get("quantity", 0)
        weight = pos.get("market_value", 0) / total_value

        if weight < 0.001:
            continue

        df = read_data_func(symbol)
        if df is None or df.empty or len(df) < 20:
            continue

        df = df.sort_values("date").tail(lookback_period)
        if len(df) < 20:
            continue

        position_value = df["close"] * quantity
        position_value.index = df["date"]

        if portfolio_value_series is None:
            portfolio_value_series = position_value * 0

        portfolio_value_series = portfolio_value_series.add(position_value, fill_value=0)
        valid_positions += 1

    if portfolio_value_series is None or valid_positions == 0 or len(portfolio_value_series) < 30:
        return None

    returns = portfolio_value_series.pct_change().dropna()
    return returns


def calculate_historical_var(returns: pd.Series, confidence_level: float, total_value: float) -> Dict:
    """歷史模擬法計算 VaR 和 CVaR"""
    var_quantile = returns.quantile(1 - confidence_level)
    var_absolute = abs(var_quantile * total_value)
    var_percentage = abs(var_quantile)

    tail_losses = returns[returns <= var_quantile]
    if len(tail_losses) > 0:
        cvar_quantile = tail_losses.mean()
        cvar_absolute = abs(cvar_quantile * total_value)
        cvar_percentage = abs(cvar_quantile)
    else:
        cvar_absolute = var_absolute
        cvar_percentage = var_percentage

    return {"var": var_absolute, "var_pct": var_percentage, "cvar": cvar_absolute, "cvar_pct": cvar_percentage}


def calculate_parametric_var(returns: pd.Series, confidence_level: float, total_value: float) -> Dict:
    """參數法(正態分布)計算 VaR 和 CVaR"""
    mean = returns.mean()
    std = returns.std()

    z_scores = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326, 0.999: 3.090}
    z_score = z_scores.get(confidence_level, 1.645)

    var_quantile = mean - z_score * std
    var_absolute = abs(var_quantile * total_value)
    var_percentage = abs(var_quantile)

    phi = stats.norm.pdf(z_score)
    cvar_quantile = mean - std * phi / (1 - confidence_level)
    cvar_absolute = abs(cvar_quantile * total_value)
    cvar_percentage = abs(cvar_quantile)

    return {"var": var_absolute, "var_pct": var_percentage, "cvar": cvar_absolute, "cvar_pct": cvar_percentage}


def calculate_monte_carlo_var(returns: pd.Series, confidence_level: float, total_value: float, n_simulations: int) -> Dict:
    """蒙地卡羅模擬法計算 VaR 和 CVaR"""
    mean = returns.mean()
    std = returns.std()

    np.random.seed(42)
    simulated_returns = np.random.normal(mean, std, n_simulations)

    var_quantile = np.percentile(simulated_returns, (1 - confidence_level) * 100)
    var_absolute = abs(var_quantile * total_value)
    var_percentage = abs(var_quantile)

    tail_losses = simulated_returns[simulated_returns <= var_quantile]
    cvar_quantile = tail_losses.mean() if len(tail_losses) > 0 else var_quantile
    cvar_absolute = abs(cvar_quantile * total_value)
    cvar_percentage = abs(cvar_quantile)

    return {"var": var_absolute, "var_pct": var_percentage, "cvar": cvar_absolute, "cvar_pct": cvar_percentage}


def calculate_max_drawdown(returns: pd.Series, total_value: float) -> Dict:
    """計算最大回撤"""
    if len(returns) == 0:
        return {"max_dd": 0, "max_dd_pct": 0, "duration": 0, "current_dd": 0}

    cumulative_returns = (1 + returns).cumprod()
    running_max = cumulative_returns.expanding().max()
    drawdown = (cumulative_returns - running_max) / running_max

    max_dd_pct = abs(drawdown.min())
    max_dd_absolute = max_dd_pct * total_value

    duration = 0
    if max_dd_pct > 0:
        max_dd_idx = drawdown.idxmin()
        dd_start_idx = None
        for i in range(len(drawdown)):
            if drawdown.index[i] >= max_dd_idx:
                break
            if drawdown.iloc[i] == 0:
                dd_start_idx = i

        if dd_start_idx is not None:
            # 使用位置差而不是直接相減
            max_dd_pos = drawdown.index.get_loc(max_dd_idx)
            duration = max_dd_pos - dd_start_idx

    current_dd = abs(drawdown.iloc[-1]) if len(drawdown) > 0 else 0

    return {"max_dd": max_dd_absolute, "max_dd_pct": max_dd_pct, "duration": duration, "current_dd": current_dd}


def calculate_tail_risk(returns: pd.Series, confidence_level: float) -> Dict:
    """計算尾部風險指標"""
    skewness = returns.skew()
    kurtosis = returns.kurtosis()

    right_tail = returns.quantile(0.95)
    left_tail = returns.quantile(0.05)
    tail_ratio = abs(right_tail / left_tail) if left_tail != 0 else 1.0

    var_threshold = returns.quantile(1 - confidence_level)
    tail_losses = returns[returns <= var_threshold]
    expected_shortfall = abs(tail_losses.mean()) if len(tail_losses) > 0 else 0

    return {"skewness": skewness, "kurtosis": kurtosis, "tail_ratio": tail_ratio, "expected_shortfall": expected_shortfall}


def assess_risk_level(var_pct: float, annual_volatility: float, max_dd_pct: float) -> str:
    """評估風險等級"""
    risk_score = 0

    if var_pct > 0.05:
        risk_score += 3
    elif var_pct > 0.03:
        risk_score += 2
    elif var_pct > 0.02:
        risk_score += 1

    if annual_volatility > 0.30:
        risk_score += 3
    elif annual_volatility > 0.20:
        risk_score += 2
    elif annual_volatility > 0.15:
        risk_score += 1

    if max_dd_pct > 0.30:
        risk_score += 3
    elif max_dd_pct > 0.20:
        risk_score += 2
    elif max_dd_pct > 0.10:
        risk_score += 1

    if risk_score >= 7:
        return "極高風險"
    elif risk_score >= 5:
        return "高風險"
    elif risk_score >= 3:
        return "中等風險"
    elif risk_score >= 1:
        return "低風險"
    else:
        return "極低風險"


# ==================== 市場分析工具 ====================


def calculate_market_breadth(symbols_list: List[str], read_data_func) -> Dict:
    """計算市場廣度指標"""
    if not symbols_list:
        return {"advance_decline_ratio": 0.5, "composite_score": 0.5}

    advancing = 0
    declining = 0
    new_highs = 0
    new_lows = 0
    total_stocks = 0

    for symbol in symbols_list:
        df = read_data_func(symbol)
        if df is None or df.empty or len(df) < 60:
            continue

        df = df.sort_values("date").tail(60)
        total_stocks += 1

        if len(df) >= 2:
            price_change = df["close"].iloc[-1] - df["close"].iloc[-2]
            if price_change > 0:
                advancing += 1
            elif price_change < 0:
                declining += 1

        recent_high = df["close"].tail(60).max()
        recent_low = df["close"].tail(60).min()
        current_price = df["close"].iloc[-1]

        if abs(current_price - recent_high) / recent_high < 0.01:
            new_highs += 1
        if abs(current_price - recent_low) / recent_low < 0.01:
            new_lows += 1

    if total_stocks == 0:
        return {"advance_decline_ratio": 0.5, "composite_score": 0.5}

    adl_ratio = advancing / total_stocks
    nh_nl_total = new_highs + new_lows
    nh_nl_ratio = new_highs / nh_nl_total if nh_nl_total > 0 else 0.5

    composite_score = (adl_ratio + nh_nl_ratio) / 2

    return {
        "advance_decline_ratio": adl_ratio,
        "advancing_stocks": advancing,
        "declining_stocks": declining,
        "new_high_low_ratio": nh_nl_ratio,
        "new_highs": new_highs,
        "new_lows": new_lows,
        "total_stocks": total_stocks,
        "composite_score": composite_score,
    }


def calculate_money_flow(df: pd.DataFrame) -> Dict:
    """計算資金流向指標(MFI)"""
    if df is None or df.empty or len(df) < 14:
        return {"mfi": 50, "composite_score": 0.5}

    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    money_flow = typical_price * df["volume"]

    price_changes = typical_price.diff()
    positive_flow = money_flow.where(price_changes > 0, 0).tail(14).sum()
    negative_flow = money_flow.where(price_changes < 0, 0).tail(14).sum()

    if negative_flow == 0:
        mfi = 100
    else:
        money_ratio = positive_flow / abs(negative_flow)
        mfi = 100 - (100 / (1 + money_ratio))

    total_flow = positive_flow + abs(negative_flow)
    positive_ratio = positive_flow / total_flow if total_flow > 0 else 0.5

    composite_score = (mfi / 100 + positive_ratio) / 2

    return {
        "mfi": mfi,
        "positive_flow": positive_flow,
        "negative_flow": abs(negative_flow),
        "positive_flow_ratio": positive_ratio,
        "composite_score": composite_score,
    }


def calculate_fear_greed_index(technical_score: float, breadth_score: float, volume_score: float) -> Dict:
    """計算恐懼貪婪指數"""
    overall_score = technical_score * 0.4 + breadth_score * 0.3 + volume_score * 0.3
    fear_greed_value = overall_score * 100

    if fear_greed_value >= 75:
        level = "極度貪婪"
        sentiment = "市場過熱"
    elif fear_greed_value >= 55:
        level = "貪婪"
        sentiment = "市場樂觀"
    elif fear_greed_value >= 45:
        level = "中性"
        sentiment = "市場平衡"
    elif fear_greed_value >= 25:
        level = "恐懼"
        sentiment = "市場悲觀"
    else:
        level = "極度恐懼"
        sentiment = "市場恐慌"

    return {"fear_greed_index": fear_greed_value, "level": level, "sentiment": sentiment, "composite_score": overall_score}
