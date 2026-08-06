"""Pure quantitative calculations backed by caller-supplied market data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import optimize, stats

MIN_RETURN_OBSERVATIONS = 60
TRADING_DAYS_PER_YEAR = 252


class InsufficientDataError(ValueError):
    """Raised when a calculation cannot be supported by observed data."""


@dataclass(frozen=True)
class MatrixCoverage:
    symbols: List[str]
    observations: int
    start_date: str
    end_date: str


def build_price_matrix(
    symbols: Sequence[str],
    lookback_days: int,
    history_loader: Callable[[str, int], pd.DataFrame],
    min_observations: int = MIN_RETURN_OBSERVATIONS,
) -> Tuple[pd.DataFrame, MatrixCoverage]:
    """Build an inner-joined close-price matrix from verified market histories."""
    unique_symbols = list(dict.fromkeys(symbol.strip() for symbol in symbols if symbol and symbol.strip()))
    if not unique_symbols:
        raise InsufficientDataError("未提供可分析的商品代碼")

    close_series = []
    unavailable = []
    for symbol in unique_symbols:
        frame = history_loader(symbol, lookback_days + 1)
        if frame is None or frame.empty or not {"date", "close"}.issubset(frame.columns):
            unavailable.append(symbol)
            continue

        normalized = frame[["date", "close"]].copy()
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized["close"] = pd.to_numeric(normalized["close"], errors="coerce")
        normalized = normalized.dropna().drop_duplicates("date", keep="last").sort_values("date")
        normalized = normalized[normalized["close"] > 0].tail(lookback_days + 1)
        if len(normalized) < min_observations + 1:
            unavailable.append(symbol)
            continue

        close_series.append(normalized.set_index("date")["close"].rename(symbol))

    if unavailable:
        raise InsufficientDataError(f"以下商品缺少至少 {min_observations + 1} 筆正式歷史價格: {', '.join(unavailable)}")

    prices = pd.concat(close_series, axis=1, join="inner").dropna().sort_index().tail(lookback_days + 1)
    if len(prices) < min_observations + 1:
        raise InsufficientDataError(f"商品共同交易日不足，需要至少 {min_observations + 1} 筆價格，目前 {len(prices)} 筆")

    coverage = MatrixCoverage(
        symbols=unique_symbols,
        observations=len(prices) - 1,
        start_date=prices.index[0].date().isoformat(),
        end_date=prices.index[-1].date().isoformat(),
    )
    return prices, coverage


def build_return_matrix(
    symbols: Sequence[str],
    lookback_days: int,
    history_loader: Callable[[str, int], pd.DataFrame],
    min_observations: int = MIN_RETURN_OBSERVATIONS,
) -> Tuple[pd.DataFrame, MatrixCoverage]:
    """Build aligned simple daily returns from verified close prices."""
    prices, coverage = build_price_matrix(symbols, lookback_days, history_loader, min_observations)
    returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()
    if len(returns) < min_observations:
        raise InsufficientDataError(f"有效共同報酬不足，需要至少 {min_observations} 筆，目前 {len(returns)} 筆")
    return returns, coverage


def calculate_var_metrics(
    daily_returns: pd.Series,
    portfolio_value: float,
    confidence_level: float,
    time_horizon: int,
    method: str,
    simulations: int,
) -> Dict[str, float | int | str]:
    """Calculate VaR and CVaR from an observed portfolio return series."""
    clean = pd.to_numeric(daily_returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_RETURN_OBSERVATIONS:
        raise InsufficientDataError(f"投資組合有效報酬不足，需要至少 {MIN_RETURN_OBSERVATIONS} 筆，目前 {len(clean)} 筆")
    if portfolio_value <= 0:
        raise InsufficientDataError("投資組合市值必須大於零")

    if time_horizon == 1:
        horizon_returns = clean
    else:
        horizon_returns = (1 + clean).rolling(time_horizon).apply(np.prod, raw=True).dropna() - 1
    if horizon_returns.empty:
        raise InsufficientDataError("時間範圍超過可用歷史資料")

    tail_probability = 1 - confidence_level
    if method == "historical":
        return_quantile = float(horizon_returns.quantile(tail_probability))
        tail = horizon_returns[horizon_returns <= return_quantile]
        expected_tail_return = float(tail.mean()) if not tail.empty else return_quantile
    elif method == "parametric":
        mean = float(clean.mean()) * time_horizon
        std = float(clean.std(ddof=1)) * np.sqrt(time_horizon)
        return_quantile = mean + float(stats.norm.ppf(tail_probability)) * std
        expected_tail_return = mean - std * float(stats.norm.pdf(stats.norm.ppf(tail_probability))) / tail_probability
    elif method == "monte_carlo":
        mean = float(clean.mean()) * time_horizon
        std = float(clean.std(ddof=1)) * np.sqrt(time_horizon)
        rng = np.random.default_rng(42)
        simulated = rng.normal(mean, std, simulations)
        return_quantile = float(np.quantile(simulated, tail_probability))
        tail = simulated[simulated <= return_quantile]
        expected_tail_return = float(tail.mean()) if len(tail) else return_quantile
    else:
        raise ValueError(f"不支援的 VaR 方法: {method}")

    var_percentage = max(0.0, -return_quantile)
    cvar_percentage = max(var_percentage, -expected_tail_return)
    return {
        "var_estimate": portfolio_value * var_percentage,
        "cvar_estimate": portfolio_value * cvar_percentage,
        "var_percentage": var_percentage,
        "cvar_percentage": cvar_percentage,
        "annualized_volatility": float(clean.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)),
        "observations": int(len(clean)),
        "simulation_seed": 42 if method == "monte_carlo" else "not_applicable",
    }


def optimize_long_only_portfolio(
    returns: pd.DataFrame,
    method: str,
    risk_free_rate: float,
    target_return: float | None,
    max_volatility: float | None,
    max_weight: float,
) -> Dict[str, object]:
    """Optimize a fully-invested long-only portfolio using observed returns."""
    if returns.empty or len(returns) < MIN_RETURN_OBSERVATIONS:
        raise InsufficientDataError("最佳化需要至少 60 筆共同日報酬")
    symbols = list(returns.columns)
    asset_count = len(symbols)
    if asset_count < 2:
        raise InsufficientDataError("投資組合最佳化至少需要兩個商品")
    if max_weight * asset_count < 1 - 1e-9:
        raise ValueError("max_weight 太低，無法使權重總和達到 1")
    if method == "target_return" and target_return is None:
        raise ValueError("target_return 方法必須提供 target_return")

    expected_returns = returns.mean() * TRADING_DAYS_PER_YEAR
    covariance = returns.cov() * TRADING_DAYS_PER_YEAR

    def portfolio_return(weights: np.ndarray) -> float:
        return float(np.dot(weights, expected_returns.to_numpy()))

    def portfolio_volatility(weights: np.ndarray) -> float:
        variance = float(weights @ covariance.to_numpy() @ weights)
        return float(np.sqrt(max(variance, 0.0)))

    constraints = [{"type": "eq", "fun": lambda weights: float(np.sum(weights) - 1)}]
    if target_return is not None and method == "target_return":
        constraints.append({"type": "ineq", "fun": lambda weights: portfolio_return(weights) - target_return})
    if max_volatility is not None:
        constraints.append({"type": "ineq", "fun": lambda weights: max_volatility - portfolio_volatility(weights)})

    if method == "max_sharpe":
        objective = lambda weights: -(portfolio_return(weights) - risk_free_rate) / max(portfolio_volatility(weights), 1e-12)
    elif method in {"min_volatility", "target_return"}:
        objective = portfolio_volatility
    else:
        raise ValueError(f"不支援的最佳化方法: {method}")

    initial = np.full(asset_count, 1 / asset_count)
    result = optimize.minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=[(0.0, max_weight)] * asset_count,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    if not result.success:
        raise InsufficientDataError(f"最佳化約束無可行解: {result.message}")

    weights = np.clip(result.x, 0, max_weight)
    weights = weights / weights.sum()
    expected_return = portfolio_return(weights)
    volatility = portfolio_volatility(weights)
    sharpe = (expected_return - risk_free_rate) / volatility if volatility > 0 else None
    return {
        "optimized_weights": {symbol: float(weight) for symbol, weight in zip(symbols, weights)},
        "expected_annual_return": expected_return,
        "expected_volatility": volatility,
        "sharpe_ratio": float(sharpe) if sharpe is not None else None,
        "asset_expected_returns": {symbol: float(expected_returns[symbol]) for symbol in symbols},
        "annualized_covariance": {row: {column: float(covariance.loc[row, column]) for column in symbols} for row in symbols},
    }


def calculate_pair_statistics(prices: pd.DataFrame, entry_zscore: float) -> List[Dict[str, object]]:
    """Calculate observed log-price spread statistics for every symbol pair."""
    if len(prices) < MIN_RETURN_OBSERVATIONS:
        raise InsufficientDataError("配對分析需要至少 60 筆共同價格")

    results = []
    columns = list(prices.columns)
    for left_index, left_symbol in enumerate(columns):
        for right_symbol in columns[left_index + 1 :]:
            left = np.log(prices[left_symbol].astype(float))
            right = np.log(prices[right_symbol].astype(float))
            hedge_ratio, intercept = np.polyfit(right.to_numpy(), left.to_numpy(), 1)
            spread = left - (hedge_ratio * right + intercept)
            spread_std = float(spread.std(ddof=1))
            if not np.isfinite(spread_std) or spread_std <= 0:
                continue
            z_score = float((spread.iloc[-1] - spread.mean()) / spread_std)
            correlation = float(left.diff().corr(right.diff()))
            results.append(
                {
                    "left_symbol": left_symbol,
                    "right_symbol": right_symbol,
                    "hedge_ratio": float(hedge_ratio),
                    "current_spread": float(spread.iloc[-1]),
                    "mean_spread": float(spread.mean()),
                    "spread_std": spread_std,
                    "z_score": z_score,
                    "correlation": correlation,
                    "threshold_exceeded": abs(z_score) >= entry_zscore,
                    "observations": int(len(spread)),
                }
            )
    return results
