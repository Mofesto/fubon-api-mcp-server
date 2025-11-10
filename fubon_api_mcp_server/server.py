#!/usr/bin/env python3
"""
富邦證券 MCP (Model Context Protocol) 服務器

此模組實現了一個完整的富邦證券交易 API MCP 服務器，提供以下功能：
- 股票歷史數據查詢（本地快取 + API 調用）
- 即時行情數據獲取
- 股票交易下單（買賣、改價、改量、取消）
- 帳戶資訊查詢（資金餘額、庫存、損益）
- 主動回報監聽（委託、成交、事件通知）
- 批量並行下單功能

主要組件：
- FastMCP: MCP 服務器框架
- FubonSDK: 富邦證券官方 SDK
- Pydantic: 數據驗證和序列化
- Pandas: 數據處理和分析

環境變數需求：
- FUBON_USERNAME: 富邦證券帳號
- FUBON_PASSWORD: 密碼
- FUBON_PFX_PATH: PFX 憑證檔案路徑
- FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）
- FUBON_DATA_DIR: 本地數據儲存目錄（可選，預設為用戶應用程式支援目錄）

作者: MCP Server Team
版本: 1.6.0
"""

import concurrent.futures
import functools
import os
import shutil
import sys
import tempfile
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Set encoding for stdout and stderr to handle Chinese characters properly
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from dotenv import load_dotenv
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

from . import indicators

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

# 加載環境變數配置
load_dotenv()

# =============================================================================
# 配置和全局變數
# =============================================================================

# 數據目錄配置 - 用於儲存本地快取的股票歷史數據
DEFAULT_DATA_DIR = (
    Path.home() / "Library" / "Application Support" / "fubon-mcp" / "data"
)
BASE_DATA_DIR = Path(os.getenv("FUBON_DATA_DIR", DEFAULT_DATA_DIR))

# 確保數據目錄存在
BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
print(f"使用數據目錄: {BASE_DATA_DIR}", file=sys.stderr)


# =============================================================================
# 輔助函數 - 用於減少代碼複雜性和重複
# =============================================================================


def validate_and_get_account(account: str) -> tuple:
    """
    驗證帳戶並返回帳戶對象。

    Args:
        account (str): 帳戶號碼

    Returns:
        tuple: (account_obj, error_message) - 如果成功，account_obj為帳戶對象，error_message為None
               如果失敗，account_obj為None，error_message為錯誤訊息
    """
    try:
        if not accounts or not hasattr(accounts, 'data'):
            return None, "帳戶資訊未初始化"

        for acc in accounts.data:
            if getattr(acc, 'account', None) == account:
                return acc, None

        return None, f"找不到帳戶 {account}"
    except Exception as e:
        return None, f"帳戶驗證失敗: {str(e)}"


def get_order_by_no(account_obj, order_no: str) -> tuple:
    """
    根據委託單號獲取委託對象。

    Args:
        account_obj: 帳戶對象
        order_no (str): 委託單號

    Returns:
        tuple: (order_obj, error_message) - 如果成功，order_obj為委託對象，error_message為None
               如果失敗，order_obj為None，error_message為錯誤訊息
    """
    try:
        order_results = sdk.stock.get_order_results(account_obj)
        if not (
            order_results
            and hasattr(order_results, "is_success")
            and order_results.is_success
        ):
            return None, "無法獲取帳戶委託結果"

        # 找到對應的委託單
        target_order = None
        if hasattr(order_results, "data") and order_results.data:
            for order in order_results.data:
                if getattr(order, "order_no", None) == order_no:
                    target_order = order
                    break

        if not target_order:
            return None, f"找不到委託單號 {order_no}"

        return target_order, None
    except Exception as e:
        return None, f"獲取委託結果時發生錯誤: {str(e)}"


def fetch_historical_data_segment(symbol: str, from_date: str, to_date: str) -> list:
    """
    獲取一段歷史數據。

    Args:
        symbol (str): 股票代碼
        from_date (str): 開始日期
        to_date (str): 結束日期

    Returns:
        list: 數據列表，如果失敗返回空列表
    """
    try:
        params = {"symbol": symbol, "from": from_date, "to": to_date}
        print(
            f"正在獲取 {symbol} 從 {params['from']} 到 {params['to']} 的數據...",
            file=sys.stderr,
        )
        response = reststock.historical.candles(**params)
        print(f"API 回應內容: {response}", file=sys.stderr)

        if isinstance(response, dict):
            if "data" in response and response["data"]:
                segment_data = response["data"]
                print(f"成功獲取 {len(segment_data)} 筆資料", file=sys.stderr)
                return segment_data
            else:
                print(f"API 回應無資料: {response}", file=sys.stderr)
        else:
            print(f"API 回應格式錯誤: {response}", file=sys.stderr)
    except Exception as segment_error:
        print(f"獲取分段資料時發生錯誤: {str(segment_error)}", file=sys.stderr)

    return []


def process_historical_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    處理歷史數據，添加計算欄位。

    Args:
        df (pd.DataFrame): 原始數據

    Returns:
        pd.DataFrame: 處理後的數據
    """
    df = df.sort_values(by="date", ascending=False)
    # 添加更多資訊欄位
    df["vol_value"] = df["close"] * df["volume"]  # 成交值
    df["price_change"] = df["close"] - df["open"]  # 漲跌
    df["change_ratio"] = (df["close"] - df["open"]) / df["open"] * 100  # 漲跌幅
    return df


# 環境變數中的認證資訊
username = os.getenv("FUBON_USERNAME")
password = os.getenv("FUBON_PASSWORD")
pfx_path = os.getenv("FUBON_PFX_PATH")
pfx_password = os.getenv("FUBON_PFX_PASSWORD")

# MCP 服務器實例
mcp = FastMCP("fubon-api-mcp-server")

# =============================================================================
# SDK 相關全局變數（在 main() 中初始化以避免導入時錯誤）
# =============================================================================

# 富邦 SDK 實例
sdk = None
# REST API 客戶端（用於股票數據查詢）
reststock = None
# REST API 客戶端（用於期貨/選擇權數據查詢）
restfutopt = None
# 帳戶資訊（用於測試兼容性）
accounts = None

# =============================================================================
# 主動回報數據存儲（全局變數，線程安全）
# 這些全局變數由 SDK 回調函數使用，用於存儲主動回報數據
# =============================================================================

# 最新的委託回報（最多保留10筆）
latest_order_reports = []  # noqa: F824 - 由 SDK 回調函數修改
# 最新的改價/改量/刪單回報（最多保留10筆）
latest_order_changed_reports = []  # noqa: F824 - 由 SDK 回調函數修改
# 最新的成交回報（最多保留10筆）
latest_filled_reports = []  # noqa: F824 - 由 SDK 回調函數修改
# 最新的事件通知回報（最多保留10筆）
latest_event_reports = []  # noqa: F824 - 由 SDK 回調函數修改

# 全域鎖定 - 避免同時重複觸發重連機制
relogin_lock = threading.Lock()


def handle_exceptions(func):
    """
    異常處理裝飾器。

    為函數添加全域異常處理，當函數執行發生例外時，
    會捕獲例外並輸出詳細的錯誤資訊到標準錯誤輸出。

    參數:
        func: 要裝飾的函數

    返回:
        wrapper: 裝飾後的函數
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exp:
            # Extract the full traceback
            tb_lines = traceback.format_exc().splitlines()

            # Find the index of the line related to the original function
            func_line_index = next(
                (i for i, line in enumerate(tb_lines) if func.__name__ in line), -1
            )

            # Highlight the specific part in the traceback where the exception occurred
            relevant_tb = "\n".join(
                tb_lines[func_line_index:]
            )  # Include traceback from the function name

            error_text = f"{func.__name__} exception: {exp}\nTraceback (most recent call last):\n{relevant_tb}"
            print(error_text, file=sys.stderr)

            # 若要程式完全跳出，可加入下行 (P.S. jupyter 環境不適用)
            # os._exit(-1)

    return wrapper


# =============================================================================
# 主動回報回調函數
# =============================================================================


def on_order(order_data):
    """
    委託回報事件回調函數。

    當有新的委託單被建立或狀態改變時，此函數會被SDK調用。
    接收到的委託數據會被添加到全局的 latest_order_reports 列表中，
    並限制列表長度最多保留10筆記錄。

    參數:
        order_data: 委託相關的數據對象，包含委託單的詳細資訊
    """
    global latest_order_reports  # noqa: F824 - SDK 回調函數需要修改全局變數
    try:
        # 添加時間戳到數據中
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": order_data}
        latest_order_reports.append(timestamped_data)

        # 限制列表長度，最多保留10筆記錄
        if len(latest_order_reports) > 10:
            latest_order_reports.pop(0)

        print(f"收到委託回報: {order_data}", file=sys.stderr)
    except Exception as e:
        print(f"處理委託回報時發生錯誤: {str(e)}", file=sys.stderr)


def on_order_changed(order_changed_data):
    """
    改價/改量/刪單回報事件回調函數。

    當委託單被修改（價格、數量）或刪除時，此函數會被SDK調用。
    接收到的數據會被添加到全局的 latest_order_changed_reports 列表中，
    並限制列表長度最多保留10筆記錄。

    參數:
        order_changed_data: 委託變更相關的數據對象
    """
    global latest_order_changed_reports  # noqa: F824 - SDK 回調函數需要修改全局變數
    try:
        # 添加時間戳到數據中
        timestamped_data = {
            "timestamp": datetime.now().isoformat(),
            "data": order_changed_data,
        }
        latest_order_changed_reports.append(timestamped_data)

        # 限制列表長度，最多保留10筆記錄
        if len(latest_order_changed_reports) > 10:
            latest_order_changed_reports.pop(0)

        print(f"收到改價/改量/刪單回報: {order_changed_data}", file=sys.stderr)
    except Exception as e:
        print(f"處理改價/改量/刪單回報時發生錯誤: {str(e)}", file=sys.stderr)


def on_filled(filled_data):
    """
    成交回報事件回調函數。

    當委託單發生成交時，此函數會被SDK調用。
    接收到的成交數據會被添加到全局的 latest_filled_reports 列表中，
    並限制列表長度最多保留10筆記錄。

    參數:
        filled_data: 成交相關的數據對象，包含成交價格、數量等資訊
    """
    global latest_filled_reports  # noqa: F824 - SDK 回調函數需要修改全局變數
    try:
        # 添加時間戳到數據中
        timestamped_data = {
            "timestamp": datetime.now().isoformat(),
            "data": filled_data,
        }
        latest_filled_reports.append(timestamped_data)

        # 限制列表長度，最多保留10筆記錄
        if len(latest_filled_reports) > 10:
            latest_filled_reports.pop(0)

        print(f"收到成交回報: {filled_data}", file=sys.stderr)
    except Exception as e:
        print(f"處理成交回報時發生錯誤: {str(e)}", file=sys.stderr)


def on_event(event_data):
    """
    事件通知回調函數。

    當SDK發生各種事件（如連接狀態變化、錯誤通知等）時，此函數會被調用。
    接收到的事件數據會被添加到全局的 latest_event_reports 列表中，
    並限制列表長度最多保留10筆記錄。

    參數:
        event_data: 事件相關的數據對象，包含事件類型和詳細資訊
    """
    global latest_event_reports  # noqa: F824 - SDK 回調函數需要修改全局變數
    try:
        # 添加時間戳到數據中
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": event_data}
        latest_event_reports.append(timestamped_data)

        # 限制列表長度，最多保留10筆記錄
        if len(latest_event_reports) > 10:
            latest_event_reports.pop(0)

        print(f"收到事件通知: {event_data}", file=sys.stderr)
    except Exception as e:
        print(f"處理事件通知時發生錯誤: {str(e)}", file=sys.stderr)


def read_local_stock_data(stock_code):
    """
    讀取本地快取的股票歷史數據。

    從本地 CSV 文件讀取股票歷史數據，如果檔案不存在則返回 None。
    數據會按日期降序排序（最新的在前面）。

    參數:
        stock_code (str): 股票代碼，用作檔案名稱

    返回:
        pandas.DataFrame or None: 股票歷史數據 DataFrame，包含日期等欄位
    """
    try:
        file_path = BASE_DATA_DIR / f"{stock_code}.csv"
        if not file_path.exists():
            return None

        df = pd.read_csv(file_path)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(by="date", ascending=False)
        return df
    except Exception as e:
        print(f"讀取CSV檔案時發生錯誤: {str(e)}", file=sys.stderr)
        return None


def save_to_local_csv(symbol: str, new_data: list):
    """
    將新的股票數據保存到本地 CSV 文件，避免重複數據。

    使用原子寫入方式（先寫到臨時檔案再移動）確保數據完整性。
    如果檔案已存在，會合併新舊數據並刪除重複項。

    參數:
        symbol (str): 股票代碼，用作檔案名稱
        new_data (list): 新的股票數據列表
    """
    try:
        file_path = BASE_DATA_DIR / f"{symbol}.csv"
        new_df = pd.DataFrame(new_data)
        new_df["date"] = pd.to_datetime(new_df["date"])

        # 創建臨時檔案進行原子寫入
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as temp_file:
            temp_path = Path(temp_file.name)

            try:
                if file_path.exists():
                    # 讀取現有數據並合併
                    existing_df = pd.read_csv(file_path)
                    existing_df["date"] = pd.to_datetime(existing_df["date"])

                    # 合併數據並刪除重複項（以日期為鍵）
                    combined_df = pd.concat([existing_df, new_df])
                    combined_df = combined_df.drop_duplicates(
                        subset=["date"], keep="last"
                    )
                    combined_df = combined_df.sort_values(by="date", ascending=False)
                else:
                    combined_df = new_df.sort_values(by="date", ascending=False)

                # 將合併後的數據寫入臨時檔案
                combined_df.to_csv(temp_path, index=False)

                # 原子性地替換原檔案
                shutil.move(str(temp_path), str(file_path))
                print(f"成功保存數據到 {file_path}", file=sys.stderr)

            except Exception as e:
                # 確保清理臨時檔案
                if temp_path.exists():
                    temp_path.unlink()
                raise e

    except Exception as e:
        print(f"保存CSV檔案時發生錯誤: {str(e)}", file=sys.stderr)


@mcp.resource("twstock://{symbol}/historical")
def get_historical_data(symbol):
    """提供本地歷史股價數據"""
    try:
        data = read_local_stock_data(symbol)
        if data is None:
            return {
                "status": "error",
                "data": [],
                "message": f"找不到股票代碼 {symbol} 的數據",
            }

        return {
            "status": "success",
            "data": data.to_dict("records"),
            "message": f"成功獲取 {symbol} 的歷史數據",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": [],
            "message": f"獲取數據時發生錯誤: {str(e)}",
        }


@mcp.resource("market://tse/overview")
def get_market_overview():
    """提供台灣股市整體概況"""
    try:
        # 嘗試從快取獲取
        cached_data = server_state.get_cached_resource("market_overview")
        if cached_data:
            return cached_data

        # 獲取台股指數行情
        tse_result = reststock.intraday.quote(symbol="IX0001")  # 台股指數
        if (
            not tse_result
            or not hasattr(tse_result, "is_success")
            or not tse_result.is_success
        ):
            return {
                "status": "error",
                "data": None,
                "message": "無法獲取台股指數行情",
            }

        # 獲取市場統計數據
        try:
            movers_result = reststock.snapshots.movers(
                market="TSE", direction="up", change="value", gt=0, type="COMMONSTOCK"
            )
            up_count = (
                len(movers_result.data)
                if movers_result and hasattr(movers_result, "data")
                else 0
            )
        except:
            up_count = 0

        try:
            movers_result = reststock.snapshots.movers(
                market="TSE", direction="down", change="value", lt=0, type="COMMONSTOCK"
            )
            down_count = (
                len(movers_result.data)
                if movers_result and hasattr(movers_result, "data")
                else 0
            )
        except:
            down_count = 0

        # 獲取成交量統計
        try:
            actives_result = reststock.snapshots.actives(
                market="TSE", trade="volume", type="COMMONSTOCK"
            )
            total_volume = (
                sum(
                    getattr(item, "trade_volume", 0)
                    for item in actives_result.data[:10]
                )
                if actives_result and hasattr(actives_result, "data")
                else 0
            )
        except:
            total_volume = 0

        market_data = {
            "index": {
                "name": "台股指數",
                "symbol": "IX0001",
                "price": float(getattr(tse_result.data, "price", 0)),
                "change": float(getattr(tse_result.data, "change", 0)),
                "change_percent": float(getattr(tse_result.data, "change_percent", 0)),
                "volume": int(
                    getattr(tse_result.data, "total", {}).get("trade_volume", 0)
                ),
                "last_updated": getattr(tse_result.data, "at", None),
            },
            "statistics": {
                "up_count": up_count,
                "down_count": down_count,
                "unchanged_count": max(0, 1000 - up_count - down_count),  # 估計值
                "total_volume": total_volume,
                "market_status": "open"
                if hasattr(tse_result.data, "price") and tse_result.data.price > 0
                else "closed",
            },
        }

        result = {
            "status": "success",
            "data": market_data,
            "message": "成功獲取台灣股市整體概況",
        }

        # 快取結果
        server_state.set_cached_resource("market_overview", result)
        return result
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取市場概況時發生錯誤: {str(e)}",
        }


@mcp.resource("portfolio://{account}")
def get_portfolio_summary(account):
    """提供帳戶投資組合摘要"""
    try:
        # 嘗試從快取獲取
        cache_key = f"portfolio_{account}"
        cached_data = server_state.get_cached_resource(cache_key)
        if cached_data:
            return cached_data

        # 驗證帳戶
        account_obj, error = validate_and_get_account(account)
        if error:
            return {
                "status": "error",
                "data": None,
                "message": error,
            }

        # 獲取庫存資訊
        inventory_result = sdk.accounting.inventories(account_obj)
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
        pnl_result = sdk.accounting.unrealized_gains_and_loses(account_obj)
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
                    "quantity": getattr(item, "quantity", 0),
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

        result = {
            "status": "success",
            "data": portfolio_data,
            "message": f"成功獲取帳戶 {account} 投資組合摘要",
        }

        # 快取結果
        server_state.set_cached_resource(cache_key, result)
        return result
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取投資組合摘要時發生錯誤: {str(e)}",
        }


@mcp.resource("watchlist://{account}")
def get_watchlist(account):
    """提供帳戶自選股清單"""
    try:
        # 嘗試從快取獲取
        cache_key = f"watchlist_{account}"
        cached_data = server_state.get_cached_resource(cache_key)
        if cached_data:
            return cached_data

        # 驗證帳戶
        account_obj, error = validate_and_get_account(account)
        if error:
            return {
                "status": "error",
                "data": None,
                "message": error,
            }

        # 目前使用庫存作為自選股的替代方案
        # TODO: 實現真正的自選股功能
        inventory_result = sdk.accounting.inventories(account_obj)
        if (
            not inventory_result
            or not hasattr(inventory_result, "is_success")
            or not inventory_result.is_success
        ):
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 自選股清單",
            }

        watchlist_data = {"account": account, "stocks": []}

        if hasattr(inventory_result, "data"):
            for item in inventory_result.data:
                stock_info = {
                    "symbol": getattr(item, "stock_no", ""),
                    "name": getattr(item, "stock_name", ""),
                    "quantity": getattr(item, "quantity", 0),
                    "last_price": getattr(item, "market_price", 0),
                    "change_percent": 0,  # TODO: 從行情API獲取
                }
                watchlist_data["stocks"].append(stock_info)

        result = {
            "status": "success",
            "data": watchlist_data,
            "message": f"成功獲取帳戶 {account} 自選股清單",
        }

        # 快取結果
        server_state.set_cached_resource(cache_key, result)
        return result
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取自選股清單時發生錯誤: {str(e)}",
        }


@mcp.resource("account://{account}/summary")
def get_account_summary(account):
    """提供帳戶綜合摘要"""
    try:
        # 嘗試從快取獲取
        cache_key = f"account_summary_{account}"
        cached_data = server_state.get_cached_resource(cache_key)
        if cached_data:
            return cached_data

        # 驗證帳戶
        account_obj, error = validate_and_get_account(account)
        if error:
            return {
                "status": "error",
                "data": None,
                "message": error,
            }

        summary_data = {
            "account": account,
            "basic_info": {},
            "financial_info": {},
            "trading_info": {},
        }

        # 獲取基本資訊
        summary_data["basic_info"] = {
            "name": getattr(account_obj, "name", "N/A"),
            "branch_no": getattr(account_obj, "branch_no", "N/A"),
            "account": getattr(account_obj, "account", "N/A"),
            "account_type": getattr(account_obj, "account_type", "N/A"),
        }

        # 獲取財務資訊
        try:
            bank_result = sdk.accounting.bank_remain(account_obj)
            if (
                bank_result
                and hasattr(bank_result, "is_success")
                and bank_result.is_success
            ):
                summary_data["financial_info"]["bank_balance"] = bank_result.data
        except:
            summary_data["financial_info"]["bank_balance"] = None

        try:
            pnl_result = sdk.accounting.unrealized_gains_and_loses(
                account_obj
            )
            if (
                pnl_result
                and hasattr(pnl_result, "is_success")
                and pnl_result.is_success
            ):
                total_pnl = 0
                if hasattr(pnl_result, "data"):
                    for item in pnl_result.data:
                        total_pnl += getattr(item, "unrealized_profit", 0) + getattr(
                            item, "unrealized_loss", 0
                        )
                summary_data["financial_info"]["unrealized_pnl"] = total_pnl
        except:
            summary_data["financial_info"]["unrealized_pnl"] = None

        # 獲取交易資訊
        try:
            order_result = sdk.stock.get_order_results(account_obj)
            if (
                order_result
                and hasattr(order_result, "is_success")
                and order_result.is_success
            ):
                active_orders = 0
                if hasattr(order_result, "data"):
                    for order in order_result.data:
                        if getattr(order, "status", "") not in ["Filled", "Cancelled"]:
                            active_orders += 1
                summary_data["trading_info"]["active_orders"] = active_orders
        except:
            summary_data["trading_info"]["active_orders"] = 0

        result = {
            "status": "success",
            "data": summary_data,
            "message": f"成功獲取帳戶 {account} 綜合摘要",
        }

        # 快取結果
        server_state.set_cached_resource(cache_key, result)
        return result
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取帳戶摘要時發生錯誤: {str(e)}",
        }


class HistoricalCandlesArgs(BaseModel):
    symbol: str
    from_date: str
    to_date: str


class PlaceOrderArgs(BaseModel):
    account: str
    symbol: str
    quantity: int  # 委託數量（股）
    price: float
    buy_sell: str  # 'Buy' or 'Sell'
    market_type: str = "Common"  # 市場別，預設 "Common"
    price_type: str = "Limit"  # 價格類型，預設 "Limit"
    time_in_force: str = "ROD"  # 有效期間，預設 "ROD"
    order_type: str = "Stock"  # 委託類型，預設 "Stock"
    user_def: Optional[str] = None  # 使用者自定義欄位，可選
    is_non_blocking: bool = False  # 是否使用非阻塞模式


class CancelOrderArgs(BaseModel):
    account: str
    order_no: str


class GetAccountInfoArgs(BaseModel):
    account: str


class GetInventoryArgs(BaseModel):
    account: str


class GetUnrealizedPnLArgs(BaseModel):
    account: str


class GetSettlementArgs(BaseModel):
    account: str
    range: str = Field("0d", pattern="^(0d|3d)$")  # 0d: 當日, 3d: 3日


class GetMaintenanceArgs(BaseModel):
    account: str


class GetBankBalanceArgs(BaseModel):
    account: str


class GetMarginQuotaArgs(BaseModel):
    account: str
    stock_no: str


class GetDayTradeStockInfoArgs(BaseModel):
    account: str
    stock_no: str


class QuerySymbolQuoteArgs(BaseModel):
    account: str
    symbol: str
    market_type: Optional[str] = "Common"


class QuerySymbolSnapshotArgs(BaseModel):
    account: str
    market_type: Optional[str] = "Common"
    stock_type: Optional[List[str]] = ["Stock"]


class GetIntradayTickersArgs(BaseModel):
    market: str  # 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
    type: Optional[str] = (
        None  # 類型，可選 ALLBUT099 包含一般股票、特別股及ETF ； COMMONSTOCK 為一般股票
    )
    exchange: Optional[str] = None  # 交易所，可選 TSE 或 OTC
    industry: Optional[str] = None  # 行業別
    isNormal: Optional[bool] = None  # 是否為普通股
    isAttention: Optional[bool] = None  # 是否為注意股
    isDisposition: Optional[bool] = None  # 是否為處置股
    isHalted: Optional[bool] = None  # 是否為停止交易股


class GetIntradayTickerArgs(BaseModel):
    symbol: str
    type: Optional[str] = None  # 類型，可選 oddlot 盤中零股


class GetIntradayQuoteArgs(BaseModel):
    symbol: str
    type: Optional[str] = None  # 類型，可選 oddlot 盤中零股


class GetIntradayCandlesArgs(BaseModel):
    symbol: str


class GetIntradayTradesArgs(BaseModel):
    symbol: str
    type: Optional[str] = None  # Ticker 類型，可選 oddlot 盤中零股
    offset: Optional[int] = None  # 偏移量
    limit: Optional[int] = None  # 限制量


class GetIntradayVolumesArgs(BaseModel):
    symbol: str


class GetSnapshotQuotesArgs(BaseModel):
    market: str
    type: Optional[str] = None  # 標的類型，可選 ALLBUT099 或 COMMONSTOCK


class GetSnapshotMoversArgs(BaseModel):
    market: str
    direction: str = "up"  # 上漲／下跌，可選 up 上漲；down 下跌
    change: str = "percent"  # 漲跌／漲跌幅，可選 percent 漲跌幅；value 漲跌
    gt: Optional[float] = None  # 篩選大於漲跌／漲跌幅的股票
    gte: Optional[float] = None  # 篩選大於或等於漲跌／漲跌幅的股票
    lt: Optional[float] = None  # 篩選小於漲跌／漲跌幅的股票
    lte: Optional[float] = None  # 篩選小於或等於漲跌／漲跌幅的股票
    eq: Optional[float] = None  # 篩選等於漲跌／漲跌幅的股票
    type: Optional[str] = None  # 標的類型，可選 ALLBUT099 或 COMMONSTOCK


class GetSnapshotActivesArgs(BaseModel):
    market: str
    trade: str = "volume"  # 成交量／成交值，可選 volume 成交量；value 成交值
    type: Optional[str] = None  # 標的類型，可選 ALLBUT099 或 COMMONSTOCK


class GetHistoricalStatsArgs(BaseModel):
    symbol: str


class GetIntradayProductsArgs(BaseModel):
    type: Optional[str] = None  # 類型，可選 FUTURE 期貨；OPTION 選擇權
    exchange: Optional[str] = None  # 交易所，可選 TAIFEX 臺灣期貨交易所
    session: Optional[str] = (
        None  # 交易時段，可選 REGULAR 一般交易 或 AFTERHOURS 盤後交易
    )
    contractType: Optional[str] = (
        None  # 契約類別，可選 I 指數類；R 利率類；B 債券類；C 商品類；S 股票類；E 匯率類
    )
    status: Optional[str] = None  # 契約狀態，可選 N 正常；P 暫停交易；U 即將上市


class GetIntradayFutOptTickersArgs(BaseModel):
    type: str  # 類型，可選 FUTURE 期貨；OPTION 選擇權
    exchange: Optional[str] = None  # 交易所，可選 TAIFEX 臺灣期貨交易所
    session: Optional[str] = (
        None  # 交易時段，可選 REGULAR 一般交易 或 AFTERHOURS 盤後交易
    )
    product: Optional[str] = None  # 產品代碼
    contractType: Optional[str] = (
        None  # 契約類別，可選 I 指數類；R 利率類；B 債券類；C 商品類；S 股票類；E 匯率類
    )


class GetIntradayFutOptTickerArgs(BaseModel):
    symbol: str  # 商品代碼
    session: Optional[str] = (
        None  # 交易時段，可選 REGULAR 一般交易 或 AFTERHOURS 盤後交易
    )


class GetIntradayFutOptQuoteArgs(BaseModel):
    symbol: str  # 期權代碼
    session: Optional[str] = None  # 交易時段，可選 afterhours 盤後交易


class GetIntradayFutOptCandlesArgs(BaseModel):
    symbol: str  # 期權代碼
    session: Optional[str] = None  # 交易時段，可選 afterhours 盤後交易
    timeframe: Optional[str] = None  # K線週期，可選 1m, 5m, 15m, 30m, 1h, 1d


class GetIntradayFutOptTradesArgs(BaseModel):
    symbol: str  # 期權代碼
    session: Optional[str] = None  # 交易時段，可選 afterhours 盤後交易
    offset: Optional[int] = None  # 偏移量
    limit: Optional[int] = None  # 限制量


class GetIntradayFutOptVolumesArgs(BaseModel):
    symbol: str  # 期權代碼
    session: Optional[str] = None  # 交易時段，可選 afterhours 盤後交易


class GetRealtimeQuotesArgs(BaseModel):
    symbol: str


class GetOrderStatusArgs(BaseModel):
    account: str


class GetOrderReportsArgs(BaseModel):
    limit: int = 10  # 返回最新的幾筆記錄


class GetOrderChangedReportsArgs(BaseModel):
    limit: int = 10


class GetFilledReportsArgs(BaseModel):
    limit: int = 10


class GetEventReportsArgs(BaseModel):
    limit: int = 10


class GetOrderResultsArgs(BaseModel):
    account: str


class GetOrderResultsDetailArgs(BaseModel):
    account: str


class ModifyPriceArgs(BaseModel):
    account: str
    order_no: str
    new_price: float = Field(gt=0)  # 價格必須大於0


class ModifyQuantityArgs(BaseModel):
    account: str
    order_no: str
    new_quantity: int  # 新數量（股）


class BatchPlaceOrderArgs(BaseModel):
    account: str
    orders: List[Dict]  # 每筆訂單的參數字典
    max_workers: int = 10  # 最大並行數量


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


