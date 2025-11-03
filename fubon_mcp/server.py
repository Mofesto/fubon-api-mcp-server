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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from fubon_neo.sdk import FubonSDK
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

# 加載環境變數配置
load_dotenv()

# =============================================================================
# 配置和全局變數
# =============================================================================

# 數據目錄配置 - 用於儲存本地快取的股票歷史數據
DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "fubon-mcp" / "data"
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
    # 檢查 accounts 是否成功
    if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
        return None, "帳戶認證失敗，請檢查憑證是否過期"

    # 找到對應的帳戶對象
    account_obj = None
    if hasattr(accounts, "data") and accounts.data:
        for acc in accounts.data:
            if getattr(acc, "account", None) == account:
                account_obj = acc
                break

    if not account_obj:
        return None, f"找不到帳戶 {account}"

    return account_obj, None


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
        if not (order_results and hasattr(order_results, "is_success") and order_results.is_success):
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
        print(f"正在獲取 {symbol} 從 {params['from']} 到 {params['to']} 的數據...", file=sys.stderr)
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
# 登入後的帳戶資訊
accounts = None
# REST API 客戶端（用於股票數據查詢）
reststock = None

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
            func_line_index = next((i for i, line in enumerate(tb_lines) if func.__name__ in line), -1)

            # Highlight the specific part in the traceback where the exception occurred
            relevant_tb = "\n".join(tb_lines[func_line_index:])  # Include traceback from the function name

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
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": order_changed_data}
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
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": filled_data}
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
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp_file:
            temp_path = Path(temp_file.name)

            try:
                if file_path.exists():
                    # 讀取現有數據並合併
                    existing_df = pd.read_csv(file_path)
                    existing_df["date"] = pd.to_datetime(existing_df["date"])

                    # 合併數據並刪除重複項（以日期為鍵）
                    combined_df = pd.concat([existing_df, new_df])
                    combined_df = combined_df.drop_duplicates(subset=["date"], keep="last")
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
            return {"status": "error", "data": [], "message": f"找不到股票代碼 {symbol} 的數據"}

        return {"status": "success", "data": data.to_dict("records"), "message": f"成功獲取 {symbol} 的歷史數據"}
    except Exception as e:
        return {"status": "error", "data": [], "message": f"獲取數據時發生錯誤: {str(e)}"}


class HistoricalCandlesArgs(BaseModel):
    symbol: str
    from_date: str
    to_date: str


class PlaceOrderArgs(BaseModel):
    account: str
    symbol: str
    quantity: int
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
    days: str = "0d"  # 0d, 1d, 2d, 3d


class GetBankBalanceArgs(BaseModel):
    account: str


class GetIntradayTickersArgs(BaseModel):
    market: str  # e.g., TSE, OTC


class GetIntradayTickerArgs(BaseModel):
    symbol: str


class GetIntradayQuoteArgs(BaseModel):
    symbol: str


class GetIntradayCandlesArgs(BaseModel):
    symbol: str


class GetIntradayTradesArgs(BaseModel):
    symbol: str


class GetIntradayVolumesArgs(BaseModel):
    symbol: str


class GetSnapshotQuotesArgs(BaseModel):
    market: str


class GetSnapshotMoversArgs(BaseModel):
    market: str


class GetSnapshotActivesArgs(BaseModel):
    market: str


class GetHistoricalStatsArgs(BaseModel):
    symbol: str


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


class ModifyPriceArgs(BaseModel):
    account: str
    order_no: str
    new_price: float


class ModifyQuantityArgs(BaseModel):
    account: str
    order_no: str
    new_quantity: int


