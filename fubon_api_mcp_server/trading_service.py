#!/usr/bin/env python3
"""
富邦證券交易服務

此模組提供股票和期貨/選擇權的交易功能，包括：
- 普通委託單下單、取消、改價、改量
- 批量下單
- 條件單（單一條件、多條件、當沖條件）
- 分時分量條件單
- 停損停利條件單
- 移動鎖利單
- 委託結果查詢
- 成交回報查詢
- 損益查詢

主要組件：
- TradingService: 交易服務類
- 委託單管理
- 條件單管理
- 損益計算
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from fubon_neo.constant import (
    ConditionMarketType,
    ConditionOrderType,
    ConditionPriceType,
    ConditionStatus,
    Direction,
    HistoryStatus,
    Operator,
    SplitDescription,
    StopSign,
    TimeSliceOrderType,
    TPSLOrder,
    TPSLWrapper,
    TradingType,
    TrailOrder,
    TriggerContent,
)
from fubon_neo.sdk import Condition, ConditionDayTrade, ConditionOrder, FubonSDK
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .utils import validate_and_get_account

# 本地模組導入
from .enums import (
    to_bs_action,
    to_condition_market_type,
    to_condition_order_type,
    to_condition_price_type,
    to_condition_status,
    to_direction,
    to_history_status,
    to_market_type,
    to_operator,
    to_order_type,
    to_price_type,
    to_stock_types,
    to_stop_sign,
    to_time_in_force,
    to_time_slice_order_type,
    to_trading_type,
    to_trigger_content,
)


class TradingService:
    """交易服務類"""

    def __init__(
        self,
        mcp: FastMCP,
        sdk: FubonSDK,
        accounts: List[str],
        base_data_dir: Path,
        reststock,
        restfutopt,
    ):
        self.mcp = mcp
        self.sdk = sdk
        self.accounts = accounts
        self.base_data_dir = base_data_dir
        self.reststock = reststock
        self.restfutopt = restfutopt
        self._register_tools()

    def _register_tools(self):
        """註冊所有交易相關的工具"""
        # 普通委託單工具
        self.mcp.tool()(self.place_order)
        self.mcp.tool()(self.cancel_order)
        self.mcp.tool()(self.modify_price)
        self.mcp.tool()(self.modify_quantity)
        self.mcp.tool()(self.batch_place_order)

        # 條件單工具
        self.mcp.tool()(self.place_condition_order)
        self.mcp.tool()(self.place_multi_condition_order)
        self.mcp.tool()(self.place_daytrade_condition_order)
        self.mcp.tool()(self.place_daytrade_multi_condition_order)
        self.mcp.tool()(self.place_time_slice_order)
        self.mcp.tool()(self.place_tpsl_condition_order)
        self.mcp.tool()(self.cancel_condition_order)
        self.mcp.tool()(self.get_condition_order)
        self.mcp.tool()(self.get_condition_order_by_id)
        self.mcp.tool()(self.get_daytrade_condition_by_id)
        self.mcp.tool()(self.get_trail_order)
        self.mcp.tool()(self.place_trail_profit)
        self.mcp.tool()(self.get_time_slice_order)

        # 委託結果和回報工具
        self.mcp.tool()(self.get_order_results)
        self.mcp.tool()(self.get_order_results_detail)
        self.mcp.tool()(self.get_trail_history)
        self.mcp.tool()(self.get_condition_history)

    def place_order(self, args: Dict) -> dict:
        """
        下單委託

        Args:
            account (str): 帳戶號碼
            buy_sell (str): 買賣別，Buy 或 Sell
            symbol (str): 股票代碼
            price (str): 委託價格
            quantity (int): 委託數量（股）
            market_type (str, optional): 市場類型，Common, Emg, Odd，預設 "Common"
            price_type (str, optional): 價格類型，Limit, Market, LimitUp, LimitDown，預設 "Limit"
            time_in_force (str, optional): 有效期間，ROD, IOC, FOK，預設 "ROD"
            order_type (str, optional): 委託類型，Stock, Margin, Short, DayTrade，預設 "Stock"
        """
        try:
            validated_args = PlaceOrderArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 構建委託單參數
            order_params = {
                "account": account_obj,
                "buy_sell": validated_args.buy_sell,
                "symbol": validated_args.symbol,
                "price": validated_args.price,
                "quantity": validated_args.quantity,
                "market_type": validated_args.market_type,
                "price_type": validated_args.price_type,
                "time_in_force": validated_args.time_in_force,
                "order_type": validated_args.order_type,
            }

            # 調用 SDK 下單
            result = self.sdk.stock.place_order(**order_params)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"委託單下單成功，委託單號: {result.data.get('order_no', 'N/A')}",
                }
            else:
                error_msg = "下單失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"下單失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"下單時發生錯誤: {str(e)}",
            }

    def cancel_order(self, args: Dict) -> dict:
        """
        取消委託單

        Args:
            account (str): 帳戶號碼
            order_no (str): 委託單號
        """
        try:
            validated_args = CancelOrderArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 取消委託
            result = self.sdk.stock.cancel_order(
                account=account_obj, order_no=validated_args.order_no
            )

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"委託單 {validated_args.order_no} 取消成功",
                }
            else:
                error_msg = "取消委託失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"取消委託失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"取消委託時發生錯誤: {str(e)}",
            }

    def modify_price(self, args: Dict) -> dict:
        """
        修改委託價格

        Args:
            account (str): 帳戶號碼
            order_no (str): 委託單號
            new_price (float): 新價格
        """
        try:
            validated_args = ModifyPriceArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 調用 SDK 修改價格
            result = self.sdk.modify_price(
                account=account,
                order_no=validated_args.order_no,
                new_price=validated_args.new_price,
            )

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"委託單 {validated_args.order_no} 價格修改成功",
                }
            else:
                error_msg = "修改價格失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"修改價格失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"修改價格時發生錯誤: {str(e)}",
            }

    def modify_quantity(self, args: Dict) -> dict:
        """
        修改委託數量

        Args:
            account (str): 帳戶號碼
            order_no (str): 委託單號
            new_quantity (int): 新數量
        """
        try:
            validated_args = ModifyQuantityArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 調用 SDK 修改數量
            result = self.sdk.modify_quantity(
                account=account,
                order_no=validated_args.order_no,
                new_quantity=validated_args.new_quantity,
            )

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"委託單 {validated_args.order_no} 數量修改成功",
                }
            else:
                error_msg = "修改數量失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"修改數量失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"修改數量時發生錯誤: {str(e)}",
            }

    def batch_place_order(self, args: Dict) -> dict:
        """
        批量下單委託

        Args:
            orders (list): 委託單列表，每筆委託包含：
                - account (str): 帳戶號碼
                - buy_sell (str): 買賣別，Buy 或 Sell
                - symbol (str): 股票代碼
                - price (str): 委託價格
                - quantity (int): 委託數量（股）
                - market_type (str, optional): 市場類型，預設 "Common"
                - price_type (str, optional): 價格類型，預設 "Limit"
                - time_in_force (str, optional): 有效期間，預設 "ROD"
                - order_type (str, optional): 委託類型，預設 "Stock"
        """
        try:
            validated_args = BatchPlaceOrderArgs(**args)
            orders = validated_args.orders

            results = []
            success_count = 0
            error_count = 0

            # 使用 ThreadPoolExecutor 進行並發下單
            with ThreadPoolExecutor(max_workers=min(len(orders), 10)) as executor:
                future_to_order = {
                    executor.submit(self._place_single_order, order): order
                    for order in orders
                }

                for future in as_completed(future_to_order):
                    order = future_to_order[future]
                    try:
                        result = future.result()
                        results.append(result)
                        if result["status"] == "success":
                            success_count += 1
                        else:
                            error_count += 1
                    except Exception as exc:
                        error_result = {
                            "status": "error",
                            "data": None,
                            "message": f"委託 {order.get('symbol', 'N/A')} 下單時發生異常: {str(exc)}",
                        }
                        results.append(error_result)
                        error_count += 1

            return {
                "status": "success",
                "data": {
                    "results": results,
                    "summary": {
                        "total": len(orders),
                        "success": success_count,
                        "error": error_count,
                    },
                },
                "message": f"批量下單完成，總計 {len(orders)} 筆，成功 {success_count} 筆，失敗 {error_count} 筆",
            }

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"批量下單時發生錯誤: {str(e)}",
            }

    def _place_single_order(self, order: Dict) -> dict:
        """下單單筆委託（用於批量下單）"""
        try:
            # 驗證帳戶
            account = validate_and_get_account(order["account"])

            # 構建委託參數
            order_params = {
                "account": account,
                "buy_sell": order["buy_sell"],
                "symbol": order["symbol"],
                "price": order["price"],
                "quantity": order["quantity"],
                "market_type": order.get("market_type", "Common"),
                "price_type": order.get("price_type", "Limit"),
                "time_in_force": order.get("time_in_force", "ROD"),
                "order_type": order.get("order_type", "Stock"),
            }

            # 調用 SDK 下單
            result = self.sdk.place_order(**order_params)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "symbol": order["symbol"],
                    "message": f"委託單下單成功，委託單號: {result.data.get('order_no', 'N/A')}",
                }
            else:
                error_msg = "下單失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"下單失敗: {result.message}"
                return {
                    "status": "error",
                    "data": None,
                    "symbol": order["symbol"],
                    "message": error_msg,
                }

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "symbol": order["symbol"],
                "message": f"下單時發生錯誤: {str(e)}",
            }

    def place_condition_order(self, args: Dict) -> dict:
        """
        單一條件單（可選停損停利）

        當觸發條件達成時，自動送出委託單。可選擇性加入停損停利設定。
        使用富邦官方 single_condition API。

        ⚠️ 重要提醒：
        - 條件單目前不支援期權商品與現貨商品混用
        - 停損停利設定僅為觸發送單，不保證必定成交，需視市場狀況調整
        - 請確認停損停利委託類別設定符合適合之交易規則
        - 待主單完全成交後，停損停利部分才會啟動

        Args:
            account (str): 帳戶號碼
            start_date (str): 開始日期，格式: YYYYMMDD (例: "20240426")
            end_date (str): 結束日期，格式: YYYYMMDD (例: "20240430")
            stop_sign (str): 條件停止條件
                - Full: 全部成交為止（預設）
                - Partial: 部分成交為止
                - UntilEnd: 效期結束為止
            condition (dict): 觸發條件
                - market_type (str): 市場類型，Reference(參考價) 或 LastPrice(最新價)
                - symbol (str): 股票代碼
                - trigger (str): 觸發內容，MatchedPrice(成交價), BuyPrice(買價), SellPrice(賣價)
                - trigger_value (str): 觸發值
                - comparison (str): 比較運算子，LessThan(<), LessOrEqual(<=), Equal(=), Greater(>), GreaterOrEqual(>=)
            order (dict): 委託單參數
                - buy_sell (str): Buy 或 Sell
                - symbol (str): 股票代碼
                - price (str): 委託價格
                - quantity (int): 委託數量（股）
                - market_type (str): Common, Emg, Odd，預設 "Common"
                - price_type (str): Limit, Market, LimitUp, LimitDown，預設 "Limit"
                - time_in_force (str): ROD, IOC, FOK，預設 "ROD"
                - order_type (str): Stock, Margin, Short, DayTrade，預設 "Stock"
            tpsl (dict, optional): 停損停利參數（選填）
                - stop_sign (str): Full 或 Flat，預設 "Full"
                - tp (dict, optional): 停利單參數
                    - time_in_force (str): ROD, IOC, FOK
                    - price_type (str): Limit 或 Market
                    - order_type (str): Stock, Margin, Short, DayTrade
                    - target_price (str): 觸發價格
                    - price (str): 委託價格（Market則填""）
                    - trigger (str): 觸發內容，預設 "MatchedPrice"
                - sl (dict, optional): 停損單參數（同tp結構）
                - end_date (str, optional): 結束日期 YYYYMMDD
                - intraday (bool, optional): 是否當日有效，預設 False

        Returns:
            dict: 包含狀態和條件單號的字典

        Example (單一條件單):
            {
                "account": "1234567",
                "start_date": "20240427",
                "end_date": "20240516",
                "stop_sign": "Full",
                "condition": {
                    "market_type": "Reference",
                    "symbol": "2881",
                    "trigger": "MatchedPrice",
                    "trigger_value": "80",
                    "comparison": "LessThan"
                },
                "order": {
                    "buy_sell": "Sell",
                    "symbol": "2881",
                    "price": "60",
                    "quantity": 1000
                }
            }

        Example (含停損停利):
            {
                "account": "1234567",
                "start_date": "20240426",
                "end_date": "20240430",
                "condition": {...},
                "order": {...},
                "tpsl": {
                    "stop_sign": "Full",
                    "tp": {
                        "time_in_force": "ROD",
                        "price_type": "Limit",
                        "order_type": "Stock",
                        "target_price": "85",
                        "price": "85"
                    },
                    "sl": {
                        "time_in_force": "ROD",
                        "price_type": "Limit",
                        "order_type": "Stock",
                        "target_price": "60",
                        "price": "60"
                    },
                    "end_date": "20240517",
                    "intraday": False
                }
            }
        """
        try:
            validated_args = PlaceConditionOrderArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 構建條件單參數
            condition_params = {
                "account": account,
                "start_date": validated_args.start_date,
                "end_date": validated_args.end_date,
                "stop_sign": validated_args.stop_sign,
                "condition": validated_args.condition,
                "order": validated_args.order,
            }

            # 添加停損停利參數（如果有）
            if validated_args.tpsl:
                condition_params["tpsl"] = validated_args.tpsl

            # 調用 SDK 建立條件單
            result = self.sdk.place_condition_order(**condition_params)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"條件單建立成功，條件單號: {result.data.get('condition_no', 'N/A')}",
                }
            else:
                error_msg = "條件單建立失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"條件單建立失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"建立條件單時發生錯誤: {str(e)}",
            }

    def place_multi_condition_order(self, args: Dict) -> dict:
        """
        多條件單（可選停損停利）

        支援設定多個觸發條件，當所有條件都達成時才送出委託單。
        使用富邦官方 multi_condition API。

        ⚠️ 重要提醒：
        - 條件單目前不支援期權商品與現貨商品混用
        - 停損停利設定僅為觸發送單，不保證必定成交，需視市場狀況調整
        - 請確認停損停利委託類別設定符合適合之交易規則
        - 待主單完全成交後，停損停利部分才會啟動
        - **所有條件必須同時滿足**才會觸發委託單

        Args:
            account (str): 帳戶號碼
            start_date (str): 開始日期，格式: YYYYMMDD (例: "20240426")
            end_date (str): 結束日期，格式: YYYYMMDD (例: "20240430")
            stop_sign (str): 條件停止條件
                - Full: 全部成交為止（預設）
                - Partial: 部分成交為止
                - UntilEnd: 效期結束為止
            conditions (list): 多個觸發條件（**所有條件須同時滿足**）
                每個條件包含：
                - market_type (str): 市場類型，Reference(參考價) 或 LastPrice(最新價)
                - symbol (str): 股票代碼
                - trigger (str): 觸發內容
                    - MatchedPrice: 成交價
                    - BuyPrice: 買價
                    - SellPrice: 賣價
                    - TotalQuantity: 總量
                - trigger_value (str): 觸發值
                - comparison (str): 比較運算子
                    - LessThan: <
                    - LessOrEqual: <=
                    - Equal: =
                    - Greater: >
                    - GreaterOrEqual: >=
            order (dict): 委託單參數
                - buy_sell (str): Buy 或 Sell
                - symbol (str): 股票代碼
                - price (str): 委託價格
                - quantity (int): 委託數量（股）
                - market_type (str): Common, Emg, Odd，預設 "Common"
                - price_type (str): Limit, Market, LimitUp, LimitDown，預設 "Limit"
                - time_in_force (str): ROD, IOC, FOK，預設 "ROD"
                - order_type (str): Stock, Margin, Short, DayTrade，預設 "Stock"
            tpsl (dict, optional): 停損停利參數（選填）
                - stop_sign (str): Full 或 Flat，預設 "Full"
                - tp (dict, optional): 停利單參數
                - sl (dict, optional): 停損單參數
                - end_date (str, optional): 結束日期 YYYYMMDD
                - intraday (bool, optional): 是否當日有效

        Returns:
            dict: 包含狀態和條件單號的字典

        Example (多條件單 - 價格 AND 成交量):
            {
                "account": "1234567",
                "start_date": "20240426",
                "end_date": "20240430",
                "stop_sign": "Full",
                "conditions": [
                    {
                        "market_type": "Reference",
                        "symbol": "2881",
                        "trigger": "MatchedPrice",
                        "trigger_value": "66",
                        "comparison": "LessThan"
                    },
                    {
                        "market_type": "Reference",
                        "symbol": "2881",
                        "trigger": "TotalQuantity",
                        "trigger_value": "8000",
                        "comparison": "LessThan"
                    }
                ],
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2881",
                    "price": "66",
                    "quantity": 1000
                }
            }

        Example (含停損停利):
            {
                "account": "1234567",
                "conditions": [...],
                "order": {...},
                "tpsl": {
                    "tp": {"target_price": "85", "price": "85"},
                    "sl": {"target_price": "60", "price": "60"},
                    "end_date": "20240517"
                }
            }
        """
        try:
            validated_args = PlaceMultiConditionOrderArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 構建多條件單參數
            condition_params = {
                "account": account,
                "start_date": validated_args.start_date,
                "end_date": validated_args.end_date,
                "stop_sign": validated_args.stop_sign,
                "conditions": validated_args.conditions,
                "order": validated_args.order,
            }

            # 添加停損停利參數（如果有）
            if validated_args.tpsl:
                condition_params["tpsl"] = validated_args.tpsl

            # 調用 SDK 建立多條件單
            result = self.sdk.place_multi_condition_order(**condition_params)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"多條件單建立成功，條件單號: {result.data.get('condition_no', 'N/A')}",
                }
            else:
                error_msg = "多條件單建立失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"多條件單建立失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"建立多條件單時發生錯誤: {str(e)}",
            }

    def place_daytrade_condition_order(self, args: Dict) -> dict:
        """
        當沖條件單

        當沖條件單用於當日沖銷交易，支援設定多個觸發條件。
        使用富邦官方 daytrade_condition API。

        ⚠️ 重要提醒：
        - 當沖條件單僅適用於當日沖銷交易
        - 條件單目前不支援期權商品與現貨商品混用
        - 請確認交易規則符合當沖條件

        Args:
            account (str): 帳戶號碼
            start_date (str): 開始日期，格式: YYYYMMDD
            end_date (str): 結束日期，格式: YYYYMMDD
            stop_sign (str): 條件停止條件
                - Full: 全部成交為止
                - Partial: 部分成交為止
                - UntilEnd: 效期結束為止
            conditions (list): 多個觸發條件（所有條件須同時滿足）
                每個條件包含：
                - market_type (str): 市場類型，Reference 或 LastPrice
                - symbol (str): 股票代碼
                - trigger (str): 觸發內容
                - trigger_value (str): 觸發值
                - comparison (str): 比較運算子
            order (dict): 委託單參數
                - buy_sell (str): Buy 或 Sell
                - symbol (str): 股票代碼
                - price (str): 委託價格
                - quantity (int): 委託數量（股）
                - market_type (str): 預設 "Common"
                - price_type (str): 預設 "Limit"
                - time_in_force (str): 預設 "ROD"
                - order_type (str): 預設 "DayTrade"

        Returns:
            dict: 包含狀態和條件單號的字典
        """
        try:
            validated_args = PlaceDaytradeConditionOrderArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 構建當沖條件單參數
            condition_params = {
                "account": account,
                "start_date": validated_args.start_date,
                "end_date": validated_args.end_date,
                "stop_sign": validated_args.stop_sign,
                "conditions": validated_args.conditions,
                "order": validated_args.order,
            }

            # 調用 SDK 建立當沖條件單
            result = self.sdk.place_daytrade_condition_order(**condition_params)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"當沖條件單建立成功，條件單號: {result.data.get('condition_no', 'N/A')}",
                }
            else:
                error_msg = "當沖條件單建立失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"當沖條件單建立失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"建立當沖條件單時發生錯誤: {str(e)}",
            }

    def place_daytrade_multi_condition_order(self, args: Dict) -> dict:
        """
        當沖多條件單（可選停損停利）

        使用富邦官方 multi_condition_day_trade API。支援多個條件同時滿足後觸發主單，
        主單成交後依設定於指定時間前進行回補；可選擇加入停損停利設定。

        ⚠️ 重要提醒：
        - 條件單不支援期權商品與現貨商品混用
        - 停損利設定僅為觸發送單，不保證必定回補成功
        - 當沖停損停利委託類別需符合當日沖銷交易規則（例如資券互抵）
        - 主單完全成交後，停損停利才會啟動

        Args:
            account (str): 帳戶號碼
            stop_sign (str): 條件停止條件，Full/Partial/UntilEnd，預設 "Full"
            end_time (str): 父單洗價結束時間（例："130000"）
            conditions (list): 多個觸發條件（List of ConditionArgs）
                每個條件包含：
                - market_type (str): 市場類型，Reference 或 LastPrice
                - symbol (str): 股票代碼
                - trigger (str): 觸發內容，MatchedPrice/BuyPrice/SellPrice/TotalQuantity
                - trigger_value (str): 觸發值
                - comparison (str): 比較運算子，LessThan/LessOrEqual/Equal/Greater/GreaterOrEqual
            order (dict): 主單委託內容（ConditionOrderArgs）
                - buy_sell (str): Buy 或 Sell
                - symbol (str): 股票代碼
                - price (str): 委託價格
                - quantity (int): 委託數量（股）
                - market_type (str): Common/Emg/Odd，預設 "Common"
                - price_type (str): Limit/Market/LimitUp/LimitDown，預設 "Limit"
                - time_in_force (str): ROD/IOC/FOK，預設 "ROD"
                - order_type (str): Stock/Margin/Short/DayTrade，預設 "DayTrade"
            daytrade (dict): 當沖回補內容（ConditionDayTradeArgs）
                - day_trade_end_time (str): 當沖回補結束時間（例："133000"）
                - auto_cancel (bool): 是否自動取消，預設 False
                - price (str): 回補價格
                - price_type (str): 回補價格類型，Limit 或 Market
            tpsl (dict, optional): 停損停利（TPSLWrapperArgs，選填）
                - stop_sign (str): Full 或 Flat，預設 "Full"
                - tp (dict, optional): 停利單參數
                    - time_in_force (str): ROD/IOC/FOK
                    - price_type (str): Limit 或 Market
                    - order_type (str): Stock/Margin/Short/DayTrade
                    - target_price (str): 觸發價格
                    - price (str): 委託價格（Market則填""）
                    - trigger (str): 觸發內容，預設 "MatchedPrice"
                - sl (dict, optional): 停損單參數（同tp結構）
                - end_date (str, optional): 結束日期 YYYYMMDD
                - intraday (bool, optional): 是否當日有效，預設 False
            fix_session (bool): 是否執行定盤回補，預設 False

        Returns:
            dict: 包含狀態和條件單號的字典

        Example (基本當沖多條件單):
            {
                "account": "1234567",
                "stop_sign": "Full",
                "end_time": "130000",
                "conditions": [
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "MatchedPrice",
                        "trigger_value": "850",
                        "comparison": "LessThan"
                    },
                    {
                        "market_type": "Reference",
                        "symbol": "2330",
                        "trigger": "TotalQuantity",
                        "trigger_value": "10000",
                        "comparison": "GreaterOrEqual"
                    }
                ],
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2330",
                    "price": "845",
                    "quantity": 1000,
                    "order_type": "DayTrade"
                },
                "daytrade": {
                    "day_trade_end_time": "133000",
                    "auto_cancel": False,
                    "price": "855",
                    "price_type": "Limit"
                }
            }

        Example (含停損停利):
            {
                "account": "1234567",
                "conditions": [...],
                "order": {...},
                "daytrade": {...},
                "tpsl": {
                    "stop_sign": "Full",
                    "tp": {
                        "time_in_force": "ROD",
                        "price_type": "Limit",
                        "order_type": "DayTrade",
                        "target_price": "870",
                        "price": "870"
                    },
                    "sl": {
                        "time_in_force": "ROD",
                        "price_type": "Limit",
                        "order_type": "DayTrade",
                        "target_price": "830",
                        "price": "830"
                    },
                    "end_date": "20241115",
                    "intraday": True
                }
            }
        """
        try:
            from fubon_neo.constant import BSAction, TimeInForce

            validated = PlaceDayTradeMultiConditionOrderArgs(**args)

            # 帳戶驗證
            account_obj, error = validate_and_get_account(validated.account)
            if error:
                return {"status": "error", "message": error}

            # 多個條件
            conditions = []
            for cond in validated.conditions:
                c = ConditionArgs(**cond)
                conditions.append(
                    Condition(
                        market_type=to_trading_type(c.market_type),
                        symbol=c.symbol,
                        trigger=to_trigger_content(c.trigger),
                        trigger_value=c.trigger_value,
                        comparison=to_operator(c.comparison),
                    )
                )

            # 主單
            ord_args = ConditionOrderArgs(**validated.order)
            order = ConditionOrder(
                buy_sell=to_bs_action(ord_args.buy_sell),
                symbol=ord_args.symbol,
                price=ord_args.price,
                quantity=ord_args.quantity,
                market_type=to_condition_market_type(ord_args.market_type),
                price_type=to_condition_price_type(ord_args.price_type),
                time_in_force=to_time_in_force(ord_args.time_in_force),
                order_type=to_condition_order_type(ord_args.order_type),
            )

            # 當沖設定
            dt_args = ConditionDayTradeArgs(**validated.daytrade)
            daytrade_obj = ConditionDayTrade(
                day_trade_end_time=dt_args.day_trade_end_time,
                auto_cancel=dt_args.auto_cancel,
                price=dt_args.price,
                price_type=getattr(ConditionPriceType, dt_args.price_type),
            )

            # 停損停利（可選）
            tpsl = None
            if validated.tpsl:
                wrap = TPSLWrapperArgs(**validated.tpsl)
                tp = None
                if wrap.tp:
                    tpa = TPSLOrderArgs(**wrap.tp)
                    tp = TPSLOrder(
                        time_in_force=to_time_in_force(tpa.time_in_force),
                        price_type=to_condition_price_type(tpa.price_type),
                        order_type=to_condition_order_type(tpa.order_type),
                        target_price=tpa.target_price,
                        price=tpa.price,
                        trigger=to_trigger_content(tpa.trigger)
                        if tpa.trigger
                        else TriggerContent.MatchedPrice,
                    )
                sl = None
                if wrap.sl:
                    sla = TPSLOrderArgs(**wrap.sl)
                    sl = TPSLOrder(
                        time_in_force=to_time_in_force(sla.time_in_force),
                        price_type=to_condition_price_type(sla.price_type),
                        order_type=to_condition_order_type(sla.order_type),
                        target_price=sla.target_price,
                        price=sla.price,
                        trigger=to_trigger_content(sla.trigger)
                        if sla.trigger
                        else TriggerContent.MatchedPrice,
                    )
                tpsl = TPSLWrapper(
                    stop_sign=to_stop_sign(wrap.stop_sign),
                    tp=tp,
                    sl=sl,
                    end_date=wrap.end_date,
                    intraday=wrap.intraday,
                )

            # 呼叫 SDK：multi_condition_day_trade
            result = self.sdk.stock.multi_condition_day_trade(
                account_obj,
                to_stop_sign(validated.stop_sign),
                validated.end_time,
                conditions,
                order,
                daytrade_obj,
                tpsl,
                validated.fix_session,
            )

            if result and hasattr(result, "is_success") and result.is_success:
                guid = (
                    getattr(result.data, "guid", None)
                    if hasattr(result, "data")
                    else None
                )
                msg = f"當沖多條件單已成功建立 - {ord_args.symbol} ({len(conditions)} 個條件)"
                if validated.tpsl:
                    msg += " (含停損停利)"

                return {
                    "status": "success",
                    "data": {
                        "guid": guid,
                        "condition_no": guid,
                        "symbol": ord_args.symbol,
                        "buy_sell": ord_args.buy_sell,
                        "quantity": ord_args.quantity,
                        "end_time": validated.end_time,
                        "day_trade_end_time": dt_args.day_trade_end_time,
                        "conditions_count": len(conditions),
                        "has_tpsl": bool(validated.tpsl),
                    },
                    "message": msg,
                }

            error_msg = (
                getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
            )
            return {"status": "error", "message": f"當沖多條件單建立失敗: {error_msg}"}

        except Exception as e:
            return {
                "status": "error",
                "message": f"當沖多條件單建立時發生錯誤: {str(e)}",
            }

    def place_time_slice_order(self, args: Dict) -> dict:
        """
        分時分量條件單（time_slice_order）

        依據 `SplitDescription` 拆單策略與 `ConditionOrder` 委託內容，於指定期間內按時間分批送單。

        ⚠️ 重要提醒：
        - 數量單位為「股」，必須為1000的倍數（即張數）
        - 例如：5張 = 5000股，10張 = 10000股
        - **取消方式特殊**：分時分量條件單會立即產生多個普通委託單，不適用 `cancel_condition_order`
          請使用 `get_order_results` 查詢委託結果，然後用 `cancel_order` 逐筆取消各個委託單

        Args:
            account (str): 帳號
            start_date (str): 監控開始日 YYYYMMDD
            end_date (str): 監控結束日 YYYYMMDD
            stop_sign (str): Full / Partial / UntilEnd
            split (dict): 分時分量設定（TimeSliceSplitArgs）
                基本字段:
                - method (str): 分單類型 - "Type1"/"Type2"/"Type3" 或 "TimeSlice"(自動推斷)
                - interval (int): 間隔秒數
                - single_quantity (int): 每次委託股數（必須為1000的倍數）
                - start_time (str): 開始時間，格式如 '083000' **（必填）**
                - end_time (str, optional): 結束時間，Type2/Type3 必填 **（使用 TimeSlice 時通常必填）**
                - total_quantity (int, optional): 總委託股數（必須為1000的倍數）

                便捷字段（可選，會自動計算 total_quantity）:
                - split_count (int): 總拆單次數，會自動計算 total_quantity = split_count * single_quantity **（推薦使用，替代 total_quantity）**
            order (dict): 委託內容（ConditionOrderArgs）
                - quantity (int): 總委託股數（必須為1000的倍數）

        Returns:
            dict: 成功時回傳 guid 與摘要資訊

        Example:
            # 使用基本字段（5張 = 5000股）
            {
                "account": "123456",
                "start_date": "20241106",
                "end_date": "20241107",
                "stop_sign": "Full",
                "split": {
                    "method": "Type1",
                    "interval": 30,
                    "single_quantity": 1000,  # 1張 = 1000股
                    "total_quantity": 5000,   # 5張 = 5000股
                    "start_time": "090000"
                },
                "order": {
                    "buy_sell": "Buy",
                    "symbol": "2867",
                    "price": "6.41",
                    "quantity": 5000,  # 總數量5張 = 5000股
                    "market_type": "Common",
                    "price_type": "Limit",
                    "time_in_force": "ROD",
                    "order_type": "Stock"
                }
            }

            # 使用便捷字段（自動計算總量）
            {
                "account": "123456",
                "start_date": "20241106",
                "end_date": "20241107",
                "stop_sign": "Full",
                "split": {
                    "method": "Type2",
                    "interval": 30,
                    "single_quantity": 1000,  # 每次1張
                    "split_count": 5,         # 總共5次，自動計算 total_quantity = 5 * 1000 = 5000
                    "start_time": "090000",
                    "end_time": "133000"
                },
                "order": {...}
            }

        Note:
            **取消分時分量條件單的正確流程**:
            1. 使用 `get_order_results(account)` 獲取所有委託結果
            2. 從結果中找到對應的分時分量委託單（可依 symbol、quantity 等識別）
            3. 對每個委託單使用 `cancel_order(account, order_no)` 取消
            4. **不要使用** `cancel_condition_order(account, guid)` 因為分時分量條件單不屬於一般條件單類型
        """
        try:
            validated_args = PlaceTimeSliceOrderArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 構建分時分量條件單參數
            condition_params = {
                "account": account,
                "start_date": validated_args.start_date,
                "end_date": validated_args.end_date,
                "stop_sign": validated_args.stop_sign,
                "split": validated_args.split,
                "order": validated_args.order,
            }

            # 調用 SDK 建立分時分量條件單
            result = self.sdk.place_time_slice_order(**condition_params)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"分時分量條件單建立成功，GUID: {result.data.get('guid', 'N/A')}",
                }
            else:
                error_msg = "分時分量條件單建立失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"分時分量條件單建立失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"建立分時分量條件單時發生錯誤: {str(e)}",
            }

    def place_tpsl_condition_order(self, args: Dict) -> dict:
        """
        停損停利條件單（便捷方法）

        這是 place_condition_order 的便捷包裝，專門用於建立含停損停利的條件單。
        內部調用相同的 single_condition API。

        當觸發條件達成並成交後，自動啟動停損停利監控機制。
        當停利條件達成時停損失效，反之亦然（OCO機制）。

        ⚠️ 重要提醒：
        - 條件單目前不支援期權商品與現貨商品混用
        - 停損停利設定僅為觸發送單，不保證必定成交
        - 請確認停損停利委託類別設定符合交易規則
        - 待主單完全成交後，停損停利部分才會啟動

        Args: 與 place_condition_order 相同，但 tpsl 為必填

        Returns:
            dict: 包含狀態和訂單資訊的字典

        Note:
            此方法為便捷包裝，實際功能與 place_condition_order(含tpsl參數) 相同。
            建議直接使用 place_condition_order 並視需要提供 tpsl 參數。
        """
        try:
            validated_args = PlaceTpslConditionOrderArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 構建停損停利條件單參數
            condition_params = {
                "account": account,
                "start_date": validated_args.start_date,
                "end_date": validated_args.end_date,
                "stop_sign": validated_args.stop_sign,
                "condition": validated_args.condition,
                "order": validated_args.order,
                "tpsl": validated_args.tpsl,
            }

            # 調用 SDK 建立停損停利條件單
            result = self.sdk.place_condition_order(**condition_params)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"停損停利條件單建立成功，條件單號: {result.data.get('condition_no', 'N/A')}",
                }
            else:
                error_msg = "停損停利條件單建立失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"停損停利條件單建立失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"建立停損停利條件單時發生錯誤: {str(e)}",
            }

    def cancel_condition_order(self, args: Dict) -> dict:
        """
        取消條件單

        Args:
            account (str): 帳戶號碼
            condition_no (str): 條件單號
        """
        try:
            validated_args = CancelConditionOrderArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 調用 SDK 取消條件單
            result = self.sdk.cancel_condition_order(
                account=account, condition_no=validated_args.condition_no
            )

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"條件單 {validated_args.condition_no} 取消成功",
                }
            else:
                error_msg = "取消條件單失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"取消條件單失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"取消條件單時發生錯誤: {str(e)}",
            }

    def get_condition_order(self, args: Dict) -> dict:
        """
        查詢條件單清單

        Args:
            account (str): 帳戶號碼
        """
        try:
            validated_args = GetConditionOrderArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 查詢條件單
            result = self.sdk.stock.get_condition_order(account=account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"成功獲取條件單清單",
                }
            else:
                error_msg = "查詢條件單失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"查詢條件單失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"查詢條件單時發生錯誤: {str(e)}",
            }

    def get_condition_order_by_id(self, args: Dict) -> dict:
        """
        依條件單號查詢條件單

        Args:
            account (str): 帳戶號碼
            condition_no (str): 條件單號
        """
        try:
            validated_args = GetConditionOrderByIdArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 調用 SDK 查詢條件單
            result = self.sdk.get_condition_order_by_id(
                account=account, condition_no=validated_args.condition_no
            )

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"成功獲取條件單 {validated_args.condition_no} 詳細資訊",
                }
            else:
                error_msg = "查詢條件單失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"查詢條件單失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"查詢條件單時發生錯誤: {str(e)}",
            }

    def get_daytrade_condition_by_id(self, args: Dict) -> dict:
        """
        依條件單號查詢當沖條件單

        Args:
            account (str): 帳戶號碼
            condition_no (str): 條件單號
        """
        try:
            validated_args = GetDaytradeConditionByIdArgs(**args)
            account = validate_and_get_account(validated_args.account)

            # 調用 SDK 查詢當沖條件單
            result = self.sdk.get_daytrade_condition_by_id(
                account=account, condition_no=validated_args.condition_no
            )

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"成功獲取當沖條件單 {validated_args.condition_no} 詳細資訊",
                }
            else:
                error_msg = "查詢當沖條件單失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"查詢當沖條件單失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"查詢當沖條件單時發生錯誤: {str(e)}",
            }

    def get_trail_order(self, args: Dict) -> dict:
        """
        有效移動鎖利查詢（get_trail_order）

        查詢目前有效的移動鎖利條件單清單，對應官方 SDK `get_trail_order`。

        Args:
            account (str): 帳號

        Returns:
            dict: 成功時回傳展開的清單資料（可序列化 dict 陣列）
        """
        try:
            validated_args = GetTrailOrderArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 查詢移動鎖利單
            result = self.sdk.stock.get_trail_order(account=account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"成功獲取移動鎖利單清單",
                }
            else:
                error_msg = "查詢移動鎖利單失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"查詢移動鎖利單失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"查詢移動鎖利單時發生錯誤: {str(e)}",
            }

    def get_order_results(self, args: Dict) -> dict:
        """
        獲取委託結果

        Args:
            account (str): 帳戶號碼
        """
        try:
            validated_args = GetOrderResultsArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取委託結果
            result = self.sdk.stock.get_order_results(account=account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"成功獲取委託結果",
                }
            else:
                error_msg = "獲取委託結果失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取委託結果失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取委託結果時發生錯誤: {str(e)}",
            }

    def get_order_results_detail(self, args: Dict) -> dict:
        """
        獲取委託結果詳細資訊（包含修改歷史）

        查詢帳戶下的所有委託單狀態及詳細資訊，對應官方 SDK `get_order_results_detail(account)`。
        與 get_order_results 不同，此函數返回包含委託單修改歷史的詳細資訊。

        ⚠️ 重要用途：
        - 確認普通委託單的狀態及修改歷史
        - **查詢分時分量條件單產生的子委託單**（用於取消操作）
        - 監控委託單的執行進度及所有修改記錄

        Args:
            account (str): 帳戶號碼

        Returns:
            dict: 成功時返回委託結果詳細列表，每筆委託單包含以下關鍵字段：
                - function_type (str): 功能類型
                - date (str): 日期
                - seq_no (str): 序號
                - branch_no (str): 分行號碼
                - account (str): 帳戶號碼
                - order_no (str): 委託單號
                - asset_type (str): 資產類型
                - market (str): 市場
                - market_type (str): 市場類型
                - stock_no (str): 股票代碼
                - buy_sell (str): 買賣別
                - price_type (str): 價格類型
                - price (str): 委託價格
                - quantity (int): 原始委託數量
                - time_in_force (str): 有效期間
                - order_type (str): 委託類型
                - status (str): 委託狀態
                - filled_qty (int): 已成交數量
                - filled_money (float): 已成交金額
                - details (list): 詳細資訊及修改歷史
                    - function_type (str): 功能類型
                    - modified_time (str): 修改時間
                    - before_qty (int): 修改前數量
                    - after_qty (int): 修改後數量
                    - status (str): 狀態
                    - error_message (str): 錯誤訊息（如有）
                - error_message (str): 錯誤訊息

        Note:
            **委託單修改歷史追蹤**:
            - details 陣列記錄了委託單的所有修改操作
            - 包括改價、改量、取消等操作的詳細記錄
            - 可追蹤委託單從建立到最終狀態的完整生命週期

            **用於取消分時分量條件單**:
            分時分量條件單會產生多個子委託單，此函數返回的結果包含所有委託單，
            可從中找到對應的 order_no 用於 cancel_order 操作。
        """
        try:
            validated_args = GetOrderResultsDetailArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取委託結果詳細資訊
            result = self.sdk.stock.get_order_results_detail(account=account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"成功獲取委託結果詳細資訊",
                }
            else:
                error_msg = "獲取委託結果詳細資訊失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取委託結果詳細資訊失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取委託結果詳細資訊時發生錯誤: {str(e)}",
            }

    def place_trail_profit(self, args: Dict) -> dict:
        """
        移動鎖利條件單（trail_profit）

        當前價格相對於基準價達到設定之漲跌百分比（以 percentage 與 direction 計算）時觸發下單。

        ⚠️ 注意：
        - TrailOrder 基準價 price 只可輸入至多小數點後兩位，否則可能造成洗價失敗（此工具已做基本檢核）
        - 條件單不支援期權與現貨混用

        Args:
            account (str): 帳號
            start_date (str): 監控開始時間（YYYYMMDD）
            end_date (str): 監控結束時間（YYYYMMDD）
            stop_sign (str): Full/Partial/UntilEnd
            trail (dict): TrailOrder 參數（TrailOrderArgs 結構）

        Returns:
            dict: 成功時回傳 guid 與摘要

        Example:
            {
                "account": "1234567",
                "start_date": "20240427",
                "end_date": "20240516",
                "stop_sign": "Full",
                "trail": {
                    "symbol": "2330",
                    "price": "860",
                    "direction": "Up",
                    "percentage": 5,
                    "buy_sell": "Buy",
                    "quantity": 2000,
                    "price_type": "MatchedPrice",
                    "diff": 5,
                    "time_in_force": "ROD",
                    "order_type": "Stock"
                }
            }
        """
        try:
            from fubon_neo.constant import BSAction, TimeInForce

            # 驗證輸入
            account = args.get("account")
            start_date = args.get("start_date")
            end_date = args.get("end_date")
            stop_sign = args.get("stop_sign", "Full")
            trail_dict = args.get("trail") or {}

            # 檢核 trail 參數
            trail_args = TrailOrderArgs(**trail_dict)

            # 帳戶
            account_obj, error = validate_and_get_account(account)
            if error:
                return {"status": "error", "message": error}

            # 組 TrailOrder 物件
            trail = TrailOrder(
                symbol=trail_args.symbol,
                price=trail_args.price,
                direction=to_direction(trail_args.direction),
                percentage=trail_args.percentage,
                buy_sell=to_bs_action(trail_args.buysell),
                quantity=trail_args.quantity,
                price_type=to_condition_price_type(trail_args.price_type),
                diff=trail_args.diff,
                time_in_force=to_time_in_force(trail_args.time_in_force),
                order_type=to_condition_order_type(trail_args.order_type),
            )

            # 呼叫 SDK
            result = self.sdk.stock.trail_profit(
                account_obj,
                start_date,
                end_date,
                to_stop_sign(stop_sign),
                trail,
            )

            if result and hasattr(result, "is_success") and result.is_success:
                guid = (
                    getattr(result.data, "guid", None)
                    if hasattr(result, "data")
                    else None
                )
                return {
                    "status": "success",
                    "data": {
                        "guid": guid,
                        "condition_no": guid,
                        "symbol": trail_args.symbol,
                        "buy_sell": trail_args.buysell,
                        "quantity": trail_args.quantity,
                        "direction": trail_args.direction,
                        "percentage": trail_args.percentage,
                    },
                    "message": f"移動鎖利條件單已建立 - {trail_args.symbol}",
                }

            error_msg = (
                getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
            )
            return {
                "status": "error",
                "message": f"移動鎖利條件單建立失敗: {error_msg}",
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"移動鎖利條件單建立時發生錯誤: {str(e)}",
            }

    def get_trail_history(self, args: Dict) -> dict:
        """
        歷史移動鎖利查詢（get_trail_history）

        查詢指定期間內的歷史移動鎖利條件單紀錄，對應官方 SDK `get_trail_history(account, start_date, end_date)`。

        Args:
            account (str): 帳號
            start_date (str): 查詢開始日，格式 YYYYMMDD
            end_date (str): 查詢截止日，格式 YYYYMMDD

        Returns:
            dict: 成功時回傳可序列化的歷史條件單清單資料（ConditionDetail 陣列）
        """
        try:
            validated = GetTrailHistoryArgs(**args)

            # 帳戶驗證
            account_obj, error = validate_and_get_account(validated.account)
            if error:
                return {"status": "error", "message": error}

            # 呼叫 SDK
            result = self.sdk.stock.get_trail_history(
                account_obj, validated.start_date, validated.end_date
            )

            if result and hasattr(result, "is_success") and result.is_success:
                data = getattr(result, "data", []) or []
                data_list = self._to_dict(data) or []
                count = len(data_list) if isinstance(data_list, list) else 0
                return {
                    "status": "success",
                    "data": data_list,
                    "message": f"查詢成功，共 {count} 筆（{validated.start_date}~{validated.end_date}）",
                }

            error_msg = (
                getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
            )
            return {"status": "error", "message": f"查詢失敗: {error_msg}"}

        except Exception as e:
            return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}

    def get_condition_history(self, args: Dict) -> dict:
        """
        歷史條件單查詢（get_condition_history）

        查詢指定期間內的歷史條件單紀錄，對應官方 SDK `get_condition_history(account, start_date, end_date)`。

        Args:
            account (str): 帳號
            start_date (str): 查詢開始日，格式 YYYYMMDD
            end_date (str): 查詢截止日，格式 YYYYMMDD

        Returns:
            dict: 成功時回傳可序列化的歷史條件單清單資料（ConditionDetail 陣列）
        """
        try:
            validated = GetConditionHistoryArgs(**args)

            # 帳戶驗證
            account_obj, error = validate_and_get_account(validated.account)
            if error:
                return {"status": "error", "message": error}

            # 呼叫 SDK
            result = self.sdk.stock.get_condition_history(
                account_obj, validated.start_date, validated.end_date
            )

            if result and hasattr(result, "is_success") and result.is_success:
                data = getattr(result, "data", []) or []
                data_list = self._to_dict(data) or []
                count = len(data_list) if isinstance(data_list, list) else 0
                return {
                    "status": "success",
                    "data": data_list,
                    "message": f"查詢成功，共 {count} 筆（{validated.start_date}~{validated.end_date}）",
                }

            error_msg = (
                getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
            )
            return {"status": "error", "message": f"查詢失敗: {error_msg}"}

        except Exception as e:
            return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}

    def get_time_slice_order(self, args: Dict) -> dict:
        """
        分時分量查詢（get_time_slice_order）

        查詢指定分時分量條件單號的明細列表，對應官方 SDK
        `get_time_slice_order(account, batch_no)`。

        ⚠️ 查詢用途：
        - 查看分時分量條件單的設定和狀態
        - 監控拆單進度
        - **注意**：此函數查詢的是條件單本身，不是產生的委託單
        如需取消，請使用 get_order_results + cancel_order

        Args:
            account (str): 帳號
            batch_no (str): 分時分量條件單號

        Returns:
            dict: 成功時回傳展開的明細陣列（ConditionDetail list）

        Note:
            此函數返回條件單的設定資訊，但**無法用於取消操作**。
            分時分量條件單會立即產生多個普通委託單，取消時需要：
            1. 用 get_order_results 查詢所有委託單
            2. 用 cancel_order 逐筆取消各個子委託單
        """
        try:
            validated = GetTimeSliceOrderArgs(**args)

            # 帳戶驗證
            account_obj, error = validate_and_get_account(validated.account)
            if error:
                return {"status": "error", "message": error}

            # 呼叫 SDK
            result = self.sdk.stock.get_time_slice_order(
                account_obj, validated.batch_no
            )

            # 序列化
            def to_dict(obj):
                if obj is None:
                    return None
                if isinstance(obj, (str, int, float, bool)):
                    return obj
                if isinstance(obj, list):
                    return [to_dict(x) for x in obj]
                if isinstance(obj, dict):
                    return {k: to_dict(v) for k, v in obj.items()}
                try:
                    return {
                        k: to_dict(v)
                        for k, v in vars(obj).items()
                        if not k.startswith("_")
                    }
                except Exception:
                    return str(obj)

            if result and hasattr(result, "is_success") and result.is_success:
                data = getattr(result, "data", []) or []
                data_list = to_dict(data) or []
                count = len(data_list) if isinstance(data_list, list) else 0
                return {
                    "status": "success",
                    "data": data_list,
                    "message": f"查詢成功，共 {count} 筆（batch_no={validated.batch_no}）",
                }

            error_msg = (
                getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
            )
            return {"status": "error", "message": f"查詢失敗: {error_msg}"}

        except Exception as e:
            return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


# 參數模型定義
class PlaceOrderArgs(BaseModel):
    account: str
    buy_sell: str
    symbol: str
    price: str
    quantity: int
    market_type: str = "Common"
    price_type: str = "Limit"
    time_in_force: str = "ROD"
    order_type: str = "Stock"


class CancelOrderArgs(BaseModel):
    account: str
    order_no: str


class ModifyPriceArgs(BaseModel):
    account: str
    order_no: str
    new_price: float


class ModifyQuantityArgs(BaseModel):
    account: str
    order_no: str
    new_quantity: int


class BatchPlaceOrderArgs(BaseModel):
    orders: List[Dict]


class PlaceConditionOrderArgs(BaseModel):
    """單一條件單參數模型（可選停損停利）"""

    account: str  # 帳戶號碼
    start_date: str  # 開始日期 YYYYMMDD
    end_date: str  # 結束日期 YYYYMMDD
    stop_sign: str = "Full"  # Full(全部成交), Partial(部分成交), UntilEnd(效期結束)
    condition: Dict  # 條件參數（ConditionArgs）
    order: Dict  # 委託單參數（ConditionOrderArgs）
    tpsl: Optional[Dict] = None  # 停損停利參數（TPSLWrapperArgs，選填）


class PlaceMultiConditionOrderArgs(BaseModel):
    """多條件單參數模型（可選停損停利）"""

    account: str  # 帳戶號碼
    start_date: str  # 開始日期 YYYYMMDD
    end_date: str  # 結束日期 YYYYMMDD
    stop_sign: str = "Full"  # Full(全部成交), Partial(部分成交), UntilEnd(效期結束)
    conditions: List[Dict]  # 多個條件參數（List of ConditionArgs）
    order: Dict  # 委託單參數（ConditionOrderArgs）
    tpsl: Optional[Dict] = None  # 停損停利參數（TPSLWrapperArgs，選填）


class PlaceDaytradeConditionOrderArgs(BaseModel):
    account: str
    start_date: str
    end_date: str
    stop_sign: str = "Full"
    conditions: List[Dict]
    order: Dict


class PlaceDayTradeMultiConditionOrderArgs(BaseModel):
    """當沖多條件單參數模型（可選停損停利）"""

    account: str
    stop_sign: str = "Full"  # Full(全部成交), Partial(部分成交), UntilEnd(效期結束)
    end_time: str  # 父單洗價結束時間（例："130000"）
    conditions: List[Dict]  # 多個觸發條件（List of ConditionArgs）
    order: Dict  # 主單委託內容（ConditionOrderArgs）
    daytrade: Dict  # 當沖回補內容（ConditionDayTradeArgs）
    tpsl: Optional[Dict] = None  # 停損停利（TPSLWrapperArgs，選填）
    fix_session: bool = False  # 是否執行定盤回補


class PlaceTimeSliceOrderArgs(BaseModel):
    """分時分量條件單請求參數"""

    account: str
    start_date: str
    end_date: str
    stop_sign: str = "Full"  # Full, Partial, UntilEnd
    split: Dict  # TimeSliceSplitArgs
    order: Dict  # ConditionOrderArgs


class PlaceTpslConditionOrderArgs(BaseModel):
    account: str
    start_date: str
    end_date: str
    stop_sign: str = "Full"
    condition: Dict
    order: Dict
    tpsl: Dict


class CancelConditionOrderArgs(BaseModel):
    """取消條件單參數"""

    account: str
    condition_no: str


class GetConditionOrderArgs(BaseModel):
    """條件單查詢參數"""

    account: str
    condition_status: Optional[str] = None  # 對應 ConditionStatus，選填


class GetConditionOrderByIdArgs(BaseModel):
    account: str
    condition_no: str


class GetDaytradeConditionByIdArgs(BaseModel):
    account: str
    condition_no: str


class GetTrailOrderArgs(BaseModel):
    account: str


class GetOrderResultsArgs(BaseModel):
    account: str


class GetOrderResultsDetailArgs(BaseModel):
    account: str


class TPSLOrderArgs(BaseModel):
    """停損停利單參數模型"""

    time_in_force: str = "ROD"  # ROD, IOC, FOK
    price_type: str = "Limit"  # BidPrice, AskPrice, MatchedPrice, Limit, LimitUp, LimitDown, Market, Reference
    order_type: str = "Stock"  # Stock, Margin, Short
    target_price: str  # 停損/停利觸發價
    price: str  # 停損/停利委託價，若為市價則填空值""
    trigger: Optional[str] = (
        "MatchedPrice"  # 停損/停利觸發條件，可選 MatchedPrice, BidPrice, AskPrice，預設 MatchedPrice
    )


class TPSLWrapperArgs(BaseModel):
    """停損停利包裝器參數模型"""

    stop_sign: str = "Full"  # Full(全部), Flat(減碼)
    tp: Optional[Dict] = None  # 停利單參數（TPSLOrderArgs）
    sl: Optional[Dict] = None  # 停損單參數（TPSLOrderArgs）
    end_date: Optional[str] = None  # 結束日期 YYYYMMDD（選填）
    intraday: Optional[bool] = False  # 是否為當日有效（選填）


class ConditionDayTradeArgs(BaseModel):
    """當沖回補參數模型 (ConditionDayTrade)"""

    day_trade_end_time: str  # 收盤前沖銷時間，區間 130100 ~ 132000
    auto_cancel: bool = True  # 是否自動取消
    price: str = ""  # 定盤/沖銷價格，市價時請留空字串
    price_type: str = "Market"  # Market 或 Limit（對應 ConditionPriceType）


class ConditionArgs(BaseModel):
    """條件單觸發條件參數模型"""

    market_type: str = "Reference"  # 對應 TradingType：Reference, LastPrice
    symbol: str  # 股票代碼
    trigger: str = "MatchedPrice"  # 觸發內容：MatchedPrice(成交價), BuyPrice(買價), SellPrice(賣價), TotalQuantity(累計成交量), Time(時間)
    trigger_value: str  # 觸發值
    comparison: str = "LessThan"  # 比較運算子：LessThan(<), LessOrEqual(<=), Equal(=), Greater(>), GreaterOrEqual(>=)


class ConditionOrderArgs(BaseModel):
    """條件委託單參數模型"""

    buy_sell: str  # Buy, Sell
    symbol: str  # 股票代碼
    price: str  # 委託價格
    quantity: int  # 委託數量（股）
    market_type: str = "Common"  # Common(一般), Emg(緊急), Odd(盤後零股)
    price_type: str = "Limit"  # Limit, Market, LimitUp, LimitDown
    time_in_force: str = "ROD"  # ROD, IOC, FOK
    order_type: str = "Stock"  # Stock, Margin, Short, DayTrade


class TrailOrderArgs(BaseModel):
    """移動鎖利 TrailOrder 參數模型"""

    symbol: str
    price: str  # 基準價，至多小數兩位
    direction: str  # Up 或 Down
    percentage: int  # 漲跌百分比（整數）
    buysell: str  # Buy 或 Sell (官方參數名稱)
    quantity: int  # 委託數量（股）
    price_type: str = "MatchedPrice"
    diff: int  # 追價 tick 數（向下為負值）
    time_in_force: str = "ROD"
    order_type: str = "Stock"

    @classmethod
    def _validate_two_decimals(cls, value: str) -> str:
        if value is None:
            return value
        if "." in value:
            frac = value.split(".", 1)[1]
            if len(frac) > 2:
                raise ValueError("TrailOrder.price 只可至多小數點後兩位")
        return value

    @classmethod
    def _validate_direction(cls, value: str) -> str:
        """驗證 direction 字段是否為有效的 Direction 枚舉值"""
        if value not in ["Up", "Down"]:
            raise ValueError("TrailOrder.direction 必須是 'Up' 或 'Down'")
        return value

    def model_post_init(self, __context):
        # 執行 price 小數位數檢核
        self.price = self._validate_two_decimals(self.price)
        # 驗證 direction
        self.direction = self._validate_direction(self.direction)


class GetTimeSliceOrderArgs(BaseModel):
    """分時分量查詢參數"""

    account: str
    batch_no: str


class GetTrailHistoryArgs(BaseModel):
    account: str
    start_date: str
    end_date: str


class GetConditionHistoryArgs(BaseModel):
    """歷史條件單查詢參數"""

    account: str
    start_date: str
    end_date: str
    condition_history_status: Optional[str] = None  # 對應 HistoryStatus，選填