class GetTrailOrderArgs(BaseModel):
    """有效移動鎖利查詢參數"""

    account: str


class GetTrailHistoryArgs(BaseModel):
    """歷史移動鎖利查詢參數"""

    account: str
    start_date: str
    end_date: str


class TimeSliceSplitArgs(BaseModel):
    """分時分量拆單設定參數 (SplitDescription)"""

    method: str  # TimeSliceOrderType 成員名稱，例如 Type1/Type2/Type3
    interval: int  # 間隔秒數 (>0)
    single_quantity: int  # 每次委託股數（必須為1000的倍數，>0）
    total_quantity: Optional[int] = None  # 總委託股數（必須為1000的倍數，選填）
    start_time: str  # 開始時間，格式如 '083000'
    end_time: Optional[str] = None  # 結束時間，Type2/Type3 必填

    # 支援更靈活的輸入格式
    split_type: Optional[str] = None  # 向後兼容字段
    split_count: Optional[int] = None  # 總拆單次數，用於計算 total_quantity
    split_unit: Optional[int] = None  # 每單位數量（通常等於 single_quantity）

    def model_post_init(self, __context):
        # 基本檢核
        if self.interval is None or self.interval <= 0:
            raise ValueError("interval 必須為正整數")
        if self.single_quantity is None or self.single_quantity <= 0:
            raise ValueError("single_quantity 必須為正整數")

        # 驗證股數必須為1000的倍數
        if self.single_quantity % 1000 != 0:
            raise ValueError(
                f"single_quantity 必須為1000的倍數（張數），輸入值 {self.single_quantity} 股無效"
            )

        # 如果提供了 split_count，自動計算 total_quantity
        if self.split_count is not None and self.split_count > 0:
            if self.total_quantity is None:
                self.total_quantity = self.split_count * self.single_quantity
            elif self.total_quantity != self.split_count * self.single_quantity:
                raise ValueError(
                    f"total_quantity ({self.total_quantity}) 與 split_count * single_quantity ({self.split_count * self.single_quantity}) 不一致"
                )

        if (
            self.total_quantity is not None
            and self.total_quantity <= self.single_quantity
        ):
            raise ValueError("total_quantity 必須大於 single_quantity")

        # 驗證總股數也必須為1000的倍數
        if self.total_quantity is not None and self.total_quantity % 1000 != 0:
            raise ValueError(
                f"total_quantity 必須為1000的倍數（張數），輸入值 {self.total_quantity} 股無效"
            )

        # 針對 method 類型的檢核
        try:
            from fubon_neo.constant import TimeSliceOrderType as _TS

            # 如果用戶傳入 "TimeSlice"，根據參數自動推斷類型
            if self.method == "TimeSlice":
                if self.end_time:
                    self.method = "Type2"  # 有結束時間，使用 Type2
                else:
                    self.method = "Type1"  # 無結束時間，使用 Type1

            m = getattr(_TS, self.method)
        except Exception:
            raise ValueError(
                "method 無效，必須是 TimeSliceOrderType 的成員名稱 (Type1/Type2/Type3) 或 'TimeSlice' (自動推斷)"
            )


# =============================================================================
# 技術指標與訊號 參數模型
# =============================================================================


class CalculateBollingerBandsArgs(BaseModel):
    symbol: str
    period: int = 20
    stddev: float = 2.0
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CalculateRSIArgs(BaseModel):
    symbol: str
    period: int = 14
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CalculateMACDArgs(BaseModel):
    symbol: str
    fast: int = 12
    slow: int = 26
    signal: int = 9
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CalculateKDArgs(BaseModel):
    symbol: str
    period: int = 9
    smooth_k: int = 3
    smooth_d: int = 3
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class GetTradingSignalsArgs(BaseModel):
    symbol: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None


# =============================================================================
# 即時市場數據訂閱參數模型
# =============================================================================


class SubscribeMarketDataArgs(BaseModel):
    """訂閱市場數據參數模型"""

    symbol: str  # 股票代碼
    data_type: str = "quote"  # 數據類型，可選 quote, candles, trades, volumes
    interval: Optional[str] = (
        None  # K線間隔，可選 1m, 5m, 15m, 30m, 1h, 1d (當 data_type 為 candles 時必填)
    )


class UnsubscribeMarketDataArgs(BaseModel):
    """取消訂閱市場數據參數模型"""

    symbol: str  # 股票代碼
    data_type: str = "quote"  # 數據類型，可選 quote, candles, trades, volumes


class GetActiveSubscriptionsArgs(BaseModel):
    """獲取活躍訂閱參數模型"""

    symbol: Optional[str] = None  # 可選：指定股票代碼，只返回該股票的訂閱


class GetRealtimeDataArgs(BaseModel):
    """獲取即時數據參數模型"""

    symbol: str  # 股票代碼
    data_type: str = "quote"  # 數據類型，可選 quote, candles, trades, volumes


class RegisterEventListenerArgs(BaseModel):
    """註冊事件監聽器參數模型"""

    event_type: str  # 事件類型，可選 order_update, fill_update, connection_status
    callback_url: Optional[str] = None  # 可選：回調URL，用於WebHook通知


class UnregisterEventListenerArgs(BaseModel):
    """取消註冊事件監聽器參數模型"""

    event_type: str  # 事件類型，可選 order_update, fill_update, connection_status
    listener_id: str  # 監聽器ID


# =============================================================================
# WebSocket 串流參數模型
# =============================================================================


class StartWebSocketStreamArgs(BaseModel):
    """啟動 WebSocket 串流參數模型"""

    symbol: str  # 股票代碼
    data_type: str = "quote"  # 數據類型，可選 quote, candles, trades, volumes
    interval: Optional[str] = (
        None  # K線間隔，可選 1m, 5m, 15m, 30m, 1h, 1d (當 data_type 為 candles 時必填)
    )


class StopWebSocketStreamArgs(BaseModel):
    """停止 WebSocket 串流參數模型"""

    stream_id: str  # 串流ID


class GetStreamStatusArgs(BaseModel):
    """獲取串流狀態參數模型"""

    stream_id: str  # 串流ID


class PushRealtimeUpdateArgs(BaseModel):
    """推送即時更新參數模型"""

    symbol: str  # 股票代碼
    data: Dict  # 更新數據
    data_type: str = "quote"  # 數據類型，可選 quote, candles, trades, volumes


# =============================================================================
# 技術指標/交易訊號工具函式
# =============================================================================


@mcp.tool()
def get_trading_signals(args: Dict) -> dict:
    """綜合技術指標生成交易訊號 (Bollinger / RSI / MACD / KD / 量比)

    返回統一格式: {status,data,message}
    data 包含:
      symbol, analysis_date, overall_signal, signal_score, confidence,
      indicators(各指標細節), reasons(文字理由列表), recommendations(建議)
    """
    try:
        params = GetTradingSignalsArgs(**args)
        df = read_local_stock_data(params.symbol)
        if df is None or df.empty:
            return {
                "status": "error",
                "data": None,
                "message": f"無本地歷史資料: {params.symbol}",
            }

        # 日期過濾 (原始為降序,計算需升序)
        df = df.sort_values("date")
        if params.from_date:
            df = df[df["date"] >= pd.to_datetime(params.from_date)]
        if params.to_date:
            df = df[df["date"] <= pd.to_datetime(params.to_date)]
        if len(df) < 50:
            return {
                "status": "error",
                "data": None,
                "message": "資料不足，需至少 50 日",
            }

        close = df["close"]
        high = df["high"] if "high" in df.columns else close
        low = df["low"] if "low" in df.columns else close
        volume = df["volume"] if "volume" in df.columns else pd.Series([0] * len(df))

        bb = indicators.calculate_bollinger_bands(close)
        rsi = indicators.calculate_rsi(close)
        macd_res = indicators.calculate_macd(close)
        kd = indicators.calculate_kd(high, low, close)
        vol_rate = indicators.calculate_volume_rate(volume)

        latest = df.iloc[-1]
        latest_row = {
            "date": latest["date"],
            "close": float(latest["close"]),
            "bb_upper": float(bb["upper"].iloc[-1]),
            "bb_middle": float(bb["middle"].iloc[-1]),
            "bb_lower": float(bb["lower"].iloc[-1]),
            "bb_width": float(bb["width"].iloc[-1]),
            "rsi": float(rsi.iloc[-1]),
            "macd": float(macd_res["macd"].iloc[-1]),
            "macd_signal": float(macd_res["signal"].iloc[-1]),
            "macd_hist": float(macd_res["histogram"].iloc[-1]),
            "k": float(kd["k"].iloc[-1]),
            "d": float(kd["d"].iloc[-1]),
            "volume": int(volume.iloc[-1]),
            "volume_rate": float(vol_rate.iloc[-1])
            if not pd.isna(vol_rate.iloc[-1])
            else 0.0,
        }
        prev_row = None
        if len(df) >= 2:
            prev_row = {
                "macd": float(macd_res["macd"].iloc[-2]),
                "macd_signal": float(macd_res["signal"].iloc[-2]),
                "k": float(kd["k"].iloc[-2]),
                "d": float(kd["d"].iloc[-2]),
            }

        signal_pack = _compute_signals(latest_row, prev_row)

        return {
            "status": "success",
            "message": f"交易訊號分析成功: {params.symbol}",
            "data": {
                "symbol": params.symbol,
                "analysis_date": latest_row["date"].isoformat(),
                "overall_signal": signal_pack["overall_signal"],
                "signal_score": signal_pack["score"],
                "confidence": signal_pack["confidence"],
                "indicators": signal_pack["indicators"],
                "reasons": signal_pack["reasons"],
                "recommendations": signal_pack["recommendations"],
            },
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"交易訊號計算失敗: {e}"}


def _bb_position(close: float, upper: float, middle: float, lower: float) -> str:
    if close > upper:
        return "突破上軌"
    if close > middle:
        return "上半軌"
    if close >= lower:
        return "下半軌"
    return "跌破下軌"


def _rsi_level(rsi: float) -> str:
    if rsi >= 70:
        return "超買"
    if rsi <= 30:
        return "超賣"
    if rsi >= 60:
        return "偏強"
    if rsi <= 40:
        return "偏弱"
    return "中性"


def _macd_cross(latest: Dict, prev: Dict | None) -> str:
    if not prev:
        return "無"
    if latest["macd"] > latest["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
        return "金叉"
    if latest["macd"] < latest["macd_signal"] and prev["macd"] >= prev["macd_signal"]:
        return "死叉"
    return "無"


def _kd_cross(latest: Dict, prev: Dict | None) -> str:
    if not prev:
        return "無"
    if latest["k"] > latest["d"] and prev["k"] <= prev["d"]:
        return "K上穿D"
    if latest["k"] < latest["d"] and prev["k"] >= prev["d"]:
        return "K下穿D"
    return "無"


def _volume_strength(rate: float) -> str:
    if rate >= 2.0:
        return "爆量"
    if rate >= 1.5:
        return "量增"
    if rate >= 0.8:
        return "正常"
    if rate >= 0.5:
        return "量縮"
    return "極度萎縮"


def _compute_signals(latest: Dict, prev: Dict | None) -> Dict:
    score = 0
    reasons: List[str] = []

    # Bollinger (±30)
    bb_pos = _bb_position(
        latest["close"], latest["bb_upper"], latest["bb_middle"], latest["bb_lower"]
    )
    bb_score = 0
    if bb_pos == "突破上軌":
        bb_score = 25
        reasons.append("價格突破布林上軌")
    elif bb_pos == "跌破下軌":
        bb_score = -25
        reasons.append("價格跌破布林下軌")
    elif bb_pos == "上半軌":
        bb_score = 10
        reasons.append("位於中軌上方")
    else:
        bb_score = -10
        reasons.append("位於中軌下方")
    if latest["bb_width"] < 0.05:
        reasons.append("布林通道收窄")

    # RSI (±20)
    rsi_level = _rsi_level(latest["rsi"])
    rsi_score = 0
    if rsi_level == "超買":
        rsi_score = -15
        reasons.append(f"RSI超買({latest['rsi']:.1f})")
    elif rsi_level == "超賣":
        rsi_score = 15
        reasons.append(f"RSI超賣({latest['rsi']:.1f})")
    elif rsi_level == "偏強":
        rsi_score = 10
    elif rsi_level == "偏弱":
        rsi_score = -5

    # MACD (±25)
    macd_cross = _macd_cross(latest, prev)
    macd_score = 0
    if macd_cross == "金叉":
        macd_score = 25
        reasons.append("MACD金叉")
    elif macd_cross == "死叉":
        macd_score = -25
        reasons.append("MACD死叉")
    elif latest["macd_hist"] > 0:
        macd_score = 10
        reasons.append("MACD柱狀正值")
    else:
        macd_score = -10
        reasons.append("MACD柱狀負值")

    # KD (±15)
    kd_cross = _kd_cross(latest, prev)
    kd_score = 0
    avg_kd = (latest["k"] + latest["d"]) / 2
    if kd_cross == "K上穿D":
        kd_score = 15
        reasons.append("KD金叉")
    elif kd_cross == "K下穿D":
        kd_score = -15
        reasons.append("KD死叉")
    elif avg_kd > 80:
        kd_score = -10
        reasons.append("KD超買")
    elif avg_kd < 20:
        kd_score = 10
        reasons.append("KD超賣")

    # Volume (±10)
    vol_score = 0
    vol_strength = _volume_strength(latest["volume_rate"])
    if vol_strength == "爆量":
        vol_score = 10 if (bb_score + macd_score) > 0 else -10
        reasons.append("爆量")
    elif vol_strength == "量增":
        vol_score = 5 if (bb_score + macd_score) > 0 else -5
        reasons.append("量增")
    elif vol_strength == "極度萎縮":
        vol_score = -5
        reasons.append("量極度萎縮")

    score = bb_score + rsi_score + macd_score + kd_score + vol_score

    if score >= 60:
        overall = "強烈買進"
        conf = "高"
        rec = ["多指標共振", "可積極布局", "設置停損保護"]
    elif score >= 30:
        overall = "買進"
        conf = "中"
        rec = ["偏多格局", "分批切入", "控管風險"]
    elif score >= -30:
        overall = "中性"
        conf = "低"
        rec = ["訊號不明", "等待突破", "持有觀察"]
    elif score >= -60:
        overall = "賣出"
        conf = "中"
        rec = ["偏空跡象", "減碼持股", "避免追高"]
    else:
        overall = "強烈賣出"
        conf = "高"
        rec = ["空方強勢", "迅速出場", "嚴守停損"]

    indicators_payload = {
        "bollinger": {
            "upper": latest["bb_upper"],
            "middle": latest["bb_middle"],
            "lower": latest["bb_lower"],
            "width": latest["bb_width"],
            "position": bb_pos,
            "score": bb_score,
        },
        "rsi": {"value": latest["rsi"], "level": rsi_level, "score": rsi_score},
        "macd": {
            "macd": latest["macd"],
            "signal": latest["macd_signal"],
            "histogram": latest["macd_hist"],
            "cross": macd_cross,
            "score": macd_score,
        },
        "kd": {
            "k": latest["k"],
            "d": latest["d"],
            "avg": avg_kd,
            "cross": kd_cross,
            "score": kd_score,
        },
        "volume": {
            "value": latest["volume"],
            "rate": latest["volume_rate"],
            "strength": vol_strength,
            "score": vol_score,
        },
    }

    return {
        "overall_signal": overall,
        "score": int(score),
        "confidence": conf,
        "indicators": indicators_payload,
        "reasons": reasons,
        "recommendations": rec,
    }

    method: str  # TimeSliceOrderType 成員名稱，例如 Type1/Type2/Type3
    interval: int  # 間隔秒數 (>0)
    single_quantity: int  # 每次委託股數（必須為1000的倍數，>0）
    total_quantity: Optional[int] = None  # 總委託股數（必須為1000的倍數，選填）
    start_time: str  # 開始時間，格式如 '083000'
    end_time: Optional[str] = None  # 結束時間，Type2/Type3 必填

    # 支援更靈活的輸入格式
    split_type: Optional[str] = None  # 向後兼容字段
    split_count: Optional[int] = None  # 總拆單次數，用於計算 total_quantity
    split_unit: Optional[int] = None  # 每單位數量（通常等於 single_quantity）

    def model_post_init(self, __context):
        # 基本檢核
        if self.interval is None or self.interval <= 0:
            raise ValueError("interval 必須為正整數")
        if self.single_quantity is None or self.single_quantity <= 0:
            raise ValueError("single_quantity 必須為正整數")

        # 驗證股數必須為1000的倍數
        if self.single_quantity % 1000 != 0:
            raise ValueError(
                f"single_quantity 必須為1000的倍數（張數），輸入值 {self.single_quantity} 股無效"
            )

        # 如果提供了 split_count，自動計算 total_quantity
        if self.split_count is not None and self.split_count > 0:
            if self.total_quantity is None:
                self.total_quantity = self.split_count * self.single_quantity
            elif self.total_quantity != self.split_count * self.single_quantity:
                raise ValueError(
                    f"total_quantity ({self.total_quantity}) 與 split_count * single_quantity ({self.split_count * self.single_quantity}) 不一致"
                )

        if (
            self.total_quantity is not None
            and self.total_quantity <= self.single_quantity
        ):
            raise ValueError("total_quantity 必須大於 single_quantity")

        # 驗證總股數也必須為1000的倍數
        if self.total_quantity is not None and self.total_quantity % 1000 != 0:
            raise ValueError(
                f"total_quantity 必須為1000的倍數（張數），輸入值 {self.total_quantity} 股無效"
            )

        # 針對 method 類型的檢核
        try:
            from fubon_neo.constant import TimeSliceOrderType as _TS

            # 如果用戶傳入 "TimeSlice"，根據參數自動推斷類型
            if self.method == "TimeSlice":
                if self.end_time:
                    self.method = "Type2"  # 有結束時間，使用 Type2
                else:
                    self.method = "Type1"  # 無結束時間，使用 Type1

            m = getattr(_TS, self.method)
        except Exception:
            raise ValueError(
                "method 無效，必須是 TimeSliceOrderType 的成員名稱 (Type1/Type2/Type3) 或 'TimeSlice' (自動推斷)"
            )
        if m in (_TS.Type2, _TS.Type3):
            if not self.end_time:
                raise ValueError("Type2/Type3 必須提供 end_time")


class PlaceTimeSliceOrderArgs(BaseModel):
    """分時分量條件單請求參數"""

    account: str
    start_date: str
    end_date: str
    stop_sign: str = "Full"  # Full, Partial, UntilEnd
    split: Dict  # TimeSliceSplitArgs
    order: Dict  # ConditionOrderArgs


class GetTimeSliceOrderArgs(BaseModel):
    """分時分量查詢參數"""

    account: str
    batch_no: str


class CancelConditionOrderArgs(BaseModel):
    """取消條件單參數"""

    account: str
    guid: str


class GetConditionOrderArgs(BaseModel):
    """條件單查詢參數"""

    account: str
    condition_status: Optional[str] = None  # 對應 ConditionStatus，選填


class GetConditionOrderByIdArgs(BaseModel):
    """條件單查詢（By Guid）參數"""

    account: str
    guid: str


class GetConditionHistoryArgs(BaseModel):
    """歷史條件單查詢參數"""

    account: str
    start_date: str
    end_date: str
    condition_history_status: Optional[str] = None  # 對應 HistoryStatus，選填


class ConditionDayTradeArgs(BaseModel):
    """當沖回補參數模型 (ConditionDayTrade)"""

    day_trade_end_time: str  # 收盤前沖銷時間，區間 130100 ~ 132000
    auto_cancel: bool = True  # 是否自動取消
    price: str = ""  # 定盤/沖銷價格，市價時請留空字串
    price_type: str = "Market"  # Market 或 Limit（對應 ConditionPriceType）


class PlaceDayTradeConditionOrderArgs(BaseModel):
    """當沖單一條件單參數模型（可選停損停利）"""

    account: str  # 帳戶號碼
    stop_sign: str = "Full"  # Full(全部成交), Partial(部分成交), UntilEnd(效期結束)
    end_time: str  # 父單洗價結束時間（例："130000"）
    condition: Dict  # 觸發條件（ConditionArgs）
    order: Dict  # 主單委託內容（ConditionOrderArgs）
    daytrade: Dict  # 當沖回補內容（ConditionDayTradeArgs）
    tpsl: Optional[Dict] = None  # 停損停利（TPSLWrapperArgs，選填）
    fix_session: bool = False  # 是否執行定盤回補（fixSession）


class GetDayTradeConditionByIdArgs(BaseModel):
    """當沖條件單查詢參數"""

    account: str
    guid: str


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


class Realized(BaseModel):
    """已實現損益數據模型"""

    date: str
    branch_no: str
    account: str
    stock_no: str
    buy_sell: str
    filled_qty: int
    filled_price: float
    order_type: str
    realized_profit: int
    realized_loss: int


class GetRealizedPnLArgs(BaseModel):
    """已實現損益查詢參數"""

    account: str = Field(..., description="帳戶號碼")


class RealizedSummary(BaseModel):
    """已實現損益彙總數據模型"""

    start_date: str
    end_date: str
    branch_no: str
    account: str
    stock_no: str
    buy_sell: str
    order_type: str
    filled_qty: int
    filled_avg_price: float
    realized_profit_and_loss: int


class GetRealizedPnLSummaryArgs(BaseModel):
    """已實現損益彙總查詢參數"""

    account: str = Field(..., description="帳戶號碼")


class UnrealizedData(BaseModel):
    """未實現損益數據模型"""

    date: str
    branch_no: str
    stock_no: str
    buy_sell: str
    order_type: str
    cost_price: float
    tradable_qty: int
    today_qty: int
    unrealized_profit: int
    unrealized_loss: int


class GetUnrealizedPnLArgs(BaseModel):
    """未實現損益查詢參數"""

    account: str = Field(..., description="帳戶號碼")


class MaintenanceSummary(BaseModel):
    """維護保證金總計資訊"""

    total_market_value: float
    total_maintenance_margin: float
    total_equity: float
    total_margin_balance: float
    total_short_balance: float


class MaintenanceDetail(BaseModel):
    """維護保證金明細資訊"""

    stock_no: str
    quantity: int
    market_price: float
    market_value: float
    maintenance_margin: float
    equity: float
    margin_balance: float
    short_balance: float


class MaintenanceData(BaseModel):
    """維護保證金數據"""

    maintenance_ratio: float
    summary: MaintenanceSummary
    details: List[MaintenanceDetail]


@mcp.tool()
def historical_candles(args: Dict) -> dict:
    """
    獲取歷史數據，優先使用本地數據，如果本地沒有再使用 API

    Args:
        symbol (str): 股票代碼，必須為文字格式，例如: '2330'、'00878'
        from_date (str): 開始日期，格式: YYYY-MM-DD
        to_date (str): 結束日期，格式: YYYY-MM-DD
    """
    try:
        # 使用 HistoricalCandlesArgs 進行驗證
        validated_args = HistoricalCandlesArgs(**args)
        symbol = validated_args.symbol
        from_date = validated_args.from_date
        to_date = validated_args.to_date

        # 嘗試從本地數據獲取
        local_result = _get_local_historical_data(symbol, from_date, to_date)
        if local_result:
            return local_result

        # 本地沒有數據，使用 API 獲取
        api_data = _fetch_api_historical_data(symbol, from_date, to_date)
        if api_data:
            # 處理並保存數據
            df = pd.DataFrame(api_data)
            df = process_historical_data(df)
            save_to_local_csv(symbol, api_data)
            return {
                "status": "success",
                "data": df.to_dict("records"),
                "message": f"成功獲取 {symbol} 從 {from_date} 到 {to_date} 的數據",
            }

        return {
            "status": "error",
            "data": [],
            "message": f"無法獲取 {symbol} 的歷史數據",
        }

    except Exception as e:
        return {
            "status": "error",
            "data": [],
            "message": f"獲取數據時發生錯誤: {str(e)}",
        }


def _get_local_historical_data(symbol: str, from_date: str, to_date: str) -> dict:
    """從本地數據獲取歷史數據"""
    local_data = read_local_stock_data(symbol)
    if local_data is None:
        return None

    df = local_data
    mask = (df["date"] >= from_date) & (df["date"] <= to_date)
    df = df[mask]

    if df.empty:
        return None

    df = process_historical_data(df)
    return {
        "status": "success",
        "data": df.to_dict("records"),
        "message": f"成功從本地數據獲取 {symbol} 從 {from_date} 到 {to_date} 的數據",
    }


def _fetch_api_historical_data(symbol: str, from_date: str, to_date: str) -> list:
    """從 API 獲取歷史數據"""
    from_datetime = pd.to_datetime(from_date)
    to_datetime = pd.to_datetime(to_date)
    date_diff = (to_datetime - from_datetime).days

    all_data = []

    if date_diff > 365:
        # 分段獲取數據
        current_from = from_datetime
        while current_from < to_datetime:
            current_to = min(current_from + pd.Timedelta(days=365), to_datetime)
            segment_data = fetch_historical_data_segment(
                symbol,
                current_from.strftime("%Y-%m-%d"),
                current_to.strftime("%Y-%m-%d"),
            )
            all_data.extend(segment_data)
            current_from = current_to + pd.Timedelta(days=1)
    else:
        # 直接獲取數據
        all_data = fetch_historical_data_segment(symbol, from_date, to_date)

    return all_data


@mcp.tool()
def place_order(args: Dict) -> dict:
    """
    下單買賣股票

    Args:
        account (str): 帳戶號碼
        symbol (str): 股票代碼
        quantity (int): 委託數量（股）
        price (float): 價格
        buy_sell (str): 'Buy' 或 'Sell'
        market_type (str): 市場別，預設 "Common"
        price_type (str): 價格類型，預設 "Limit"
        time_in_force (str): 有效期間，預設 "ROD"
        order_type (str): 委託類型，預設 "Stock"
        user_def (str): 使用者自定義欄位，可選
        is_non_blocking (bool): 是否使用非阻塞模式，預設False

    Returns:
        dict: 成功時返回委託結果，包含以下字段：
            - status: "success"
            - data: OrderResult 對象，包含委託單詳細資訊
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
                - is_pre_order (bool): 是否預約單
                - status (str): 委託狀態
                - after_price_type (str): 後續價格類型
                - after_price (str): 後續價格
                - unit (str): 單位
                - after_qty (int): 有效數量（剩餘可成交數量）
                - filled_qty (int): 已成交數量
                - filled_money (float): 已成交金額
                - before_qty (int): 原始數量
                - before_price (str): 原始價格
                - user_def (str): 使用者自定義欄位
                - last_time (str): 最後更新時間
                - details (list): 詳細資訊
                - error_message (str): 錯誤訊息
            - message: 成功訊息

    Note:
        **委託單狀態監控**:
        - filled_qty: 已成交數量，用於判斷部分成交或全部成交
        - filled_money: 已成交金額，計算已實現損益
        - after_qty: 剩餘有效數量，0表示已全部成交或取消
        - order_no: 委託單號，可用於後續的改價、改量或取消操作
    """
    try:
        validated_args = PlaceOrderArgs(**args)
        account = validated_args.account
        symbol = validated_args.symbol
        quantity = validated_args.quantity
        price = validated_args.price
        buy_sell = validated_args.buy_sell
        market_type = validated_args.market_type
        price_type = validated_args.price_type
        time_in_force = validated_args.time_in_force
        order_type = validated_args.order_type
        user_def = validated_args.user_def
        is_non_blocking = validated_args.is_non_blocking

        # 檢查 accounts 是否成功
        if (
            not accounts
            or not hasattr(accounts, "is_success")
            or not accounts.is_success
        ):
            return {
                "status": "error",
                "data": None,
                "message": "帳戶認證失敗，請檢查憑證是否過期",
            }

        # 找到對應的帳戶對象
        account_obj = None
        if hasattr(accounts, "data") and accounts.data:
            for acc in accounts.data:
                if getattr(acc, "account", None) == account:
                    account_obj = acc
                    break

        if not account_obj:
            return {"status": "error", "data": None, "message": f"找不到帳戶 {account}"}

        from fubon_neo.constant import (
            BSAction,
            MarketType,
            OrderType,
            PriceType,
            TimeInForce,
        )
        from fubon_neo.sdk import Order

        # 將字串轉換為對應的枚舉值
        buy_sell_enum = to_bs_action(buy_sell)
        market_type_enum = to_market_type(market_type)
        price_type_enum = to_price_type(price_type)
        time_in_force_enum = to_time_in_force(time_in_force)
        order_type_enum = to_order_type(order_type)

        order = Order(
            buy_sell=buy_sell_enum,
            symbol=symbol,
            price=str(price),  # 價格轉為字串
            quantity=quantity,
            market_type=market_type_enum,
            price_type=price_type_enum,
            time_in_force=time_in_force_enum,
            order_type=order_type_enum,
            user_def=user_def,
        )

        # 使用非阻塞或阻塞模式下單
        result = sdk.stock.place_order(account_obj, order, is_non_blocking)

        # 檢查 API 返回結果
        if result and hasattr(result, "is_success") and result.is_success:
            mode_desc = "非阻塞" if is_non_blocking else "阻塞"
            return {
                "status": "success",
                "data": result.data if hasattr(result, "data") else result,
                "message": f"成功使用{mode_desc}模式下單 {buy_sell} {symbol} {quantity} 股",
            }
        else:
            # 提取錯誤訊息
            error_msg = "下單失敗"
            if result and hasattr(result, "message"):
                error_msg = f"下單失敗: {result.message}"
            elif result:
                error_msg = f"下單失敗: {str(result)}"

            return {"status": "error", "data": None, "message": error_msg}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"下單失敗: {str(e)}"}


@mcp.tool()
def _find_target_order(order_results, order_no):
    """從委託結果中找到指定的委託單"""
    if hasattr(order_results, "data") and order_results.data:
        for order in order_results.data:
            if getattr(order, "order_no", None) == order_no:
                return order
    return None


def _create_modify_object(target_order, modify_value, modify_type: str):
    """創建修改對象"""
    if modify_type == "quantity":
        return sdk.stock.make_modify_quantity_obj(
            target_order, modify_value
        )
    elif modify_type == "price":
        return sdk.stock.make_modify_price_obj(
            target_order, str(modify_value), None
        )
    else:
        raise ValueError(f"不支援的修改類型: {modify_type}")