class BatchPlaceOrderArgs(BaseModel):
    account: str
    orders: List[Dict]  # 每筆訂單的參數字典
    max_workers: int = 10  # 最大並行數量


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

        return {"status": "error", "data": [], "message": f"無法獲取 {symbol} 的歷史數據"}

    except Exception as e:
        return {"status": "error", "data": [], "message": f"獲取數據時發生錯誤: {str(e)}"}


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
                symbol, current_from.strftime("%Y-%m-%d"), current_to.strftime("%Y-%m-%d")
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
        quantity (int): 數量
        price (float): 價格
        buy_sell (str): 'Buy' 或 'Sell'
        market_type (str): 市場別，預設 "Common"
        price_type (str): 價格類型，預設 "Limit"
        time_in_force (str): 有效期間，預設 "ROD"
        order_type (str): 委託類型，預設 "Stock"
        user_def (str): 使用者自定義欄位，可選
        is_non_blocking (bool): 是否使用非阻塞模式，預設False
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
        if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
            return {"status": "error", "data": None, "message": "帳戶認證失敗，請檢查憑證是否過期"}

        # 找到對應的帳戶對象
        account_obj = None
        if hasattr(accounts, "data") and accounts.data:
            for acc in accounts.data:
                if getattr(acc, "account", None) == account:
                    account_obj = acc
                    break

        if not account_obj:
            return {"status": "error", "data": None, "message": f"找不到帳戶 {account}"}

        from fubon_neo.constant import BSAction, MarketType, OrderType, PriceType, TimeInForce
        from fubon_neo.sdk import Order

        # 將字串轉換為對應的枚舉值
        buy_sell_enum = BSAction.Buy if buy_sell == "Buy" else BSAction.Sell
        market_type_enum = getattr(MarketType, market_type, MarketType.Common)
        price_type_enum = getattr(PriceType, price_type, PriceType.Limit)
        time_in_force_enum = getattr(TimeInForce, time_in_force, TimeInForce.ROD)
        order_type_enum = getattr(OrderType, order_type, OrderType.Stock)

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

        mode_desc = "非阻塞" if is_non_blocking else "阻塞"
        return {
            "status": "success",
            "data": result,
            "message": f"成功使用{mode_desc}模式下單 {buy_sell} {symbol} {quantity} 股",
        }
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
        return sdk.stock.make_modify_quantity_obj(target_order, modify_value)
    elif modify_type == "price":
        return sdk.stock.make_modify_price_obj(target_order, str(modify_value))
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
        if not (order_results and hasattr(order_results, "is_success") and order_results.is_success):
            return {"status": "error", "data": None, "message": f"無法獲取帳戶 {account} 委託結果"}

        # 找到對應的委託單
        target_order = _find_target_order(order_results, order_no)
        if not target_order:
            return {"status": "error", "data": None, "message": f"找不到委託單號 {order_no}"}

        # 創建修改對象並執行修改
        modify_obj = _create_modify_object(target_order, modify_value, modify_type)
        result = _execute_modify_operation(account_obj, modify_obj, modify_type)

        if result and hasattr(result, "is_success") and result.is_success:
            value_desc = f"數量為 {modify_value}" if modify_type == "quantity" else f"價格為 {modify_value}"
            return {
                "status": "success",
                "data": result.data if hasattr(result, "data") else result,
                "message": f"成功修改委託 {order_no} {value_desc}",
            }
        else:
            return {"status": "error", "data": None, "message": f"修改委託 {order_no} {modify_type} 失敗"}

    except Exception as modify_error:
        return {"status": "error", "data": None, "message": f"修改{modify_type}時發生錯誤: {str(modify_error)}"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"修改{modify_type}失敗: {str(e)}"}


