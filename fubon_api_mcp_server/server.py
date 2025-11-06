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

# 本地模組導入
from .enums import (
    to_bs_action, to_market_type, to_order_type, to_price_type, to_time_in_force,
    to_trading_type, to_trigger_content, to_operator, to_condition_market_type,
    to_condition_order_type, to_condition_price_type, to_stop_sign, to_direction,
    to_time_slice_order_type, to_condition_status, to_history_status
)

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
    trigger: Optional[str] = "MatchedPrice"  # 停損/停利觸發條件，可選 MatchedPrice, BidPrice, AskPrice，預設 MatchedPrice


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
    trigger: str = (
        "MatchedPrice"  # 觸發內容：MatchedPrice(成交價), BuyPrice(買價), SellPrice(賣價), TotalQuantity(累計成交量), Time(時間)
    )
    trigger_value: str  # 觸發值
    comparison: str = (
        "LessThan"  # 比較運算子：LessThan(<), LessOrEqual(<=), Equal(=), Greater(>), GreaterOrEqual(>=)
    )


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
            raise ValueError(f"single_quantity 必須為1000的倍數（張數），輸入值 {self.single_quantity} 股無效")

        # 如果提供了 split_count，自動計算 total_quantity
        if self.split_count is not None and self.split_count > 0:
            if self.total_quantity is None:
                self.total_quantity = self.split_count * self.single_quantity
            elif self.total_quantity != self.split_count * self.single_quantity:
                raise ValueError(f"total_quantity ({self.total_quantity}) 與 split_count * single_quantity ({self.split_count * self.single_quantity}) 不一致")

        if self.total_quantity is not None and self.total_quantity <= self.single_quantity:
            raise ValueError("total_quantity 必須大於 single_quantity")

        # 驗證總股數也必須為1000的倍數
        if self.total_quantity is not None and self.total_quantity % 1000 != 0:
            raise ValueError(f"total_quantity 必須為1000的倍數（張數），輸入值 {self.total_quantity} 股無效")

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
            raise ValueError("method 無效，必須是 TimeSliceOrderType 的成員名稱 (Type1/Type2/Type3) 或 'TimeSlice' (自動推斷)")
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
        quantity (int): 委託數量（股）
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
        return {
            "status": "success",
            "data": result.dict() if hasattr(result, "dict") else result,
            "message": f"成功獲取 {symbol} 基本資料",
        }
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
        return {
            "status": "success",
            "data": result.dict() if hasattr(result, "dict") else result,
            "message": f"成功獲取 {symbol} 即時報價",
        }
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

        result = reststock.intraday.candles(symbol=symbol)
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

        result = reststock.intraday.volumes(symbol=symbol)
        return {"status": "success", "data": result, "message": f"成功獲取 {symbol} 分價量表"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取分價量表失敗: {str(e)}"}


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
                return {"status": "error", "data": None, "message": "API 返回的 data 欄位不是列表格式"}
        else:
            # 如果返回的不是預期的字典格式
            return {"status": "success", "data": result, "message": f"成功獲取 {market} 行情快照"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取行情快照失敗: {str(e)}"}


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
                return {"status": "error", "data": None, "message": "API 返回的 data 欄位不是列表格式"}
        else:
            # 如果返回的不是預期的字典格式
            return {"status": "success", "data": result, "message": f"成功獲取 {market} {direction} {change}排行"}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"獲取漲跌幅排行失敗: {str(e)}"}


@mcp.tool()
def get_snapshot_actives(args: Dict) -> dict:
    """
    獲取股票成交量值排行（依市場別）

    Args:
        market (str): 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
        trade (str): 成交量／成交值，可選 volume 成交量；value 成交值，預設 "volume"
        type (str): 標的類型，可選 ALLBUT099 包含一般股票、特別股及ETF ； COMMONSTOCK 為一般股票
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
                return {"status": "error", "data": None, "message": "API 返回的 data 欄位不是列表格式"}
        else:
            # 如果返回的不是預期的字典格式
            return {"status": "success", "data": result, "message": f"成功獲取 {market} {trade}排行"}
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
            return {"status": "success", "data": stats, "message": f"成功獲取 {symbol} 近 52 週統計"}
        else:
            return {"status": "error", "data": None, "message": f"API 返回格式錯誤: {result}"}

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
                    trigger=to_trigger_content(tp_data.trigger) if tp_data.trigger else TriggerContent.MatchedPrice,
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
                    trigger=to_trigger_content(sl_data.trigger) if sl_data.trigger else TriggerContent.MatchedPrice,
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
            guid = getattr(result.data, "guid", None) if hasattr(result, "data") else None
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
            error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
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
                    trigger=to_trigger_content(tp_data.trigger) if tp_data.trigger else TriggerContent.MatchedPrice,
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
                    trigger=to_trigger_content(sl_data.trigger) if sl_data.trigger else TriggerContent.MatchedPrice,
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
            guid = getattr(result.data, "guid", None) if hasattr(result, "data") else None

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

            message = f"多條件單已成功建立 - {order_data.symbol} ({len(conditions)} 個條件)"
            if response_data.get("has_tpsl"):
                message += " (含停損停利)"

            return {
                "status": "success",
                "data": response_data,
                "message": message,
            }
        else:
            error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
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
                    trigger=to_trigger_content(tp_args.trigger) if tp_args.trigger else TriggerContent.MatchedPrice,
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
                    trigger=to_trigger_content(sl_args.trigger) if sl_args.trigger else TriggerContent.MatchedPrice,
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
            guid = getattr(result.data, "guid", None) if hasattr(result, "data") else None

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
                return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
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
                    trigger=to_trigger_content(tpa.trigger) if tpa.trigger else TriggerContent.MatchedPrice,
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
                    trigger=to_trigger_content(sla.trigger) if sla.trigger else TriggerContent.MatchedPrice,
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
            guid = getattr(result.data, "guid", None) if hasattr(result, "data") else None
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
            guid = getattr(result.data, "guid", None) if hasattr(result, "data") else None
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
                return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
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
        result = sdk.stock.get_trail_history(account_obj, validated.start_date, validated.end_date)

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
                return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
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

    Args:
        account (str): 帳號
        batch_no (str): 分時分量條件單號

    Returns:
        dict: 成功時回傳展開的明細陣列（ConditionDetail list）
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
                return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
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

    Args:
        account (str): 帳號
        guid (str): 條件單號

    Returns:
        dict: 成功時回傳 `advisory` 等資訊
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
                return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data_dict = to_dict(getattr(result, "data", None)) or {}
            advisory_text = data_dict.get("advisory") if isinstance(data_dict, dict) else None
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
                return {"status": "error", "message": f"不支援的條件單狀態: {validated.condition_status}"}
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
                return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data = getattr(result, "data", []) or []
            data_list = to_dict(data) or []
            count = len(data_list) if isinstance(data_list, list) else 0
            suffix = f", 狀態={validated.condition_status}" if validated.condition_status else ""
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
                return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
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
                return {"status": "error", "message": f"不支援的歷史條件單狀態: {validated.condition_history_status}"}
            result = sdk.stock.get_condition_history(account_obj, validated.start_date, validated.end_date, hist_enum)
        else:
            result = sdk.stock.get_condition_history(account_obj, validated.start_date, validated.end_date)

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
                return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
            except Exception:
                return str(obj)

        if result and hasattr(result, "is_success") and result.is_success:
            data = getattr(result, "data", []) or []
            data_list = to_dict(data) or []
            count = len(data_list) if isinstance(data_list, list) else 0
            suffix = f", 狀態={validated.condition_history_status}" if validated.condition_history_status else ""
            return {
                "status": "success",
                "data": data_list,
                "message": f"查詢成功，共 {count} 筆（{validated.start_date}~{validated.end_date}{suffix}）",
            }

        error_msg = getattr(result, "message", "未知錯誤") if result else "API 調用失敗"
        return {"status": "error", "message": f"查詢失敗: {error_msg}"}

    except Exception as e:
        return {"status": "error", "message": f"查詢時發生錯誤: {str(e)}"}


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
    except KeyboardInterrupt:
        print("收到中斷信號，正在優雅關閉...", file=sys.stderr)
        if sdk:
            try:
                result = sdk.logout()
                if result:
                    print("已成功登出", file=sys.stderr)
                else:
                    print("登出失敗", file=sys.stderr)
            except Exception as e:
                print(f"登出時發生錯誤: {str(e)}", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"啟動伺服器時發生錯誤: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