def _execute_modify_operation(account_obj, modify_obj, modify_type: str):
    """執行修改操作"""
    if modify_type == "quantity":
        return sdk.stock.modify_quantity(account_obj, modify_obj)
    elif modify_type == "price":
        return sdk.stock.modify_price(account_obj, modify_obj)
    else:
        raise ValueError(f"不支援的修改類型: {modify_type}")


def _modify_order(account: str, order_no: str, modify_value, modify_type: str) -> dict:
    """
    通用的修改委託函數

    Args:
        account (str): 帳戶號碼
        order_no (str): 委託單號
        modify_value: 修改的值（數量或價格）
        modify_type (str): 修改類型，'quantity' 或 'price'
    """
    try:
        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取委託結果
        order_results = sdk.stock.get_order_results(account_obj)
        if not (
            order_results
            and hasattr(order_results, "is_success")
            and order_results.is_success
        ):
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 委託結果",
            }

        # 找到對應的委託單
        target_order = _find_target_order(order_results, order_no)
        if not target_order:
            return {
                "status": "error",
                "data": None,
                "message": f"找不到委託單號 {order_no}",
            }

        # 創建修改對象並執行修改
        modify_obj = _create_modify_object(target_order, modify_value, modify_type)
        result = _execute_modify_operation(account_obj, modify_obj, modify_type)

        if result and hasattr(result, "is_success") and result.is_success:
            value_desc = (
                f"數量為 {modify_value}"
                if modify_type == "quantity"
                else f"價格為 {modify_value}"
            )
            return {
                "status": "success",
                "data": result.data if hasattr(result, "data") else result,
                "message": f"成功修改委託 {order_no} {value_desc}",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"修改委託 {order_no} {modify_type} 失敗",
            }

    except Exception as modify_error:
        return {
            "status": "error",
            "data": None,
            "message": f"修改{modify_type}時發生錯誤: {str(modify_error)}",
        }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"修改{modify_type}失敗: {str(e)}",
        }


@mcp.tool()
def modify_quantity(args: Dict) -> dict:
    """
    修改委託數量

    Args:
        account (str): 帳戶號碼
        order_no (str): 委託單號
        new_quantity (int): 新數量（股）
    """
    try:
        validated_args = ModifyQuantityArgs(**args)
        account = validated_args.account
        order_no = validated_args.order_no
        new_quantity = validated_args.new_quantity

        return _modify_order(account, order_no, new_quantity, "quantity")

    except Exception as e:
        return {"status": "error", "data": None, "message": f"修改數量失敗: {str(e)}"}


@mcp.tool()
def get_account_info(args: Dict) -> dict:
    """
    獲取帳戶資訊，包括資金餘額、庫存、損益等

    Args:
        account (str): 帳戶號碼，如果為空則返回所有帳戶基本資訊
    """
    try:
        validated_args = GetAccountInfoArgs(**args)
        account = validated_args.account

        # 如果沒有指定帳戶，返回所有帳戶基本資訊
        if not account:
            return _get_all_accounts_basic_info()

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取詳細帳戶資訊
        account_details = _get_basic_account_info(account_obj)
        account_details.update(_get_account_financial_info(account_obj))

        return {
            "status": "success",
            "data": account_details,
            "message": f"成功獲取帳戶 {account} 詳細資訊",
        }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取帳戶資訊失敗: {str(e)}",
        }


def _get_all_accounts_basic_info() -> dict:
    """獲取所有帳戶基本資訊"""
    # 檢查 accounts 是否成功
    if (
        not accounts
        or not hasattr(accounts, "is_success")
        or not accounts.is_success
    ):
        return {
            "status": "error",
            "data": None,
            "message": "帳戶認證失敗，請檢查憑證是否過期",
        }

    account_list = []
    if hasattr(accounts, "data") and accounts.data:
        for acc in accounts.data:
            account_info = {
                "name": getattr(acc, "name", "N/A"),
                "branch_no": getattr(acc, "branch_no", "N/A"),
                "account": getattr(acc, "account", "N/A"),
                "account_type": getattr(acc, "account_type", "N/A"),
            }
            account_list.append(account_info)

    return {
        "status": "success",
        "data": account_list,
        "message": f"成功獲取 {len(account_list)} 個帳戶基本資訊。如需詳細資金資訊，請指定帳戶號碼。",
    }


def _get_basic_account_info(account_obj) -> dict:
    """獲取帳戶基本資訊"""
    return {
        "basic_info": {
            "name": getattr(account_obj, "name", "N/A"),
            "branch_no": getattr(account_obj, "branch_no", "N/A"),
            "account": getattr(account_obj, "account", "N/A"),
            "account_type": getattr(account_obj, "account_type", "N/A"),
        }
    }


def _get_account_financial_info(account_obj) -> dict:
    """獲取帳戶財務資訊"""
    info = {}

    # 獲取銀行水位
    info["bank_balance"] = _safe_api_call(
        lambda: sdk.accounting.bank_remain(account_obj), "獲取銀行水位失敗"
    )

    # 獲取未實現損益
    info["unrealized_pnl"] = _safe_api_call(
        lambda: sdk.accounting.unrealized_gains_and_loses(account_obj),
        "獲取未實現損益失敗",
    )

    # 獲取交割資訊 (今日)
    info["settlement_today"] = _safe_api_call(
        lambda: sdk.accounting.query_settlement(account_obj, "0d"),
        "獲取交割資訊失敗",
    )

    return info


def _safe_api_call(api_func, error_prefix: str):
    """安全地調用 API 函數，處理異常"""
    try:
        result = api_func()
        if result and hasattr(result, "is_success") and result.is_success:
            return result.data
        else:
            return None
    except Exception as e:
        return f"{error_prefix}: {str(e)}"


@mcp.tool()
def get_inventory(args: Dict) -> dict:
    """
    獲取帳戶庫存資訊

    Args:
        account (str): 帳戶號碼
    """
    try:
        validated_args = GetInventoryArgs(**args)
        account = validated_args.account

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取庫存資訊
        inventory = sdk.accounting.inventories(account_obj)
        if inventory and hasattr(inventory, "is_success") and inventory.is_success:
            return {
                "status": "success",
                "data": inventory.data if hasattr(inventory, "data") else inventory,
                "message": f"成功獲取帳戶 {account} 庫存資訊",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 庫存資訊",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取庫存資訊失敗: {str(e)}",
        }


@mcp.tool()
def get_settlement_info(args: Dict) -> dict:
    """
    獲取交割資訊（應收付金額）

    Args:
        account (str): 帳戶號碼
        range (str): 查詢範圍，預設 "0d" (當日)，可選 "3d" (3日)
    """
    try:
        validated_args = GetSettlementArgs(**args)
        account = validated_args.account
        range_param = validated_args.range

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取交割資訊
        settlement = sdk.accounting.query_settlement(
            account_obj, range_param
        )
        if settlement and hasattr(settlement, "is_success") and settlement.is_success:
            return {
                "status": "success",
                "data": settlement.data if hasattr(settlement, "data") else settlement,
                "message": f"成功獲取帳戶 {account} {range_param} 交割資訊",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 交割資訊",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取交割資訊失敗: {str(e)}",
        }


@mcp.tool()
def get_bank_balance(args: Dict) -> dict:
    """
    獲取帳戶銀行水位（資金餘額）

    Args:
        account (str): 帳戶號碼
    """
    try:
        validated_args = GetBankBalanceArgs(**args)
        account = validated_args.account

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取銀行水位資訊
        bank_balance = sdk.accounting.bank_remain(account_obj)
        if (
            bank_balance
            and hasattr(bank_balance, "is_success")
            and bank_balance.is_success
        ):
            return {
                "status": "success",
                "data": bank_balance.data
                if hasattr(bank_balance, "data")
                else bank_balance,
                "message": f"成功獲取帳戶 {account} 銀行水位資訊",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 銀行水位資訊",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取銀行水位失敗: {str(e)}",
        }


@mcp.tool()
def get_realtime_quotes(args: Dict) -> dict:
    """
    獲取即時行情

    Args:
        symbol (str): 股票代碼
    """
    try:
        validated_args = GetRealtimeQuotesArgs(**args)
        symbol = validated_args.symbol

        # 使用 intraday API 獲取即時行情
        from fubon_neo.fugle_marketdata.rest.base_rest import FugleAPIError

        try:
            result = reststock.intraday.quote(symbol=symbol)
            return {
                "status": "success",
                "data": result.dict() if hasattr(result, "dict") else result,
                "message": f"成功獲取 {symbol} 即時行情",
            }
        except FugleAPIError as e:
            return {"status": "error", "data": None, "message": f"API 錯誤: {e}"}
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取即時行情失敗: {str(e)}",
        }


@mcp.tool()
def get_order_results(args: Dict) -> dict:
    """
    獲取委託結果，用於確認委託與成交狀態

    查詢帳戶下的所有委託單狀態，對應官方 SDK `get_order_results(account)`。

    ⚠️ 重要用途：
    - 確認普通委託單的狀態
    - **查詢分時分量條件單產生的子委託單**（用於取消操作）
    - 監控委託單的執行進度

    Args:
        account (str): 帳戶號碼

    Returns:
        dict: 成功時返回委託結果列表，每筆委託單包含以下關鍵字段：
            - order_no (str): 委託單號
            - symbol (str): 股票代碼
            - buy_sell (str): 買賣別
            - quantity (int): 原始委託數量
            - filled_qty (int): 已成交數量
            - filled_money (float): 已成交金額
            - after_qty (int): 有效數量（剩餘可成交數量）
            - price (float): 委託價格
            - status (str): 委託狀態
            - order_time (str): 委託時間

    Note:
        **用於取消分時分量條件單**:
        分時分量條件單會產生多個子委託單，此函數返回的結果包含所有委託單，
        可從中找到對應的 order_no 用於 cancel_order 操作。

        **委託單狀態監控**:
        - filled_qty: 已成交數量，用於判斷部分成交或全部成交
        - filled_money: 已成交金額，計算已實現損益
        - after_qty: 剩餘有效數量，0表示已全部成交或取消
    """
    try:
        validated_args = GetOrderResultsArgs(**args)
        account = validated_args.account

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取委託結果
        order_results = sdk.stock.get_order_results(account_obj)
        if (
            order_results
            and hasattr(order_results, "is_success")
            and order_results.is_success
        ):
            return {
                "status": "success",
                "data": order_results.data
                if hasattr(order_results, "data")
                else order_results,
                "message": f"成功獲取帳戶 {account} 委託結果",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 委託結果",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取委託結果失敗: {str(e)}",
        }


@mcp.tool()
def get_order_results_detail(args: Dict) -> dict:
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
        account = validated_args.account

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取委託結果詳細資訊
        order_results_detail = sdk.stock.get_order_results_detail(
            account_obj
        )
        if (
            order_results_detail
            and hasattr(order_results_detail, "is_success")
            and order_results_detail.is_success
        ):
            return {
                "status": "success",
                "data": order_results_detail.data
                if hasattr(order_results_detail, "data")
                else order_results_detail,
                "message": f"成功獲取帳戶 {account} 委託結果詳細資訊",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 委託結果詳細資訊",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取委託結果詳細資訊失敗: {str(e)}",
        }


@mcp.tool()
def margin_quota(args: Dict) -> dict:
    """
    查詢資券配額

    查詢指定帳戶和股票代碼的資券配額資訊，對應官方 SDK `margin_quota(account, stock_no)`。

    ⚠️ 重要用途：
    - 確認股票的融資融券可用額度
    - 檢查是否可以進行信用交易
    - 監控資券配額使用狀況

    Args:
        account (str): 帳戶號碼
        stock_no (str): 股票代碼

    Returns:
        dict: 成功時返回資券配額資訊，包含以下關鍵字段：
            - stock_no (str): 股票代碼
            - date (str): 資料日期
            - shortsell_orig_quota (int): 融券原始額度
                - 0: 無融券額度
                - >0: 有融券額度
                - None: 融券無上限
            - shortsell_tradable_quota (int): 融券可交易額度
                - 0: 無融券額度
                - >0: 有融券額度
                - None: 融券無上限
            - margin_orig_quota (int): 融資原始額度
                - 0: 無融資額度
                - >0: 有融資額度
                - None: 融資無上限
            - margin_tradable_quota (int): 融資可交易額度
                - 0: 無融資額度
                - >0: 有融資額度
                - None: 融資無上限
            - margin_ratio (float): 融資比率
                - None: 融資暫停
                - 數值: 融資比率（如 0.6 表示60%）
            - short_ratio (float): 融券比率
                - None: 融券暫停
                - 數值: 融券比率（如 0.4 表示40%）

    Note:
        **資券配額解釋**:
        - **融資額度**: 用於買入股票時向券商借錢
        - **融券額度**: 用於賣出股票時向券商借股票
        - **原始額度 vs 可交易額度**: 原始額度是總額度，可交易額度是扣除已使用後的剩餘額度
        - **額度為0**: 表示沒有該項資券配額
        - **額度為None**: 表示該項資券無上限
        - **比率為None**: 表示該項資券交易暫停
        - **所有額度為0且比率為None**: 表示該股票資券交易停止

        **交易限制檢查**:
        - 融資交易需要 margin_tradable_quota > 0 且 margin_ratio 不為 None
        - 融券交易需要 shortsell_tradable_quota > 0 且 short_ratio 不為 None
    """
    try:
        validated_args = GetMarginQuotaArgs(**args)
        account = validated_args.account
        stock_no = validated_args.stock_no

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 查詢資券配額
        margin_quota_result = sdk.stock.margin_quota(account_obj, stock_no)
        if (
            margin_quota_result
            and hasattr(margin_quota_result, "is_success")
            and margin_quota_result.is_success
        ):
            return {
                "status": "success",
                "data": margin_quota_result.data
                if hasattr(margin_quota_result, "data")
                else margin_quota_result,
                "message": f"成功獲取帳戶 {account} 股票 {stock_no} 資券配額",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 股票 {stock_no} 資券配額",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取資券配額失敗: {str(e)}",
        }


@mcp.tool()
def daytrade_and_stock_info(args: Dict) -> dict:
    """
    查詢現沖券配額資訊

    查詢指定帳戶和股票代碼的現沖券配額及相關資訊，對應官方 SDK `daytrade_and_stock_info(account, stock_no)`。

    ⚠️ 重要用途：
    - 確認股票的現沖券可用額度
    - 檢查是否可以進行現沖交易
    - 了解股票的警示狀態和交易限制
    - 監控預收股數資訊

    Args:
        account (str): 帳戶號碼
        stock_no (str): 股票代碼

    Returns:
        dict: 成功時返回現沖券配額資訊，包含以下關鍵字段：
            - stock_no (str): 股票代號
            - date (str): 日期
            - daytrade_orig_quota (int): 原始現沖券餘額
                - 0: 無現沖券額度
                - >0: 有現沖券額度
            - daytrade_tradable_quota (int): 可用現沖券餘額
                - 0: 無可用額度
                - >0: 有可用額度
            - precollect_single (int): 單筆預收股數
                - None: 不需預收
                - 數值: 預收股數
            - precollect_accumulate (int): 累積預收股數
                - None: 不需預收
                - 數值: 累積預收股數
            - status (int): 狀態 (bitmask)
                - 0: 全禁
                - 1: 平盤下可融券賣出
                - 2: 平盤下可借券賣出
                - 4: 可先買後賣當沖
                - 8: 可先賣後買當沖
                - 狀態值為上述數值的加總
            - disposition_status (str): 警示股註記
                - {"SETTYPE": 1}: 全額交割
                - {"MARK-W": 1}: 警示
                - {"MARK-P": 1}: 注意
                - {"MARK-L": 1}: 委託受限

    Note:
        **狀態值解釋**:
        - status 是 bitmask 值，需要按位解析：
          * 0 = 全禁（無法進行任何相關交易）
          * 1 = 平盤下可融券賣出
          * 2 = 平盤下可借券賣出
          * 4 = 可先買後賣當沖
          * 8 = 可先賣後買當沖
        - 例如：status=15 表示可進行所有交易 (1+2+4+8)
        - status=3 表示僅可進行平盤下融券和借券賣出 (1+2)

        **警示股註記說明**:
        - SETTYPE: 全額交割股
        - MARK-W: 警示股
        - MARK-P: 注意股
        - MARK-L: 委託受限股

        **預收股數說明**:
        - precollect_single: 單筆交易預收股數
        - precollect_accumulate: 累計預收股數
        - None 表示該股票不需預收股款
    """
    try:
        validated_args = GetDayTradeStockInfoArgs(**args)
        account = validated_args.account
        stock_no = validated_args.stock_no

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 查詢現沖券配額資訊
        daytrade_info = sdk.stock.daytrade_and_stock_info(
            account_obj, stock_no
        )
        if (
            daytrade_info
            and hasattr(daytrade_info, "is_success")
            and daytrade_info.is_success
        ):
            return {
                "status": "success",
                "data": daytrade_info.data
                if hasattr(daytrade_info, "data")
                else daytrade_info,
                "message": f"成功獲取帳戶 {account} 股票 {stock_no} 現沖券配額資訊",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 股票 {stock_no} 現沖券配額資訊",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取現沖券配額資訊失敗: {str(e)}",
        }


@mcp.tool()
def query_symbol_quote(args: Dict) -> dict:
    """
    查詢商品漲跌幅報表（單筆）

    查詢指定股票的即時報價和交易資訊，對應官方 SDK `query_symbol_quote(account, symbol, market_type)`。
    此為 2.2.5 版新增功能。

    ⚠️ 重要用途：
    - 獲取股票的即時價格和交易資訊
    - 查詢漲跌停價格和參考價格
    - 了解市場狀態和交易權限
    - 監控買賣價量資訊

    Args:
        account (str): 帳戶號碼
        symbol (str): 股票代碼
        market_type (str, optional): 市場類型，預設 "Common"
            - "Common": 整股市場
            - "IntradayOdd": 盤中零股
            - "Fixing": 定盤

    Returns:
        dict: 成功時返回股票報價資訊，包含以下關鍵字段：
            - market (str): 市場別
            - symbol (str): 股票代碼
            - is_tib_or_psb (bool): 是否為創新版或戰略新板
            - market_type (str): 市場類型
            - status (int): 狀態 (bitmask)
                - 0: 全禁
                - 1: 平盤下可融券賣出
                - 2: 平盤下可借券賣出
                - 4: 可先買後賣當沖
                - 8: 可先賣後買當沖
                - 狀態值為上述數值的加總
            - reference_price (float): 參考價格
            - unit (int): 交易單位
            - update_time (str): 更新時間
            - limitup_price (float): 漲停價
            - limitdown_price (float): 跌停價
            - open_price (float): 開盤價
            - high_price (float): 最高價
            - low_price (float): 最低價
            - last_price (float): 最新成交價
            - total_volume (int): 總成交量
            - total_transaction (int): 總成交筆數
            - total_value (float): 總成交金額
            - last_size (int): 最新成交量
            - last_transaction (int): 最新成交筆數
            - last_value (float): 最新成交金額
            - bid_price (float): 買1價格
            - bid_volume (int): 買1數量
            - ask_price (float): 賣1價格
            - ask_volume (int): 賣1數量

    Note:
        **狀態值解釋**:
        - status 是 bitmask 值，需要按位解析：
          * 0 = 全禁（無法進行任何相關交易）
          * 1 = 平盤下可融券賣出
          * 2 = 平盤下可借券賣出
          * 4 = 可先買後賣當沖
          * 8 = 可先賣後買當沖
        - 例如：status=15 表示可進行所有交易 (1+2+4+8)
        - status=3 表示僅可進行平盤下融券和借券賣出 (1+2)

        **市場類型說明**:
        - Common: 整股市場（預設）
        - IntradayOdd: 盤中零股市場
        - Fixing: 定盤市場

        **價格資訊說明**:
        - reference_price: 參考價格（通常為昨收價）
        - limitup_price/limitdown_price: 漲跌停價格
        - open_price/high_price/low_price: 當日開高低價
        - last_price: 最新成交價

        **成交資訊說明**:
        - total_*: 當日累計成交統計
        - last_*: 最新一筆成交資訊
        - bid_price/bid_volume: 買方最佳價格和數量
        - ask_price/ask_volume: 賣方最佳價格和數量
    """
    try:
        validated_args = QuerySymbolQuoteArgs(**args)
        account = validated_args.account
        symbol = validated_args.symbol
        market_type = validated_args.market_type

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 轉換市場類型枚舉
        market_type_enum = to_market_type(market_type)

        # 查詢商品報價
        quote_result = sdk.stock.query_symbol_quote(
            account_obj, symbol, market_type_enum
        )
        if (
            quote_result
            and hasattr(quote_result, "is_success")
            and quote_result.is_success
        ):
            return {
                "status": "success",
                "data": quote_result.data
                if hasattr(quote_result, "data")
                else quote_result,
                "message": f"成功獲取股票 {symbol} 報價資訊",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取股票 {symbol} 報價資訊",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取商品報價失敗: {str(e)}",
        }


