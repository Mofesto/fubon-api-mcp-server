#!/usr/bin/env python3
"""Read-only quantitative analysis backed exclusively by Fubon data."""

from __future__ import annotations

import datetime
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
from fubon_neo.sdk import FubonSDK
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field, field_validator

from . import indicators
from .quant_analysis import (
    MIN_RETURN_OBSERVATIONS,
    InsufficientDataError,
    build_price_matrix,
    build_return_matrix,
    calculate_pair_statistics,
    calculate_var_metrics,
    optimize_long_only_portfolio,
)
from .utils import validate_and_get_account


class AnalysisSourceError(RuntimeError):
    """Raised when an upstream Fubon query fails."""


class AnalysisService:
    """Fubon-backed, read-only indicators and portfolio analysis tools."""

    def __init__(self, mcp: MCPServer, sdk: FubonSDK, accounts: List[str], reststock=None, restfutopt=None):
        self.mcp = mcp
        self.sdk = sdk
        self.accounts = accounts
        self.reststock = reststock
        self.restfutopt = restfutopt
        self.logger = logging.getLogger(__name__)
        self._register_tools()

    def _register_tools(self):
        self.mcp.tool()(self.calculate_portfolio_var)
        self.mcp.tool()(self.run_portfolio_stress_test)
        self.mcp.tool()(self.optimize_portfolio_allocation)
        self.mcp.tool()(self.calculate_performance_attribution)
        self.mcp.tool()(self.detect_arbitrage_opportunities)
        self.mcp.tool()(self.generate_market_sentiment_index)
        self.mcp.tool()(self.analyze_stock)

    @staticmethod
    def _error(message: str) -> dict:
        return {"status": "error", "data": None, "message": message}

    @staticmethod
    def _insufficient(message: str) -> dict:
        return {"status": "error", "data": None, "message": f"insufficient_data: {message}"}

    @classmethod
    def _to_dict(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime.date, datetime.datetime, pd.Timestamp)):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: cls._to_dict(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._to_dict(item) for item in value]
        if hasattr(value, "model_dump"):
            return cls._to_dict(value.model_dump())
        if hasattr(value, "dict") and callable(value.dict):
            return cls._to_dict(value.dict())
        if isinstance(value, Enum):
            return value.name
        if hasattr(value, "__dict__"):
            return {
                key: cls._to_dict(item) for key, item in vars(value).items() if not key.startswith("_") and not callable(item)
            }
        return str(value)

    @classmethod
    def _result_records(cls, result: Any, source_name: str) -> List[Dict[str, Any]]:
        if result is None:
            raise AnalysisSourceError(f"{source_name} 未回傳資料")
        if hasattr(result, "is_success") and not result.is_success:
            raise AnalysisSourceError(getattr(result, "message", None) or f"{source_name} 查詢失敗")

        payload = getattr(result, "data", result)
        payload = cls._to_dict(payload)
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if payload is None:
            return []
        if isinstance(payload, dict):
            return [payload]
        if not isinstance(payload, list):
            raise AnalysisSourceError(f"{source_name} 回傳格式不符")
        return [item for item in payload if isinstance(item, dict)]

    def _query_records_with_retry(self, query, source_name: str) -> List[Dict[str, Any]]:
        """Run a read-only SDK query with bounded retry for broker flow control."""
        for attempt in range(4):
            try:
                return self._result_records(query(), source_name)
            except Exception as exc:
                message = str(exc).lower()
                is_rate_limited = "流量控管" in message or "rate limit" in message or "too many requests" in message
                if not is_rate_limited or attempt == 3:
                    raise
                time.sleep(1.0 * (2**attempt))
        raise AnalysisSourceError(f"{source_name} 查詢重試耗盡")

    @staticmethod
    def _normalize_history(records: List[Dict[str, Any]], close_candidates: List[str]) -> pd.DataFrame:
        normalized = []
        for record in records:
            date_value = record.get("date") or record.get("tradeDate") or record.get("time")
            close_value = next((record.get(field) for field in close_candidates if record.get(field) is not None), None)
            if date_value is None or close_value is None:
                continue
            normalized.append(
                {
                    "date": date_value,
                    "open": record.get("open", record.get("openPrice", close_value)),
                    "high": record.get("high", record.get("highPrice", close_value)),
                    "low": record.get("low", record.get("lowPrice", close_value)),
                    "close": close_value,
                    "volume": record.get("volume", record.get("tradeVolume", 0)),
                }
            )
        frame = pd.DataFrame(normalized)
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        for column in ["open", "high", "low", "close", "volume"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame.dropna(subset=["date", "close"]).drop_duplicates("date", keep="last").sort_values("date")

    def _get_stock_history(
        self, symbol: str, lookback_days: int, minimum_rows: int = MIN_RETURN_OBSERVATIONS + 1
    ) -> pd.DataFrame:
        if self.reststock is None:
            raise AnalysisSourceError("證券行情服務未初始化，請先登入系統")

        calendar_days = min(max(lookback_days * 2, 120), 365)
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=calendar_days)
        result = self.reststock.historical.candles(
            symbol=symbol,
            **{"from": start_date.isoformat(), "to": end_date.isoformat()},
        )
        records = self._result_records(result, f"{symbol} 證券歷史行情")
        frame = self._normalize_history(records, ["close", "closePrice", "lastPrice"])
        if len(frame) < minimum_rows:
            raise InsufficientDataError(f"{symbol} 需要至少 {minimum_rows} 筆正式歷史價格，目前 {len(frame)} 筆")

        latest_date = frame["date"].max().date()
        age = (end_date - latest_date).days
        if age > 10:
            raise InsufficientDataError(f"{symbol} 最新行情日期 {latest_date.isoformat()}，已超過 10 天")
        return frame.tail(lookback_days + 1).reset_index(drop=True)

    def _get_futopt_history(self, symbol: str, lookback_days: int) -> pd.DataFrame:
        if self.restfutopt is None:
            raise AnalysisSourceError("期貨/選擇權行情服務未初始化，請先登入系統")

        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=min(max(lookback_days * 2, 120), 365))
        result = self.restfutopt.historical.daily(
            symbol=symbol,
            **{"from": start_date.isoformat(), "to": end_date.isoformat()},
        )
        records = self._result_records(result, f"{symbol} 期貨歷史行情")
        frame = self._normalize_history(records, ["close", "closePrice", "settlementPrice"])
        if len(frame) < MIN_RETURN_OBSERVATIONS + 1:
            raise InsufficientDataError(
                f"{symbol} 需要至少 {MIN_RETURN_OBSERVATIONS + 1} 筆正式期貨歷史價格，目前 {len(frame)} 筆"
            )
        latest_date = frame["date"].max().date()
        if (end_date - latest_date).days > 10:
            raise InsufficientDataError(f"{symbol} 最新期貨行情日期 {latest_date.isoformat()}，已超過 10 天")
        return frame.tail(lookback_days + 1).reset_index(drop=True)

    @staticmethod
    def _quote_price(quote: Any) -> float:
        payload = AnalysisService._to_dict(getattr(quote, "data", quote))
        if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
            payload = payload["data"]
        if not isinstance(payload, dict):
            return 0.0
        for field in ["lastPrice", "closePrice", "price", "referencePrice"]:
            value = payload.get(field)
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if price > 0:
                return price
        return 0.0

    def _get_portfolio_data(self, account_obj: Any, account: str) -> Dict[str, Any]:
        inventories = self._query_records_with_retry(lambda: self.sdk.accounting.inventories(account=account_obj), "庫存")
        unrealized = self._query_records_with_retry(
            lambda: self.sdk.accounting.unrealized_gains_and_loses(account=account_obj), "未實現損益"
        )

        pnl_by_symbol: Dict[str, Dict[str, float]] = {}
        for item in unrealized:
            symbol = str(item.get("stock_no", ""))
            if not symbol:
                continue
            entry = pnl_by_symbol.setdefault(symbol, {"unrealized_pnl": 0.0, "cost_value": 0.0, "quantity": 0.0})
            quantity = float(item.get("today_qty") or 0)
            cost_price = float(item.get("cost_price") or 0)
            entry["unrealized_pnl"] += float(item.get("unrealized_profit") or 0) + float(item.get("unrealized_loss") or 0)
            entry["cost_value"] += quantity * cost_price
            entry["quantity"] += quantity

        quantities: Dict[str, float] = {}
        for item in inventories:
            symbol = str(item.get("stock_no", ""))
            if not symbol:
                continue
            quantity = float(item.get("today_qty") or 0)
            odd = item.get("odd") if isinstance(item.get("odd"), dict) else {}
            quantity += float(odd.get("today_qty") or 0)
            quantities[symbol] = quantities.get(symbol, 0.0) + quantity

        positions = []
        missing_prices = []
        for symbol, quantity in quantities.items():
            if quantity == 0:
                continue
            if self.reststock is None:
                raise AnalysisSourceError("證券行情服務未初始化，無法取得持倉市價")
            quote = self.reststock.intraday.quote(symbol=symbol)
            market_price = self._quote_price(quote)
            if market_price <= 0:
                missing_prices.append(symbol)
                continue
            pnl = pnl_by_symbol.get(symbol, {})
            pnl_quantity = float(pnl.get("quantity", 0))
            cost_price = float(pnl.get("cost_value", 0)) / pnl_quantity if pnl_quantity else None
            positions.append(
                {
                    "stock_no": symbol,
                    "quantity": quantity,
                    "cost_price": cost_price,
                    "market_price": market_price,
                    "market_value": market_price * quantity,
                    "unrealized_pnl": float(pnl.get("unrealized_pnl", 0)),
                }
            )

        if missing_prices:
            raise InsufficientDataError(f"以下持倉無法取得正式市價: {', '.join(missing_prices)}")
        return {
            "account": account,
            "inventory": positions,
            "total_positions": len(positions),
            "as_of": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
        }

    @staticmethod
    def _portfolio_weights(positions: List[Dict[str, Any]]) -> tuple[List[str], np.ndarray, float]:
        positive = [position for position in positions if float(position.get("market_value") or 0) > 0]
        total_value = sum(float(position["market_value"]) for position in positive)
        if not positive or total_value <= 0:
            raise InsufficientDataError("帳戶目前沒有可估值的證券持倉")
        symbols = [str(position["stock_no"]) for position in positive]
        weights = np.array([float(position["market_value"]) / total_value for position in positive])
        return symbols, weights, total_value

    def calculate_portfolio_var(self, args: Dict) -> dict:
        """Calculate portfolio VaR/CVaR from current holdings and Fubon historical prices."""
        try:
            validated = CalculatePortfolioVaRArgs(**args)
            account_obj, error = validate_and_get_account(validated.account)
            if error:
                return self._error(error)
            portfolio = self._get_portfolio_data(account_obj, validated.account)
            symbols, weights, total_value = self._portfolio_weights(portfolio["inventory"])
            returns, coverage = build_return_matrix(symbols, validated.lookback_days, self._get_stock_history)
            portfolio_returns = returns[symbols].dot(weights)
            metrics = calculate_var_metrics(
                portfolio_returns,
                total_value,
                validated.confidence_level,
                validated.time_horizon,
                validated.method,
                validated.simulations,
            )
            return {
                "status": "success",
                "data": {
                    "portfolio_value": total_value,
                    "confidence_level": validated.confidence_level,
                    "time_horizon": validated.time_horizon,
                    "method": validated.method,
                    "lookback_days": validated.lookback_days,
                    **metrics,
                    "data_source": "fubon_accounting+fubon_marketdata",
                    "as_of": portfolio["as_of"],
                    "coverage": coverage.__dict__,
                },
                "message": f"已使用 {coverage.observations} 筆正式共同日報酬計算 VaR/CVaR",
            }
        except InsufficientDataError as exc:
            return self._insufficient(str(exc))
        except (AnalysisSourceError, ValueError) as exc:
            return self._error(f"計算投資組合 VaR 失敗: {exc}")
        except Exception as exc:
            self.logger.exception("計算投資組合 VaR 失敗")
            return self._error(f"計算投資組合 VaR 失敗: {exc}")

    def run_portfolio_stress_test(self, args: Dict) -> dict:
        """Apply explicit caller-supplied price shocks to current Fubon holdings."""
        try:
            validated = RunPortfolioStressTestArgs(**args)
            account_obj, error = validate_and_get_account(validated.account)
            if error:
                return self._error(error)
            portfolio = self._get_portfolio_data(account_obj, validated.account)
            positions = portfolio["inventory"]
            _, _, total_value = self._portfolio_weights(positions)

            results = []
            for scenario in validated.scenarios:
                position_results = []
                total_change = 0.0
                for position in positions:
                    symbol = position["stock_no"]
                    applied_change = scenario.symbol_changes.get(symbol, scenario.equity_change)
                    market_value = float(position["market_value"])
                    projected_change = market_value * applied_change
                    total_change += projected_change
                    position_results.append(
                        {
                            "stock_no": symbol,
                            "current_value": market_value,
                            "applied_price_change": applied_change,
                            "projected_value_change": projected_change,
                            "projected_value": market_value + projected_change,
                        }
                    )
                results.append(
                    {
                        "scenario": scenario.name,
                        "total_portfolio_value": total_value,
                        "total_projected_change": total_change,
                        "projected_change_percentage": total_change / total_value,
                        "projected_portfolio_value": total_value + total_change,
                        "position_results": position_results,
                    }
                )

            return {
                "status": "success",
                "data": {
                    "stress_test_results": results,
                    "scenarios_tested": len(results),
                    "data_source": "fubon_accounting+fubon_marketdata",
                    "as_of": portfolio["as_of"],
                    "assumption_source": "caller_supplied_price_shocks",
                },
                "message": f"已對正式持倉套用 {len(results)} 個明確價格衝擊情境",
            }
        except InsufficientDataError as exc:
            return self._insufficient(str(exc))
        except (AnalysisSourceError, ValueError) as exc:
            return self._error(f"執行壓力測試失敗: {exc}")
        except Exception as exc:
            self.logger.exception("執行壓力測試失敗")
            return self._error(f"執行壓力測試失敗: {exc}")

    def optimize_portfolio_allocation(self, args: Dict) -> dict:
        """Optimize a long-only portfolio from Fubon historical returns."""
        try:
            validated = OptimizePortfolioAllocationArgs(**args)
            account_obj, error = validate_and_get_account(validated.account)
            if error:
                return self._error(error)
            portfolio = self._get_portfolio_data(account_obj, validated.account)
            positions = portfolio["inventory"]
            held_symbols = [position["stock_no"] for position in positions]
            symbols = list(dict.fromkeys(validated.symbols or held_symbols))
            if not symbols:
                raise InsufficientDataError("帳戶沒有持倉；請明確提供至少兩個 symbols 作為最佳化範圍")

            returns, coverage = build_return_matrix(symbols, validated.lookback_days, self._get_stock_history)
            optimized = optimize_long_only_portfolio(
                returns,
                validated.optimization_method,
                validated.risk_free_rate,
                validated.target_return,
                validated.max_volatility,
                validated.max_weight,
            )
            current_values = {position["stock_no"]: float(position["market_value"]) for position in positions}
            current_total = sum(current_values.get(symbol, 0.0) for symbol in symbols)
            current_weights = {
                symbol: current_values.get(symbol, 0.0) / current_total if current_total > 0 else 0.0 for symbol in symbols
            }
            return {
                "status": "success",
                "data": {
                    "current_weights": current_weights,
                    **optimized,
                    "optimization_method": validated.optimization_method,
                    "risk_free_rate": validated.risk_free_rate,
                    "target_return": validated.target_return,
                    "max_volatility": validated.max_volatility,
                    "max_weight": validated.max_weight,
                    "data_source": "fubon_accounting+fubon_marketdata",
                    "as_of": portfolio["as_of"],
                    "coverage": coverage.__dict__,
                },
                "message": f"已使用正式歷史報酬完成 {validated.optimization_method} 最佳化",
            }
        except InsufficientDataError as exc:
            return self._insufficient(str(exc))
        except (AnalysisSourceError, ValueError) as exc:
            return self._error(f"投資組合最佳化失敗: {exc}")
        except Exception as exc:
            self.logger.exception("投資組合最佳化失敗")
            return self._error(f"投資組合最佳化失敗: {exc}")

    @staticmethod
    def _period_dates(period: str) -> tuple[datetime.date, datetime.date, int]:
        end_date = datetime.date.today()
        offsets = {"1M": (1, 23), "3M": (3, 66), "6M": (6, 132), "1Y": (12, 252)}
        if period == "YTD":
            start_date = datetime.date(end_date.year, 1, 1)
            lookback = max(2, int((end_date - start_date).days * 0.72))
        else:
            months, lookback = offsets[period]
            start_date = (pd.Timestamp(end_date) - pd.DateOffset(months=months)).date()
        return start_date, end_date, lookback

    def _fetch_filled_history(
        self, account_obj: Any, start_date: datetime.date, end_date: datetime.date
    ) -> List[Dict[str, Any]]:
        cursor = start_date
        records: List[Dict[str, Any]] = []
        seen = set()
        while cursor <= end_date:
            chunk_end = min(cursor + datetime.timedelta(days=29), end_date)
            chunk_records = self._query_records_with_retry(
                lambda: self.sdk.stock.filled_history(
                    account=account_obj,
                    start_date=cursor.strftime("%Y%m%d"),
                    end_date=chunk_end.strftime("%Y%m%d"),
                ),
                "歷史成交",
            )

            for record in chunk_records:
                key = (
                    record.get("date"),
                    record.get("order_no"),
                    record.get("filled_no"),
                    record.get("stock_no"),
                    record.get("filled_time"),
                )
                if key not in seen:
                    seen.add(key)
                    records.append(record)
            cursor = chunk_end + datetime.timedelta(days=1)
        return records

    @staticmethod
    def _aggregate_fills(fills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_symbol: Dict[str, Dict[str, Any]] = {}
        for fill in fills:
            symbol = str(fill.get("stock_no", ""))
            if not symbol:
                continue
            quantity = float(fill.get("filled_qty") or 0)
            price = float(fill.get("filled_price") or fill.get("filled_avg_price") or 0)
            action_value = fill.get("buy_sell")
            action = str(action_value.get("name") if isinstance(action_value, dict) else action_value).lower()
            entry = by_symbol.setdefault(
                symbol,
                {
                    "stock_no": symbol,
                    "buy_quantity": 0.0,
                    "sell_quantity": 0.0,
                    "buy_notional": 0.0,
                    "sell_notional": 0.0,
                    "fill_count": 0,
                },
            )
            if "sell" in action:
                entry["sell_quantity"] += quantity
                entry["sell_notional"] += quantity * price
            else:
                entry["buy_quantity"] += quantity
                entry["buy_notional"] += quantity * price
            entry["fill_count"] += 1
        for entry in by_symbol.values():
            entry["net_trading_cash_flow"] = entry["sell_notional"] - entry["buy_notional"]
        return sorted(by_symbol.values(), key=lambda item: item["stock_no"])

    def calculate_performance_attribution(self, args: Dict) -> dict:
        """Report source-backed fill cash flows and current PnL contribution without invented returns."""
        try:
            validated = CalculatePerformanceAttributionArgs(**args)
            account_obj, error = validate_and_get_account(validated.account)
            if error:
                return self._error(error)
            start_date, end_date, benchmark_lookback = self._period_dates(validated.period)
            fills = self._fetch_filled_history(account_obj, start_date, end_date)
            fill_contributions = self._aggregate_fills(fills)
            portfolio = self._get_portfolio_data(account_obj, validated.account)
            positions = portfolio["inventory"]
            if not fills and not positions:
                raise InsufficientDataError("指定期間沒有成交，帳戶目前也沒有持倉，無法產生損益貢獻")

            benchmark = self._get_stock_history(validated.benchmark, benchmark_lookback, minimum_rows=2)
            benchmark_return = float(benchmark["close"].iloc[-1] / benchmark["close"].iloc[0] - 1)
            current_pnl = [
                {
                    "stock_no": position["stock_no"],
                    "quantity": position["quantity"],
                    "market_value": position["market_value"],
                    "unrealized_pnl": position["unrealized_pnl"],
                }
                for position in positions
            ]
            return {
                "status": "success",
                "data": {
                    "period": validated.period,
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "benchmark_symbol": validated.benchmark,
                    "benchmark_price_return": benchmark_return,
                    "fill_cash_flow_contribution": fill_contributions,
                    "current_unrealized_pnl_contribution": current_pnl,
                    "fill_count": len(fills),
                    "data_source": "fubon_filled_history+fubon_accounting+fubon_marketdata",
                    "as_of": portfolio["as_of"],
                    "unavailable_metrics": [
                        "portfolio_return",
                        "excess_return",
                        "brinson_allocation_effect",
                        "brinson_selection_effect",
                    ],
                    "limitation": "富邦 API 未提供期間起始淨值與完整入出金歷史，因此不推算帳戶報酬率或 Brinson 歸因。",
                },
                "message": "已完成正式成交現金流、目前未實現損益與基準價格報酬對照",
            }
        except InsufficientDataError as exc:
            return self._insufficient(str(exc))
        except (AnalysisSourceError, ValueError) as exc:
            return self._error(f"績效貢獻分析失敗: {exc}")
        except Exception as exc:
            self.logger.exception("績效貢獻分析失敗")
            return self._error(f"績效貢獻分析失敗: {exc}")

    def detect_arbitrage_opportunities(self, args: Dict) -> dict:
        """Calculate observed statistical and futures-calendar spreads from Fubon prices."""
        try:
            validated = DetectArbitrageOpportunitiesArgs(**args)
            result_data: Dict[str, Any] = {}
            coverage: Dict[str, Any] = {}
            if "statistical" in validated.arbitrage_types:
                if len(validated.symbols) < 2:
                    raise ValueError("statistical 分析至少需要兩個 symbols")
                prices, matrix_coverage = build_price_matrix(
                    validated.symbols, validated.lookback_days, self._get_stock_history
                )
                result_data["statistical_pairs"] = calculate_pair_statistics(prices, validated.entry_zscore)
                coverage["statistical"] = matrix_coverage.__dict__

            if "futures_calendar" in validated.arbitrage_types:
                if not validated.futures_pairs:
                    raise ValueError("futures_calendar 分析必須提供 futures_pairs")
                futures_results = []
                for pair in validated.futures_pairs:
                    prices, matrix_coverage = build_price_matrix(
                        [pair.near_symbol, pair.far_symbol], validated.lookback_days, self._get_futopt_history
                    )
                    spread = prices[pair.far_symbol] - prices[pair.near_symbol]
                    spread_std = float(spread.std(ddof=1))
                    if not np.isfinite(spread_std) or spread_std <= 0:
                        raise InsufficientDataError(f"{pair.near_symbol}/{pair.far_symbol} 價差沒有有效變異")
                    z_score = float((spread.iloc[-1] - spread.mean()) / spread_std)
                    futures_results.append(
                        {
                            "near_symbol": pair.near_symbol,
                            "far_symbol": pair.far_symbol,
                            "near_price": float(prices[pair.near_symbol].iloc[-1]),
                            "far_price": float(prices[pair.far_symbol].iloc[-1]),
                            "current_spread": float(spread.iloc[-1]),
                            "mean_spread": float(spread.mean()),
                            "spread_std": spread_std,
                            "z_score": z_score,
                            "threshold_exceeded": abs(z_score) >= validated.entry_zscore,
                            "observations": len(spread),
                        }
                    )
                    coverage[f"{pair.near_symbol}/{pair.far_symbol}"] = matrix_coverage.__dict__
                result_data["futures_calendar_spreads"] = futures_results

            threshold_count = sum(int(item["threshold_exceeded"]) for values in result_data.values() for item in values)
            return {
                "status": "success",
                "data": {
                    "arbitrage_types": validated.arbitrage_types,
                    **result_data,
                    "threshold_exceeded_count": threshold_count,
                    "entry_zscore": validated.entry_zscore,
                    "data_source": "fubon_marketdata",
                    "as_of": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
                    "coverage": coverage,
                    "limitation": "統計偏離不是保證獲利或可成交的套利機會。",
                },
                "message": f"已使用正式行情完成價差分析，{threshold_count} 組超過指定門檻",
            }
        except InsufficientDataError as exc:
            return self._insufficient(str(exc))
        except (AnalysisSourceError, ValueError) as exc:
            return self._error(f"價差分析失敗: {exc}")
        except Exception as exc:
            self.logger.exception("價差分析失敗")
            return self._error(f"價差分析失敗: {exc}")

    @staticmethod
    def _technical_sentiment(frame: pd.DataFrame) -> Dict[str, float]:
        close = frame["close"]
        rsi = indicators.calculate_rsi(close)
        macd = indicators.calculate_macd(close)
        bands = indicators.calculate_bollinger_bands(close)
        rsi_value = float(rsi.iloc[-1])
        histogram = float(macd["histogram"].iloc[-1])
        band_width = float(bands["upper"].iloc[-1] - bands["lower"].iloc[-1])
        band_position = float((close.iloc[-1] - bands["lower"].iloc[-1]) / band_width) if band_width else 0.5
        rsi_score = min(max(rsi_value / 100, 0), 1)
        macd_score = float(0.5 + 0.5 * np.tanh(histogram / max(abs(float(close.iloc[-1])) * 0.01, 1e-9)))
        band_score = min(max(band_position, 0), 1)
        return {
            "rsi": rsi_value,
            "macd_histogram": histogram,
            "bollinger_position": band_position,
            "score": float(np.mean([rsi_score, macd_score, band_score])),
        }

    @staticmethod
    def _volume_sentiment(frame: pd.DataFrame) -> Dict[str, float]:
        close = frame["close"]
        volume = frame["volume"]
        obv = indicators.calculate_obv(close, volume)
        recent_volume = float(volume.tail(5).mean())
        baseline_volume = float(volume.iloc[:-5].tail(20).mean()) if len(volume) > 5 else float(volume.mean())
        volume_ratio = recent_volume / baseline_volume if baseline_volume > 0 else 1.0
        price_return = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) >= 6 else 0.0
        obv_change = float(obv.iloc[-1] - obv.iloc[-6]) if len(obv) >= 6 else 0.0
        direction = np.sign(price_return) + np.sign(obv_change)
        score = float(0.5 + 0.25 * np.tanh(direction * max(volume_ratio, 0)))
        return {
            "recent_to_baseline_volume": volume_ratio,
            "five_day_price_return": price_return,
            "five_day_obv_change": obv_change,
            "score": min(max(score, 0), 1),
        }

    def generate_market_sentiment_index(self, args: Dict) -> dict:
        """Calculate technical/volume sentiment from explicitly selected Fubon symbols."""
        try:
            validated = GenerateMarketSentimentIndexArgs(**args)
            symbol_results = []
            for symbol in validated.symbols:
                frame = self._get_stock_history(
                    symbol, validated.lookback_period, minimum_rows=max(30, validated.lookback_period)
                )
                components: Dict[str, Any] = {}
                if "technical" in validated.index_components:
                    components["technical"] = self._technical_sentiment(frame)
                if "volume" in validated.index_components:
                    components["volume"] = self._volume_sentiment(frame)
                score = float(np.mean([component["score"] for component in components.values()]))
                symbol_results.append(
                    {
                        "symbol": symbol,
                        "score": score,
                        "components": components,
                        "latest_market_date": frame["date"].max().date().isoformat(),
                        "observations": len(frame),
                    }
                )

            overall = float(np.mean([result["score"] for result in symbol_results]))
            if overall >= 0.65:
                level = "技術與量能偏強"
            elif overall <= 0.35:
                level = "技術與量能偏弱"
            else:
                level = "技術與量能中性"
            return {
                "status": "success",
                "data": {
                    "overall_sentiment_index": overall,
                    "sentiment_level": level,
                    "components_requested": validated.index_components,
                    "symbols": symbol_results,
                    "lookback_period": validated.lookback_period,
                    "data_source": "fubon_marketdata",
                    "as_of": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
                    "limitation": "此指數僅反映所選標的的技術與成交量狀態，不代表新聞、社群或選擇權情緒。",
                },
                "message": f"已使用 {len(symbol_results)} 個指定標的的正式行情產生情緒指數",
            }
        except InsufficientDataError as exc:
            return self._insufficient(str(exc))
        except (AnalysisSourceError, ValueError) as exc:
            return self._error(f"市場情緒分析失敗: {exc}")
        except Exception as exc:
            self.logger.exception("市場情緒分析失敗")
            return self._error(f"市場情緒分析失敗: {exc}")

    def analyze_stock(self, args: Dict) -> dict:
        """Analyze one stock from fresh Fubon daily candles without executing orders."""
        try:
            validated = AnalyzeStockArgs(**args)
            frame = self._get_stock_history(validated.symbol, 120, minimum_rows=60)
            close = frame["close"]
            high = frame["high"]
            low = frame["low"]
            volume = frame["volume"]
            ma20 = indicators.calculate_sma(close, 20)
            ma60 = indicators.calculate_sma(close, 60)
            rsi = indicators.calculate_rsi(close)
            macd = indicators.calculate_macd(close)
            atr = indicators.calculate_atr(high, low, close)

            score = 0
            reasons = []
            if close.iloc[-1] > ma20.iloc[-1]:
                score += 1
                reasons.append("收盤價高於 20 日均線")
            else:
                score -= 1
                reasons.append("收盤價低於 20 日均線")
            if ma20.iloc[-1] > ma60.iloc[-1]:
                score += 1
                reasons.append("20 日均線高於 60 日均線")
            else:
                score -= 1
                reasons.append("20 日均線低於 60 日均線")
            if macd["histogram"].iloc[-1] > 0:
                score += 1
                reasons.append("MACD 柱狀體為正")
            else:
                score -= 1
                reasons.append("MACD 柱狀體為負")
            if rsi.iloc[-1] >= 70:
                score -= 1
                reasons.append("RSI 位於高檔")
            elif rsi.iloc[-1] <= 30:
                score += 1
                reasons.append("RSI 位於低檔")

            trend = "偏多" if score >= 2 else "偏空" if score <= -2 else "中性"
            return {
                "status": "success",
                "data": {
                    "symbol": validated.symbol,
                    "trend": trend,
                    "current_price": float(close.iloc[-1]),
                    "latest_market_date": frame["date"].max().date().isoformat(),
                    "indicators": {
                        "ma20": float(ma20.iloc[-1]),
                        "ma60": float(ma60.iloc[-1]),
                        "rsi": float(rsi.iloc[-1]),
                        "macd_histogram": float(macd["histogram"].iloc[-1]),
                        "atr": float(atr.iloc[-1]),
                    },
                    "support_resistance": {
                        "twenty_day_low": float(low.tail(20).min()),
                        "twenty_day_high": float(high.tail(20).max()),
                    },
                    "analysis": {
                        "signal": trend,
                        "confidence": min(abs(score) / 4, 1.0),
                        "reasons": reasons,
                    },
                    "data_source": "fubon_marketdata",
                    "as_of": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
                    "limitation": "技術分析不構成獲利保證或下單指示。",
                },
                "message": f"已使用正式行情完成 {validated.symbol} 技術分析：{trend}",
            }
        except InsufficientDataError as exc:
            return self._insufficient(str(exc))
        except (AnalysisSourceError, ValueError) as exc:
            return self._error(f"股票分析失敗: {exc}")
        except Exception as exc:
            self.logger.exception("股票分析失敗")
            return self._error(f"股票分析失敗: {exc}")