@mcp.tool()
def modify_quantity(args: Dict) -> dict:
    """
    修改委託數量

    Args:
        account (str): 帳戶號碼
        order_no (str): 委託單號
        new_quantity (int): 新數量
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

        return {"status": "success", "data": account_details, "message": f"成功獲取帳戶 {account} 詳細資訊"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取帳戶資訊失敗: {str(e)}"}


def _get_all_accounts_basic_info() -> dict:
    """獲取所有帳戶基本資訊"""
    # 檢查 accounts 是否成功
    if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
        return {"status": "error", "data": None, "message": "帳戶認證失敗，請檢查憑證是否過期"}

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
    info["bank_balance"] = _safe_api_call(lambda: sdk.accounting.bank_remain(account_obj), "獲取銀行水位失敗")

    # 獲取未實現損益
    info["unrealized_pnl"] = _safe_api_call(
        lambda: sdk.accounting.unrealized_gains_and_loses(account_obj), "獲取未實現損益失敗"
    )

    # 獲取交割資訊 (今日)
    info["settlement_today"] = _safe_api_call(lambda: sdk.accounting.query_settlement(account_obj, "0d"), "獲取交割資訊失敗")

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
            return {"status": "error", "data": None, "message": f"無法獲取帳戶 {account} 庫存資訊"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取庫存資訊失敗: {str(e)}"}


@mcp.tool()
def get_unrealized_pnl(args: Dict) -> dict:
    """
    獲取未實現損益資訊

    Args:
        account (str): 帳戶號碼
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
        if unrealized_pnl and hasattr(unrealized_pnl, "is_success") and unrealized_pnl.is_success:
            return {
                "status": "success",
                "data": unrealized_pnl.data if hasattr(unrealized_pnl, "data") else unrealized_pnl,
                "message": f"成功獲取帳戶 {account} 未實現損益",
            }
        else:
            return {"status": "error", "data": None, "message": f"無法獲取帳戶 {account} 未實現損益"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取未實現損益失敗: {str(e)}"}


@mcp.tool()
def get_settlement_info(args: Dict) -> dict:
    """
    獲取交割資訊（應收付金額）

    Args:
        account (str): 帳戶號碼
        days (str): 查詢天數，預設 "0d" (今天)，可選 "1d", "2d", "3d"
    """
    try:
        validated_args = GetSettlementArgs(**args)
        account = validated_args.account
        days = validated_args.days

        # 驗證並獲取帳戶對象
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # 獲取交割資訊
        settlement = sdk.accounting.query_settlement(account_obj, days)
        if settlement and hasattr(settlement, "is_success") and settlement.is_success:
            return {
                "status": "success",
                "data": settlement.data if hasattr(settlement, "data") else settlement,
                "message": f"成功獲取帳戶 {account} {days} 交割資訊",
            }
        else:
            return {"status": "error", "data": None, "message": f"無法獲取帳戶 {account} 交割資訊"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取交割資訊失敗: {str(e)}"}


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
        if bank_balance and hasattr(bank_balance, "is_success") and bank_balance.is_success:
            return {
                "status": "success",
                "data": bank_balance.data if hasattr(bank_balance, "data") else bank_balance,
                "message": f"成功獲取帳戶 {account} 銀行水位資訊",
            }
        else:
            return {"status": "error", "data": None, "message": f"無法獲取帳戶 {account} 銀行水位資訊"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取銀行水位失敗: {str(e)}"}


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

        # 使用 realtime API
        quotes = sdk.marketdata.realtime.quote(symbol)
        return {"status": "success", "data": quotes, "message": f"成功獲取 {symbol} 即時行情"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取即時行情失敗: {str(e)}"}


@mcp.tool()
def get_order_results(args: Dict) -> dict:
    """
    獲取委託結果，用於確認委託與成交狀態

    Args:
        account (str): 帳戶號碼
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
        if order_results and hasattr(order_results, "is_success") and order_results.is_success:
            return {
                "status": "success",
                "data": order_results.data if hasattr(order_results, "data") else order_results,
                "message": f"成功獲取帳戶 {account} 委託結果",
            }
        else:
            return {"status": "error", "data": None, "message": f"無法獲取帳戶 {account} 委託結果"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取委託結果失敗: {str(e)}"}


@mcp.tool()
def get_intraday_tickers(args: Dict) -> dict:
    """
    獲取股票或指數列表（依條件查詢）

    Args:
        market (str): 市場別，如 TSE, OTC
    """
    try:
        validated_args = GetIntradayTickersArgs(**args)
        market = validated_args.market

        result = reststock.intraday.tickers(market=market)
        return {"status": "success", "data": result, "message": f"成功獲取 {market} 市場股票列表"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取股票列表失敗: {str(e)}"}


@mcp.tool()
def get_intraday_ticker(args: Dict) -> dict:
    """
    獲取股票基本資料（依代碼查詢）

    Args:
        symbol (str): 股票代碼
    """
    try:
        validated_args = GetIntradayTickerArgs(**args)
        symbol = validated_args.symbol

        result = reststock.intraday.ticker(symbol)
        return {"status": "success", "data": result, "message": f"成功獲取 {symbol} 基本資料"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取基本資料失敗: {str(e)}"}


@mcp.tool()
def get_intraday_quote(args: Dict) -> dict:
    """
    獲取股票即時報價（依代碼查詢）

    Args:
        symbol (str): 股票代碼
    """
    try:
        validated_args = GetIntradayQuoteArgs(**args)
        symbol = validated_args.symbol

        result = reststock.intraday.quote(symbol)
        return {"status": "success", "data": result, "message": f"成功獲取 {symbol} 即時報價"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取即時報價失敗: {str(e)}"}


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

        result = reststock.intraday.candles(symbol)
        return {"status": "success", "data": result, "message": f"成功獲取 {symbol} 盤中 K 線"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取盤中 K 線失敗: {str(e)}"}


@mcp.tool()
def get_intraday_trades(args: Dict) -> dict:
    """
    獲取股票成交明細（依代碼查詢）

    Args:
        symbol (str): 股票代碼
    """
    try:
        validated_args = GetIntradayTradesArgs(**args)
        symbol = validated_args.symbol

        result = reststock.intraday.trades(symbol)
        return {"status": "success", "data": result, "message": f"成功獲取 {symbol} 成交明細"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取成交明細失敗: {str(e)}"}


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

        result = reststock.intraday.volumes(symbol)
        return {"status": "success", "data": result, "message": f"成功獲取 {symbol} 分價量表"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取分價量表失敗: {str(e)}"}


@mcp.tool()
def get_snapshot_quotes(args: Dict) -> dict:
    """
    獲取股票行情快照（依市場別）

    Args:
        market (str): 市場別，如 TSE, OTC
    """
    try:
        validated_args = GetSnapshotQuotesArgs(**args)
        market = validated_args.market

        result = reststock.snapshot.quotes(market)
        return {"status": "success", "data": result, "message": f"成功獲取 {market} 行情快照"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取行情快照失敗: {str(e)}"}


@mcp.tool()
def get_snapshot_movers(args: Dict) -> dict:
    """
    獲取股票漲跌幅排行（依市場別）

    Args:
        market (str): 市場別，如 TSE, OTC
    """
    try:
        validated_args = GetSnapshotMoversArgs(**args)
        market = validated_args.market

        result = reststock.snapshot.movers(market)
        return {"status": "success", "data": result, "message": f"成功獲取 {market} 漲跌幅排行"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取漲跌幅排行失敗: {str(e)}"}


@mcp.tool()
def get_snapshot_actives(args: Dict) -> dict:
    """
    獲取股票成交量值排行（依市場別）

    Args:
        market (str): 市場別，如 TSE, OTC
    """
    try:
        validated_args = GetSnapshotActivesArgs(**args)
        market = validated_args.market

        result = reststock.snapshot.actives(market=market, trade="volume")

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
                    "message": f"成功獲取 {market} 成交量值排行 (顯示前 {len(limited_data)} 筆，共 {len(data)} 筆)",
                }
            else:
                return {"status": "error", "data": None, "message": "API 返回的 data 欄位不是列表格式"}
        else:
            # 如果返回的不是預期的字典格式
            return {"status": "success", "data": result, "message": f"成功獲取 {market} 成交量值排行"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取成交量值排行失敗: {str(e)}"}


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

        result = reststock.historical.stats(symbol)
        return {"status": "success", "data": result, "message": f"成功獲取 {symbol} 近 52 週數據"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取歷史統計失敗: {str(e)}"}


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
        return {"status": "error", "data": None, "message": f"獲取委託回報失敗: {str(e)}"}


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
        reports = latest_order_changed_reports[-limit:] if latest_order_changed_reports else []

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"成功獲取最新的 {len(reports)} 筆改價/改量/刪單回報",
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取改價/改量/刪單回報失敗: {str(e)}"}


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
        return {"status": "error", "data": None, "message": f"獲取成交回報失敗: {str(e)}"}


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
        return {"status": "error", "data": None, "message": f"獲取事件通知失敗: {str(e)}"}


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
            "order_reports": latest_order_reports[-limit:] if latest_order_reports else [],
            "order_changed_reports": latest_order_changed_reports[-limit:] if latest_order_changed_reports else [],
            "filled_reports": latest_filled_reports[-limit:] if latest_filled_reports else [],
            "event_reports": latest_event_reports[-limit:] if latest_event_reports else [],
        }

        total_count = sum(len(reports) for reports in all_reports.values())

        return {
            "status": "success",
            "data": all_reports,
            "total_count": total_count,
            "message": f"成功獲取所有類型的主動回報，共 {total_count} 筆記錄",
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取所有回報失敗: {str(e)}"}


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

    Args:
        account (str): 帳戶號碼
        order_no (str): 委託單號
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
        if not (order_results and hasattr(order_results, "is_success") and order_results.is_success):
            return {"status": "error", "data": None, "message": f"無法獲取帳戶 {account} 委託結果"}

        # 找到對應的委託單
        target_order = _find_target_order(order_results, order_no)
        if not target_order:
            return {"status": "error", "data": None, "message": f"找不到委託單號 {order_no}"}

        # 取消委託
        result = sdk.stock.cancel_order(account_obj, target_order)
        if result and hasattr(result, "is_success") and result.is_success:
            return {
                "status": "success",
                "data": result.data if hasattr(result, "data") else result,
                "message": f"成功取消委託 {order_no}",
            }
        else:
            return {"status": "error", "data": None, "message": f"取消委託 {order_no} 失敗"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"取消委託失敗: {str(e)}"}


def _convert_order_data_to_enums(order_data):
    """將訂單數據轉換為枚舉值"""
    from fubon_neo.constant import BSAction, MarketType, OrderType, PriceType, TimeInForce

    buy_sell_str = order_data.get("buy_sell", "Buy")
    buy_sell_enum = BSAction.Buy if buy_sell_str == "Buy" else BSAction.Sell

    market_type_str = order_data.get("market_type", "Common")
    market_type_enum = getattr(MarketType, market_type_str, MarketType.Common)

    price_type_str = order_data.get("price_type", "Limit")
    price_type_enum = getattr(PriceType, price_type_str, PriceType.Limit)

    time_in_force_str = order_data.get("time_in_force", "ROD")
    time_in_force_enum = getattr(TimeInForce, time_in_force_str, TimeInForce.ROD)

    order_type_str = order_data.get("order_type", "Stock")
    order_type_enum = getattr(OrderType, order_type_str, OrderType.Stock)

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

        return {"order_data": order_data, "result": result, "success": True, "error": None}
    except Exception as e:
        return {"order_data": order_data, "result": None, "success": False, "error": str(e)}


def _execute_batch_orders(account_obj, orders, max_workers):
    """執行批量訂單"""
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任務
        future_to_order = {executor.submit(_place_single_order, account_obj, order_data): order_data for order_data in orders}

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
            - quantity (int): 數量
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
    global sdk, accounts, reststock

    try:
        # 檢查必要的環境變數
        if not all([username, password, pfx_path]):
            raise ValueError("FUBON_USERNAME, FUBON_PASSWORD, and FUBON_PFX_PATH environment variables are required")

        print("正在初始化富邦證券SDK...", file=sys.stderr)

        # 初始化 SDK 並登入
        sdk = FubonSDK()
        accounts = sdk.login(username, password, pfx_path, pfx_password or "")
        sdk.init_realtime()
        reststock = sdk.marketdata.rest_client.stock

        # 驗證登入是否成功
        if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
            raise ValueError("登入失敗，請檢查憑證是否正確")

        # 設定主動回報事件回調函數
        sdk.set_on_order(on_order)
        sdk.set_on_order_changed(on_order_changed)
        sdk.set_on_filled(on_filled)
        sdk.set_on_event(on_event)

        print("富邦證券MCP server運行中...", file=sys.stderr)
        mcp.run()
    except Exception as e:
        print(f"啟動伺服器時發生錯誤: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