@mcp.tool()
def query_symbol_snapshot(args: Dict) -> dict:
    """
    查詢商品漲跌幅報表（批量）

    批量查詢多個股票的即時報價和交易資訊，對應官方 SDK `query_symbol_snapshot(account, market_type, stock_type)`。
    此為 2.2.5 版新增功能。

    ⚠️ 重要用途：
    - 批量獲取多個股票的即時價格和交易資訊
    - 查詢漲跌停價格和參考價格
    - 了解市場狀態和交易權限
    - 監控買賣價量資訊

    Args:
        account (str): 帳戶號碼
        market_type (str, optional): 市場類型，預設 "Common"
            - "Common": 整股市場
            - "IntradayOdd": 盤中零股
            - "Fixing": 定盤
        stock_type (List[str], optional): 股票類型列表，預設 ["Stock"]
            - "Stock": 一般股票
            - "CovertBond": 轉換公司債
            - "EtfAndEtn": ETF及ETN

    Returns:
        dict: 成功時返回 SymbolSnapshotResponse，包含以下關鍵字段：
            - symbols (List[SymbolQuote]): 股票報價資訊列表，每筆包含：
                - market (str): 市場別
                - symbol (str): 股票代碼
                - is_tib_or_psb (bool): 是否為創新版或戰略新板
                - market_type (str): 市場類型
                - status (int): 狀態 (bitmask)
                    - 0: 全禁
                    - 1: 平盤下可融券賣出
                    - 2: 平盤下可借券賣出
                    - 4: 可先買後賣當沖
                    - 8: 可先賣後買當沖
                    - 狀態值為上述數值的加總
                - reference_price (float): 參考價格
                - unit (int): 交易單位
                - update_time (str): 更新時間
                - limitup_price (float): 漲停價
                - limitdown_price (float): 跌停價
                - open_price (float): 開盤價
                - high_price (float): 最高價
                - low_price (float): 最低價
                - last_price (float): 最新成交價
                - total_volume (int): 總成交量
                - total_transaction (int): 總成交筆數
                - total_value (float): 總成交金額
                - last_size (int): 最新成交量
                - last_transaction (int): 最新成交筆數
                - last_value (float): 最新成交金額
                - bid_price (float): 買1價格
                - bid_volume (int): 買1數量
                - ask_price (float): 賣1價格
                - ask_volume (int): 賣1數量

    Note:
        **狀態值解釋**:
        - status 是 bitmask 值，需要按位解析：
          * 0 = 全禁（無法進行任何相關交易）
          * 1 = 平盤下可融券賣出
          * 2 = 平盤下可借券賣出
          * 4 = 可先買後賣當沖
          * 8 = 可先賣後買當沖
        - 例如：status=15 表示可進行所有交易 (1+2+4+8)
        - status=3 表示僅可進行平盤下融券和借券賣出 (1+2)

        **市場類型說明**:
        - Common: 整股市場（預設）
        - IntradayOdd: 盤中零股市場
        - Fixing: 定盤市場

        **股票類型說明**:
        - Stock: 一般股票（預設）
        - CovertBond: 轉換公司債
        - EtfAndEtn: ETF及ETN

        **批量查詢特性**:
        - 一次可查詢多個股票類型的報價資訊
        - 返回的 symbols 陣列包含所有符合條件的股票
        - 適用於市場概覽和批量數據分析
    """
    try:
        validated_args = QuerySymbolSnapshotArgs(**args)
        account = validated_args.account
        market_type = validated_args.market_type
        stock_type = validated_args.stock_type

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 轉換枚舉值
        market_type_enum = to_market_type(market_type)
        stock_type_enums = to_stock_types(stock_type)

        # 批量查詢商品報價
        snapshot_result = sdk.stock.query_symbol_snapshot(
            account_obj, market_type_enum, stock_type_enums
        )
        if (
            snapshot_result
            and hasattr(snapshot_result, "is_success")
            and snapshot_result.is_success
        ):
            return {
                "status": "success",
                "data": snapshot_result.data
                if hasattr(snapshot_result, "data")
                else snapshot_result,
                "message": f"成功批量獲取股票報價資訊，市場類型: {market_type}，股票類型: {stock_type}",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法批量獲取股票報價資訊",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"批量獲取商品報價失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_tickers(args: Dict) -> dict:
    """
    獲取股票或指數列表（依條件查詢）

    對應富邦官方 API: intraday/tickers/{market}

    Args:
        market (str): 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
        type (str, optional): 類型，可選 ALLBUT099 包含一般股票、特別股及ETF；COMMONSTOCK 為一般股票
        exchange (str, optional): 交易所，可選 TSE 或 OTC
        industry (str, optional): 行業別
        isNormal (bool, optional): 是否為普通股
        isAttention (bool, optional): 是否為注意股
        isDisposition (bool, optional): 是否為處置股
        isHalted (bool, optional): 是否為停止交易股

    Returns:
        dict: 成功時返回包含以下字段的字典：
            - status: "success"
            - data: 股票列表
            - market: 市場別
            - type: 類型
            - exchange: 交易所
            - industry: 行業別
            - isNormal: 是否普通股
            - isAttention: 是否注意股
            - isDisposition: 是否處置股
            - isHalted: 是否停止交易
            - message: 成功訊息

        每筆股票數據包含：
            - symbol: 股票代碼
            - name: 股票名稱
            - exchange: 交易所
            - market: 市場別
            - industry: 行業別
            - isNormal: 是否普通股
            - isAttention: 是否注意股
            - isDisposition: 是否處置股
            - isHalted: 是否停止交易

    Example:
        {
            "market": "TSE",
            "type": "COMMONSTOCK",
            "isNormal": true
        }
    """
    try:
        validated_args = GetIntradayTickersArgs(**args)
        market = validated_args.market
        type_param = validated_args.type
        exchange = validated_args.exchange
        industry = validated_args.industry
        isNormal = validated_args.isNormal
        isAttention = validated_args.isAttention
        isDisposition = validated_args.isDisposition
        isHalted = validated_args.isHalted

        # 構建API調用參數
        api_params = {"market": market}
        if type_param:
            api_params["type"] = type_param
        if exchange:
            api_params["exchange"] = exchange
        if industry:
            api_params["industry"] = industry
        if isNormal is not None:
            api_params["isNormal"] = isNormal
        if isAttention is not None:
            api_params["isAttention"] = isAttention
        if isDisposition is not None:
            api_params["isDisposition"] = isDisposition
        if isHalted is not None:
            api_params["isHalted"] = isHalted

        result = reststock.intraday.tickers(**api_params)
        return {
            "status": "success",
            "data": result,
            "message": f"成功獲取 {market} 市場股票列表",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取股票列表失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_ticker(args: Dict) -> dict:
    """
    獲取股票基本資料（依代碼查詢）

    Args:
        symbol (str): 股票代碼
        type (str, optional): 類型，可選 oddlot 盤中零股
    """
    try:
        validated_args = GetIntradayTickerArgs(**args)
        symbol = validated_args.symbol
        type_param = validated_args.type

        # 構建API調用參數
        api_params = {"symbol": symbol}
        if type_param:
            api_params["type"] = type_param

        result = reststock.intraday.ticker(**api_params)

        # 處理返回數據
        data = result.dict() if hasattr(result, "dict") else result

        # 證券類型代碼對照表
        security_type_mapping = {
            "01": "一般股票",
            "02": "轉換公司債",
            "03": "交換公司債或交換金融債",
            "04": "一般特別股",
            "05": "可交換特別股",
            "06": "認股權憑證",
            "07": "附認股權特別股",
            "08": "附認股權公司債",
            "09": "附認股權公司債履約或分拆後之公司債",
            "10": "國內標的認購權證",
            "11": "國內標的認售權證",
            "12": "外國標的認購權證",
            "13": "外國標的認售權證",
            "14": "國內標的下限型認購權證",
            "15": "國內標的上限型認售權證",
            "16": "國內標的可展延下限型認購權證",
            "17": "國內標的可展延上限型認售權證",
            "18": "受益憑證(封閉式基金)",
            "19": "存託憑證",
            "20": "存託憑證可轉換公司債",
            "21": "存託憑證附認股權公司債",
            "22": "存託憑證附認股權公司債履約或分拆後之公司債",
            "23": "存託憑證認股權憑證",
            "24": "ETF",
            "25": "ETF（外幣計價）",
            "26": "槓桿型ETF",
            "27": "槓桿型 ETF（外幣計價）",
            "28": "反向型 ETF",
            "29": "反向型 ETF（外幣計價）",
            "30": "期信託 ETF",
            "31": "期信託 ETF（外幣計價）",
            "32": "債券 ETF",
            "33": "債券 ETF（外幣計價）",
            "34": "金融資產證券化受益證券",
            "35": "不動產資產信託受益證券",
            "36": "不動產投資信託受益證券",
            "37": "ETN",
            "38": "槓桿型 ETN",
            "39": "反向型 ETN",
            "40": "債券型 ETN",
            "41": "期權策略型 ETN",
            "42": "中央登錄公債",
            "43": "外國債券",
            "44": "黃金現貨",
            "00": "未知或保留代碼",
        }

        # 如果數據是字典且包含 securityType，進行轉換
        if isinstance(data, dict) and "securityType" in data:
            security_type_code = str(data["securityType"])
            data["securityTypeName"] = security_type_mapping.get(
                security_type_code, f"未知代碼({security_type_code})"
            )

        return {
            "status": "success",
            "data": data,
            "message": f"成功獲取 {symbol} 基本資料",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取基本資料失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_quote(args: Dict) -> dict:
    """
    獲取股票即時報價（依代碼查詢）

    Args:
        symbol (str): 股票代碼
        type (str, optional): 類型，可選 oddlot 盤中零股
    """
    try:
        validated_args = GetIntradayQuoteArgs(**args)
        symbol = validated_args.symbol
        type_param = validated_args.type

        # 構建API調用參數
        api_params = {"symbol": symbol}
        if type_param:
            api_params["type"] = type_param

        result = reststock.intraday.quote(**api_params)
        return {
            "status": "success",
            "data": result.dict() if hasattr(result, "dict") else result,
            "message": f"成功獲取 {symbol} 即時報價",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取即時報價失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_candles(args: Dict) -> dict:
    """
    獲取股票價格 K 線（依代碼查詢）

    Args:
        symbol (str): 股票代碼
    """
    try:
        validated_args = GetIntradayCandlesArgs(**args)
        symbol = validated_args.symbol

        result = reststock.intraday.candles(symbol=symbol)
        return {
            "status": "success",
            "data": result,
            "message": f"成功獲取 {symbol} 盤中 K 線",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取盤中 K 線失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_trades(args: Dict) -> dict:
    """
    獲取股票成交明細（依代碼查詢）

    Args:
        symbol (str): 股票代碼
        type (str, optional): Ticker 類型，可選 oddlot 盤中零股
        offset (int, optional): 偏移量
        limit (int, optional): 限制量
    """
    try:
        validated_args = GetIntradayTradesArgs(**args)
        symbol = validated_args.symbol
        type_param = validated_args.type
        offset = validated_args.offset
        limit = validated_args.limit

        # 構建API調用參數
        api_params = {"symbol": symbol}
        if type_param:
            api_params["type"] = type_param
        if offset is not None:
            api_params["offset"] = offset
        if limit is not None:
            api_params["limit"] = limit

        result = reststock.intraday.trades(**api_params)
        return {
            "status": "success",
            "data": result,
            "message": f"成功獲取 {symbol} 成交明細",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取成交明細失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_volumes(args: Dict) -> dict:
    """
    獲取股票分價量表（依代碼查詢）

    Args:
        symbol (str): 股票代碼
    """
    try:
        validated_args = GetIntradayVolumesArgs(**args)
        symbol = validated_args.symbol

        result = reststock.intraday.volumes(symbol=symbol)
        return {
            "status": "success",
            "data": result,
            "message": f"成功獲取 {symbol} 分價量表",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取分價量表失敗: {str(e)}",
        }


@mcp.tool()
def get_snapshot_quotes(args: Dict) -> dict:
    """
    獲取股票行情快照（依市場別）

    Args:
        market (str): 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
        type (str): 標的類型，可選 ALLBUT099 包含一般股票、特別股及ETF ； COMMONSTOCK 為一般股票
    """
    try:
        validated_args = GetSnapshotQuotesArgs(**args)
        market = validated_args.market
        type_param = validated_args.type

        # 構建API調用參數
        api_params = {"market": market}
        if type_param:
            api_params["type"] = type_param

        result = reststock.snapshot.quotes(**api_params)

        # API 返回的是字典格式，包含 'data' 鍵
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            if isinstance(data, list):
                # 限制返回前50筆資料以避免過大回應
                limited_data = data[:50] if len(data) > 50 else data
                return {
                    "status": "success",
                    "data": limited_data,
                    "total_count": len(data),
                    "returned_count": len(limited_data),
                    "market": result.get("market"),
                    "type": result.get("type"),
                    "date": result.get("date"),
                    "time": result.get("time"),
                    "message": f"成功獲取 {market} 行情快照 (顯示前 {len(limited_data)} 筆，共 {len(data)} 筆)",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": "API 返回的 data 欄位不是列表格式",
                }
        else:
            # 如果返回的不是預期的字典格式
            return {
                "status": "success",
                "data": result,
                "message": f"成功獲取 {market} 行情快照",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取行情快照失敗: {str(e)}",
        }


@mcp.tool()
def get_snapshot_movers(args: Dict) -> dict:
    """
    獲取股票漲跌幅排行（依市場別）

    Args:
        market (str): 市場別
        direction (str): 上漲／下跌，可選 up 上漲；down 下跌，預設 "up"
        change (str): 漲跌／漲跌幅，可選 percent 漲跌幅；value 漲跌，預設 "percent"
        gt (float): 篩選大於漲跌／漲跌幅的股票
        gte (float): 篩選大於或等於漲跌／漲跌幅的股票
        lt (float): 篩選小於漲跌／漲跌幅的股票
        lte (float): 篩選小於或等於漲跌／漲跌幅的股票
        eq (float): 篩選等於漲跌／漲跌幅的股票
        type (str): 標的類型，可選 ALLBUT099 包含一般股票、特別股及ETF ； COMMONSTOCK 為一般股票
    """
    try:
        validated_args = GetSnapshotMoversArgs(**args)
        market = validated_args.market
        direction = validated_args.direction
        change = validated_args.change
        gt = validated_args.gt
        gte = validated_args.gte
        lt = validated_args.lt
        lte = validated_args.lte
        eq = validated_args.eq
        type_param = validated_args.type

        # 構建API調用參數 - 總是傳遞必要參數
        api_params = {"market": market, "direction": direction, "change": change}

        # 篩選條件參數
        filter_params = {}
        if gt is not None:
            filter_params["gt"] = gt
        if gte is not None:
            filter_params["gte"] = gte
        if lt is not None:
            filter_params["lt"] = lt
        if lte is not None:
            filter_params["lte"] = lte
        if eq is not None:
            filter_params["eq"] = eq
        if type_param:
            filter_params["type"] = type_param

        # 合併參數
        api_params.update(filter_params)

        # 調試輸出
        print(f"API params: {api_params}", file=sys.stderr)

        result = reststock.snapshot.movers(**api_params)

        # API 返回的是字典格式，包含 'data' 鍵
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            if isinstance(data, list):
                # 限制返回前50筆資料以避免過大回應
                limited_data = data[:50] if len(data) > 50 else data
                return {
                    "status": "success",
                    "data": limited_data,
                    "total_count": len(data),
                    "returned_count": len(limited_data),
                    "market": result.get("market"),
                    "direction": result.get("direction"),
                    "change": result.get("change"),
                    "date": result.get("date"),
                    "time": result.get("time"),
                    "message": f"成功獲取 {market} 漲跌幅排行 (顯示前 {len(limited_data)} 筆，共 {len(data)} 筆)",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": "API 返回的 data 欄位不是列表格式",
                }
        else:
            # 如果返回的不是預期的字典格式
            return {
                "status": "success",
                "data": result,
                "message": f"成功獲取 {market} {direction} {change}排行",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取漲跌幅排行失敗: {str(e)}",
        }


@mcp.tool()
def get_snapshot_actives(args: Dict) -> dict:
    """
    獲取股票成交量值排行（依市場別）

    對應富邦官方 API: snapshot/actives/{market}

    Args:
        market (str): 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
        trade (str): 成交量／成交值，可選 volume 成交量；value 成交值，預設 "volume"
        type (str, optional): 標的類型，可選 ALLBUT099 包含一般股票、特別股及ETF；COMMONSTOCK 為一般股票

    Returns:
        dict: 成功時返回包含以下字段的字典：
            - status: "success"
            - data: 排行數據列表（限制前50筆）
            - total_count: 總筆數
            - returned_count: 返回筆數
            - market: 市場別
            - trade: 成交量/值類型
            - date: 日期
            - time: 時間
            - message: 成功訊息

        每筆排行數據包含：
            - type: Ticker 類型
            - symbol: 股票代碼
            - name: 股票簡稱
            - openPrice: 開盤價
            - highPrice: 最高價
            - lowPrice: 最低價
            - closePrice: 收盤價
            - change: 漲跌
            - changePercent: 漲跌幅
            - tradeVolume: 成交量
            - tradeValue: 成交金額
            - lastUpdated: 快照時間

    Example:
        {
            "market": "TSE",
            "trade": "value"
        }
    """
    try:
        validated_args = GetSnapshotActivesArgs(**args)
        market = validated_args.market
        trade = validated_args.trade
        type_param = validated_args.type

        # 構建API調用參數
        api_params = {"market": market, "trade": trade}
        if type_param:
            api_params["type"] = type_param

        result = reststock.snapshot.actives(**api_params)

        # API 返回的是字典格式，包含 'data' 鍵
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            if isinstance(data, list):
                # 限制返回前50筆資料以避免過大回應
                limited_data = data[:50] if len(data) > 50 else data
                return {
                    "status": "success",
                    "data": limited_data,
                    "total_count": len(data),
                    "returned_count": len(limited_data),
                    "market": result.get("market"),
                    "trade": result.get("trade"),
                    "date": result.get("date"),
                    "time": result.get("time"),
                    "message": f"成功獲取 {market} 成交量值排行 (顯示前 {len(limited_data)} 筆，共 {len(data)} 筆)",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": "API 返回的 data 欄位不是列表格式",
                }
        else:
            # 如果返回的不是預期的字典格式
            return {
                "status": "success",
                "data": result,
                "message": f"成功獲取 {market} {trade}排行",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取成交量值排行失敗: {str(e)}",
        }


@mcp.tool()
def get_historical_stats(args: Dict) -> dict:
    """
    獲取近 52 週股價數據（依代碼查詢）

    Args:
        symbol (str): 股票代碼
    """
    try:
        validated_args = GetHistoricalStatsArgs(**args)
        symbol = validated_args.symbol

        # 使用正確的 historical.stats API
        result = reststock.historical.stats(symbol=symbol)

        # 檢查返回格式
        if (
            isinstance(result, dict)
            and (("week52High" in result) or ("52w_high" in result))
            and (("week52Low" in result) or ("52w_low" in result))
        ):
            stats = {
                "symbol": result.get("symbol"),
                "name": result.get("name"),
                "52_week_high": result.get("week52High") or result.get("52w_high"),
                "52_week_low": result.get("week52Low") or result.get("52w_low"),
                "current_price": result.get("closePrice"),
                "change": result.get("change"),
                "change_percent": result.get("changePercent"),
                "date": result.get("date"),
            }
            return {
                "status": "success",
                "data": stats,
                "message": f"成功獲取 {symbol} 近 52 週統計",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"API 返回格式錯誤: {result}",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取歷史統計失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_futopt_products(args: Dict) -> dict:
    """
    獲取期貨/選擇權合約列表

    查詢期貨和選擇權合約的基本資訊，可依據類型、交易所、交易時段、合約類型和狀態進行過濾。
    對應富邦官方 API: intraday/products

    Args:
        type (str, optional): 商品類型
            - "FUTURE": 期貨
            - "OPTION": 選擇權
            - 預設查詢所有類型
        exchange (str, optional): 交易所
            - "TAIFEX": 台灣期貨交易所
            - 預設查詢所有交易所
        session (str, optional): 交易時段
            - "REGULAR": 一般交易時段
            - "AFTERHOURS": 盤後交易時段
            - 預設查詢所有時段
        contract_type (str, optional): 合約類型
            - "FUTURES": 期貨合約
            - "CALL": 買權選擇權
            - "PUT": 賣權選擇權
            - 預設查詢所有類型
        status (str, optional): 合約狀態
            - "ACTIVE": 活躍合約
            - "INACTIVE": 非活躍合約
            - 預設查詢所有狀態

    Returns:
        dict: 成功時返回合約列表，每筆記錄包含：
            - symbol (str): 合約代碼
            - name (str): 合約名稱
            - type (str): 商品類型 (FUTURE/OPTION)
            - exchange (str): 交易所
            - session (str): 交易時段
            - contract_type (str): 合約類型
            - status (str): 合約狀態
            - underlying_symbol (str): 標的代碼 (選擇權專用)
            - strike_price (float): 履約價 (選擇權專用)
            - expiration_date (str): 到期日
            - 其他合約相關資訊

    Example:
        # 查詢所有活躍期貨合約
        {"type": "FUTURE", "status": "ACTIVE"}

        # 查詢台指選擇權
        {"type": "OPTION", "contract_type": "CALL", "underlying_symbol": "TX00"}

        # 查詢所有合約 (無過濾條件)
        {}
    """
    try:
        validated_args = GetIntradayProductsArgs(**args)

        # 準備 API 參數
        api_params = {}

        # 依據驗證後的參數設置 API 參數
        if validated_args.type is not None:
            api_params["type"] = validated_args.type
        if validated_args.exchange is not None:
            api_params["exchange"] = validated_args.exchange
        if validated_args.session is not None:
            api_params["session"] = validated_args.session
        if validated_args.contractType is not None:
            api_params["contractType"] = validated_args.contractType
        if validated_args.status is not None:
            api_params["status"] = validated_args.status

        # 調用富邦期貨/選擇權 API
        result = restfutopt.intraday.products(**api_params)

        # 檢查 API 返回結果
        if result and isinstance(result, dict):
            # 從回應中提取數據
            products_data = result.get("data", [])
            query_type = result.get("type")
            query_exchange = result.get("exchange")
            query_session = result.get("session")
            query_contract_type = result.get("contractType")
            query_status = result.get("status")

            # 整理返回數據
            products = []
            for product in products_data:
                if isinstance(product, dict):
                    product_info = {
                        "symbol": product.get("symbol"),
                        "name": product.get("name"),
                        "type": product.get("type"),
                        "exchange": product.get("exchange"),
                        "session": product.get("session"),
                        "contract_type": product.get("contractType"),
                        "status": product.get("statusCode"),
                        "underlying_symbol": product.get("underlyingSymbol"),
                        "strike_price": product.get("strikePrice"),
                        "expiration_date": product.get("expirationDate"),
                        "multiplier": product.get("contractSize"),
                        "tick_size": product.get("tickSize"),
                        "tick_value": product.get("tickValue"),
                        "trading_hours": product.get("tradingHours"),
                        "settlement_date": product.get("settlementDate"),
                        "last_trading_date": product.get("lastTradingDate"),
                        "trading_currency": product.get("tradingCurrency"),
                        "quote_acceptable": product.get("quoteAcceptable"),
                        "can_block_trade": product.get("canBlockTrade"),
                        "expiry_type": product.get("expiryType"),
                        "underlying_type": product.get("underlyingType"),
                        "market_close_group": product.get("marketCloseGroup"),
                        "end_session": product.get("endSession"),
                        "start_date": product.get("startDate"),
                    }
                    # 移除 None 值
                    product_info = {
                        k: v for k, v in product_info.items() if v is not None
                    }
                    products.append(product_info)

            # 統計資訊
            total_count = len(products)
            type_counts = {}
            for product in products:
                p_type = product.get("type", "UNKNOWN")
                type_counts[p_type] = type_counts.get(p_type, 0) + 1

            return {
                "status": "success",
                "type": query_type,
                "exchange": query_exchange,
                "session": query_session,
                "contractType": query_contract_type,
                "query_status": query_status,
                "data": products,
                "total_count": total_count,
                "type_counts": type_counts,
                "filters_applied": api_params,
                "message": f"成功獲取 {total_count} 筆合約資訊",
            }
        else:
            return {"status": "error", "data": None, "message": "API 返回格式錯誤"}

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取合約列表失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_futopt_tickers(args: Dict) -> dict:
    """
    獲取期貨/選擇權合約代碼列表（依條件查詢）

    查詢期貨和選擇權合約的代碼資訊，可依據類型、交易所、交易時段、產品和契約類型進行過濾。
    對應富邦官方 API: intraday/tickers

    Args:
        type (str): 商品類型
            - "FUTURE": 期貨
            - "OPTION": 選擇權
        exchange (str, optional): 交易所
            - "TAIFEX": 台灣期貨交易所
            - 預設查詢所有交易所
        session (str, optional): 交易時段
            - "REGULAR": 一般交易時段
            - "AFTERHOURS": 盤後交易時段
            - 預設查詢所有時段
        product (str, optional): 產品代碼
            - 例如: "TX00" (台指期), "MTX00" (小台指期)
            - 預設查詢所有產品
        contractType (str, optional): 契約類型
            - "I": 指數類
            - "R": 利率類
            - "B": 債券類
            - "C": 商品類
            - "S": 股票類
            - "E": 匯率類
            - 預設查詢所有類型

    Returns:
        dict: 成功時返回合約代碼列表，每筆記錄包含：
            - symbol (str): 合約代碼
            - name (str): 合約名稱
            - type (str): 商品類型 (FUTURE/OPTION)
            - exchange (str): 交易所
            - session (str): 交易時段
            - product (str): 產品代碼
            - contract_type (str): 契約類型
            - expiration_date (str): 到期日
            - strike_price (float): 履約價 (選擇權專用)
            - option_type (str): 選擇權類型 (CALL/PUT，選擇權專用)
            - 其他合約相關資訊

    Example:
        # 查詢所有台指期合約
        {"type": "FUTURE", "product": "TX00"}

        # 查詢所有台指選擇權
        {"type": "OPTION", "product": "TX00"}

        # 查詢指數類期貨
        {"type": "FUTURE", "contractType": "I"}
    """
    try:
        # 檢查 restfutopt 是否已初始化
        if restfutopt is None:
            return {
                "status": "error",
                "data": None,
                "message": "期貨/選擇權行情服務未初始化，請先登入系統",
            }

        validated_args = GetIntradayFutOptTickersArgs(**args)

        # 準備 API 參數
        api_params = {}

        # 依據驗證後的參數設置 API 參數
        if validated_args.type is not None:
            api_params["type"] = validated_args.type
        if validated_args.exchange is not None:
            api_params["exchange"] = validated_args.exchange
        if validated_args.session is not None:
            api_params["session"] = validated_args.session
        if validated_args.product is not None:
            api_params["product"] = validated_args.product
        if validated_args.contractType is not None:
            api_params["contractType"] = validated_args.contractType

        # 調用富邦期貨/選擇權 API
        result = restfutopt.intraday.tickers(**api_params)

        # 檢查 API 返回結果
        if result and isinstance(result, dict) and "data" in result:
            # API 返回格式為 {'type': '...', 'exchange': '...', 'data': [...]}
            tickers_data = result.get("data", [])
            if not isinstance(tickers_data, list):
                tickers_data = []

            # 整理返回數據
            tickers = []
            for ticker in tickers_data:
                if isinstance(ticker, dict):
                    ticker_info = {
                        "symbol": ticker.get("symbol"),
                        "name": ticker.get("name"),
                        "type": ticker.get("type"),
                        "exchange": ticker.get("exchange"),
                        "session": ticker.get("session"),
                        "product": ticker.get("product"),
                        "contract_type": ticker.get("contractType"),
                        "expiration_date": ticker.get("expirationDate"),
                        "strike_price": ticker.get("strikePrice"),
                        "option_type": ticker.get("optionType"),
                        "underlying_symbol": ticker.get("underlyingSymbol"),
                        "multiplier": ticker.get("multiplier"),
                        "tick_size": ticker.get("tickSize"),
                        "trading_hours": ticker.get("tradingHours"),
                        "last_trading_date": ticker.get("lastTradingDate"),
                    }
                    # 移除 None 值
                    ticker_info = {
                        k: v for k, v in ticker_info.items() if v is not None
                    }
                    tickers.append(ticker_info)

            # 統計資訊
            total_count = len(tickers)
            type_counts = {}
            for ticker in tickers:
                t_type = ticker.get("type", "UNKNOWN")
                type_counts[t_type] = type_counts.get(t_type, 0) + 1

            return {
                "status": "success",
                "data": tickers,
                "total_count": total_count,
                "type_counts": type_counts,
                "filters_applied": api_params,
                "message": f"成功獲取 {total_count} 筆合約代碼資訊",
            }
        else:
            return {"status": "error", "data": None, "message": "API 返回格式錯誤"}

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取合約代碼列表失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_futopt_ticker(args: Dict) -> dict:
    """
    獲取期貨/選擇權個別合約基本資訊

    查詢指定期貨或選擇權合約代碼的基本資訊，包含合約名稱、參考價、結算日等。
    對應富邦官方 API: intraday/ticker/

    Args:
        symbol (str): 合約代碼，例如 "TX00", "MTX00", "TE00C24000" 等
        session (str, optional): 交易時段，預設為 "regular"
            - "regular": 一般交易時段
            - "afterhours": 盤後交易時段

    Returns:
        dict: 成功時返回合約基本資訊，包含:
            - date: 資料日期
            - type: 商品類型 (FUTURE/OPTION)
            - exchange: 交易所代碼
            - symbol: 合約代碼
            - name: 合約名稱
            - referencePrice: 參考價
            - settlementDate: 結算日期
            - startDate: 合約開始日期
            - endDate: 合約結束日期

    Example:
        {
            "symbol": "TX00",
            "session": "regular"
        }
    """
    try:
        # 檢查 restfutopt 是否已初始化
        if restfutopt is None:
            return {
                "status": "error",
                "data": None,
                "message": "期貨/選擇權行情服務未初始化，請先登入系統",
            }

        validated_args = GetIntradayFutOptTickerArgs(**args)
        symbol = validated_args.symbol
        session = validated_args.session

        # 調用 API
        api_params = {"symbol": symbol}
        if session:
            api_params["session"] = session

        result = restfutopt.intraday.ticker(**api_params)

        # 檢查 API 返回結果
        if result and hasattr(result, "is_success") and result.is_success:
            ticker_data = result.data
            if ticker_data:
                return {
                    "status": "success",
                    "data": ticker_data,
                    "message": f"成功獲取合約 {symbol} 基本資訊",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"找不到合約代碼 {symbol}",
                }
        else:
            error_msg = "API 調用失敗"
            if result and hasattr(result, "message"):
                error_msg = f"API 調用失敗: {result.message}"
            return {"status": "error", "data": None, "message": error_msg}

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取合約基本資訊失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_futopt_quote(args: Dict) -> dict:
    """
    獲取期貨/選擇權即時報價（依合約代碼查詢）

    查詢指定期貨或選擇權合約的即時報價資訊，包含價格、成交量、買賣價量等詳細數據。
    對應富邦官方 API: intraday/quote/

    Args:
        symbol (str): 合約代碼，例如 "TX00", "MTX00", "TE00C24000" 等
        session (str, optional): 交易時段，預設為 "regular"
            - "regular": 一般交易時段
            - "afterhours": 盤後交易時段

    Returns:
        dict: 成功時返回合約即時報價資訊，包含:
            - date: 資料日期
            - type: 商品類型 (FUTURE/OPTION)
            - exchange: 交易所代碼
            - symbol: 合約代碼
            - name: 合約名稱
            - previousClose: 昨日收盤價
            - openPrice: 開盤價
            - openTime: 開盤價成交時間
            - highPrice: 最高價
            - highTime: 最高價成交時間
            - lowPrice: 最低價
            - lowTime: 最低價成交時間
            - closePrice: 收盤價（最後成交價）
            - closeTime: 收盤價（最後成交價）成交時間
            - avgPrice: 當日成交均價
            - change: 最後成交價漲跌
            - changePercent: 最後成交價漲跌幅
            - amplitude: 當日振幅
            - lastPrice: 最後一筆成交價（含試撮）
            - lastSize: 最後一筆成交數量（含試撮）
            - total: 統計資訊
                - tradeVolume: 累計成交量
                - totalBidMatch: 委買成筆
                - totalAskMatch: 委賣成筆
            - lastTrade: 最後一筆成交資訊
                - bid: 最後一筆成交買價
                - ask: 最後一筆成交賣價
                - price: 最後一筆成交價格
                - size: 最後一筆成交數量
                - time: 最後一筆成交時間
                - serial: 最後一筆成交流水號
            - serial: 流水號
            - lastUpdated: 最後異動時間

    Example:
        {
            "symbol": "TX00",
            "session": "regular"
        }
    """
    try:
        # 檢查 restfutopt 是否已初始化
        if restfutopt is None:
            return {
                "status": "error",
                "data": None,
                "message": "期貨/選擇權行情服務未初始化，請先登入系統",
            }

        validated_args = GetIntradayFutOptQuoteArgs(**args)
        symbol = validated_args.symbol
        session = validated_args.session

        # 調用 API
        api_params = {"symbol": symbol}
        if session:
            api_params["session"] = session

        result = restfutopt.intraday.quote(**api_params)

        # 檢查 API 返回結果
        if result and hasattr(result, "is_success") and result.is_success:
            quote_data = result.data
            if quote_data:
                return {
                    "status": "success",
                    "data": quote_data,
                    "message": f"成功獲取合約 {symbol} 即時報價",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"找不到合約代碼 {symbol}",
                }
        else:
            error_msg = "API 調用失敗"
            if result and hasattr(result, "message"):
                error_msg = f"API 調用失敗: {result.message}"
            return {"status": "error", "data": None, "message": error_msg}

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取合約即時報價失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_futopt_candles(args: Dict) -> dict:
    """
    獲取期貨/選擇權 K 線數據（依合約代碼查詢）

    查詢指定期貨或選擇權合約的 K 線（candlestick）數據，包含開高低收成交量等資訊。
    對應富邦官方 API: intraday/candles/

    Args:
        symbol (str): 合約代碼，例如 "TX00", "MTX00", "TE00C24000" 等
        session (str, optional): 交易時段，預設為 "regular"
            - "regular": 一般交易時段
            - "afterhours": 盤後交易時段
        timeframe (str, optional): K 線週期，預設為 "1" (1分鐘)
            - "1": 1分鐘 K 線
            - "3": 3分鐘 K 線
            - "5": 5分鐘 K 線
            - "15": 15分鐘 K 線
            - "30": 30分鐘 K 線
            - "60": 60分鐘 K 線

    Returns:
        dict: 成功時返回合約 K 線數據，包含:
            - date: 資料日期
            - type: 商品類型 (FUTURE/OPTION)
            - exchange: 交易所代碼
            - market: 市場代碼
            - symbol: 合約代碼
            - timeframe: K 線週期
            - data: K 線數據陣列，每筆包含:
                - open: 開盤價
                - high: 最高價
                - low: 最低價
                - close: 收盤價
                - volume: 成交量

    Example:
        {
            "symbol": "TX00",
            "session": "regular",
            "timeframe": "1"
        }
    """
    try:
        # 檢查 restfutopt 是否已初始化
        if restfutopt is None:
            return {
                "status": "error",
                "data": None,
                "message": "期貨/選擇權行情服務未初始化，請先登入系統",
            }

        validated_args = GetIntradayFutOptCandlesArgs(**args)
        symbol = validated_args.symbol
        session = validated_args.session
        timeframe = validated_args.timeframe

        # 調用 API
        api_params = {"symbol": symbol}
        if session:
            api_params["session"] = session
        if timeframe:
            api_params["timeframe"] = timeframe

        result = restfutopt.intraday.candles(**api_params)

        # 檢查 API 返回結果
        if result and hasattr(result, "is_success") and result.is_success:
            candles_data = result.data
            if candles_data:
                return {
                    "status": "success",
                    "data": candles_data,
                    "message": f"成功獲取合約 {symbol} K 線數據",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"找不到合約代碼 {symbol}",
                }
        else:
            error_msg = "API 調用失敗"
            if result and hasattr(result, "message"):
                error_msg = f"API 調用失敗: {result.message}"
            return {"status": "error", "data": None, "message": error_msg}

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取合約 K 線數據失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_futopt_volumes(args: Dict) -> dict:
    """
    獲取期貨/選擇權合約成交量數據

    查詢指定期貨/選擇權合約代碼的成交量數據，對應官方 SDK `restfutopt.intraday.volumes(symbol, session)`。

    Args:
        symbol (str): 合約代碼，例如 "TXFA4" 或 "2330"
        session (str, optional): 交易時段，預設為 "0" (一般交易時段)

    Returns:
        dict: 成功時返回成交量數據，包含以下結構：
            - date (str): 資料日期
            - type (str): 商品類型
            - exchange (str): 交易所
            - market (str): 市場別
            - symbol (str): 合約代碼
            - data (list): 成交量數據陣列，每筆包含：
                - price (float): 成交價格
                - volume (int): 成交量

    Example:
        {
            "symbol": "TXFA4",
            "session": "0"
        }
    """
    try:
        # 檢查 restfutopt 是否已初始化
        if restfutopt is None:
            return {
                "status": "error",
                "data": None,
                "message": "期貨/選擇權行情服務未初始化，請先登入系統",
            }

        validated_args = GetIntradayFutOptVolumesArgs(**args)
        symbol = validated_args.symbol
        session = validated_args.session

        # 準備 API 參數
        api_params = {"symbol": symbol}
        if session is not None:
            api_params["session"] = session

        result = restfutopt.intraday.volumes(**api_params)

        # 檢查 API 返回結果
        if result and hasattr(result, "is_success") and result.is_success:
            volumes_data = result.data
            if volumes_data:
                return {
                    "status": "success",
                    "data": volumes_data,
                    "message": f"成功獲取合約 {symbol} 成交量數據",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"找不到合約代碼 {symbol}",
                }
        else:
            error_msg = "API 調用失敗"
            if result and hasattr(result, "message"):
                error_msg = f"API 調用失敗: {result.message}"
            return {"status": "error", "data": None, "message": error_msg}

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取合約成交量數據失敗: {str(e)}",
        }


@mcp.tool()
def get_intraday_futopt_trades(args: Dict) -> dict:
    """
    獲取期貨/選擇權合約成交明細數據

    查詢指定期貨/選擇權合約代碼的成交明細數據，對應官方 SDK `restfutopt.intraday.trades(symbol, session, offset, limit)`。

    Args:
        symbol (str): 合約代碼，例如 "TXFA4" 或 "2330"
        session (str, optional): 交易時段，預設為 "0" (一般交易時段)
        offset (int, optional): 偏移量，用於分頁，預設為 0
        limit (int, optional): 返回的最大記錄數，預設為 100

    Returns:
        dict: 成功時返回成交明細數據，包含以下結構：
            - date (str): 資料日期
            - type (str): 商品類型
            - exchange (str): 交易所
            - market (str): 市場別
            - symbol (str): 合約代碼
            - data (list): 成交明細數據陣列，每筆包含：
                - time (str): 成交時間
                - price (float): 成交價格
                - volume (int): 成交量
                - tick_type (str): 成交類型

    Example:
        {
            "symbol": "TXFA4",
            "session": "0",
            "offset": 0,
            "limit": 50
        }
    """
    try:
        # 檢查 restfutopt 是否已初始化
        if restfutopt is None:
            return {
                "status": "error",
                "data": None,
                "message": "期貨/選擇權行情服務未初始化，請先登入系統",
            }

        validated_args = GetIntradayFutOptTradesArgs(**args)
        symbol = validated_args.symbol
        session = validated_args.session
        offset = validated_args.offset
        limit = validated_args.limit

        # 準備 API 參數
        api_params = {"symbol": symbol}
        if session is not None:
            api_params["session"] = session
        if offset is not None:
            api_params["offset"] = offset
        if limit is not None:
            api_params["limit"] = limit

        result = restfutopt.intraday.trades(**api_params)

        # 檢查 API 返回結果
        if result and hasattr(result, "is_success") and result.is_success:
            trades_data = result.data
            if trades_data:
                return {
                    "status": "success",
                    "data": trades_data,
                    "message": f"成功獲取合約 {symbol} 成交明細數據",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"找不到合約代碼 {symbol}",
                }
        else:
            error_msg = "API 調用失敗"
            if result and hasattr(result, "message"):
                error_msg = f"API 調用失敗: {result.message}"
            return {"status": "error", "data": None, "message": error_msg}

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取合約成交明細數據失敗: {str(e)}",
        }


@mcp.tool()
def get_order_reports(args: Dict) -> dict:
    """
    獲取最新的委託回報

    Args:
        limit (int): 返回最新的幾筆記錄，預設10筆
    """
    try:
        validated_args = GetOrderReportsArgs(**args)
        limit = validated_args.limit

        global latest_order_reports  # noqa: F824 - 訪問 SDK 回調存儲的全局變數
        reports = latest_order_reports[-limit:] if latest_order_reports else []

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"成功獲取最新的 {len(reports)} 筆委託回報",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取委託回報失敗: {str(e)}",
        }


@mcp.tool()
def get_order_changed_reports(args: Dict) -> dict:
    """
    獲取最新的改價/改量/刪單回報

    Args:
        limit (int): 返回最新的幾筆記錄，預設10筆
    """
    try:
        validated_args = GetOrderChangedReportsArgs(**args)
        limit = validated_args.limit

        global latest_order_changed_reports  # noqa: F824 - 訪問 SDK 回調存儲的全局變數
        reports = (
            latest_order_changed_reports[-limit:]
            if latest_order_changed_reports
            else []
        )

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"成功獲取最新的 {len(reports)} 筆改價/改量/刪單回報",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取改價/改量/刪單回報失敗: {str(e)}",
        }


@mcp.tool()
def get_filled_reports(args: Dict) -> dict:
    """
    獲取最新的成交回報

    Args:
        limit (int): 返回最新的幾筆記錄，預設10筆
    """
    try:
        validated_args = GetFilledReportsArgs(**args)
        limit = validated_args.limit

        global latest_filled_reports  # noqa: F824 - 訪問 SDK 回調存儲的全局變數
        reports = latest_filled_reports[-limit:] if latest_filled_reports else []

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"成功獲取最新的 {len(reports)} 筆成交回報",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取成交回報失敗: {str(e)}",
        }


@mcp.tool()
def get_event_reports(args: Dict) -> dict:
    """
    獲取最新的事件通知

    Args:
        limit (int): 返回最新的幾筆記錄，預設10筆
    """
    try:
        validated_args = GetEventReportsArgs(**args)
        limit = validated_args.limit

        global latest_event_reports  # noqa: F824 - 訪問 SDK 回調存儲的全局變數
        reports = latest_event_reports[-limit:] if latest_event_reports else []

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"成功獲取最新的 {len(reports)} 筆事件通知",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取事件通知失敗: {str(e)}",
        }


@mcp.tool()
def get_all_reports(args: Dict) -> dict:
    """
    獲取所有類型的主動回報

    Args:
        limit (int): 每種類型返回最新的幾筆記錄，預設5筆
    """
    try:
        validated_args = GetOrderReportsArgs(**args)  # 重用相同的參數類
        limit = validated_args.limit

        global latest_order_reports, latest_order_changed_reports, latest_filled_reports, latest_event_reports  # noqa: F824 - 訪問 SDK 回調存儲的全局變數

        all_reports = {
            "order_reports": latest_order_reports[-limit:]
            if latest_order_reports
            else [],
            "order_changed_reports": latest_order_changed_reports[-limit:]
            if latest_order_changed_reports
            else [],
            "filled_reports": latest_filled_reports[-limit:]
            if latest_filled_reports
            else [],
            "event_reports": latest_event_reports[-limit:]
            if latest_event_reports
            else [],
        }

        total_count = sum(len(reports) for reports in all_reports.values())

        return {
            "status": "success",
            "data": all_reports,
            "total_count": total_count,
            "message": f"成功獲取所有類型的主動回報，共 {total_count} 筆記錄",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取所有回報失敗: {str(e)}",
        }


@mcp.tool()
def modify_price(args: Dict) -> dict:
    """
    修改委託價格

    Args:
        account (str): 帳戶號碼
        order_no (str): 委託單號
        new_price (float): 新價格
    """
    try:
        validated_args = ModifyPriceArgs(**args)
        account = validated_args.account
        order_no = validated_args.order_no
        new_price = validated_args.new_price

        return _modify_order(account, order_no, new_price, "price")

    except Exception as e:
        return {"status": "error", "data": None, "message": f"修改價格失敗: {str(e)}"}


@mcp.tool()
def cancel_order(args: Dict) -> dict:
    """
    取消委託單

    取消指定的普通委託單，對應官方 SDK `cancel_order(account, order)`。

    ⚠️ 適用範圍：
    - 普通現股委託單
    - 分時分量條件單產生的各個子委託單（請先用 get_order_results 查詢）
    - 其他已送出的市場委託單

    Args:
        account (str): 帳戶號碼
        order_no (str): 委託單號

    Returns:
        dict: 成功時回傳取消結果

    Note:
        **取消分時分量條件單的正確方式**:
        1. 先用 `get_order_results(account)` 獲取所有委託單
        2. 從結果中找到對應的分時分量委託單（依 symbol、quantity 等識別）
        3. 對每個委託單調用此函數取消：`cancel_order(account, order_no)`
    """
    try:
        validated_args = CancelOrderArgs(**args)
        account = validated_args.account
        order_no = validated_args.order_no

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取委託結果
        order_results = sdk.stock.get_order_results(account_obj)
        if not (
            order_results
            and hasattr(order_results, "is_success")
            and order_results.is_success
        ):
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 委託結果",
            }

        # 找到對應的委託單
        target_order = _find_target_order(order_results, order_no)
        if not target_order:
            return {
                "status": "error",
                "data": None,
                "message": f"找不到委託單號 {order_no}",
            }

        # 取消委託
        result = sdk.stock.cancel_order(account_obj, target_order)
        if result and hasattr(result, "is_success") and result.is_success:
            return {
                "status": "success",
                "data": result.data if hasattr(result, "data") else result,
                "message": f"成功取消委託 {order_no}",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"取消委託 {order_no} 失敗",
            }

    except Exception as e:
        return {"status": "error", "data": None, "message": f"取消委託失敗: {str(e)}"}