class AnalyzeStockArgs(BaseModel):
    symbol: str = Field(min_length=2, max_length=20)
    account: Optional[str] = None


class CalculatePortfolioVaRArgs(BaseModel):
    account: str
    confidence_level: float = Field(0.95, ge=0.8, le=0.999)
    time_horizon: int = Field(1, ge=1, le=30)
    method: Literal["historical", "parametric", "monte_carlo"] = "historical"
    lookback_days: int = Field(252, ge=MIN_RETURN_OBSERVATIONS, le=252)
    simulations: int = Field(10000, ge=1000, le=1_000_000)


class StressScenario(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    equity_change: float = Field(ge=-1.0, le=1.0)
    symbol_changes: Dict[str, float] = Field(default_factory=dict)

    @field_validator("symbol_changes")
    @classmethod
    def validate_symbol_changes(cls, changes: Dict[str, float]) -> Dict[str, float]:
        invalid = [symbol for symbol, change in changes.items() if not -1.0 <= change <= 1.0]
        if invalid:
            raise ValueError(f"symbol_changes 必須介於 -1 與 1: {', '.join(invalid)}")
        return changes


class RunPortfolioStressTestArgs(BaseModel):
    account: str
    scenarios: List[StressScenario] = Field(min_length=1, max_length=20)


class OptimizePortfolioAllocationArgs(BaseModel):
    account: str
    symbols: Optional[List[str]] = Field(default=None, min_length=2, max_length=30)
    target_return: Optional[float] = Field(None, ge=-1.0, le=2.0)
    max_volatility: Optional[float] = Field(None, gt=0.0, le=2.0)
    optimization_method: Literal["max_sharpe", "min_volatility", "target_return"] = "max_sharpe"
    lookback_days: int = Field(252, ge=MIN_RETURN_OBSERVATIONS, le=252)
    risk_free_rate: float = Field(0.0, ge=-0.2, le=0.5)
    max_weight: float = Field(1.0, gt=0.0, le=1.0)


class CalculatePerformanceAttributionArgs(BaseModel):
    account: str
    benchmark: str = Field("IX0001", min_length=2, max_length=20)
    period: Literal["1M", "3M", "6M", "1Y", "YTD"] = "3M"


class FuturesPair(BaseModel):
    near_symbol: str = Field(min_length=2, max_length=30)
    far_symbol: str = Field(min_length=2, max_length=30)


class DetectArbitrageOpportunitiesArgs(BaseModel):
    symbols: List[str] = Field(default_factory=list, max_length=20)
    futures_pairs: List[FuturesPair] = Field(default_factory=list, max_length=10)
    arbitrage_types: List[Literal["statistical", "futures_calendar"]] = Field(
        default_factory=lambda: ["statistical"], min_length=1
    )
    lookback_days: int = Field(252, ge=MIN_RETURN_OBSERVATIONS, le=252)
    entry_zscore: float = Field(2.0, ge=1.0, le=5.0)


class GenerateMarketSentimentIndexArgs(BaseModel):
    symbols: List[str] = Field(min_length=1, max_length=20)
    index_components: List[Literal["technical", "volume"]] = Field(
        default_factory=lambda: ["technical", "volume"], min_length=1
    )
    lookback_period: int = Field(60, ge=30, le=252)
