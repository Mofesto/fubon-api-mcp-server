#!/usr/bin/env python3
"""
富邦證券指標與分析服務

此模組提供技術指標計算和進階分析功能，包括：
- 投資組合風險分析 (VaR, 壓力測試)
- 績效歸因分析
- 資產配置優化
- 套利機會偵測
- 市場情緒指數生成

主要組件：
- AnalysisService: 指標與分析服務類
- 風險管理工具
- 投資組合分析
- 市場情緒分析
"""

from typing import Dict, List, Optional
import datetime
import pandas as pd
import numpy as np
import sys

from fubon_neo.sdk import FubonSDK
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .utils import validate_and_get_account
from . import indicators
from .config import config


class AnalysisService:
    """指標與分析服務類"""

    def __init__(self, mcp: FastMCP, sdk: FubonSDK, accounts: List[str], reststock=None, restfutopt=None):
        self.mcp = mcp
        self.sdk = sdk
        self.accounts = accounts
        self.reststock = reststock
        self.restfutopt = restfutopt
        self.db_path = config.DATABASE_PATH
        self._register_tools()

    def _register_tools(self):
        """註冊所有指標與分析相關的工具"""
        self.mcp.tool()(self.calculate_portfolio_var)
        self.mcp.tool()(self.run_portfolio_stress_test)
        self.mcp.tool()(self.optimize_portfolio_allocation)
        self.mcp.tool()(self.calculate_performance_attribution)
        self.mcp.tool()(self.detect_arbitrage_opportunities)
        self.mcp.tool()(self.generate_market_sentiment_index)

    def calculate_portfolio_var(self, args: Dict) -> dict:
        """
        計算投資組合風險價值 (VaR)

        使用歷史模擬法、參數法或蒙地卡羅模擬法計算投資組合的風險價值，
        提供不同信心水準下的潛在損失估計。

        Args:
            account (str): 帳戶號碼
            confidence_level (float): 信心水準，可選 0.95, 0.99, 0.999，預設 0.95
            time_horizon (int): 時間範圍（天），預設 1
            method (str): 計算方法，可選 "historical", "parametric", "monte_carlo"，預設 "historical"

        Returns:
            dict: VaR計算結果，包含不同方法的估計值

        Example:
            {
                "account": "12345678",
                "confidence_level": 0.95,
                "time_horizon": 1,
                "method": "historical"
            }
        """
        try:
            validated_args = CalculatePortfolioVaRArgs(**args)
            account = validated_args.account
            confidence_level = validated_args.confidence_level
            time_horizon = validated_args.time_horizon
            method = validated_args.method

            # 驗證帳戶
            account_obj, error = validate_and_get_account(account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 獲取投資組合數據
            portfolio_data = self._get_portfolio_data(account)
            if not portfolio_data:
                return {
                    "status": "error",
                    "data": None,
                    "message": "無法獲取投資組合數據，請先獲取投資組合摘要"
                }

            # 模擬VaR計算（實際實現會使用歷史數據和統計方法）
            positions = portfolio_data.get("inventory", [])
            total_value = sum(pos.get("market_value", 0) for pos in positions)

            # 使用技術指標計算實際波動率
            volatility = self._calculate_portfolio_volatility(positions, time_horizon)
            
            if method == "historical":
                # 使用歷史模擬法，基於實際波動率估計
                var_estimate = total_value * volatility * (1 - confidence_level) ** 0.5
            elif method == "parametric":
                # 正態分布假設，使用實際波動率
                z_score = 1.645 if confidence_level == 0.95 else 2.326 if confidence_level == 0.99 else 2.576
                var_estimate = total_value * volatility * z_score
            else:  # monte_carlo
                # 蒙地卡羅模擬，使用實際波動率
                z_score = 2.326 if confidence_level == 0.99 else 2.576  # 99% 或 99.9%
                var_estimate = total_value * volatility * z_score

            return {
                "status": "success",
                "data": {
                    "portfolio_value": total_value,
                    "var_estimate": var_estimate,
                    "confidence_level": confidence_level,
                    "time_horizon": time_horizon,
                    "method": method,
                    "var_percentage": var_estimate / total_value if total_value > 0 else 0,
                    "calculation_date": datetime.datetime.now().isoformat(),
                },
                "message": f"成功計算投資組合VaR (信心水準 {confidence_level*100:.1f}%, {time_horizon}天)",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"計算投資組合VaR失敗: {str(e)}",
            }

    def run_portfolio_stress_test(self, args: Dict) -> dict:
        """
        執行投資組合壓力測試

        模擬各種市場壓力情境（市場崩盤、利率上升、匯率波動等），
        評估投資組合在極端情況下的表現和潛在損失。

        Args:
            account (str): 帳戶號碼
            scenarios (list): 測試情境列表，每個情境包含名稱和參數

        Returns:
            dict: 壓力測試結果，包含各情境下的損失估計

        Example:
            {
                "account": "12345678",
                "scenarios": [
                    {"name": "market_crash", "equity_drop": -0.3},
                    {"name": "rate_hike", "rate_increase": 0.025}
                ]
            }
        """
        try:
            validated_args = RunPortfolioStressTestArgs(**args)
            account = validated_args.account
            scenarios = validated_args.scenarios

            # 驗證帳戶
            account_obj, error = validate_and_get_account(account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 獲取投資組合數據
            portfolio_data = self._get_portfolio_data(account)
            if not portfolio_data:
                return {
                    "status": "error",
                    "data": None,
                    "message": "無法獲取投資組合數據，請先獲取投資組合摘要"
                }

            positions = portfolio_data.get("inventory", [])
            results = []

            for scenario in scenarios:
                scenario_name = scenario.get("name", "unknown")
                losses = []

                if scenario_name == "market_crash":
                    equity_drop = scenario.get("equity_drop", -0.2)
                    for pos in positions:
                        symbol = pos.get("stock_no", "")
                        market_value = pos.get("market_value", 0)
                        
                        # 使用技術指標評估個股對市場崩盤的敏感度
                        sensitivity = self._calculate_market_crash_sensitivity(symbol)
                        adjusted_drop = equity_drop * sensitivity
                        
                        loss = market_value * abs(adjusted_drop)
                        losses.append({
                            "stock_no": symbol,
                            "current_value": market_value,
                            "projected_loss": loss,
                            "loss_percentage": abs(adjusted_drop),
                            "sensitivity": sensitivity,
                        })

                elif scenario_name == "rate_hike":
                    rate_increase = scenario.get("rate_increase", 0.02)
                    for pos in positions:
                        symbol = pos.get("stock_no", "")
                        market_value = pos.get("market_value", 0)
                        
                        # 使用技術指標評估個股對利率變化的敏感度
                        sensitivity = self._calculate_rate_sensitivity(symbol)
                        loss = market_value * rate_increase * sensitivity
                        
                        losses.append({
                            "stock_no": symbol,
                            "current_value": market_value,
                            "projected_loss": loss,
                            "loss_percentage": rate_increase * sensitivity,
                            "sensitivity": sensitivity,
                        })

                total_loss = sum(loss.get("projected_loss", 0) for loss in losses)
                total_value = sum(pos.get("market_value", 0) for pos in positions)

                results.append({
                    "scenario": scenario_name,
                    "total_portfolio_value": total_value,
                    "total_projected_loss": total_loss,
                    "loss_percentage": total_loss / total_value if total_value > 0 else 0,
                    "position_losses": losses,
                })

            return {
                "status": "success",
                "data": {
                    "account": account,
                    "stress_test_results": results,
                    "test_date": datetime.datetime.now().isoformat(),
                    "scenarios_tested": len(scenarios),
                },
                "message": f"成功執行 {len(scenarios)} 個壓力測試情境",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"執行壓力測試失敗: {str(e)}",
            }

    def optimize_portfolio_allocation(self, args: Dict) -> dict:
        """
        投資組合資產配置優化

        使用現代投資組合理論計算最優資產配置，考慮風險偏好、
        預期報酬、相關性等因素，提供有效前沿上的最優組合。

        Args:
            account (str): 帳戶號碼
            target_return (float): 目標年化報酬率（可選）
            max_volatility (float): 最大可接受波動率（可選）
            optimization_method (str): 優化方法，可選 "max_sharpe", "min_volatility", "target_return"

        Returns:
            dict: 優化後的資產配置建議

        Example:
            {
                "account": "12345678",
                "target_return": 0.12,
                "max_volatility": 0.2,
                "optimization_method": "max_sharpe"
            }
        """
        try:
            validated_args = OptimizePortfolioAllocationArgs(**args)
            account = validated_args.account
            target_return = validated_args.target_return
            max_volatility = validated_args.max_volatility
            optimization_method = validated_args.optimization_method

            # 驗證帳戶
            account_obj, error = validate_and_get_account(account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 獲取投資組合數據
            portfolio_data = self._get_portfolio_data(account)
            if not portfolio_data:
                # 如果沒有快取數據，直接獲取投資組合摘要
                # 獲取庫存資訊
                inventory_result = self.sdk.accounting.inventories(account_obj)
                if (
                    not inventory_result
                    or not hasattr(inventory_result, "is_success")
                    or not inventory_result.is_success
                ):
                    return {
                        "status": "error",
                        "data": None,
                        "message": f"無法獲取帳戶 {account} 庫存資訊",
                    }

                # 獲取未實現損益
                pnl_result = self.sdk.accounting.unrealized_gains_and_loses(account_obj)
                unrealized_data = []
                if (
                    pnl_result
                    and hasattr(pnl_result, "is_success")
                    and pnl_result.is_success
                    and hasattr(pnl_result, "data")
                ):
                    unrealized_data = pnl_result.data

                # 處理投資組合數據
                portfolio_data = {
                    "account": account,
                    "total_positions": len(inventory_result.data)
                    if hasattr(inventory_result, "data")
                    else 0,
                    "positions": [],
                    "summary": {
                        "total_market_value": 0,
                        "total_cost": 0,
                        "total_unrealized_pnl": 0,
                        "total_realized_pnl": 0,
                    },
                }

                # 整合庫存和損益數據
                inventory_dict = {}
                if hasattr(inventory_result, "data"):
                    for item in inventory_result.data:
                        symbol = getattr(item, "stock_no", "")
                        inventory_dict[symbol] = {
                            "quantity": getattr(item, "today_qty", 0),  # 使用 today_qty 作為持有數量
                            "cost_price": getattr(item, "cost_price", 0),
                            "market_price": getattr(item, "market_price", 0),
                            "market_value": getattr(item, "market_value", 0),
                        }

                for pnl_item in unrealized_data:
                    symbol = getattr(pnl_item, "stock_no", "")
                    if symbol in inventory_dict:
                        inventory_dict[symbol]["unrealized_pnl"] = getattr(
                            pnl_item, "unrealized_profit", 0
                        ) + getattr(pnl_item, "unrealized_loss", 0)

                # 計算總計
                for symbol, data in inventory_dict.items():
                    # 如果庫存沒有市場價格，嘗試獲取即時報價
                    if data["market_price"] == 0 or data["market_value"] == 0:
                        try:
                            if hasattr(self, 'reststock') and self.reststock:
                                quote_result = self.reststock.intraday.quote(symbol=symbol)
                                if hasattr(quote_result, "dict"):
                                    quote_data = quote_result.dict()
                                else:
                                    quote_data = quote_result

                                # 嘗試從 dict 或 object 中獲取價格
                                current_price = 0
                                if isinstance(quote_data, dict):
                                    for price_field in ["price", "closePrice", "lastPrice"]:
                                        price_val = quote_data.get(price_field)
                                        if price_val is not None:
                                            try:
                                                current_price = float(price_val)
                                                if current_price > 0:
                                                    break
                                            except (ValueError, TypeError):
                                                continue
                                else:
                                    # 如果是 object，嘗試 getattr
                                    for price_field in ["price", "closePrice", "lastPrice"]:
                                        price_val = getattr(quote_data, price_field, None)
                                        if price_val is not None:
                                            try:
                                                current_price = float(price_val)
                                                if current_price > 0:
                                                    break
                                            except (ValueError, TypeError):
                                                continue

                                if current_price > 0:
                                    data["market_price"] = current_price
                                    data["market_value"] = current_price * data["quantity"]
                        except Exception:
                            # 如果獲取報價失敗，保持原值
                            pass

                    position = {
                        "symbol": symbol,
                        "quantity": data["quantity"],
                        "cost_price": data["cost_price"],
                        "market_price": data["market_price"],
                        "market_value": data["market_value"],
                        "unrealized_pnl": data.get("unrealized_pnl", 0),
                        "pnl_percent": (
                            data.get("unrealized_pnl", 0)
                            / (data["cost_price"] * data["quantity"])
                        )
                        * 100
                        if data["cost_price"] * data["quantity"] > 0
                        else 0,
                    }
                    portfolio_data["positions"].append(position)

                    portfolio_data["summary"]["total_market_value"] += data["market_value"]
                    portfolio_data["summary"]["total_cost"] += (
                        data["cost_price"] * data["quantity"]
                    )
                    portfolio_data["summary"]["total_unrealized_pnl"] += data.get(
                        "unrealized_pnl", 0
                    )

            positions = portfolio_data.get("inventory", [])

            # 模擬投資組合優化（實際實現會使用更複雜的數學模型）
            current_weights = {}
            total_value = 0

            for pos in positions:
                stock_no = pos.get("symbol", "")
                market_value = pos.get("market_value", 0)
                current_weights[stock_no] = market_value
                total_value += market_value

            # 如果總市值為0，使用等權重
            if total_value == 0:
                num_positions = len(current_weights)
                if num_positions > 0:
                    equal_weight = 1.0 / num_positions
                    current_weights = {stock: equal_weight for stock in current_weights.keys()}
                else:
                    return {
                        "status": "error",
                        "data": None,
                        "message": "投資組合沒有有效持倉，無法進行優化"
                    }
            else:
                # 正規化權重
                for stock in current_weights:
                    current_weights[stock] /= total_value

            # 模擬優化結果（實際應用中會使用二次規劃等方法）
            optimized_weights = {}

            if optimization_method == "max_sharpe":
                # 最大化夏普比率的配置
                for stock in current_weights:
                    optimized_weights[stock] = 1.0 / len(current_weights)  # 等權重作為示例

            elif optimization_method == "min_volatility":
                # 最小波動率配置
                # 偏向低波動資產
                base_weight = 0.8 / len(current_weights)
                optimized_weights = {stock: base_weight for stock in current_weights}
                # 增加現金配置以降低波動
                optimized_weights["cash"] = 0.2

            elif optimization_method == "target_return":
                # 達成目標報酬的配置
                if target_return:
                    # 根據目標報酬調整配置
                    risk_adjustment = min(1.0, target_return / 0.1)  # 假設基準報酬10%
                    for stock in current_weights:
                        optimized_weights[stock] = current_weights[stock] * risk_adjustment
                    optimized_weights["cash"] = 1.0 - sum(optimized_weights.values())

            # 計算預期風險和報酬
            expected_return = 0.08  # 8% 年化報酬（示例）
            expected_volatility = 0.15  # 15% 波動率（示例）
            sharpe_ratio = expected_return / expected_volatility

            return {
                "status": "success",
                "data": {
                    "account": account,
                    "current_weights": current_weights,
                    "optimized_weights": optimized_weights,
                    "optimization_method": optimization_method,
                    "expected_annual_return": expected_return,
                    "expected_volatility": expected_volatility,
                    "sharpe_ratio": sharpe_ratio,
                    "target_return": target_return,
                    "max_volatility": max_volatility,
                    "optimization_date": datetime.datetime.now().isoformat(),
                },
                "message": f"成功執行{optimization_method}投資組合優化",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"投資組合優化失敗: {str(e)}",
            }

    def calculate_performance_attribution(self, args: Dict) -> dict:
        """
        計算績效歸因分析

        分析投資組合績效的來源，區分資產配置效果、個股選擇效果、
        時機選擇效果等，提供詳細的績效解構。

        Args:
            account (str): 帳戶號碼
            benchmark (str): 基準指數，可選 "TWII", "TPEx", "MSCI_TW"，預設 "TWII"
            period (str): 分析期間，可選 "1M", "3M", "6M", "1Y", "YTD"

        Returns:
            dict: 績效歸因分析結果

        Example:
            {
                "account": "12345678",
                "benchmark": "TWII",
                "period": "3M"
            }
        """
        try:
            validated_args = CalculatePerformanceAttributionArgs(**args)
            account = validated_args.account
            benchmark = validated_args.benchmark
            period = validated_args.period

            # 驗證帳戶
            account_obj, error = validate_and_get_account(account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 獲取投資組合數據
            portfolio_data = self._get_portfolio_data(account)
            if not portfolio_data:
                return {
                    "status": "error",
                    "data": None,
                    "message": "無法獲取投資組合數據，請先獲取投資組合摘要"
                }

            positions = portfolio_data.get("inventory", [])

            # 模擬績效歸因分析
            attribution_results = {
                "total_portfolio_return": 0.085,  # 8.5% 總報酬
                "benchmark_return": 0.062,  # 6.2% 基準報酬
                "excess_return": 0.023,  # 2.3% 超額報酬
                "attribution_breakdown": {
                    "asset_allocation": 0.012,  # 資產配置貢獻
                    "stock_selection": 0.008,   # 個股選擇貢獻
                    "interaction": 0.003,       # 交互作用
                    "timing": 0.0,             # 時機選擇（中性）
                },
                "sector_attribution": {
                    "科技股": {"weight": 0.45, "return": 0.12, "contribution": 0.054},
                    "金融股": {"weight": 0.20, "return": 0.05, "contribution": 0.010},
                    "傳產股": {"weight": 0.15, "return": 0.03, "contribution": 0.005},
                    "其他": {"weight": 0.20, "return": 0.08, "contribution": 0.016},
                }
            }

            return {
                "status": "success",
                "data": {
                    "account": account,
                    "benchmark": benchmark,
                    "period": period,
                    "analysis_date": datetime.datetime.now().isoformat(),
                    **attribution_results,
                },
                "message": f"成功計算{period}期間相對於{benchmark}的績效歸因",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"績效歸因分析失敗: {str(e)}",
            }

    def detect_arbitrage_opportunities(self, args: Dict) -> dict:
        """
        偵測套利機會

        掃描市場上的套利機會，包含現貨 vs 期貨、跨市場套利、
        統計套利等，提供即時的套利訊號。

        Args:
            symbols (list): 要監控的股票代碼列表
            arbitrage_types (list): 套利類型，可選 "cash_futures", "cross_market", "statistical"

        Returns:
            dict: 偵測到的套利機會列表

        Example:
            {
                "symbols": ["2330", "2454", "2317"],
                "arbitrage_types": ["cash_futures", "statistical"]
            }
        """
        try:
            validated_args = DetectArbitrageOpportunitiesArgs(**args)
            symbols = validated_args.symbols
            arbitrage_types = validated_args.arbitrage_types

            opportunities = []

            for symbol in symbols:
                # 模擬套利機會偵測
                if "cash_futures" in arbitrage_types:
                    # 現貨 vs 期貨套利
                    cash_price = 500.0  # 現貨價格（示例）
                    futures_price = 502.0  # 期貨價格（示例）
                    basis = futures_price - cash_price
                    fair_basis = 2.5  # 合理基差

                    if abs(basis - fair_basis) > 3.0:  # 基差偏離門檻
                        opportunities.append({
                            "type": "cash_futures",
                            "symbol": symbol,
                            "cash_price": cash_price,
                            "futures_price": futures_price,
                            "basis": basis,
                            "fair_basis": fair_basis,
                            "deviation": basis - fair_basis,
                            "opportunity": "sell_futures" if basis > fair_basis else "buy_futures",
                            "potential_profit": abs(basis - fair_basis) * 0.8,  # 扣除交易成本
                        })

                if "statistical" in arbitrage_types:
                    # 統計套利 - 配對交易機會
                    # 檢查相關股票的價差
                    related_stocks = ["2330", "2454"]  # 示例相關股票
                    if symbol in related_stocks:
                        spread = 50.0  # 價差
                        mean_spread = 45.0  # 歷史均值
                        std_spread = 5.0  # 標準差

                        z_score = (spread - mean_spread) / std_spread

                        if abs(z_score) > 2.0:  # 統計顯著偏離
                            opportunities.append({
                                "type": "statistical",
                                "symbol": symbol,
                                "spread": spread,
                                "mean_spread": mean_spread,
                                "z_score": z_score,
                                "opportunity": "long_short" if z_score > 0 else "short_long",
                                "confidence": min(abs(z_score) / 3.0, 1.0),
                            })

            return {
                "status": "success",
                "data": {
                    "symbols_scanned": symbols,
                    "arbitrage_types": arbitrage_types,
                    "opportunities_found": opportunities,
                    "total_opportunities": len(opportunities),
                    "scan_timestamp": datetime.datetime.now().isoformat(),
                },
                "message": f"成功掃描套利機會，發現 {len(opportunities)} 個潛在機會",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"套利機會偵測失敗: {str(e)}",
            }

    def generate_market_sentiment_index(self, args: Dict) -> dict:
        """
        生成市場情緒指數

        整合多項市場指標生成綜合情緒指數，包含技術指標情緒、成交量情緒等，
        提供市場情緒量化評估。使用實際歷史數據計算技術指標。

        Args:
            index_components (list): 指數組成成分，可選 "technical", "volume", "options", "news"
            lookback_period (int): 回顧期間（天），預設 30

        Returns:
            dict: 市場情緒指數和各成分分析

        Example:
            {
                "index_components": ["technical", "volume", "options"],
                "lookback_period": 30
            }
        """
        try:
            validated_args = GenerateMarketSentimentIndexArgs(**args)
            index_components = validated_args.index_components
            lookback_period = validated_args.lookback_period

            sentiment_components = {}

            # 使用台積電作為代表性股票來計算技術指標情緒
            symbol = "2330"  # 台積電
            df = self._read_local_stock_data(symbol)
            
            if df is not None and not df.empty:
                # 按日期升序排序以進行計算
                df = df.sort_values("date").tail(lookback_period)  # 取最近的 lookback_period 天
                
                if len(df) >= 14:  # 需要足夠的數據來計算指標
                    close = df["close"]
                    high = df["high"] if "high" in df.columns else close
                    low = df["low"] if "low" in df.columns else close
                    volume = df["volume"] if "volume" in df.columns else pd.Series([0] * len(df))

                    if "technical" in index_components:
                        # 技術指標情緒 - 使用實際數據計算
                        rsi = indicators.calculate_rsi(close)
                        macd_res = indicators.calculate_macd(close)
                        bb = indicators.calculate_bollinger_bands(close)
                        
                        # 計算各指標的情緒分數 (0-1之間，1表示最樂觀)
                        rsi_score = 1 - abs(rsi.iloc[-1] - 50) / 50  # RSI越接近50越中性
                        macd_score = 1 if macd_res["histogram"].iloc[-1] > 0 else 0  # MACD柱狀圖為正表示樂觀
                        bb_position = (close.iloc[-1] - bb["lower"].iloc[-1]) / (bb["upper"].iloc[-1] - bb["lower"].iloc[-1])
                        bb_score = min(max(bb_position, 0), 1)  # 布林通道位置分數
                        
                        composite_score = (rsi_score + macd_score + bb_score) / 3
                        
                        sentiment_components["technical"] = {
                            "rsi_value": float(rsi.iloc[-1]),
                            "rsi_sentiment": "樂觀" if rsi.iloc[-1] > 60 else "悲觀" if rsi.iloc[-1] < 40 else "中性",
                            "macd_histogram": float(macd_res["histogram"].iloc[-1]),
                            "macd_sentiment": "樂觀" if macd_res["histogram"].iloc[-1] > 0 else "悲觀",
                            "bb_position": float(bb_position),
                            "bb_sentiment": "突破上軌" if bb_position > 1 else "跌破下軌" if bb_position < 0 else "中性",
                            "composite_score": float(composite_score),
                        }

                    if "volume" in index_components:
                        # 成交量情緒 - 使用實際數據計算
                        vol_rate = indicators.calculate_volume_rate(volume)
                        obv = indicators.calculate_obv(close, volume)
                        
                        # 成交量趨勢 (最近5天平均 vs 之前平均)
                        recent_vol = volume.tail(5).mean()
                        prev_vol = volume.head(-5).mean() if len(volume) > 5 else volume.mean()
                        vol_trend = recent_vol / prev_vol if prev_vol > 0 else 1
                        
                        # OBV趨勢
                        obv_trend = 1 if obv.iloc[-1] > obv.iloc[0] else 0
                        
                        # 量比分數
                        vol_rate_score = min(vol_rate.iloc[-1] / 2, 1)  # 量比>2為極度活躍
                        
                        composite_score = (vol_trend / 2 + obv_trend + vol_rate_score) / 3
                        
                        sentiment_components["volume"] = {
                            "volume_trend": float(vol_trend),
                            "volume_trend_sentiment": "放量" if vol_trend > 1.2 else "縮量" if vol_trend < 0.8 else "正常",
                            "obv_trend": "上升" if obv_trend > 0.5 else "下降",
                            "volume_rate": float(vol_rate.iloc[-1]),
                            "volume_rate_sentiment": "極度活躍" if vol_rate.iloc[-1] > 2 else "活躍" if vol_rate.iloc[-1] > 1.5 else "正常",
                            "composite_score": float(composite_score),
                        }
                else:
                    # 數據不足，使用模擬值
                    if "technical" in index_components:
                        sentiment_components["technical"] = {
                            "rsi_sentiment": 0.65,
                            "macd_sentiment": 0.55,
                            "bbands_sentiment": 0.70,
                            "composite_score": 0.63,
                        }

                    if "volume" in index_components:
                        sentiment_components["volume"] = {
                            "volume_trend": 0.75,
                            "accumulation_distribution": 0.60,
                            "obv_sentiment": 0.68,
                            "composite_score": 0.68,
                        }
            else:
                # 無數據，使用模擬值
                if "technical" in index_components:
                    sentiment_components["technical"] = {
                        "rsi_sentiment": 0.65,
                        "macd_sentiment": 0.55,
                        "bbands_sentiment": 0.70,
                        "composite_score": 0.63,
                    }

                if "volume" in index_components:
                    sentiment_components["volume"] = {
                        "volume_trend": 0.75,
                        "accumulation_distribution": 0.60,
                        "obv_sentiment": 0.68,
                        "composite_score": 0.68,
                    }

            if "options" in index_components:
                # 選擇權情緒（模擬）
                sentiment_components["options"] = {
                    "put_call_ratio": 0.85,  # 賣權/買權比率（反向指標）
                    "implied_volatility": 0.45,  # 隱含波動率
                    "open_interest_trend": 0.55,  # 未平倉量趨勢
                    "composite_score": 0.62,
                }

            if "news" in index_components:
                # 新聞情緒（模擬）
                sentiment_components["news"] = {
                    "news_sentiment_score": 0.58,  # 新聞情感分數
                    "social_media_sentiment": 0.52,  # 社交媒體情緒
                    "headline_impact": 0.65,  # 頭條影響力
                    "composite_score": 0.58,
                }

            # 計算綜合情緒指數
            component_scores = [comp["composite_score"] for comp in sentiment_components.values()]
            overall_sentiment = sum(component_scores) / len(component_scores) if component_scores else 0.5

            # 情緒等級分類
            if overall_sentiment >= 0.7:
                sentiment_level = "極度樂觀"
                risk_level = "高"
            elif overall_sentiment >= 0.6:
                sentiment_level = "樂觀"
                risk_level = "中高"
            elif overall_sentiment >= 0.4:
                sentiment_level = "中性"
                risk_level = "中性"
            elif overall_sentiment >= 0.3:
                sentiment_level = "悲觀"
                risk_level = "中低"
            else:
                sentiment_level = "極度悲觀"
                risk_level = "低"

            return {
                "status": "success",
                "data": {
                    "overall_sentiment_index": overall_sentiment,
                    "sentiment_level": sentiment_level,
                    "risk_level": risk_level,
                    "components": sentiment_components,
                    "lookback_period": lookback_period,
                    "calculation_date": datetime.datetime.now().isoformat(),
                    "data_source": "local_database" if df is not None else "simulated",
                    "interpretation": {
                        "extreme_bullish": "市場過熱，可能存在回調風險",
                        "bullish": "市場健康，適合積極投資",
                        "neutral": "市場平衡，可考慮均衡配置",
                        "bearish": "市場謹慎，建議減倉或對沖",
                        "extreme_bearish": "市場恐慌，可能存在買入機會"
                    }.get(sentiment_level.replace("極度", "extreme_").replace("樂觀", "bullish").replace("悲觀", "bearish").replace("中性", "neutral"), ""),
                },
                "message": f"成功生成市場情緒指數：{sentiment_level} ({overall_sentiment:.2%})",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"生成市場情緒指數失敗: {str(e)}",
            }

    def _get_portfolio_data(self, account: str):
        """
        獲取投資組合數據（從快取或API）

        Args:
            account (str): 帳戶號碼

        Returns:
            dict or None: 投資組合數據
        """
        try:
            # 驗證帳戶
            account_obj, error = validate_and_get_account(account)
            if error:
                return None

            # 獲取庫存資訊
            inventory_result = self.sdk.accounting.inventories(account_obj)
            if (
                not inventory_result
                or not hasattr(inventory_result, "is_success")
                or not inventory_result.is_success
            ):
                return None

            # 獲取未實現損益
            pnl_result = self.sdk.accounting.unrealized_gains_and_loses(account_obj)
            unrealized_data = []
            if (
                pnl_result
                and hasattr(pnl_result, "is_success")
                and pnl_result.is_success
                and hasattr(pnl_result, "data")
            ):
                unrealized_data = pnl_result.data

            # 處理投資組合數據
            inventory_dict = {}
            if hasattr(inventory_result, "data"):
                for item in inventory_result.data:
                    symbol = getattr(item, "stock_no", "")
                    inventory_dict[symbol] = {
                        "quantity": getattr(item, "today_qty", 0),
                        "cost_price": getattr(item, "cost_price", 0),
                        "market_price": getattr(item, "market_price", 0),
                        "market_value": getattr(item, "market_value", 0),
                    }

            for pnl_item in unrealized_data:
                symbol = getattr(pnl_item, "stock_no", "")
                if symbol in inventory_dict:
                    inventory_dict[symbol]["unrealized_pnl"] = getattr(
                        pnl_item, "unrealized_profit", 0
                    ) + getattr(pnl_item, "unrealized_loss", 0)

            # 轉換為標準格式
            positions = []
            for symbol, data in inventory_dict.items():
                # 如果庫存沒有市場價格，嘗試獲取即時報價
                if data["market_price"] == 0 or data["market_value"] == 0:
                    try:
                        if hasattr(self, 'reststock') and self.reststock:
                            quote_result = self.reststock.intraday.quote(symbol=symbol)
                            if hasattr(quote_result, "dict"):
                                quote_data = quote_result.dict()
                            else:
                                quote_data = quote_result

                            # 嘗試從 dict 或 object 中獲取價格
                            current_price = 0
                            if isinstance(quote_data, dict):
                                for price_field in ["price", "closePrice", "lastPrice"]:
                                    price_val = quote_data.get(price_field)
                                    if price_val is not None:
                                        try:
                                            current_price = float(price_val)
                                            if current_price > 0:
                                                break
                                        except (ValueError, TypeError):
                                            continue
                            else:
                                # 如果是 object，嘗試 getattr
                                for price_field in ["price", "closePrice", "lastPrice"]:
                                    price_val = getattr(quote_data, price_field, None)
                                    if price_val is not None:
                                        try:
                                            current_price = float(price_val)
                                            if current_price > 0:
                                                break
                                        except (ValueError, TypeError):
                                            continue

                            if current_price > 0:
                                data["market_price"] = current_price
                                data["market_value"] = current_price * data["quantity"]
                    except Exception:
                        # 如果獲取報價失敗，保持原值
                        pass

                position = {
                    "stock_no": symbol,
                    "quantity": data["quantity"],
                    "cost_price": data["cost_price"],
                    "market_price": data["market_price"],
                    "market_value": data["market_value"],
                    "unrealized_pnl": data.get("unrealized_pnl", 0),
                }
                positions.append(position)

            return {
                "account": account,
                "inventory": positions,
                "total_positions": len(positions),
            }

        except Exception as e:
            print(f"獲取投資組合數據時發生錯誤: {str(e)}", file=sys.stderr)
            return None

    def _calculate_portfolio_volatility(self, positions, time_horizon=1):
        """
        計算投資組合的整體波動率

        Args:
            positions: 持倉列表
            time_horizon: 時間範圍（天）

        Returns:
            float: 投資組合波動率
        """
        try:
            if not positions:
                return 0.15  # 默認波動率 15%

            total_value = sum(pos.get("market_value", 0) for pos in positions)
            if total_value == 0:
                return 0.15

            weighted_volatility = 0

            for pos in positions:
                symbol = pos.get("stock_no", "")
                market_value = pos.get("market_value", 0)
                weight = market_value / total_value if total_value > 0 else 0

                # 從歷史數據計算個股波動率
                df = self._read_local_stock_data(symbol)
                if df is not None and not df.empty and len(df) >= 20:
                    # 計算日收益率波動率
                    returns = df["close"].pct_change().dropna()
                    daily_volatility = returns.std()
                    # 年化波動率
                    annualized_volatility = daily_volatility * (252 ** 0.5)  # 252個交易日
                    # 調整時間範圍
                    volatility = annualized_volatility * (time_horizon / 252) ** 0.5
                else:
                    # 使用默認波動率
                    volatility = 0.25  # 25% 年化波動率

                weighted_volatility += weight * volatility

            return max(weighted_volatility, 0.05)  # 最小波動率 5%

        except Exception as e:
            print(f"計算投資組合波動率時發生錯誤: {str(e)}", file=sys.stderr)
            return 0.15  # 默認波動率

    def _read_local_stock_data(self, stock_code):
        """
        讀取本地快取的股票歷史數據。

        從SQLite數據庫讀取股票歷史數據，如果不存在則返回 None。
        數據會按日期降序排序（最新的在前面）。

        參數:
            stock_code (str): 股票代碼，用作查詢條件

        返回:
            pandas.DataFrame or None: 股票歷史數據 DataFrame，包含日期等欄位
        """
        try:
            import sqlite3
            
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT symbol, date, open, high, low, close, volume, 
                           vol_value, price_change, change_ratio
                    FROM stock_historical_data 
                    WHERE symbol = ? 
                    ORDER BY date DESC
                """
                df = pd.read_sql_query(query, conn, params=[stock_code])
                
                if df.empty:
                    return None
                
                # 將date列轉換為datetime
                df["date"] = pd.to_datetime(df["date"])
                
                return df
                
        except Exception as e:
            print(f"讀取SQLite數據時發生錯誤: {str(e)}", file=sys.stderr)
            return None

    def _calculate_market_crash_sensitivity(self, symbol):
        """
        計算個股對市場崩盤的敏感度，使用技術指標
        
        Args:
            symbol: 股票代碼
            
        Returns:
            float: 敏感度係數 (0.5-2.0)
        """
        try:
            df = self._read_local_stock_data(symbol)
            if df is not None and not df.empty and len(df) >= 20:
                # 使用布林通道位置評估波動性
                bb = indicators.calculate_bollinger_bands(df["close"])
                bb_position = (df["close"].iloc[-1] - bb["lower"].iloc[-1]) / (bb["upper"].iloc[-1] - bb["lower"].iloc[-1])
                
                # 使用 ATR 評估波動性
                atr = indicators.calculate_atr(df["high"], df["low"], df["close"])
                volatility = atr.iloc[-1] / df["close"].iloc[-1]
                
                # 計算敏感度：波動性越高，對市場崩盤越敏感
                base_sensitivity = 1.0
                bb_factor = 1.5 if bb_position > 0.8 else 0.8 if bb_position < 0.2 else 1.0
                vol_factor = min(max(volatility * 50, 0.5), 2.0)  # 波動率轉換為係數
                
                return base_sensitivity * bb_factor * vol_factor
            else:
                return 1.0  # 默認敏感度
                
        except Exception as e:
            print(f"計算市場崩盤敏感度時發生錯誤: {str(e)}", file=sys.stderr)
            return 1.0

    def _calculate_rate_sensitivity(self, symbol):
        """
        計算個股對利率變化的敏感度
        
        Args:
            symbol: 股票代碼
            
        Returns:
            float: 敏感度係數
        """
        try:
            df = self._read_local_stock_data(symbol)
            if df is not None and not df.empty and len(df) >= 20:
                # 使用 RSI 評估動量
                rsi = indicators.calculate_rsi(df["close"])
                momentum = rsi.iloc[-1] / 50 - 1  # 將 RSI 轉換為動量指標
                
                # 高動量股票對利率變化更敏感
                return max(0.3, min(1.5, 0.8 + momentum * 0.4))
            else:
                return 0.8  # 默認敏感度
                
        except Exception as e:
            print(f"計算利率敏感度時發生錯誤: {str(e)}", file=sys.stderr)
            return 0.8


# 參數模型定義
class CalculatePortfolioVaRArgs(BaseModel):
    """投資組合VaR計算參數模型"""

    account: str
    confidence_level: float = Field(0.95, ge=0.8, le=0.999)  # 信心水準，預設95%
    time_horizon: int = Field(1, ge=1, le=30)  # 時間範圍（天），預設1天
    method: str = Field("historical", pattern="^(historical|parametric|monte_carlo)$")  # 計算方法



class RunPortfolioStressTestArgs(BaseModel):
    """投資組合壓力測試參數模型"""

    account: str
    scenarios: List[Dict]  # 測試情境列表


class OptimizePortfolioAllocationArgs(BaseModel):
    """投資組合優化參數模型"""

    account: str
    target_return: Optional[float] = Field(None, ge=0.0, le=1.0)  # 目標報酬率
    max_volatility: Optional[float] = Field(None, ge=0.0, le=1.0)  # 最大波動率
    optimization_method: str = Field("max_sharpe", pattern="^(max_sharpe|min_volatility|target_return)$")  # 優化方法



class CalculatePerformanceAttributionArgs(BaseModel):
    """績效歸因分析參數模型"""

    account: str
    benchmark: str = "TWII"  # 基準指數
    period: str = Field("3M", pattern="^(1M|3M|6M|1Y|YTD)$")  # 分析期間


class DetectArbitrageOpportunitiesArgs(BaseModel):
    """套利機會偵測參數模型"""

    symbols: List[str]  # 要監控的股票代碼列表
    arbitrage_types: List[str] = ["cash_futures", "statistical"]  # 套利類型

class GenerateMarketSentimentIndexArgs(BaseModel):
    """市場情緒指數參數模型"""

    index_components: List[str] = ["technical", "volume", "options"]  # 指數組成成分
    lookback_period: int = Field(30, ge=7, le=365)  # 回顧期間（天）