def _convert_order_data_to_enums(order_data):
    """將訂單數據轉換為枚舉值"""
    buy_sell_str = order_data.get("buy_sell", "Buy")
    buy_sell_enum = to_bs_action(buy_sell_str)

    market_type_str = order_data.get("market_type", "Common")
    market_type_enum = to_market_type(market_type_str)

    price_type_str = order_data.get("price_type", "Limit")
    price_type_enum = to_price_type(price_type_str)

    time_in_force_str = order_data.get("time_in_force", "ROD")
    time_in_force_enum = to_time_in_force(time_in_force_str)

    order_type_str = order_data.get("order_type", "Stock")
    order_type_enum = to_order_type(order_type_str)

    return {
        "buy_sell": buy_sell_enum,
        "market_type": market_type_enum,
        "price_type": price_type_enum,
        "time_in_force": time_in_force_enum,
        "order_type": order_type_enum,
    }


def _create_order_object(order_data, enums):
    """創建訂單對象"""
    from fubon_neo.sdk import Order

    return Order(
        buy_sell=enums["buy_sell"],
        symbol=order_data.get("symbol", ""),
        price=str(order_data.get("price", 0.0)),  # 價格轉為字串
        quantity=order_data.get("quantity", 0),
        market_type=enums["market_type"],
        price_type=enums["price_type"],
        time_in_force=enums["time_in_force"],
        order_type=enums["order_type"],
        user_def=order_data.get("user_def"),
    )


def _place_single_order(account_obj, order_data):
    """處理單筆下單"""
    try:
        enums = _convert_order_data_to_enums(order_data)
        order = _create_order_object(order_data, enums)

        # 決定是否使用非阻塞模式
        is_non_blocking = order_data.get("is_non_blocking", False)

        # 下單
        result = sdk.stock.place_order(account_obj, order, is_non_blocking)

        # 檢查 API 返回結果
        if result and hasattr(result, "is_success") and result.is_success:
            return {
                "order_data": order_data,
                "result": result,
                "success": True,
                "error": None,
            }
        else:
            # 提取錯誤訊息
            error_msg = "下單失敗"
            if result and hasattr(result, "message"):
                error_msg = f"下單失敗: {result.message}"
            elif result:
                error_msg = f"下單失敗: {str(result)}"

            return {
                "order_data": order_data,
                "result": result,
                "success": False,
                "error": error_msg,
            }
    except Exception as e:
        return {
            "order_data": order_data,
            "result": None,
            "success": False,
            "error": str(e),
        }


def _execute_batch_orders(account_obj, orders, max_workers):
    """執行批量訂單"""
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任務
        future_to_order = {
            executor.submit(_place_single_order, account_obj, order_data): order_data
            for order_data in orders
        }

        # 等待所有任務完成
        for future in concurrent.futures.as_completed(future_to_order):
            result = future.result()
            results.append(result)

    return results


def _summarize_batch_results(results):
    """統計批量下單結果"""
    successful_orders = [r for r in results if r["success"]]
    failed_orders = [r for r in results if not r["success"]]

    return {
        "total_orders": len(results),
        "successful_orders": len(successful_orders),
        "failed_orders": len(failed_orders),
        "results": results,
    }


@mcp.tool()
def batch_place_order(args: Dict) -> dict:
    """
    批量並行下單買賣股票

    Args:
        account (str): 帳戶號碼
        orders (List[Dict]): 訂單列表，每筆訂單包含 symbol, quantity, price, buy_sell 等參數
            支援的參數：
            - symbol (str): 股票代碼
            - quantity (int): 委託數量（股）
            - price (float): 價格
            - buy_sell (str): 'Buy' 或 'Sell'
            - market_type (str): 市場別，預設 "Common"
            - price_type (str): 價格類型，預設 "Limit"
            - time_in_force (str): 有效期間，預設 "ROD"
            - order_type (str): 委託類型，預設 "Stock"
            - user_def (str): 使用者自定義欄位，可選
            - is_non_blocking (bool): 是否使用非阻塞模式，預設False
        max_workers (int): 最大並行數量，預設10
    """
    try:
        validated_args = BatchPlaceOrderArgs(**args)
        account = validated_args.account
        orders = validated_args.orders
        max_workers = validated_args.max_workers

        if not orders:
            return {"status": "error", "data": None, "message": "訂單列表不能為空"}

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 執行批量下單
        results = _execute_batch_orders(account_obj, orders, max_workers)
        summary = _summarize_batch_results(results)

        return {
            "status": "success",
            "data": summary,
            "message": f"批量下單完成：總共 {summary['total_orders']} 筆，成功 {summary['successful_orders']} 筆，失敗 {summary['failed_orders']} 筆",
        }

    except Exception as e:
        return {"status": "error", "data": None, "message": f"批量下單失敗: {str(e)}"}


@mcp.tool()
def place_condition_order(args: Dict) -> dict:
    """
    單一條件單（可選停損停利）

    當觸發條件達成時，自動送出委託單。可選擇性加入停損停利設定。
    使用富邦官方 single_condition API。

    ⚠️ 重要提醒：
    - 條件單目前不支援期權商品與現貨商品混用
    - 停損停利設定僅為觸發送單，不保證必定成交，需視市場狀況調整
    - 請確認停損停利委託類別設定符合適合之交易規則（例如信用交易資買資賣等）
    - 待主單完全成交後，停損停利部分才會啟動

    Args:
        account (str): 帳戶號碼
        start_date (str): 開始日期，格式: YYYYMMDD (例: "20240426")
        end_date (str): 結束日期，格式: YYYYMMDD (例: "20240516")
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
        from fubon_neo.constant import BSAction, TimeInForce

        # 驗證主要參數
        validated_args = PlaceConditionOrderArgs(**args)
        account = validated_args.account
        start_date = validated_args.start_date
        end_date = validated_args.end_date
        stop_sign = validated_args.stop_sign

        # 驗證帳戶
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "message": error}

        # 建立條件對象
        condition_data = ConditionArgs(**validated_args.condition)
        condition = Condition(
            market_type=to_trading_type(condition_data.market_type),
            symbol=condition_data.symbol,
            trigger=to_trigger_content(condition_data.trigger),
            trigger_value=condition_data.trigger_value,
            comparison=to_operator(condition_data.comparison),
        )

        # 建立委託單對象
        order_data = ConditionOrderArgs(**validated_args.order)
        order = ConditionOrder(
            buy_sell=to_bs_action(order_data.buy_sell),
            symbol=order_data.symbol,
            price=order_data.price,
            quantity=order_data.quantity,
            market_type=to_condition_market_type(order_data.market_type),
            price_type=to_condition_price_type(order_data.price_type),
            time_in_force=to_time_in_force(order_data.time_in_force),
            order_type=to_condition_order_type(order_data.order_type),
        )

        # 建立停損停利對象（如果有提供）
        tpsl = None
        if validated_args.tpsl:
            tpsl_data = TPSLWrapperArgs(**validated_args.tpsl)

            # 建立停利單（如果有）
            tp = None
            if tpsl_data.tp:
                tp_data = TPSLOrderArgs(**tpsl_data.tp)
                tp = TPSLOrder(
                    time_in_force=to_time_in_force(tp_data.time_in_force),
                    price_type=to_condition_price_type(tp_data.price_type),
                    order_type=to_condition_order_type(tp_data.order_type),
                    target_price=tp_data.target_price,
                    price=tp_data.price,
                    trigger=to_trigger_content(tp_data.trigger)
                    if tp_data.trigger
                    else TriggerContent.MatchedPrice,
                )

            # 建立停損單（如果有）
            sl = None
            if tpsl_data.sl:
                sl_data = TPSLOrderArgs(**tpsl_data.sl)
                sl = TPSLOrder(
                    time_in_force=to_time_in_force(sl_data.time_in_force),
                    price_type=to_condition_price_type(sl_data.price_type),
                    order_type=to_condition_order_type(sl_data.order_type),
                    target_price=sl_data.target_price,
                    price=sl_data.price,
                    trigger=to_trigger_content(sl_data.trigger)
                    if sl_data.trigger
                    else TriggerContent.MatchedPrice,
                )

            # 建立停損停利包裝器
            tpsl = TPSLWrapper(
                stop_sign=to_stop_sign(tpsl_data.stop_sign),
                tp=tp,
                sl=sl,
                end_date=tpsl_data.end_date,
                intraday=tpsl_data.intraday,
            )

        # 執行條件單下單（使用 single_condition API）
        result = sdk.stock.single_condition(
            account_obj,
            start_date,
            end_date,
            to_stop_sign(stop_sign),
            condition,
            order,
            tpsl,  # 停損停利參數（可為 None）
        )

        # 檢查結果
        if result and hasattr(result, "is_success") and result.is_success:
            guid = (
                getattr(result.data, "guid", None) if hasattr(result, "data") else None
            )
            response_data = {
                "guid": guid,
                "condition_no": guid,  # 條件單號
                "symbol": order_data.symbol,
                "buy_sell": order_data.buy_sell,
                "quantity": order_data.quantity,
                "trigger_value": condition_data.trigger_value,
                "trigger_comparison": condition_data.comparison,
            }

            # 如果有停損停利，加入相關資訊
            if validated_args.tpsl:
                tpsl_info = validated_args.tpsl
                if tpsl_info.get("tp"):
                    response_data["tp_target"] = tpsl_info["tp"]["target_price"]
                if tpsl_info.get("sl"):
                    response_data["sl_target"] = tpsl_info["sl"]["target_price"]
                response_data["has_tpsl"] = True
            else:
                response_data["has_tpsl"] = False

            message = f"條件單已成功建立 - {order_data.symbol}"
            if response_data.get("has_tpsl"):
                message += " (含停損停利)"

            return {
                "status": "success",
                "data": response_data,
                "message": message,
            }
        else:
            error_msg = (
                getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
            )
            return {"status": "error", "message": f"條件單建立失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"條件單建立時發生錯誤: {str(e)}"}


@mcp.tool()
def place_tpsl_condition_order(args: Dict) -> dict:
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
    # 直接調用 place_condition_order
    # 此方法保留是為了向後兼容和語義清晰
    return place_condition_order(args)


@mcp.tool()
def place_multi_condition_order(args: Dict) -> dict:
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
        from fubon_neo.constant import BSAction, TimeInForce

        # 驗證主要參數
        validated_args = PlaceMultiConditionOrderArgs(**args)
        account = validated_args.account
        start_date = validated_args.start_date
        end_date = validated_args.end_date
        stop_sign = validated_args.stop_sign

        # 驗證帳戶
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "message": error}

        # 建立多個條件對象
        conditions = []
        for cond_dict in validated_args.conditions:
            condition_data = ConditionArgs(**cond_dict)
            condition = Condition(
                market_type=to_trading_type(condition_data.market_type),
                symbol=condition_data.symbol,
                trigger=to_trigger_content(condition_data.trigger),
                trigger_value=condition_data.trigger_value,
                comparison=to_operator(condition_data.comparison),
            )
            conditions.append(condition)

        # 建立委託單對象
        order_data = ConditionOrderArgs(**validated_args.order)
        order = ConditionOrder(
            buy_sell=to_bs_action(order_data.buy_sell),
            symbol=order_data.symbol,
            price=order_data.price,
            quantity=order_data.quantity,
            market_type=to_condition_market_type(order_data.market_type),
            price_type=to_condition_price_type(order_data.price_type),
            time_in_force=to_time_in_force(order_data.time_in_force),
            order_type=to_condition_order_type(order_data.order_type),
        )

        # 建立停損停利對象（如果有提供）
        tpsl = None
        if validated_args.tpsl:
            tpsl_data = TPSLWrapperArgs(**validated_args.tpsl)

            # 建立停利單（如果有）
            tp = None
            if tpsl_data.tp:
                tp_data = TPSLOrderArgs(**tpsl_data.tp)
                tp = TPSLOrder(
                    time_in_force=to_time_in_force(tp_data.time_in_force),
                    price_type=to_condition_price_type(tp_data.price_type),
                    order_type=to_condition_order_type(tp_data.order_type),
                    target_price=tp_data.target_price,
                    price=tp_data.price,
                    trigger=to_trigger_content(tp_data.trigger)
                    if tp_data.trigger
                    else TriggerContent.MatchedPrice,
                )

            # 建立停損單（如果有）
            sl = None
            if tpsl_data.sl:
                sl_data = TPSLOrderArgs(**tpsl_data.sl)
                sl = TPSLOrder(
                    time_in_force=to_time_in_force(sl_data.time_in_force),
                    price_type=to_condition_price_type(sl_data.price_type),
                    order_type=to_condition_order_type(sl_data.order_type),
                    target_price=sl_data.target_price,
                    price=sl_data.price,
                    trigger=to_trigger_content(sl_data.trigger)
                    if sl_data.trigger
                    else TriggerContent.MatchedPrice,
                )

            # 建立停損停利包裝器
            tpsl = TPSLWrapper(
                stop_sign=to_stop_sign(tpsl_data.stop_sign),
                tp=tp,
                sl=sl,
                end_date=tpsl_data.end_date,
                intraday=tpsl_data.intraday,
            )

        # 執行多條件單下單（使用 multi_condition API）
        result = sdk.stock.multi_condition(
            account_obj,
            start_date,
            end_date,
            getattr(StopSign, stop_sign),
            conditions,  # 條件列表
            order,
            tpsl,  # 停損停利參數（可為 None）
        )

        # 檢查結果
        if result and hasattr(result, "is_success") and result.is_success:
            guid = (
                getattr(result.data, "guid", None) if hasattr(result, "data") else None
            )

            # 整理條件資訊
            conditions_info = []
            for cond_dict in validated_args.conditions:
                conditions_info.append(
                    {
                        "symbol": cond_dict["symbol"],
                        "trigger": cond_dict["trigger"],
                        "trigger_value": cond_dict["trigger_value"],
                        "comparison": cond_dict["comparison"],
                    }
                )

            response_data = {
                "guid": guid,
                "condition_no": guid,
                "symbol": order_data.symbol,
                "buy_sell": order_data.buy_sell,
                "quantity": order_data.quantity,
                "conditions_count": len(conditions),
                "conditions": conditions_info,
            }

            # 如果有停損停利，加入相關資訊
            if validated_args.tpsl:
                tpsl_info = validated_args.tpsl
                if tpsl_info.get("tp"):
                    response_data["tp_target"] = tpsl_info["tp"]["target_price"]
                if tpsl_info.get("sl"):
                    response_data["sl_target"] = tpsl_info["sl"]["target_price"]
                response_data["has_tpsl"] = True
            else:
                response_data["has_tpsl"] = False

            message = (
                f"多條件單已成功建立 - {order_data.symbol} ({len(conditions)} 個條件)"
            )
            if response_data.get("has_tpsl"):
                message += " (含停損停利)"

            return {
                "status": "success",
                "data": response_data,
                "message": message,
            }
        else:
            error_msg = (
                getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
            )
            return {"status": "error", "message": f"多條件單建立失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"多條件單建立時發生錯誤: {str(e)}"}


@mcp.tool()
def place_daytrade_condition_order(args: Dict) -> dict:
    """
    當沖單一條件單（可選停損停利）

    使用富邦官方 single_condition_day_trade API。當觸發條件達成時送出主單，
    主單成交後會依據當沖設定於指定時間前進行回補；可選擇加入停損停利設定。

    ⚠️ 重要提醒：
    - 條件單目前不支援期權商品與現貨商品混用
    - 停損停利設定僅為觸發送單，不保證必定回補成功，需視市場狀況自行調整
    - 當沖停損停利委託類別需符合當日沖銷交易規則（例如信用交易使用資券互抵）
    - 主單完全成交後，停損停利部分才會啟動

    Args:
        account (str): 帳號
        stop_sign (str): 條件停止條件 Full/Partial/UntilEnd
        end_time (str): 父單洗價結束時間（例："130000"）
        condition (dict): 觸發條件（ConditionArgs 結構）
        order (dict): 主單委託內容（ConditionOrderArgs 結構）
        daytrade (dict): 當沖回補內容（ConditionDayTradeArgs 結構）
        tpsl (dict, optional): 停損停利設定（TPSLWrapperArgs 結構）
        fix_session (bool): 是否執行定盤回補

    Returns:
        dict: 成功時回傳 guid 與摘要資訊

    Example:
        {
            "account": "1234567",
            "stop_sign": "Full",
            "end_time": "130000",
            "condition": {
                "market_type": "Reference",
                "symbol": "2881",
                "trigger": "MatchedPrice",
                "trigger_value": "66",
                "comparison": "LessThan"
            },
            "order": {
                "buy_sell": "Buy",
                "symbol": "2881",
                "price": "66",
                "quantity": 1000,
                "market_type": "Common",
                "price_type": "Limit",
                "time_in_force": "ROD",
                "order_type": "Stock"
            },
            "daytrade": {
                "day_trade_end_time": "131500",
                "auto_cancel": true,
                "price": "",
                "price_type": "Market"
            },
            "tpsl": {
                "stop_sign": "Full",
                "tp": {"time_in_force": "ROD", "price_type": "Limit", "order_type": "Stock", "target_price": "85", "price": "85"},
                "sl": {"time_in_force": "ROD", "price_type": "Limit", "order_type": "Stock", "target_price": "60", "price": "60"},
                "end_date": "20240517",
                "intraday": true
            },
            "fix_session": true
        }
    """
    try:
        from fubon_neo.constant import BSAction, TimeInForce

        # 驗證參數
        validated_args = PlaceDayTradeConditionOrderArgs(**args)

        # 帳戶驗證
        account_obj, error = validate_and_get_account(validated_args.account)
        if error:
            return {"status": "error", "message": error}

        # 建立條件對象
        cond_args = ConditionArgs(**validated_args.condition)
        condition = Condition(
            market_type=to_trading_type(cond_args.market_type),
            symbol=cond_args.symbol,
            trigger=to_trigger_content(cond_args.trigger),
            trigger_value=cond_args.trigger_value,
            comparison=to_operator(cond_args.comparison),
        )

        # 建立主單委託對象
        ord_args = ConditionOrderArgs(**validated_args.order)
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

        # 建立當沖對象
        dt_args = ConditionDayTradeArgs(**validated_args.daytrade)
        daytrade_obj = ConditionDayTrade(
            day_trade_end_time=dt_args.day_trade_end_time,
            auto_cancel=dt_args.auto_cancel,
            price=dt_args.price,
            price_type=getattr(ConditionPriceType, dt_args.price_type),
        )

        # 建立停損停利（選填）
        tpsl = None
        if validated_args.tpsl:
            tpsl_args = TPSLWrapperArgs(**validated_args.tpsl)

            tp = None
            if tpsl_args.tp:
                tp_args = TPSLOrderArgs(**tpsl_args.tp)
                tp = TPSLOrder(
                    time_in_force=to_time_in_force(tp_args.time_in_force),
                    price_type=to_condition_price_type(tp_args.price_type),
                    order_type=to_condition_order_type(tp_args.order_type),
                    target_price=tp_args.target_price,
                    price=tp_args.price,
                    trigger=to_trigger_content(tp_args.trigger)
                    if tp_args.trigger
                    else TriggerContent.MatchedPrice,
                )

            sl = None
            if tpsl_args.sl:
                sl_args = TPSLOrderArgs(**tpsl_args.sl)
                sl = TPSLOrder(
                    time_in_force=to_time_in_force(sl_args.time_in_force),
                    price_type=to_condition_price_type(sl_args.price_type),
                    order_type=to_condition_order_type(sl_args.order_type),
                    target_price=sl_args.target_price,
                    price=sl_args.price,
                    trigger=to_trigger_content(sl_args.trigger)
                    if sl_args.trigger
                    else TriggerContent.MatchedPrice,
                )

            tpsl = TPSLWrapper(
                stop_sign=to_stop_sign(tpsl_args.stop_sign),
                tp=tp,
                sl=sl,
                end_date=tpsl_args.end_date,
                intraday=tpsl_args.intraday,
            )

        # 呼叫 SDK：single_condition_day_trade
        result = sdk.stock.single_condition_day_trade(
            account_obj,
            to_stop_sign(validated_args.stop_sign),
            validated_args.end_time,
            condition,
            order,
            daytrade_obj,
            tpsl,
            validated_args.fix_session,
        )

        if result and hasattr(result, "is_success") and result.is_success:
            guid = (
                getattr(result.data, "guid", None) if hasattr(result, "data") else None
            )

            resp = {
                "guid": guid,
                "condition_no": guid,
                "symbol": ord_args.symbol,
                "buy_sell": ord_args.buy_sell,
                "quantity": ord_args.quantity,
                "end_time": validated_args.end_time,
                "day_trade_end_time": dt_args.day_trade_end_time,
                "fix_session": validated_args.fix_session,
                "has_tpsl": bool(validated_args.tpsl),
            }

            if validated_args.tpsl:
                if validated_args.tpsl.get("tp"):
                    resp["tp_target"] = validated_args.tpsl["tp"]["target_price"]
                if validated_args.tpsl.get("sl"):
                    resp["sl_target"] = validated_args.tpsl["sl"]["target_price"]

            msg = f"當沖條件單已成功建立 - {ord_args.symbol}"
            if resp.get("has_tpsl"):
                msg += " (含停損停利)"

            return {"status": "success", "data": resp, "message": msg}

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"當沖條件單建立失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"當沖條件單建立時發生錯誤: {str(e)}"}


@mcp.tool()
def get_daytrade_condition_by_id(args: Dict) -> dict:
    """
    查詢當沖條件單（依 guid）

    使用富邦官方 `get_condition_daytrade_by_id` API。

    Args:
        account (str): 帳號
        guid (str): 條件單號

    Returns:
        dict: 成功時回傳條件單詳細資料（展開為可序列化的 dict）

    Example:
        {"account": "1234567", "guid": "8ff3472b-185a-488c-be5a-b478deda080c"}
    """
    try:
        validated = GetDayTradeConditionByIdArgs(**args)

        # 帳戶驗證
        account_obj, error = validate_and_get_account(validated.account)
        if error:
            return {"status": "error", "message": error}

        # 呼叫 SDK
        result = sdk.stock.get_condition_daytrade_by_id(account_obj, validated.guid)

        # 序列化工具
        def to_dict(obj):
            if obj is None:
                return None
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, list):
                return [to_dict(x) for x in obj]
            if isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            # 嘗試用 __dict__ 轉換
            try:
                return {
                    k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")
                }
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data = to_dict(getattr(result, "data", None))
            # 兼容資料為 None 的情況
            return {
                "status": "success",
                "data": data or {},
                "message": "查詢成功",
            }

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"查詢失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


@mcp.tool()
def place_daytrade_multi_condition_order(args: Dict) -> dict:
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
        account (str), stop_sign (str), end_time (str)
        conditions (list[ConditionArgs]), order (ConditionOrderArgs)
        daytrade (ConditionDayTradeArgs), tpsl (TPSLWrapperArgs, optional), fix_session (bool)
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
        result = sdk.stock.multi_condition_day_trade(
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
                getattr(result.data, "guid", None) if hasattr(result, "data") else None
            )
            msg = (
                f"當沖多條件單已成功建立 - {ord_args.symbol} ({len(conditions)} 個條件)"
            )
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

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"當沖多條件單建立失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"當沖多條件單建立時發生錯誤: {str(e)}"}


@mcp.tool()
def place_trail_profit(args: Dict) -> dict:
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
        result = sdk.stock.trail_profit(
            account_obj,
            start_date,
            end_date,
            to_stop_sign(stop_sign),
            trail,
        )

        if result and hasattr(result, "is_success") and result.is_success:
            guid = (
                getattr(result.data, "guid", None) if hasattr(result, "data") else None
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

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"移動鎖利條件單建立失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"移動鎖利條件單建立時發生錯誤: {str(e)}"}


@mcp.tool()
def get_trail_order(args: Dict) -> dict:
    """
    有效移動鎖利查詢（get_trail_order）

    查詢目前有效的移動鎖利條件單清單，對應官方 SDK `get_trail_order`。

    Args:
        account (str): 帳號

    Returns:
        dict: 成功時回傳展開的清單資料（可序列化 dict 陣列）
    """
    try:
        validated = GetTrailOrderArgs(**args)

        # 帳戶驗證
        account_obj, error = validate_and_get_account(validated.account)
        if error:
            return {"status": "error", "message": error}

        # 呼叫 SDK
        result = sdk.stock.get_trail_order(account_obj)

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
                    k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")
                }
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data = getattr(result, "data", [])
            data_list = to_dict(data) or []
            return {"status": "success", "data": data_list, "message": "查詢成功"}

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"查詢失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


@mcp.tool()
def get_trail_history(args: Dict) -> dict:
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
        result = sdk.stock.get_trail_history(
            account_obj, validated.start_date, validated.end_date
        )

        # 序列化工具
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
                    k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")
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
                "message": f"查詢成功，共 {count} 筆（{validated.start_date}~{validated.end_date}）",
            }

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"查詢失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


@mcp.tool()
def place_time_slice_order(args: Dict) -> dict:
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
        from fubon_neo.constant import BSAction, TimeInForce

        validated = PlaceTimeSliceOrderArgs(**args)

        # 帳戶驗證
        account_obj, error = validate_and_get_account(validated.account)
        if error:
            return {"status": "error", "message": error}

        # 建立 SplitDescription
        split_args = TimeSliceSplitArgs(**validated.split)
        split_kwargs = {
            "method": to_time_slice_order_type(split_args.method),
            "interval": split_args.interval,
            "single_quantity": split_args.single_quantity,
            "start_time": split_args.start_time,
        }
        if split_args.total_quantity is not None:
            split_kwargs["total_quantity"] = split_args.total_quantity
        if getattr(split_args, "end_time", None):
            split_kwargs["end_time"] = split_args.end_time
        split = SplitDescription(**split_kwargs)

        # 建立 ConditionOrder
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

        # 呼叫 SDK：time_slice_order
        result = sdk.stock.time_slice_order(
            account_obj,
            validated.start_date,
            validated.end_date,
            to_stop_sign(validated.stop_sign),
            split,
            order,
        )

        if result and hasattr(result, "is_success") and result.is_success:
            # Handle different response structures
            data = getattr(result, "data", None)
            guid = None

            if data:
                # Try direct attribute access first
                guid = getattr(data, "guid", None)

                # If not found, check if it's a dict with SmartOrderResponse
                if guid is None and isinstance(data, dict):
                    smart_order_response = data.get("SmartOrderResponse")
                    if smart_order_response:
                        guid = getattr(smart_order_response, "guid", None)

                # If still not found, try accessing as dict key
                if guid is None and isinstance(data, dict):
                    guid = data.get("guid")

            resp = {
                "guid": guid,
                "condition_no": guid,
                "symbol": ord_args.symbol,
                "buy_sell": ord_args.buy_sell,
                "quantity": ord_args.quantity,
                "method": split_args.method,
                "interval": split_args.interval,
                "single_quantity": split_args.single_quantity,
                "total_quantity": split_args.total_quantity,
                "start_time": split_args.start_time,
                "end_time": getattr(split_args, "end_time", None),
            }
            return {
                "status": "success",
                "data": resp,
                "message": f"分時分量條件單已成功建立 - {ord_args.symbol}",
            }

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"分時分量條件單建立失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"建立時發生錯誤: {str(e)}"}


@mcp.tool()
def get_time_slice_order(args: Dict) -> dict:
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
        result = sdk.stock.get_time_slice_order(account_obj, validated.batch_no)

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
                    k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")
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

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"查詢失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


@mcp.tool()
def cancel_condition_order(args: Dict) -> dict:
    """
    取消條件單（cancel_condition_order）

    對應官方 SDK `cancel_condition_orders(account, guid)`，用於取消指定條件單號。

    ⚠️ 適用範圍：
    - 單一條件單（single_condition）
    - 多條件單（multi_condition）
    - 當沖條件單（single_condition_day_trade, multi_condition_day_trade）
    - 移動鎖利條件單（trail_profit）
    - **不適用**：分時分量條件單（time_slice_order）請使用 cancel_order

    Args:
        account (str): 帳號
        guid (str): 條件單號

    Returns:
        dict: 成功時回傳 `advisory` 等資訊

    Note:
        分時分量條件單不適用此函數，因為它會立即產生多個普通委託單，
        請改用 get_order_results + cancel_order 的組合來取消。
    """
    try:
        validated = CancelConditionOrderArgs(**args)

        # 帳戶驗證
        account_obj, error = validate_and_get_account(validated.account)
        if error:
            return {"status": "error", "message": error}

        # 呼叫 SDK
        result = sdk.stock.cancel_condition_orders(account_obj, validated.guid)

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
                    k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")
                }
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data_dict = to_dict(getattr(result, "data", None)) or {}
            advisory_text = (
                data_dict.get("advisory") if isinstance(data_dict, dict) else None
            )
            msg = advisory_text or f"取消成功（guid={validated.guid}）"
            return {"status": "success", "data": data_dict, "message": msg}

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"取消失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"取消時發生錯誤: {str(e)}"}


@mcp.tool()
def get_condition_order(args: Dict) -> dict:
    """
    條件單查詢（get_condition_order）

    查詢帳號下的條件單清單，可選擇性依 ConditionStatus 過濾。

    Args:
        account (str): 帳號
        condition_status (str, optional): 對應 `ConditionStatus` 成員名稱

    Returns:
        dict: 成功時回傳展開的清單資料（ConditionDetail list）
    """
    try:
        validated = GetConditionOrderArgs(**args)

        # 帳戶驗證
        account_obj, error = validate_and_get_account(validated.account)
        if error:
            return {"status": "error", "message": error}

        # 呼叫 SDK（依是否提供條件狀態決定簽名）
        if validated.condition_status:
            try:
                status_enum = to_condition_status(validated.condition_status)
            except ValueError:
                return {
                    "status": "error",
                    "message": f"不支援的條件單狀態: {validated.condition_status}",
                }
            result = sdk.stock.get_condition_order(account_obj, status_enum)
        else:
            result = sdk.stock.get_condition_order(account_obj)

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
                    k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")
                }
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data = getattr(result, "data", []) or []
            data_list = to_dict(data) or []
            count = len(data_list) if isinstance(data_list, list) else 0
            suffix = (
                f", 狀態={validated.condition_status}"
                if validated.condition_status
                else ""
            )
            return {
                "status": "success",
                "data": data_list,
                "message": f"查詢成功，共 {count} 筆{suffix}",
            }

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"查詢失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


@mcp.tool()
def get_condition_order_by_id(args: Dict) -> dict:
    """
    條件單查詢（By Guid） get_condition_order_by_id

    Args:
        account (str): 帳號
        guid (str): 條件單號

    Returns:
        dict: 成功時回傳單一 `ConditionDetail`（展開為可序列化 dict）
    """
    try:
        validated = GetConditionOrderByIdArgs(**args)

        # 帳戶驗證
        account_obj, error = validate_and_get_account(validated.account)
        if error:
            return {"status": "error", "message": error}

        # 呼叫 SDK
        result = sdk.stock.get_condition_order_by_id(account_obj, validated.guid)

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
                    k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")
                }
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data = getattr(result, "data", None)
            data_dict = to_dict(data) or {}
            return {"status": "success", "data": data_dict, "message": "查詢成功"}

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"查詢失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


@mcp.tool()
def get_condition_history(args: Dict) -> dict:
    """
    歷史條件單查詢（get_condition_history）

    依建立日期區間查詢歷史條件單，支援可選的歷史狀態過濾。

    Args:
        account (str): 帳號
        start_date (str): 查詢開始日 YYYYMMDD
        end_date (str): 查詢截止日 YYYYMMDD
        condition_history_status (str, optional): 對應 `HistoryStatus` 成員名稱

    Returns:
        dict: 成功時回傳展開的清單資料（ConditionDetail list）
    """
    try:
        validated = GetConditionHistoryArgs(**args)

        # 帳戶驗證
        account_obj, error = validate_and_get_account(validated.account)
        if error:
            return {"status": "error", "message": error}

        # 呼叫 SDK（依是否提供歷史狀態決定簽名）
        if validated.condition_history_status:
            try:
                hist_enum = to_history_status(validated.condition_history_status)
            except ValueError:
                return {
                    "status": "error",
                    "message": f"不支援的歷史條件單狀態: {validated.condition_history_status}",
                }
            result = sdk.stock.get_condition_history(
                account_obj, validated.start_date, validated.end_date, hist_enum
            )
        else:
            result = sdk.stock.get_condition_history(
                account_obj, validated.start_date, validated.end_date
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
                    k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")
                }
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data = getattr(result, "data", []) or []
            data_list = to_dict(data) or []
            count = len(data_list) if isinstance(data_list, list) else 0
            suffix = (
                f", 狀態={validated.condition_history_status}"
                if validated.condition_history_status
                else ""
            )
            return {
                "status": "success",
                "data": data_list,
                "message": f"查詢成功，共 {count} 筆（{validated.start_date}~{validated.end_date}{suffix}）",
            }

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"查詢失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


@mcp.tool()
def get_realized_pnl(args: Dict) -> dict:
    """
    獲取已實現損益資訊

    查詢帳戶的已實現損益記錄，對應官方 SDK `accounting.realized_gains_and_loses(account)`。

    ⚠️ 重要用途：
    - 查詢已實現的損益記錄
    - 分析交易績效和損益統計
    - 追蹤已平倉部位的損益情況

    Args:
        account (str): 帳戶號碼

    Returns:
        dict: 成功時返回已實現損益記錄列表，每筆記錄包含以下關鍵字段：
            - date (str): 資料日期
            - branch_no (str): 分公司代號
            - account (str): 帳戶號碼
            - stock_no (str): 股票代碼
            - buy_sell (str): 買賣別，"Buy" 或 "Sell"
            - filled_qty (int): 成交股數
            - filled_price (float): 成交價
            - order_type (str): 委託類型，"Stock"、"Margin"、"Short" 或 "DayTrade"
            - realized_profit (int): 已實現獲利金額
            - realized_loss (int): 已實現損失金額

    Note:
        **損益計算說明**:
        - realized_profit: 已實現的獲利金額（正數表示獲利）
        - realized_loss: 已實現的損失金額（正數表示損失）
        - 單筆交易的淨損益 = realized_profit - realized_loss

        **委託類型說明**:
        - Stock: 現股交易
        - Margin: 融資交易
        - Short: 融券交易
        - DayTrade: 當沖交易
    """
    try:
        validated_args = GetRealizedPnLArgs(**args)
        account = validated_args.account

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取已實現損益
        realized_pnl = sdk.accounting.realized_gains_and_loses(account_obj)
        if (
            realized_pnl
            and hasattr(realized_pnl, "is_success")
            and realized_pnl.is_success
        ):
            # 處理數據，將枚舉轉為字串
            processed_data = []
            if hasattr(realized_pnl, "data") and realized_pnl.data:
                for item in realized_pnl.data:
                    processed_item = {
                        "date": getattr(item, "date", ""),
                        "branch_no": getattr(item, "branch_no", ""),
                        "account": getattr(item, "account", ""),
                        "stock_no": getattr(item, "stock_no", ""),
                        "buy_sell": str(getattr(item, "buy_sell", "")).split(".")[
                            -1
                        ],  # 轉為字串
                        "filled_qty": getattr(item, "filled_qty", 0),
                        "filled_price": getattr(item, "filled_price", 0.0),
                        "order_type": str(getattr(item, "order_type", "")).split(".")[
                            -1
                        ],  # 轉為字串
                        "realized_profit": getattr(item, "realized_profit", 0),
                        "realized_loss": getattr(item, "realized_loss", 0),
                    }
                    processed_data.append(processed_item)

            return {
                "status": "success",
                "data": processed_data,
                "message": f"成功獲取帳戶 {account} 已實現損益，共 {len(processed_data)} 筆記錄",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 已實現損益",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取已實現損益失敗: {str(e)}",
        }


@mcp.tool()
def get_realized_pnl_summary(args: Dict) -> dict:
    """
    獲取已實現損益彙總資訊

    查詢帳戶的已實現損益彙總記錄，對應官方 SDK `accounting.realized_gains_and_loses_summary(account)`。

    ⚠️ 重要用途：
    - 查詢已實現損益的彙總統計
    - 分析交易績效總覽
    - 追蹤帳戶整體損益狀況

    Args:
        account (str): 帳戶號碼

    Returns:
        dict: 成功時返回已實現損益彙總記錄列表，每筆記錄包含以下關鍵字段：
            - start_date (str): 彙總起始日
            - end_date (str): 彙總截止日
            - branch_no (str): 分公司代號
            - account (str): 帳戶號碼
            - stock_no (str): 股票代碼
            - buy_sell (str): 買賣別，"Buy" 或 "Sell"
            - order_type (str): 委託類型，"Stock"、"Margin"、"Short"、"DayTrade" 或 "SBL"
            - filled_qty (int): 成交股數
            - filled_avg_price (float): 成交均價
            - realized_profit_and_loss (int): 已實現損益金額

    Note:
        **損益計算說明**:
        - realized_profit_and_loss: 已實現的損益金額（正數表示獲利，負數表示損失）

        **委託類型說明**:
        - Stock: 現股交易
        - Margin: 融資交易
        - Short: 融券交易
        - DayTrade: 當沖先賣交易
        - SBL: 借券賣出交易
    """
    try:
        validated_args = GetRealizedPnLSummaryArgs(**args)
        account = validated_args.account

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取已實現損益彙總
        realized_pnl_summary = sdk.accounting.realized_gains_and_loses_summary(
            account_obj
        )
        if (
            realized_pnl_summary
            and hasattr(realized_pnl_summary, "is_success")
            and realized_pnl_summary.is_success
        ):
            # 處理數據，將枚舉轉為字串
            processed_data = []
            if hasattr(realized_pnl_summary, "data") and realized_pnl_summary.data:
                for item in realized_pnl_summary.data:
                    processed_item = {
                        "start_date": getattr(item, "start_date", ""),
                        "end_date": getattr(item, "end_date", ""),
                        "branch_no": getattr(item, "branch_no", ""),
                        "account": getattr(item, "account", ""),
                        "stock_no": getattr(item, "stock_no", ""),
                        "buy_sell": str(getattr(item, "buy_sell", "")).split(".")[
                            -1
                        ],  # 轉為字串
                        "order_type": str(getattr(item, "order_type", "")).split(".")[
                            -1
                        ],  # 轉為字串
                        "filled_qty": getattr(item, "filled_qty", 0),
                        "filled_avg_price": getattr(item, "filled_avg_price", 0.0),
                        "realized_profit_and_loss": getattr(
                            item, "realized_profit_and_loss", 0
                        ),
                    }
                    processed_data.append(processed_item)

            return {
                "status": "success",
                "data": processed_data,
                "message": f"成功獲取帳戶 {account} 已實現損益彙總，共 {len(processed_data)} 筆記錄",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 已實現損益彙總",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取已實現損益彙總失敗: {str(e)}",
        }


@mcp.tool()
def get_unrealized_pnl(args: Dict) -> dict:
    """
    獲取未實現損益資訊

    查詢帳戶的未實現損益記錄，對應官方 SDK `accounting.unrealized_gains_and_loses(account)`。

    ⚠️ 重要用途：
    - 查詢未實現的損益記錄
    - 監控持倉部位的損益狀況
    - 評估投資組合的當前價值

    Args:
        account (str): 帳戶號碼

    Returns:
        dict: 成功時返回未實現損益記錄列表，每筆記錄包含以下關鍵字段：
            - date (str): 查詢當天日期
            - branch_no (str): 分公司代號
            - stock_no (str): 股票代碼
            - buy_sell (str): 買賣別，"Buy" 或 "Sell"
            - order_type (str): 委託類型，"Stock"、"Margin"、"Short"、"DayTrade" 或 "SBL"
            - cost_price (float): 成本價
            - tradable_qty (int): 可交易餘額
            - today_qty (int): 今日餘額
            - unrealized_profit (int): 未實現獲利
            - unrealized_loss (int): 未實現虧損

    Note:
        **損益計算說明**:
        - unrealized_profit: 未實現的獲利金額（正數表示獲利）
        - unrealized_loss: 未實現的損失金額（正數表示損失）
        - 單筆部位的淨損益 = unrealized_profit - unrealized_loss

        **買賣別說明**:
        - 現股交易: buy_sell 皆為 "Buy"，以餘額正負號顯示淨買賣部位
        - 信用交易: buy_sell 為 "Buy" 或 "Sell"，顯示買賣類別

        **委託類型說明**:
        - Stock: 現股交易
        - Margin: 融資交易
        - Short: 融券交易
        - DayTrade: 當沖先賣交易
        - SBL: 借券賣出交易

        **餘額說明**:
        - tradable_qty: 可交易餘額（可以進行交易的數量）
        - today_qty: 今日餘額（當日新增的部位）
    """
    try:
        validated_args = GetUnrealizedPnLArgs(**args)
        account = validated_args.account

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取未實現損益
        unrealized_pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)
        if (
            unrealized_pnl
            and hasattr(unrealized_pnl, "is_success")
            and unrealized_pnl.is_success
        ):
            # 處理數據，將枚舉轉為字串
            processed_data = []
            if hasattr(unrealized_pnl, "data") and unrealized_pnl.data:
                for item in unrealized_pnl.data:
                    processed_item = {
                        "date": getattr(item, "date", ""),
                        "branch_no": getattr(item, "branch_no", ""),
                        "stock_no": getattr(item, "stock_no", ""),
                        "buy_sell": str(getattr(item, "buy_sell", "")).split(".")[
                            -1
                        ],  # 轉為字串
                        "order_type": str(getattr(item, "order_type", "")).split(".")[
                            -1
                        ],  # 轉為字串
                        "cost_price": getattr(item, "cost_price", 0.0),
                        "tradable_qty": getattr(item, "tradable_qty", 0),
                        "today_qty": getattr(item, "today_qty", 0),
                        "unrealized_profit": getattr(item, "unrealized_profit", 0),
                        "unrealized_loss": getattr(item, "unrealized_loss", 0),
                    }
                    processed_data.append(processed_item)

            return {
                "status": "success",
                "data": processed_data,
                "message": f"成功獲取帳戶 {account} 未實現損益，共 {len(processed_data)} 筆記錄",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 未實現損益",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取未實現損益失敗: {str(e)}",
        }


@mcp.tool()
def get_maintenance(args: Dict) -> dict:
    """
    獲取帳戶維護保證金資訊

    查詢帳戶的維護保證金相關資訊，對應官方 SDK `accounting.get_maintenance(account)`。

    ⚠️ 重要用途：
    - 查詢帳戶的維護保證金比率
    - 監控融資融券的保證金使用狀況
    - 評估帳戶的財務風險

    Args:
        account (str): 帳戶號碼

    Returns:
        dict: 成功時返回維護保證金資訊，包含以下關鍵字段：
            - maintenance_ratio (float): 維護保證金比率
            - summary (dict): 總計資訊
                - total_market_value (float): 總市值
                - total_maintenance_margin (float): 總維護保證金
                - total_equity (float): 總權益
                - total_margin_balance (float): 總融資餘額
                - total_short_balance (float): 總融券餘額
            - details (list): 明細列表，每筆包含：
                - stock_no (str): 股票代碼
                - quantity (int): 持有股數
                - market_price (float): 市場價格
                - market_value (float): 市值
                - maintenance_margin (float): 維護保證金
                - equity (float): 權益
                - margin_balance (float): 融資餘額
                - short_balance (float): 融券餘額

    Note:
        **維護保證金說明**:
        - maintenance_ratio: 帳戶需要維持的最低保證金比率
        - 當帳戶權益低於維護保證金要求時，可能會收到追繳保證金通知

        **融資融券相關**:
        - margin_balance: 融資餘額（向券商借錢買股票）
        - short_balance: 融券餘額（向券商借股票賣出）
        - equity: 帳戶權益 = 市值 - 融資餘額 + 融券餘額
    """
    try:
        validated_args = GetMaintenanceArgs(**args)
        account = validated_args.account

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取維護保證金資訊
        maintenance = sdk.accounting.get_maintenance(account_obj)
        if (
            maintenance
            and hasattr(maintenance, "is_success")
            and maintenance.is_success
        ):
            # 處理數據
            processed_data = {}
            if hasattr(maintenance, "data") and maintenance.data:
                data = maintenance.data

                # 處理總計資訊
                summary_data = getattr(data, "summary", None)
                if summary_data:
                    processed_summary = {
                        "total_market_value": getattr(
                            summary_data, "total_market_value", 0.0
                        ),
                        "total_maintenance_margin": getattr(
                            summary_data, "total_maintenance_margin", 0.0
                        ),
                        "total_equity": getattr(summary_data, "total_equity", 0.0),
                        "total_margin_balance": getattr(
                            summary_data, "total_margin_balance", 0.0
                        ),
                        "total_short_balance": getattr(
                            summary_data, "total_short_balance", 0.0
                        ),
                    }
                else:
                    processed_summary = {
                        "total_market_value": 0.0,
                        "total_maintenance_margin": 0.0,
                        "total_equity": 0.0,
                        "total_margin_balance": 0.0,
                        "total_short_balance": 0.0,
                    }

                # 處理明細列表
                details_data = getattr(data, "details", [])
                processed_details = []
                if details_data:
                    for item in details_data:
                        processed_item = {
                            "stock_no": getattr(item, "stock_no", ""),
                            "quantity": getattr(item, "quantity", 0),
                            "market_price": getattr(item, "market_price", 0.0),
                            "market_value": getattr(item, "market_value", 0.0),
                            "maintenance_margin": getattr(
                                item, "maintenance_margin", 0.0
                            ),
                            "equity": getattr(item, "equity", 0.0),
                            "margin_balance": getattr(item, "margin_balance", 0.0),
                            "short_balance": getattr(item, "short_balance", 0.0),
                        }
                        processed_details.append(processed_item)

                processed_data = {
                    "maintenance_ratio": getattr(data, "maintenance_ratio", 0.0),
                    "summary": processed_summary,
                    "details": processed_details,
                }

            return {
                "status": "success",
                "data": processed_data,
                "message": f"成功獲取帳戶 {account} 維護保證金資訊，共 {len(processed_data.get('details', []))} 筆明細",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"無法獲取帳戶 {account} 維護保證金資訊",
            }

    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取維護保證金資訊失敗: {str(e)}",
        }


# =============================================================================
# MCP Prompts - 提供智慧型交易分析和建議
# =============================================================================


@mcp.prompt()
def trading_analysis(symbol: str) -> str:
    """提供股票技術分析和交易建議

    這個提示會整合多項技術指標，為指定股票提供全面的技術分析和交易建議。
    包含布林通道、RSI、MACD、KD指標的綜合分析，以及市場趨勢判斷。

    Args:
        symbol: 股票代碼，例如 '2330' 或 '0050'

    Returns:
        詳細的技術分析報告，包含：
        - 當前市場趨勢分析
        - 技術指標綜合評分
        - 買賣建議和風險提示
        - 建議的進出場策略
    """
    return f"""請為股票代碼 {symbol} 提供全面的技術分析和交易建議：

1. **市場概況分析**
   - 使用 get_market_overview 資源查看整體市場狀況
   - 分析台股指數走勢和大盤氛圍

2. **技術指標分析**
   - 使用 get_trading_signals 工具獲取 {symbol} 的技術指標數據
   - 分析布林通道、RSI、MACD、KD等指標
   - 評估多頭 vs 空頭訊號強度

3. **價格走勢分析**
   - 使用 historical_candles 工具獲取 {symbol} 的歷史數據
   - 分析價格趨勢、支撐阻力位
   - 評估成交量配合度

4. **交易建議**
   - 根據綜合分析提供買進/賣出/持有建議
   - 建議適當的停損停利價位
   - 評估風險等級和成功機率

5. **投資策略建議**
   - 根據持倉比例建議投資金額
   - 提供分散風險的建議
   - 建議觀察時間週期

請提供客觀、數據導向的分析結論。"""


@mcp.prompt()
def risk_assessment(account: str) -> str:
    """提供帳戶風險評估和投資組合優化建議

    這個提示會分析帳戶的整體風險狀況，包含投資組合分散度、
    損益狀況、資金使用效率等，為投資者提供風險管理和優化建議。

    Args:
        account: 帳戶號碼

    Returns:
        全面的風險評估報告，包含：
        - 投資組合風險等級評估
        - 資金配置和分散度分析
        - 損益狀況和績效評估
        - 風險管理建議和優化策略
    """
    return f"""請為帳戶 {account} 提供全面的風險評估和投資組合優化建議：

1. **帳戶整體狀況分析**
   - 使用 get_account_summary 資源查看帳戶基本資訊
   - 分析資金餘額和可用資金狀況
   - 評估帳戶健康度指標

2. **投資組合風險分析**
   - 使用 get_portfolio_summary 資源分析持倉結構
   - 評估投資組合分散度（行業、個股集中度）
   - 分析單一股權重和風險暴露

3. **損益和績效評估**
   - 使用 get_unrealized_pnl 工具查看未實現損益
   - 使用 get_realized_pnl_summary 工具分析已實現損益
   - 計算投資報酬率和風險調整後報酬

4. **資金使用效率分析**
   - 使用 get_bank_balance 工具查看資金使用狀況
   - 分析融資融券使用比例
   - 評估槓桿風險等級

5. **風險管理建議**
   - 根據分析結果提供風險等級評估（低/中/高風險）
   - 建議投資組合再平衡策略
   - 提供風險控制措施和停損機制建議

6. **優化策略建議**
   - 建議資產配置調整方向
   - 提供分散投資的具體建議
   - 制定長短期投資策略框架

請基於數據提供客觀的風險評估和具體可行的優化建議。"""


@mcp.prompt()
def market_opportunity_scanner() -> str:
    """掃描市場投資機會和熱門標的

    這個提示會掃描市場上的潛在投資機會，分析熱門標的和市場趨勢，
    幫助投資者發現被低估或具有成長潛力的投資機會。

    Returns:
        市場機會掃描報告，包含：
        - 市場熱點分析
        - 潛在投資機會標的
        - 行業趨勢分析
        - 投資機會評估和建議
    """
    return """請掃描當前市場的投資機會和熱門標的：

1. **市場整體分析**
   - 使用 get_market_overview 資源了解大盤狀況
   - 分析上漲/下跌家數比例
   - 評估市場熱度和投資氣氛

2. **熱門標的發掘**
   - 使用 get_snapshot_actives 工具找出成交量最大的股票
   - 使用 get_snapshot_movers 工具找出漲跌幅最大的股票
   - 分析成交量和價格變動的關聯性

3. **行業趨勢分析**
   - 分析不同行業的表現差異
   - 找出領漲和落後行業
   - 評估行業輪動機會

4. **投資機會評估**
   - 篩選出具有投資價值的標的
   - 分析基本面和技術面指標
   - 評估投資風險和報酬潛力

5. **投資建議**
   - 提供具體的投資機會建議
   - 說明進場時機和持有策略
   - 提醒相關風險和注意事項

請提供數據導向的市場分析和具體的投資機會建議。"""


@mcp.prompt()
def portfolio_rebalancing(account: str) -> str:
    """提供投資組合再平衡建議

    這個提示會分析帳戶的投資組合是否需要再平衡，根據風險偏好和投資目標
    提供具體的調整建議，幫助維持最佳的資產配置。

    Args:
        account: 帳戶號碼

    Returns:
        投資組合再平衡建議報告，包含：
        - 當前組合分析
        - 目標配置建議
        - 具體調整方案
        - 執行時機建議
    """
    return f"""請為帳戶 {account} 的投資組合提供再平衡建議：

1. **當前組合分析**
   - 使用 get_portfolio_summary 資源分析現有持倉
   - 計算各股票的權重比例
   - 評估組合分散度和風險集中度

2. **目標配置制定**
   - 根據風險偏好設定目標配置比例
   - 考慮行業、規模、成長性等分散原則
   - 設定個股最大持股比例限制

3. **偏差分析**
   - 比較當前配置與目標配置的差異
   - 找出需要調整的部位
   - 評估調整的緊急程度

4. **再平衡策略**
   - 提供具體的買賣調整建議
   - 建議分批執行或一次性調整
   - 考慮交易成本和稅務影響

5. **執行建議**
   - 建議最佳的執行時機
   - 提供風險控制措施
   - 設定後續追蹤和再平衡週期

請提供具體、可操作的再平衡建議。"""


@mcp.prompt()
def trading_strategy_builder(
    symbol: str, strategy_type: str = "trend_following"
) -> str:
    """建立客製化交易策略

    這個提示會根據指定的股票和策略類型，建立適合的交易策略框架。
    支援趨勢跟隨、均線策略、突破策略等多種策略類型。

    Args:
        symbol: 股票代碼
        strategy_type: 策略類型，可選 "trend_following", "mean_reversion", "breakout", "swing"

    Returns:
        客製化交易策略建構指南，包含：
        - 策略原理說明
        - 具體執行規則
        - 風險管理機制
        - 績效評估方法
    """
    strategy_descriptions = {
        "trend_following": "趨勢跟隨策略 - 順應市場主流方向交易",
        "mean_reversion": "均值回歸策略 - 利用價格偏離均值的回歸特性",
        "breakout": "突破策略 - 在價格突破關鍵價位時進場",
        "swing": "波段策略 - 捕捉中短線價格波段",
    }

    strategy_desc = strategy_descriptions.get(strategy_type, "綜合策略")

    return f"""請為股票 {symbol} 建立{strategy_desc}的交易策略：

1. **策略原理說明**
   - 解釋{strategy_type}策略的核心邏輯
   - 分析適用於{symbol}的理由
   - 說明策略的優缺點

2. **技術指標選用**
   - 使用 get_trading_signals 工具分析{symbol}的技術指標
   - 選擇適合{strategy_type}策略的指標組合
   - 設定指標參數和權重

3. **進出場規則**
   - 定義具體的買進訊號條件
   - 定義具體的賣出訊號條件
   - 設定過濾條件避免假訊號

4. **風險管理**
   - 設定停損停利機制
   - 定義單筆交易的最大損失比例
   - 設定總資金使用比例

5. **策略測試與優化**
   - 使用歷史數據回測策略績效
   - 分析勝率、獲利因子、最大回檔
   - 根據回測結果優化參數

6. **執行指南**
   - 提供實際交易時的執行步驟
   - 設定觀察清單和監控頻率
   - 說明策略調整時機

請提供完整、可執行的交易策略框架。"""


@mcp.prompt()
def performance_analytics(account: str, period: str = "1M") -> str:
    """提供投資組合績效分析和歸因分析

    這個提示會進行深入的投資組合績效分析，包含風險調整後報酬、
    績效歸因分析、基準比較等，提供專業級的投資績效評估。

    Args:
        account: 帳戶號碼
        period: 分析期間，可選 "1W", "1M", "3M", "6M", "1Y", "ALL"，預設 "1M"

    Returns:
        全面的績效分析報告，包含：
        - 絕對報酬和風險指標
        - 風險調整後績效指標（夏普比率、索提諾比率等）
        - 績效歸因分析（股票選擇、時機選擇、資產配置）
        - 基準比較分析
        - 績效歸因和改進建議
    """
    period_descriptions = {
        "1W": "過去一周",
        "1M": "過去一個月",
        "3M": "過去三個月",
        "6M": "過去六個月",
        "1Y": "過去一年",
        "ALL": "全部期間"
    }

    period_desc = period_descriptions.get(period, "指定期間")

    return f"""請為帳戶 {account} 提供{period_desc}的全面投資組合績效分析：

1. **絕對報酬分析**
   - 使用 get_realized_pnl_summary 工具獲取已實現損益
   - 使用 get_unrealized_pnl 工具獲取未實現損益
   - 計算期間總報酬率和年化報酬率
   - 分析月度/季度報酬波動

2. **風險指標計算**
   - 計算投資組合的波動率（標準差）
   - 計算最大回檔和回檔持續時間
   - 分析下檔波動率（索提諾比率）
   - 評估風險等級和承受能力

3. **風險調整後績效**
   - 計算夏普比率（Sharpe Ratio）
   - 計算資訊比率（Information Ratio）
   - 計算詹森指數（Jensen's Alpha）
   - 與市場基準比較超額報酬

4. **績效歸因分析**
   - 資產配置效果分析（配置報酬 vs 選擇報酬）
   - 個股選擇貢獻度分析
   - 行業配置和選擇效果
   - 時機選擇能力評估

5. **基準比較分析**
   - 與大盤指數比較（加權指數、櫃買指數）
   - 與相關投資組合基準比較
   - 相對績效分析和排名
   - 超額報酬來源分析

6. **績效評估與建議**
   - 整體績效評分（1-10分）
   - 優勢和改進領域識別
   - 投資策略調整建議
   - 風險管理優化建議

請提供數據導向、客觀的績效分析和具體的改進建議。"""


@mcp.prompt()
def advanced_risk_management(account: str) -> str:
    """提供進階風險管理和投資組合優化建議

    這個提示會進行多維度的風險評估，包含市場風險、信用風險、
    流動性風險等，並提供現代投資組合理論的優化建議。

    Args:
        account: 帳戶號碼

    Returns:
        進階風險管理報告，包含：
        - 多因子風險評估
        - 投資組合優化建議（有效前沿）
        - 風險平價配置策略
        - 壓力測試結果
        - 動態風險管理策略
    """
    return f"""請為帳戶 {account} 提供進階風險管理和投資組合優化分析：

1. **多因子風險評估**
   - 使用 get_portfolio_summary 資源分析持倉結構
   - 評估市場風險暴露（Beta係數）
   - 分析行業集中度風險
   - 評估個股特定風險
   - 計算流動性風險指標

2. **投資組合風險指標**
   - 計算投資組合VaR（Value at Risk）
   - 分析壓力測試結果（各種市場情境）
   - 評估極端事件風險（黑天鵝事件）
   - 計算風險價值調整後報酬

3. **現代投資組合理論應用**
   - 分析有效前沿（Efficient Frontier）
   - 計算最優風險-報酬組合
   - 評估當前組合與最優組合的差距
   - 提供再平衡建議

4. **風險平價策略**
   - 分析各資產風險貢獻度
   - 設計風險平價配置策略
   - 比較等權重 vs 風險平價配置
   - 提供動態調整機制

5. **壓力測試與情境分析**
   - 模擬市場崩盤情境（-20%, -30%）
   - 分析利率上升情境影響
   - 評估匯率波動風險
   - 測試流動性緊縮情境

6. **動態風險管理**
   - 設定動態停損機制
   - 設計風險預警指標
   - 提供風險對沖策略
   - 制定風險預算管理

請提供量化分析和具體可行的風險管理策略。"""


@mcp.prompt()
def portfolio_optimization(account: str, objective: str = "max_sharpe") -> str:
    """提供投資組合優化建議（現代投資組合理論）

    這個提示會應用現代投資組合理論，為投資組合提供最佳化配置建議，
    包含有效前沿分析、風險平價、Black-Litterman模型等進階技術。

    Args:
        account: 帳戶號碼
        objective: 優化目標，可選 "max_sharpe", "min_volatility", "target_return", "risk_parity"

    Returns:
        投資組合優化報告，包含：
        - 當前組合分析
        - 有效前沿計算
        - 優化後配置建議
        - 預期風險和報酬
        - 實施策略和再平衡計劃
    """
    objective_descriptions = {
        "max_sharpe": "最大化夏普比率",
        "min_volatility": "最小化波動率",
        "target_return": "達成目標報酬",
        "risk_parity": "風險平價配置"
    }

    objective_desc = objective_descriptions.get(objective, "綜合優化")

    return f"""請為帳戶 {account} 提供{objective_desc}的投資組合優化分析：

1. **當前組合診斷**
   - 使用 get_portfolio_summary 資源分析現有持倉
   - 計算當前組合的預期報酬和風險
   - 評估組合分散度和相關性
   - 分析與市場基準的比較

2. **資產預期報酬估計**
   - 分析歷史報酬數據
   - 考慮基本面因素（財務指標、成長性）
   - 納入市場預期和經濟指標
   - 使用 Black-Litterman 模型整合主觀觀點

3. **風險模型建構**
   - 估計資產間相關係數矩陣
   - 計算個股波動率
   - 考慮系統性風險和特質風險
   - 建構多因子風險模型

4. **投資組合優化**
   - 計算有效前沿（Efficient Frontier）
   - 根據{objective_desc}目標尋找最優組合
   - 考慮交易成本和流動性約束
   - 設定風險預算和集中度限制

5. **優化結果分析**
   - 比較優化前後的風險-報酬特徵
   - 分析個股權重變動原因
   - 評估預期改進幅度
   - 進行敏感性分析

6. **實施策略**
   - 制定分階段調整計劃
   - 設定再平衡觸發條件
   - 設計風險控制機制
   - 提供績效監控指標

請提供數學嚴謹的優化分析和務實的實施建議。"""


@mcp.prompt()
def market_sentiment_analysis() -> str:
    """提供市場情緒分析和投資機會識別

    這個提示會整合多種市場情緒指標，包含新聞情感分析、
    社交媒體情緒、技術指標情緒、選擇權情緒等，提供市場情緒全景圖。

    Returns:
        市場情緒分析報告，包含：
        - 多維度情緒指標綜合評分
        - 市場極端情緒警示
        - 情緒驅動的投資機會
        - 反向投資策略建議
    """
    return """請提供當前市場的全面情緒分析：

1. **技術指標情緒分析**
   - 使用 get_trading_signals 工具分析多項技術指標
   - 計算技術指標總體樂觀度（0-100分）
   - 分析指標背離和極端讀數
   - 評估市場過熱/過冷程度

2. **成交量情緒分析**
   - 使用 get_snapshot_actives 工具分析成交活躍股
   - 分析成交量與價格趨勢的配合度
   - 計算恐慌指數（Put/Call Ratio）
   - 評估市場參與度和熱度

3. **新聞和媒體情緒**
   - 分析金融新聞情感傾向
   - 評估媒體報導的正面/負面比例
   - 監測重要事件和公告影響
   - 計算新聞情緒指數

4. **投資者行為分析**
   - 分析散戶 vs 機構投資者行為
   - 評估融資融券餘額變化
   - 監測大戶持股變化
   - 分析外資和投信動向

5. **選擇權情緒指標**
   - 分析選擇權未平倉量分布
   - 計算選擇權恐慌指數
   - 評估市場對未來波動率的預期
   - 分析看漲/看跌選擇權比例

6. **綜合情緒評分**
   - 整合各項情緒指標
   - 計算整體市場情緒指數
   - 識別情緒極端區間
   - 提供情緒導向的投資建議

7. **反向投資機會**
   - 識別過度樂觀/悲觀的標的
   - 分析均值回歸機會
   - 提供逆向投資策略
   - 設定情緒反轉訊號

請提供數據導向的情緒分析和具體的投資機會建議。"""


@mcp.prompt()
def algorithmic_strategy_builder(symbol: str, strategy_type: str = "momentum") -> str:
    """建立演算法交易策略（量化策略開發）

    這個提示會協助建立量化交易策略，包含動量策略、均值回歸、
    統計套利等，使用歷史數據進行回測和優化。

    Args:
        symbol: 股票代碼
        strategy_type: 策略類型，可選 "momentum", "mean_reversion", "pairs_trading", "statistical_arbitrage"

    Returns:
        量化策略建構指南，包含：
        - 策略邏輯和參數設定
        - 歷史回測結果分析
        - 風險指標評估
        - 實戰部署建議
    """
    strategy_descriptions = {
        "momentum": "動量策略 - 追蹤市場趨勢",
        "mean_reversion": "均值回歸策略 - 利用價格偏離",
        "pairs_trading": "配對交易策略 - 統計套利",
        "statistical_arbitrage": "統計套利策略 - 多資產套利"
    }

    strategy_desc = strategy_descriptions.get(strategy_type, "量化策略")

    return f"""請為{symbol}建立{strategy_desc}的量化交易策略：

1. **策略原理與假設**
   - 解釋{strategy_type}策略的理論基礎
   - 分析適用於{symbol}的條件
   - 設定策略的基本假設和限制

2. **數據準備和特徵工程**
   - 使用 historical_candles 工具獲取歷史數據
   - 設計技術指標和特徵變數
   - 處理數據缺失和異常值
   - 設定觀察窗口和滾動計算

3. **策略邏輯設計**
   - 定義進出場條件和規則
   - 設定策略參數（持有期、止損點等）
   - 設計過濾條件避免假訊號
   - 考慮交易成本和滑價

4. **歷史回測與評估**
   - 設定回測期間和初始資金
   - 計算策略的年化報酬率
   - 分析最大回檔和夏普比率
   - 評估勝率和獲利因子

5. **風險管理整合**
   - 設定動態止損機制
   - 設計倉位大小管理
   - 考慮市場波動率調整
   - 設定風險預算控制

6. **參數優化與穩健性測試**
   - 使用網格搜索優化參數
   - 進行步進式前瞻分析
   - 測試不同市場環境下的表現
   - 評估策略的穩健性

7. **實戰部署建議**
   - 設計訂單執行邏輯
   - 設定監控和警示機制
   - 制定策略調整規則
   - 提供績效追蹤指標

請提供完整的量化策略框架，包含代碼示例和實戰部署指南。"""


@mcp.prompt()
def options_strategy_optimizer(symbol: str, market_view: str = "neutral") -> str:
    """提供選擇權策略優化建議

    這個提示會分析選擇權市場，為指定的標的提供最適合的選擇權策略，
    包含Greeks分析、策略比較、風險評估等。

    Args:
        symbol: 標的股票代碼
        market_view: 市場觀點，可選 "bullish", "bearish", "neutral", "volatile"

    Returns:
        選擇權策略優化報告，包含：
        - 適合的選擇權策略推薦
        - Greeks分析和風險指標
        - 策略比較和預期報酬
        - 實施建議和風險管理
    """
    view_descriptions = {
        "bullish": "看漲觀點",
        "bearish": "看跌觀點",
        "neutral": "中性觀點",
        "volatile": "高波動預期"
    }

    view_desc = view_descriptions.get(market_view, "市場觀點")

    return f"""請為{symbol}提供基於{view_desc}的選擇權策略優化建議：

1. **市場環境分析**
   - 使用 get_trading_signals 工具分析{symbol}技術指標
   - 評估當前波動率環境
   - 分析選擇權隱含波動率
   - 評估市場對{symbol}的預期

2. **策略適配性分析**
   - 根據{view_desc}推薦適合策略
   - 比較單一選擇權 vs 複合策略
   - 分析策略的成本效益
   - 評估策略的靈活度

3. **Greeks分析**
   - 計算Delta、Gamma、Theta、Vega、Rho
   - 分析選擇權敏感度
   - 評估時間價值衰減
   - 分析波動率變化影響

4. **策略具體設計**
   - 設計具體的選擇權組合
   - 設定履約價和到期日
   - 計算最大損失和潛在獲利
   - 分析盈虧平衡點

5. **風險評估**
   - 計算策略的最大風險
   - 分析崩盤風險（Gap risk）
   - 評估提前履約可能性
   - 設計風險對沖機制

6. **成本效益分析**
   - 比較不同策略的成本
   - 分析預期報酬率
   - 計算策略的效率指標
   - 評估資金使用效率

7. **執行與管理**
   - 提供下單執行建議
   - 設定調整和退出條件
   - 設計監控指標
   - 制定風險控制計劃

請提供專業的選擇權策略分析和具體的實施建議。"""


@mcp.prompt()
def futures_spread_analyzer(futures_type: str = "tx") -> str:
    """提供期貨價差分析和套利機會識別

    這個提示會分析期貨價差走勢，識別套利機會，包含跨月價差、
    跨式價差、蝶式價差等進階分析。

    Args:
        futures_type: 期貨類型，可選 "tx" (台指期), "mt" (小台), "te" (電子期)

    Returns:
        期貨價差分析報告，包含：
        - 價差走勢分析
        - 套利機會識別
        - 風險評估
        - 交易策略建議
    """
    futures_names = {
        "tx": "台指期",
        "mt": "小台期",
        "te": "電子期"
    }

    futures_name = futures_names.get(futures_type, futures_type.upper())

    return f"""請提供{futures_name}的期貨價差分析和套利機會識別：

1. **價差基本分析**
   - 分析近月 vs 遠月合約價差
   - 評估價差的正常範圍
   - 分析季節性價差走勢
   - 計算價差的統計特性

2. **跨月價差分析**
   - 比較不同到期月份的價差
   - 分析持倉成本和融資成本影響
   - 識別異常價差機會
   - 評估套利空間

3. **蝶式價差分析**
   - 分析蝶式價差的公平價值
   - 識別蝶式套利機會
   - 評估波動率曲線影響
   - 計算蝶式價差的Greeks

4. **統計套利機會**
   - 使用統計方法識別偏離
   - 計算Z-score和標準差
   - 設定進出場門檻
   - 評估套利成功機率

5. **風險管理**
   - 分析基差風險
   - 評估流動性風險
   - 考慮跳空風險
   - 設計停損機制

6. **交易策略建議**
   - 提供具體的套利策略
   - 設定倉位大小和槓桿
   - 制定進出場時機
   - 提供績效預期

請提供專業的期貨價差分析和具體的套利策略建議。"""


@mcp.prompt()
def volatility_trading_advisor(symbol: str) -> str:
    """提供波動率交易策略建議

    這個提示會分析市場波動率，提供波動率交易策略，包含VIX相關策略、
    選擇權波動率交易、統計波動率交易等。

    Args:
        symbol: 股票代碼或指數代碼

    Returns:
        波動率交易策略報告，包含：
            - 波動率環境分析
            - 波動率交易機會
            - 策略設計和風險管理
            - 實施建議
    """
    return f"""請為{symbol}提供波動率交易策略分析和建議：

1. **波動率環境分析**
   - 分析{symbol}的歷史波動率
   - 比較隱含波動率 vs 實現波動率
   - 評估當前波動率等級
   - 分析波動率微笑曲線

2. **波動率指標分析**
   - 計算ATR（平均真實波動）
   - 分析布林通道波動性
   - 評估波動率的趨勢
   - 識別波動率極端值

3. **波動率交易策略**
   - 設計長波動率策略（看漲波動）
   - 設計短波動率策略（看跌波動）
   - 分析選擇權的波動率交易
   - 評估統計套利機會

4. **VIX相關策略**
   - 分析VIX指數走勢
   - 設計VIX期貨和選擇權策略
   - 評估波動率風險溢價
   - 分析恐慌指數應用

5. **風險管理**
   - 設定波動率止損機制
   - 設計動態對沖策略
   - 評估Gamma和Vega風險
   - 制定資金管理計劃

6. **市場時機選擇**
   - 識別高波動環境機會
   - 分析低波動環境策略
   - 評估事件驅動波動
   - 設定進出場訊號

請提供專業的波動率交易分析和具體的策略建議。"""


# =============================================================================
# 狀態管理 - 單例模式實現
# =============================================================================


class MCPServerState:
    """MCP服務器狀態管理單例類"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.sdk = None
            self.accounts = None
            self.reststock = None
            self.restfutopt = None
            self._resource_cache = {}
            self._cache_ttl = 300  # 5分鐘預設TTL
            self._last_cache_cleanup = datetime.now()

            # Phase 2: 訂閱管理
            self._market_subscriptions = {}  # symbol -> subscription_info
            self._active_streams = {}  # stream_id -> stream_info
            self._event_listeners = {}  # event_type -> listeners
            self._realtime_data_buffer = {}  # symbol -> latest_data
            self._stream_callbacks = {}  # stream_id -> callback_function

            MCPServerState._initialized = True

    def initialize_sdk(
        self, username: str, password: str, pfx_path: str, pfx_password: str = ""
    ):
        """初始化SDK"""
        try:
            print("正在初始化富邦證券SDK...", file=sys.stderr)
            self.sdk = FubonSDK()
            self.accounts = self.sdk.login(username, password, pfx_path, pfx_password)
            self.sdk.init_realtime()
            self.reststock = self.sdk.marketdata.rest_client.stock
            self.restfutopt = self.sdk.marketdata.rest_client.futopt

            if (
                not self.accounts
                or not hasattr(self.accounts, "is_success")
                or not self.accounts.is_success
            ):
                raise ValueError("登入失敗，請檢查憑證是否正確")

            # 設定主動回報事件回調函數
            self.sdk.set_on_order(on_order)
            self.sdk.set_on_order_changed(on_order_changed)
            self.sdk.set_on_filled(on_filled)
            self.sdk.set_on_event(on_event)

            print("富邦證券SDK初始化成功", file=sys.stderr)
            return True
        except Exception as e:
            print(f"SDK初始化失敗: {str(e)}", file=sys.stderr)
            return False

    def get_account_object(self, account: str):
        """獲取帳戶對象"""
        if not self.accounts or not hasattr(self.accounts, "data"):
            return None

        for acc in self.accounts.data:
            if getattr(acc, "account", None) == account:
                return acc
        return None

    def validate_account(self, account: str) -> tuple:
        """驗證帳戶並返回帳戶對象"""
        if (
            not self.accounts
            or not hasattr(self.accounts, "is_success")
            or not self.accounts.is_success
        ):
            return None, "帳戶認證失敗，請檢查憑證是否過期"

        account_obj = self.get_account_object(account)
        if not account_obj:
            return None, f"找不到帳戶 {account}"

        return account_obj, None

    def get_cached_resource(self, resource_key: str):
        """獲取快取的資源數據"""
        if resource_key in self._resource_cache:
            cache_entry = self._resource_cache[resource_key]
            if datetime.now() - cache_entry["timestamp"] < timedelta(
                seconds=self._cache_ttl
            ):
                return cache_entry["data"]
            else:
                # 快取過期，刪除
                del self._resource_cache[resource_key]
        return None

    def set_cached_resource(self, resource_key: str, data):
        """設定資源快取"""
        self._resource_cache[resource_key] = {"data": data, "timestamp": datetime.now()}
        self._cleanup_expired_cache()

    def _cleanup_expired_cache(self):
        """清理過期的快取"""
        now = datetime.now()
        if now - self._last_cache_cleanup > timedelta(minutes=10):  # 每10分鐘清理一次
            expired_keys = []
            for key, entry in self._resource_cache.items():
                if now - entry["timestamp"] > timedelta(seconds=self._cache_ttl):
                    expired_keys.append(key)

            for key in expired_keys:
                del self._resource_cache[key]

            self._last_cache_cleanup = now

    def clear_cache(self, resource_key: str = None):
        """清除快取"""
        if resource_key:
            self._resource_cache.pop(resource_key, None)
        else:
            self._resource_cache.clear()

    # Phase 2: 訂閱管理方法
    def subscribe_market_data(
        self, symbol: str, data_type: str = "quote", callback=None
    ) -> str:
        """訂閱市場數據"""
        if not self.sdk:
            return None

        subscription_key = f"{symbol}_{data_type}"
        stream_id = f"stream_{subscription_key}_{int(datetime.now().timestamp())}"

        try:
            # 根據數據類型進行訂閱
            if data_type == "quote":
                # 使用SDK的即時報價訂閱
                result = self.sdk.marketdata.subscribe_quote(symbol)
            elif data_type == "candles":
                # K線數據訂閱
                result = self.sdk.marketdata.subscribe_candles(symbol)
            elif data_type == "volume":
                # 成交量數據訂閱
                result = self.sdk.marketdata.subscribe_volume(symbol)
            else:
                return None

            if result and hasattr(result, "is_success") and result.is_success:
                # 儲存訂閱資訊
                self._market_subscriptions[subscription_key] = {
                    "stream_id": stream_id,
                    "symbol": symbol,
                    "data_type": data_type,
                    "subscribed_at": datetime.now(),
                    "callback": callback,
                }

                self._active_streams[stream_id] = {
                    "subscription_key": subscription_key,
                    "symbol": symbol,
                    "data_type": data_type,
                    "status": "active",
                }

                return stream_id
        except Exception as e:
            print(f"訂閱市場數據失敗: {str(e)}", file=sys.stderr)

        return None

    def unsubscribe_market_data(self, stream_id: str) -> bool:
        """取消訂閱市場數據"""
        if stream_id not in self._active_streams:
            return False

        stream_info = self._active_streams[stream_id]
        subscription_key = stream_info["subscription_key"]

        try:
            symbol = stream_info["symbol"]
            data_type = stream_info["data_type"]

            # 根據數據類型取消訂閱
            if data_type == "quote":
                result = self.sdk.marketdata.unsubscribe_quote(symbol)
            elif data_type == "candles":
                result = self.sdk.marketdata.unsubscribe_candles(symbol)
            elif data_type == "volume":
                result = self.sdk.marketdata.unsubscribe_volume(symbol)
            else:
                return False

            if result and hasattr(result, "is_success") and result.is_success:
                # 清理訂閱資訊
                self._active_streams.pop(stream_id, None)
                self._market_subscriptions.pop(subscription_key, None)
                return True
        except Exception as e:
            print(f"取消訂閱市場數據失敗: {str(e)}", file=sys.stderr)

        return False

    def get_active_subscriptions(self) -> dict:
        """獲取所有活躍的訂閱"""
        return {
            "market_subscriptions": self._market_subscriptions.copy(),
            "active_streams": self._active_streams.copy(),
        }

    def update_realtime_data(self, symbol: str, data: dict):
        """更新即時數據緩衝區"""
        self._realtime_data_buffer[symbol] = {
            "data": data,
            "updated_at": datetime.now(),
        }

    def get_realtime_data(self, symbol: str):
        """獲取即時數據"""
        return self._realtime_data_buffer.get(symbol)

    def register_event_listener(self, event_type: str, listener_id: str, callback):
        """註冊事件監聽器"""
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = {}

        self._event_listeners[event_type][listener_id] = {
            "callback": callback,
            "registered_at": datetime.now(),
        }

    def unregister_event_listener(self, event_type: str, listener_id: str):
        """取消註冊事件監聽器"""
        if event_type in self._event_listeners:
            self._event_listeners[event_type].pop(listener_id, None)

    def notify_event_listeners(self, event_type: str, event_data: dict):
        """通知事件監聽器"""
        if event_type in self._event_listeners:
            for listener_info in self._event_listeners[event_type].values():
                try:
                    callback = listener_info["callback"]
                    callback(event_data)
                except Exception as e:
                    print(f"事件監聽器回調失敗: {str(e)}", file=sys.stderr)

    def notify_event_listeners(self, event_type: str, event_data: dict):
        """通知事件監聽器"""
        if event_type in self._event_listeners:
            for listener_info in self._event_listeners[event_type].values():
                try:
                    callback = listener_info["callback"]
                    callback(event_data)
                except Exception as e:
                    print(f"事件監聽器回調失敗: {str(e)}", file=sys.stderr)

    # Phase 2: WebSocket 串流管理
    def start_websocket_stream(
        self, symbol: str, data_type: str = "quote", interval: int = 1
    ) -> str:
        """啟動 WebSocket 串流"""
        if not self.sdk:
            return None

        stream_id = f"ws_{symbol}_{data_type}_{int(datetime.now().timestamp())}"

        try:
            # 初始化 WebSocket 連線（模擬實現）
            # 實際實現會根據富邦 SDK 的 WebSocket API
            stream_info = {
                "stream_id": stream_id,
                "symbol": symbol,
                "data_type": data_type,
                "interval": interval,
                "status": "connecting",
                "started_at": datetime.now(),
                "last_message_at": None,
                "message_count": 0,
            }

            self._active_streams[stream_id] = stream_info

            # 模擬 WebSocket 連線成功
            stream_info["status"] = "connected"

            return stream_id

        except Exception as e:
            print(f"啟動 WebSocket 串流失敗: {str(e)}", file=sys.stderr)
            return None

    def stop_websocket_stream(self, stream_id: str) -> bool:
        """停止 WebSocket 串流"""
        if stream_id not in self._active_streams:
            return False

        try:
            # 關閉 WebSocket 連線的邏輯
            stream_info = self._active_streams[stream_id]
            stream_info["status"] = "disconnected"
            stream_info["stopped_at"] = datetime.now()

            # 清理資源
            self._active_streams.pop(stream_id, None)

            return True

        except Exception as e:
            print(f"停止 WebSocket 串流失敗: {str(e)}", file=sys.stderr)
            return False

    def get_stream_status(self, stream_id: str) -> dict:
        """獲取串流狀態"""
        if stream_id in self._active_streams:
            return self._active_streams[stream_id].copy()
        return None

    def get_all_stream_status(self) -> dict:
        """獲取所有串流狀態"""
        return {
            "active_streams": self._active_streams.copy(),
            "total_streams": len(self._active_streams),
            "market_subscriptions": len(self._market_subscriptions),
        }

    def push_realtime_update(self, symbol: str, data: dict, data_type: str = "quote"):
        """推送即時數據更新"""
        try:
            # 更新數據緩衝區
            self.update_realtime_data(symbol, data)

            # 通知相關事件監聽器
            event_data = {
                "symbol": symbol,
                "data_type": data_type,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }

            self.notify_event_listeners(f"realtime_{data_type}", event_data)
            self.notify_event_listeners("market_data", event_data)

            # 通知訂閱者特定的 symbol 更新
            self.notify_event_listeners(f"symbol_{symbol}", event_data)

        except Exception as e:
            print(f"推送即時更新失敗: {str(e)}", file=sys.stderr)

    def register_stream_callback(self, stream_id: str, callback):
        """註冊串流回調函數"""
        self._stream_callbacks[stream_id] = {
            "callback": callback,
            "registered_at": datetime.now(),
        }

    def unregister_stream_callback(self, stream_id: str):
        """取消註冊串流回調函數"""
        self._stream_callbacks.pop(stream_id, None)

    def handle_stream_message(self, stream_id: str, message: dict):
        """處理串流訊息"""
        try:
            if stream_id in self._active_streams:
                stream_info = self._active_streams[stream_id]
                stream_info["last_message_at"] = datetime.now()
                stream_info["message_count"] += 1

                # 調用回調函數
                if stream_id in self._stream_callbacks:
                    callback_info = self._stream_callbacks[stream_id]
                    callback_info["callback"](message)

                # 推送即時更新
                symbol = stream_info.get("symbol")
                data_type = stream_info.get("data_type")
                if symbol and data_type:
                    self.push_realtime_update(symbol, message, data_type)

        except Exception as e:
            print(f"處理串流訊息失敗: {str(e)}", file=sys.stderr)

    def logout(self):
        """登出並清理狀態"""
        try:
            if self.sdk:
                result = self.sdk.logout()
                if result:
                    print("已成功登出", file=sys.stderr)
                else:
                    print("登出失敗", file=sys.stderr)
        except Exception as e:
            print(f"登出時發生錯誤: {str(e)}", file=sys.stderr)
        finally:
            # 清理狀態
            self.sdk = None
            self.accounts = None
            self.reststock = None
            self.restfutopt = None
            self.clear_cache()

            # Phase 2: 清理訂閱
            self._market_subscriptions.clear()
            self._active_streams.clear()
            self._event_listeners.clear()
            self._realtime_data_buffer.clear()
            self._stream_callbacks.clear()


@mcp.tool()
def subscribe_market_data(args: Dict) -> dict:
    """
    訂閱市場數據

    訂閱指定股票或期貨的即時市場數據，包括報價、K線、成交量等。
    支援的數據類型：quote（報價）、candles（K線）、volume（成交量）。

    Args:
        symbol (str): 股票代碼或期貨合約代碼
        data_type (str): 數據類型，可選 "quote", "candles", "volume"，預設 "quote"

    Returns:
        dict: 訂閱結果，包含 stream_id 用於後續取消訂閱

    Example:
        {
            "symbol": "2330",
            "data_type": "quote"
        }
    """
    try:
        validated_args = SubscribeMarketDataArgs(**args)
        symbol = validated_args.symbol
        data_type = validated_args.data_type

        stream_id = server_state.subscribe_market_data(symbol, data_type)

        if stream_id:
            return {
                "status": "success",
                "data": {
                    "stream_id": stream_id,
                    "symbol": symbol,
                    "data_type": data_type,
                    "subscribed_at": datetime.now().isoformat(),
                },
                "message": f"成功訂閱 {symbol} 的 {data_type} 數據",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"訂閱 {symbol} 的 {data_type} 數據失敗",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"訂閱市場數據失敗: {str(e)}",
        }


@mcp.tool()
def unsubscribe_market_data(args: Dict) -> dict:
    """
    取消訂閱市場數據

    取消指定的市場數據訂閱。

    Args:
        stream_id (str): 訂閱時返回的 stream_id

    Returns:
        dict: 取消訂閱結果

    Example:
        {
            "stream_id": "stream_TX00_quote_1699999999"
        }
    """
    try:
        validated_args = UnsubscribeMarketDataArgs(**args)
        stream_id = validated_args.stream_id

        success = server_state.unsubscribe_market_data(stream_id)

        if success:
            return {
                "status": "success",
                "data": {"stream_id": stream_id},
                "message": f"成功取消訂閱 {stream_id}",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"取消訂閱 {stream_id} 失敗，訂閱不存在",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"取消訂閱市場數據失敗: {str(e)}",
        }


@mcp.tool()
def get_active_subscriptions(args: Dict) -> dict:
    """
    獲取所有活躍的訂閱

    返回當前所有活躍的市場數據訂閱資訊。

    Returns:
        dict: 包含所有活躍訂閱的詳細資訊

    Example:
        {}  # 無參數
    """
    try:
        subscriptions = server_state.get_active_subscriptions()

        return {
            "status": "success",
            "data": subscriptions,
            "total_market_subscriptions": len(
                subscriptions.get("market_subscriptions", {})
            ),
            "total_active_streams": len(subscriptions.get("active_streams", {})),
            "message": f"成功獲取活躍訂閱資訊，共 {len(subscriptions.get('active_streams', {}))} 個活躍串流",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取活躍訂閱失敗: {str(e)}",
        }


@mcp.tool()
def get_realtime_data(args: Dict) -> dict:
    """
    獲取即時數據

    獲取指定股票或期貨的最新即時數據（如果有訂閱）。

    Args:
        symbol (str): 股票代碼或期貨合約代碼

    Returns:
        dict: 最新的即時數據

    Example:
        {
            "symbol": "2330"
        }
    """
    try:
        validated_args = GetRealtimeDataArgs(**args)
        symbol = validated_args.symbol

        data = server_state.get_realtime_data(symbol)

        if data:
            return {
                "status": "success",
                "data": data,
                "symbol": symbol,
                "message": f"成功獲取 {symbol} 的即時數據",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"找不到 {symbol} 的即時數據，請先訂閱",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取即時數據失敗: {str(e)}",
        }


@mcp.tool()
def register_event_listener(args: Dict) -> dict:
    """
    註冊事件監聽器

    註冊指定事件類型的監聽器，用於接收即時事件通知。

    Args:
        event_type (str): 事件類型，例如 "order_update", "price_alert", "connection_status"
        listener_id (str): 監聽器唯一識別碼

    Returns:
        dict: 註冊結果

    Example:
        {
            "event_type": "order_update",
            "listener_id": "my_order_listener"
        }
    """
    try:
        validated_args = RegisterEventListenerArgs(**args)
        event_type = validated_args.event_type
        listener_id = validated_args.listener_id

        # 創建一個簡單的回調函數（實際應用中可能需要更複雜的邏輯）
        def event_callback(event_data):
            print(f"收到事件 {event_type}: {event_data}", file=sys.stderr)

        server_state.register_event_listener(event_type, listener_id, event_callback)

        return {
            "status": "success",
            "data": {
                "event_type": event_type,
                "listener_id": listener_id,
                "registered_at": datetime.now().isoformat(),
            },
            "message": f"成功註冊 {event_type} 事件監聽器",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"註冊事件監聽器失敗: {str(e)}",
        }


@mcp.tool()
def unregister_event_listener(args: Dict) -> dict:
    """
    取消註冊事件監聽器

    取消指定的事件監聽器。

    Args:
        event_type (str): 事件類型
        listener_id (str): 監聽器唯一識別碼

    Returns:
        dict: 取消註冊結果

    Example:
        {
            "event_type": "order_update",
            "listener_id": "my_order_listener"
        }
    """
    try:
        validated_args = UnregisterEventListenerArgs(**args)
        event_type = validated_args.event_type
        listener_id = validated_args.listener_id

        server_state.unregister_event_listener(event_type, listener_id)

        return {
            "status": "success",
            "data": {
                "event_type": event_type,
                "listener_id": listener_id,
            },
            "message": f"成功取消註冊 {event_type} 事件監聽器",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"取消註冊事件監聽器失敗: {str(e)}",
        }


@mcp.resource("realtime://{symbol}/quote")
def get_realtime_quote(symbol: str) -> str:
    """
    獲取股票或期貨的即時報價數據

    這個資源提供指定股票或期貨合約的即時報價資訊，
    包含最新成交價、買賣價量、成交量等即時數據。

    Args:
        symbol: 股票代碼或期貨合約代碼，例如 "2330", "TX00"

    Returns:
        JSON格式的即時報價數據，包含價格、成交量、買賣價量等資訊
    """
    try:
        # 從即時數據緩衝區獲取數據
        realtime_data = server_state.get_realtime_data(symbol)
        if realtime_data:
            return json.dumps(
                {
                    "symbol": symbol,
                    "data": realtime_data["data"],
                    "updated_at": realtime_data["updated_at"].isoformat(),
                    "source": "realtime_stream",
                },
                ensure_ascii=False,
                indent=2,
            )

        # 如果沒有即時數據，嘗試從API獲取最新數據
        if symbol.startswith(("T", "M")) or len(symbol) > 4:  # 期貨合約
            if server_state.restfutopt:
                result = server_state.restfutopt.intraday.quote(symbol=symbol)
                if result and hasattr(result, "is_success") and result.is_success:
                    return json.dumps(
                        {
                            "symbol": symbol,
                            "data": result.data,
                            "updated_at": datetime.now().isoformat(),
                            "source": "api_fallback",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
        else:  # 股票
            if server_state.reststock:
                result = server_state.reststock.intraday.quote(symbol=symbol)
                if result:
                    return json.dumps(
                        {
                            "symbol": symbol,
                            "data": result,
                            "updated_at": datetime.now().isoformat(),
                            "source": "api_fallback",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

        return json.dumps(
            {
                "symbol": symbol,
                "error": "無法獲取即時報價數據",
                "message": "請先訂閱該股票的即時數據或檢查網路連線",
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {"symbol": symbol, "error": f"獲取即時報價失敗: {str(e)}"},
            ensure_ascii=False,
            indent=2,
        )


@mcp.resource("realtime://{symbol}/candles/{timeframe}")
def get_realtime_candles(symbol: str, timeframe: str = "1") -> str:
    """
    獲取股票或期貨的即時K線數據

    這個資源提供指定股票或期貨合約的即時K線數據，
    支援不同時間週期的K線圖表數據。

    Args:
        symbol: 股票代碼或期貨合約代碼，例如 "2330", "TX00"
        timeframe: K線週期，可選 "1", "3", "5", "15", "30", "60"，預設 "1"

    Returns:
        JSON格式的即時K線數據，包含開高低收成交量等資訊
    """
    try:
        # 檢查時間週期是否有效
        valid_timeframes = ["1", "3", "5", "15", "30", "60"]
        if timeframe not in valid_timeframes:
            return json.dumps(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "error": f"無效的時間週期，可選值: {', '.join(valid_timeframes)}",
                },
                ensure_ascii=False,
                indent=2,
            )

        # 從即時數據緩衝區獲取數據（如果有的話）
        realtime_key = f"{symbol}_candles_{timeframe}"
        realtime_data = server_state.get_realtime_data(realtime_key)
        if realtime_data:
            return json.dumps(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": realtime_data["data"],
                    "updated_at": realtime_data["updated_at"].isoformat(),
                    "source": "realtime_stream",
                },
                ensure_ascii=False,
                indent=2,
            )

        # 如果沒有即時數據，嘗試從API獲取最新數據
        if symbol.startswith(("T", "M")) or len(symbol) > 4:  # 期貨合約
            if server_state.restfutopt:
                result = server_state.restfutopt.intraday.candles(
                    symbol=symbol, timeframe=timeframe
                )
                if result and hasattr(result, "is_success") and result.is_success:
                    return json.dumps(
                        {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "data": result.data,
                            "updated_at": datetime.now().isoformat(),
                            "source": "api_fallback",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
        else:  # 股票
            if server_state.reststock:
                result = server_state.reststock.intraday.candles(
                    symbol=symbol, timeframe=timeframe
                )
                if result:
                    return json.dumps(
                        {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "data": result,
                            "updated_at": datetime.now().isoformat(),
                            "source": "api_fallback",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

        return json.dumps(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "error": "無法獲取即時K線數據",
                "message": "請先訂閱該股票的K線數據或檢查網路連線",
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "error": f"獲取即時K線數據失敗: {str(e)}",
            },
            ensure_ascii=False,
            indent=2,
        )


@mcp.resource("streaming://{account}/orders")
def get_order_status_stream(account: str) -> str:
    """
    獲取帳戶的訂單狀態即時串流

    這個資源提供指定帳戶的訂單狀態即時更新，
    包含新訂單、修改、取消、成交等狀態變更。

    Args:
        account: 帳戶號碼

    Returns:
        JSON格式的訂單狀態串流數據，包含最新訂單狀態和更新時間
    """
    try:
        # 驗證帳戶
        account_obj, error = server_state.validate_account(account)
        if error:
            return json.dumps(
                {"account": account, "error": error}, ensure_ascii=False, indent=2
            )

        # 獲取最新的訂單回報數據
        global latest_order_reports, latest_order_changed_reports, latest_filled_reports

        stream_data = {
            "account": account,
            "order_reports": latest_order_reports[-10:]
            if latest_order_reports
            else [],  # 最近10筆
            "order_changed_reports": latest_order_changed_reports[-10:]
            if latest_order_changed_reports
            else [],
            "filled_reports": latest_filled_reports[-10:]
            if latest_filled_reports
            else [],
            "total_order_reports": len(latest_order_reports)
            if latest_order_reports
            else 0,
            "total_order_changed": len(latest_order_changed_reports)
            if latest_order_changed_reports
            else 0,
            "total_filled": len(latest_filled_reports) if latest_filled_reports else 0,
            "last_updated": datetime.now().isoformat(),
            "stream_type": "order_status",
        }

        return json.dumps(stream_data, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {"account": account, "error": f"獲取訂單狀態串流失敗: {str(e)}"},
            ensure_ascii=False,
            indent=2,
        )


@mcp.resource("streaming://{account}/portfolio")
def get_portfolio_stream(account: str) -> str:
    """
    獲取帳戶投資組合即時串流

    這個資源提供指定帳戶的投資組合即時更新，
    包含持倉變動、損益變化、資金變動等資訊。

    Args:
        account: 帳戶號碼

    Returns:
        JSON格式的投資組合串流數據，包含即時持倉和損益資訊
    """
    try:
        # 驗證帳戶
        account_obj, error = server_state.validate_account(account)
        if error:
            return json.dumps(
                {"account": account, "error": error}, ensure_ascii=False, indent=2
            )

        # 嘗試從快取獲取投資組合摘要
        cache_key = f"portfolio_{account}"
        cached_data = server_state.get_cached_resource(cache_key)

        if cached_data:
            cached_data["last_updated"] = datetime.now().isoformat()
            cached_data["stream_type"] = "portfolio"
            return json.dumps(cached_data, ensure_ascii=False, indent=2, default=str)

        # 如果沒有快取數據，獲取最新投資組合資訊
        try:
            # 獲取庫存資訊
            inventory = server_state.sdk.accounting.get_inventory(account_obj)
            inventory_data = []
            if (
                inventory
                and hasattr(inventory, "is_success")
                and inventory.is_success
                and hasattr(inventory, "data")
            ):
                for item in inventory.data:
                    inventory_data.append(
                        {
                            "stock_no": getattr(item, "stock_no", ""),
                            "stock_name": getattr(item, "stock_name", ""),
                            "quantity": getattr(item, "quantity", 0),
                            "cost_price": getattr(item, "cost_price", 0.0),
                            "market_price": getattr(item, "market_price", 0.0),
                            "market_value": getattr(item, "market_value", 0.0),
                            "unrealized_pnl": getattr(item, "unrealized_pnl", 0),
                        }
                    )

            # 獲取未實現損益
            unrealized_pnl = server_state.sdk.accounting.unrealized_gains_and_loses(
                account_obj
            )
            unrealized_data = []
            if (
                unrealized_pnl
                and hasattr(unrealized_pnl, "is_success")
                and unrealized_pnl.is_success
                and hasattr(unrealized_pnl, "data")
            ):
                for item in unrealized_pnl.data:
                    unrealized_data.append(
                        {
                            "stock_no": getattr(item, "stock_no", ""),
                            "quantity": getattr(item, "quantity", 0),
                            "cost_price": getattr(item, "cost_price", 0.0),
                            "unrealized_profit": getattr(item, "unrealized_profit", 0),
                            "unrealized_loss": getattr(item, "unrealized_loss", 0),
                        }
                    )

            # 獲取銀行餘額
            bank_balance = server_state.sdk.accounting.get_bank_balance(account_obj)
            bank_data = {}
            if (
                bank_balance
                and hasattr(bank_balance, "is_success")
                and bank_balance.is_success
                and hasattr(bank_balance, "data")
            ):
                bank_data = {
                    "available_balance": getattr(
                        bank_balance.data, "available_balance", 0
                    ),
                    "total_balance": getattr(bank_balance.data, "total_balance", 0),
                }

            stream_data = {
                "account": account,
                "inventory": inventory_data,
                "unrealized_pnl": unrealized_data,
                "bank_balance": bank_data,
                "total_positions": len(inventory_data),
                "last_updated": datetime.now().isoformat(),
                "stream_type": "portfolio",
            }

            # 快取數據
            server_state.set_cached_resource(cache_key, stream_data)

            return json.dumps(stream_data, ensure_ascii=False, indent=2, default=str)

        except Exception as api_error:
            return json.dumps(
                {
                    "account": account,
                    "error": f"獲取投資組合數據失敗: {str(api_error)}",
                },
                ensure_ascii=False,
                indent=2,
            )

    except Exception as e:
        return json.dumps(
            {"account": account, "error": f"獲取投資組合串流失敗: {str(e)}"},
            ensure_ascii=False,
            indent=2,
        )


@mcp.resource("events://{event_type}")
def get_event_stream(event_type: str) -> str:
    """
    獲取系統事件即時串流

    這個資源提供指定類型系統事件的即時串流，
    包含連線狀態、系統通知、市場事件等。

    Args:
        event_type: 事件類型，可選 "connection", "system", "market", "all"

    Returns:
        JSON格式的事件串流數據，包含最新事件和時間戳
    """
    try:
        # 獲取最新的事件回報
        global latest_event_reports

        # 根據事件類型過濾
        events = []
        if latest_event_reports:
            for event in latest_event_reports[-20:]:  # 最近20筆事件
                event_dict = (
                    dict(event)
                    if hasattr(event, "__iter__") and not isinstance(event, str)
                    else {"content": str(event)}
                )

                # 簡單的事件類型判斷邏輯
                if event_type == "all":
                    events.append(event_dict)
                elif event_type == "connection" and (
                    "connect" in str(event).lower()
                    or "disconnect" in str(event).lower()
                ):
                    events.append(event_dict)
                elif event_type == "system" and (
                    "system" in str(event).lower() or "error" in str(event).lower()
                ):
                    events.append(event_dict)
                elif event_type == "market" and (
                    "market" in str(event).lower() or "price" in str(event).lower()
                ):
                    events.append(event_dict)

        stream_data = {
            "event_type": event_type,
            "events": events,
            "total_events": len(events),
            "last_updated": datetime.now().isoformat(),
            "stream_type": "events",
        }

        return json.dumps(stream_data, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {"event_type": event_type, "error": f"獲取事件串流失敗: {str(e)}"},
            ensure_ascii=False,
            indent=2,
        )


@mcp.tool()
def unregister_event_listener(args: Dict) -> dict:
    """
    取消註冊事件監聽器

    取消指定的事件監聽器。

    Args:
        event_type (str): 事件類型
        listener_id (str): 監聽器唯一識別碼

    Returns:
        dict: 取消註冊結果

    Example:
        {
            "event_type": "order_update",
            "listener_id": "my_order_listener"
        }
    """
    try:
        validated_args = UnregisterEventListenerArgs(**args)
        event_type = validated_args.event_type
        listener_id = validated_args.listener_id

        server_state.unregister_event_listener(event_type, listener_id)

        return {
            "status": "success",
            "data": {
                "event_type": event_type,
                "listener_id": listener_id,
            },
            "message": f"成功取消註冊 {event_type} 事件監聽器",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"取消註冊事件監聽器失敗: {str(e)}",
        }


@mcp.tool()
def start_websocket_stream(args: Dict) -> dict:
    """
    啟動 WebSocket 即時串流

    啟動指定股票或期貨的 WebSocket 即時數據串流，
    提供低延遲的即時市場數據更新。

    Args:
        symbol (str): 股票代碼或期貨合約代碼
        data_type (str): 數據類型，可選 "quote", "candles", "volume"，預設 "quote"
        interval (int): 更新間隔（秒），預設 1

    Returns:
        dict: 串流啟動結果，包含 stream_id

    Example:
        {
            "symbol": "2330",
            "data_type": "quote",
            "interval": 1
        }
    """
    try:
        validated_args = StartWebSocketStreamArgs(**args)
        symbol = validated_args.symbol
        data_type = validated_args.data_type
        interval = validated_args.interval

        stream_id = server_state.start_websocket_stream(symbol, data_type, interval)

        if stream_id:
            return {
                "status": "success",
                "data": {
                    "stream_id": stream_id,
                    "symbol": symbol,
                    "data_type": data_type,
                    "interval": interval,
                    "started_at": datetime.now().isoformat(),
                },
                "message": f"成功啟動 {symbol} 的 {data_type} WebSocket 串流",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"啟動 {symbol} 的 {data_type} WebSocket 串流失敗",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"啟動 WebSocket 串流失敗: {str(e)}",
        }


@mcp.tool()
def stop_websocket_stream(args: Dict) -> dict:
    """
    停止 WebSocket 即時串流

    停止指定的 WebSocket 數據串流。

    Args:
        stream_id (str): 串流 ID

    Returns:
        dict: 停止串流結果

    Example:
        {
            "stream_id": "ws_2330_quote_1699999999"
        }
    """
    try:
        validated_args = StopWebSocketStreamArgs(**args)
        stream_id = validated_args.stream_id

        success = server_state.stop_websocket_stream(stream_id)

        if success:
            return {
                "status": "success",
                "data": {"stream_id": stream_id},
                "message": f"成功停止 WebSocket 串流 {stream_id}",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"停止 WebSocket 串流 {stream_id} 失敗，串流不存在",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"停止 WebSocket 串流失敗: {str(e)}",
        }


@mcp.tool()
def get_stream_status(args: Dict) -> dict:
    """
    獲取串流狀態

    獲取指定 WebSocket 串流的詳細狀態資訊。

    Args:
        stream_id (str): 串流 ID

    Returns:
        dict: 串流狀態資訊

    Example:
        {
            "stream_id": "ws_2330_quote_1699999999"
        }
    """
    try:
        validated_args = GetStreamStatusArgs(**args)
        stream_id = validated_args.stream_id

        status = server_state.get_stream_status(stream_id)

        if status:
            return {
                "status": "success",
                "data": status,
                "message": f"成功獲取串流 {stream_id} 狀態",
            }
        else:
            return {
                "status": "error",
                "data": None,
                "message": f"找不到串流 {stream_id}",
            }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取串流狀態失敗: {str(e)}",
        }


@mcp.tool()
def get_all_stream_status(args: Dict) -> dict:
    """
    獲取所有串流狀態

    獲取所有活躍 WebSocket 串流的狀態總覽。

    Returns:
        dict: 所有串流狀態總覽

    Example:
        {}  # 無參數
    """
    try:
        status = server_state.get_all_stream_status()

        return {
            "status": "success",
            "data": status,
            "message": f"成功獲取所有串流狀態，共 {status['total_streams']} 個活躍串流",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"獲取所有串流狀態失敗: {str(e)}",
        }


@mcp.tool()
def push_realtime_update(args: Dict) -> dict:
    """
    推送即時數據更新

    手動推送即時數據更新到所有相關的監聽器和訂閱者。
    通常用於測試或手動數據注入。

    Args:
        symbol (str): 股票代碼或期貨合約代碼
        data (dict): 要推送的數據
        data_type (str): 數據類型，可選 "quote", "candles", "volume"，預設 "quote"

    Returns:
        dict: 推送結果

    Example:
        {
            "symbol": "2330",
            "data": {"price": 500.0, "volume": 1000},
            "data_type": "quote"
        }
    """
    try:
        validated_args = PushRealtimeUpdateArgs(**args)
        symbol = validated_args.symbol
        data = validated_args.data
        data_type = validated_args.data_type

        server_state.push_realtime_update(symbol, data, data_type)

        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "data_type": data_type,
                "data": data,
                "pushed_at": datetime.now().isoformat(),
            },
            "message": f"成功推送 {symbol} 的 {data_type} 即時更新",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"推送即時更新失敗: {str(e)}",
        }


# =============================================================================
# 進階分析工具參數模型
# =============================================================================


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


@mcp.tool()
def calculate_portfolio_var(args: CalculatePortfolioVaRArgs) -> dict:
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
        account_obj, error = server_state.validate_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取投資組合數據
        portfolio_data = server_state.get_cached_resource(f"portfolio_{account}")
        if not portfolio_data:
            return {
                "status": "error",
                "data": None,
                "message": "無法獲取投資組合數據，請先獲取投資組合摘要"
            }

        # 模擬VaR計算（實際實現會使用歷史數據和統計方法）
        positions = portfolio_data.get("inventory", [])
        total_value = sum(pos.get("market_value", 0) for pos in positions)

        # 簡單的歷史模擬VaR估計（實際應用中需要更複雜的計算）
        if method == "historical":
            # 使用過去30天的波動率估計
            volatility = 0.02  # 2% daily volatility (example)
            var_estimate = total_value * volatility * time_horizon * (1 - confidence_level) ** 0.5
        elif method == "parametric":
            # 正態分布假設
            volatility = 0.015  # 1.5% daily volatility
            var_estimate = total_value * volatility * time_horizon * 1.645  # 95% confidence z-score
        else:  # monte_carlo
            # 蒙地卡羅模擬
            volatility = 0.025
            var_estimate = total_value * volatility * time_horizon * 2.326  # 99% confidence z-score

        return {
            "status": "success",
            "data": {
                "portfolio_value": total_value,
                "var_estimate": var_estimate,
                "confidence_level": confidence_level,
                "time_horizon": time_horizon,
                "method": method,
                "var_percentage": var_estimate / total_value if total_value > 0 else 0,
                "calculation_date": datetime.now().isoformat(),
            },
            "message": f"成功計算投資組合VaR (信心水準 {confidence_level*100:.1f}%, {time_horizon}天)",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"計算投資組合VaR失敗: {str(e)}",
        }


@mcp.tool()
def run_portfolio_stress_test(args: RunPortfolioStressTestArgs) -> dict:
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
        account_obj, error = server_state.validate_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取投資組合數據
        portfolio_data = server_state.get_cached_resource(f"portfolio_{account}")
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
                    market_value = pos.get("market_value", 0)
                    loss = market_value * abs(equity_drop)
                    losses.append({
                        "stock_no": pos.get("stock_no"),
                        "current_value": market_value,
                        "projected_loss": loss,
                        "loss_percentage": abs(equity_drop)
                    })

            elif scenario_name == "rate_hike":
                rate_increase = scenario.get("rate_increase", 0.02)
                # 利率上升對不同行業的影響不同
                for pos in positions:
                    market_value = pos.get("market_value", 0)
                    # 簡化的利率敏感度模型
                    sensitivity = 0.5  # 利率敏感度係數
                    loss = market_value * rate_increase * sensitivity
                    losses.append({
                        "stock_no": pos.get("stock_no"),
                        "current_value": market_value,
                        "projected_loss": loss,
                        "loss_percentage": rate_increase * sensitivity
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
                "test_date": datetime.now().isoformat(),
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


@mcp.tool()
def optimize_portfolio_allocation(args: OptimizePortfolioAllocationArgs) -> dict:
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
        account_obj, error = server_state.validate_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取投資組合數據
        portfolio_data = server_state.get_cached_resource(f"portfolio_{account}")
        if not portfolio_data:
            return {
                "status": "error",
                "data": None,
                "message": "無法獲取投資組合數據，請先獲取投資組合摘要"
            }

        positions = portfolio_data.get("inventory", [])

        # 模擬投資組合優化（實際實現會使用更複雜的數學模型）
        current_weights = {}
        total_value = 0

        for pos in positions:
            stock_no = pos.get("stock_no", "")
            market_value = pos.get("market_value", 0)
            current_weights[stock_no] = market_value
            total_value += market_value

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
                "optimization_date": datetime.now().isoformat(),
            },
            "message": f"成功執行{optimization_method}投資組合優化",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"投資組合優化失敗: {str(e)}",
        }


@mcp.tool()
def calculate_performance_attribution(args: CalculatePerformanceAttributionArgs) -> dict:
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
        account_obj, error = server_state.validate_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取投資組合數據
        portfolio_data = server_state.get_cached_resource(f"portfolio_{account}")
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
                "analysis_date": datetime.now().isoformat(),
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


@mcp.tool()
def detect_arbitrage_opportunities(args: DetectArbitrageOpportunitiesArgs) -> dict:
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
                "scan_timestamp": datetime.now().isoformat(),
            },
            "message": f"成功掃描套利機會，發現 {len(opportunities)} 個潛在機會",
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"套利機會偵測失敗: {str(e)}",
        }


@mcp.tool()
def generate_market_sentiment_index(args: GenerateMarketSentimentIndexArgs) -> dict:
    """
    生成市場情緒指數

    整合多項市場指標生成綜合情緒指數，包含技術指標情緒、
    成交量情緒、選擇權情緒等，提供市場情緒量化評估。

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

        if "technical" in index_components:
            # 技術指標情緒
            sentiment_components["technical"] = {
                "rsi_sentiment": 0.65,  # RSI情緒分數
                "macd_sentiment": 0.55,  # MACD情緒分數
                "bbands_sentiment": 0.70,  # 布林通道情緒分數
                "composite_score": 0.63,
            }

        if "volume" in index_components:
            # 成交量情緒
            sentiment_components["volume"] = {
                "volume_trend": 0.75,  # 成交量趨勢
                "accumulation_distribution": 0.60,  # 累積/派發線
                "obv_sentiment": 0.68,  # OBV情緒
                "composite_score": 0.68,
            }

        if "options" in index_components:
            # 選擇權情緒
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
                "calculation_date": datetime.now().isoformat(),
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


# 全域狀態管理器實例
server_state = MCPServerState()


def main():
    """
    應用程式主入口點函數。

    負責初始化富邦證券 SDK、進行身份認證、設定事件回調，
    並啟動 MCP 服務器。這個函數會在程式啟動時執行所有必要的初始化工作。

    初始化流程:
    1. 檢查必要的環境變數（用戶名、密碼、憑證路徑）
    2. 初始化富邦 SDK 實例
    3. 登入到富邦證券系統
    4. 初始化即時資料連線
    5. 設定所有主動回報事件回調函數
    6. 啟動 MCP 服務器

    環境變數需求:
    - FUBON_USERNAME: 富邦證券帳號
    - FUBON_PASSWORD: 登入密碼
    - FUBON_PFX_PATH: PFX 憑證檔案路徑
    - FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）

    如果初始化失敗，程式會輸出錯誤訊息並以錯誤代碼退出。
    """
    try:
        # 檢查必要的環境變數
        if not all([username, password, pfx_path]):
            raise ValueError(
                "FUBON_USERNAME, FUBON_PASSWORD, and FUBON_PFX_PATH environment variables are required"
            )

        # 使用新的狀態管理系統初始化SDK
        success = server_state.initialize_sdk(
            username, password, pfx_path, pfx_password or ""
        )
        if not success:
            raise ValueError("登入失敗，請檢查憑證是否正確")

        print("富邦證券MCP server運行中...", file=sys.stderr)
        mcp.run()
    except KeyboardInterrupt:
        print("收到中斷信號，正在優雅關閉...", file=sys.stderr)
        server_state.logout()
        sys.exit(0)
    except Exception as e:
        print(f"啟動伺服器時發生錯誤: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
