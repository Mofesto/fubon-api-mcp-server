#!/usr/bin/env python3
"""
富邦證券市場數據服務

此模組提供股票和期貨/選擇權的市場數據查詢功能，包括：
- 歷史數據查詢（本地快取 + API 調用）
- 即時行情數據獲取
- 技術指標計算
- 市場統計數據

主要組件：
- MarketDataService: 市場數據服務類
- 數據快取和本地存儲
- API 調用封裝
"""

import os
import pandas as pd
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from .enums import to_market_type, to_stock_types
from .utils import validate_and_get_account


class QuerySymbolSnapshotArgs(BaseModel):
    account: str
    market_type: str = "Common"
    stock_type: List[str] = ["Stock"]


class MarketDataService:
    """市場數據服務類"""

    def __init__(self, mcp: FastMCP, base_data_dir: Path, reststock, restfutopt, sdk):
        self.mcp = mcp
        self.base_data_dir = base_data_dir
        self.reststock = reststock
        self.restfutopt = restfutopt
        self.sdk = sdk
        
        # 初始化數據庫連接
        self.db_path = base_data_dir / "stock_data.db"
        self._create_tables()
        
        self._register_tools()

    def _create_tables(self):
        """創建數據庫表"""
        try:
            import sqlite3
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 創建股票歷史數據表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stock_historical_data (
                        symbol TEXT NOT NULL,
                        date TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        vol_value REAL,
                        price_change REAL,
                        change_ratio REAL,
                        PRIMARY KEY (symbol, date)
                    )
                ''')
                
                # 創建索引以提高查詢性能
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_symbol_date 
                    ON stock_historical_data(symbol, date)
                ''')
                
                conn.commit()
                print(f"數據庫表創建成功: {self.db_path}", file=sys.stderr)
                
        except Exception as e:
            print(f"創建數據庫表時發生錯誤: {str(e)}", file=sys.stderr)
            raise

    def _register_tools(self):
        """註冊所有市場數據相關的工具"""
        # 股票市場數據工具
        self.mcp.tool()(self.historical_candles)
        self.mcp.tool()(self.get_intraday_tickers)
        self.mcp.tool()(self.get_intraday_ticker)
        self.mcp.tool()(self.get_intraday_quote)
        self.mcp.tool()(self.get_intraday_candles)
        self.mcp.tool()(self.get_intraday_trades)
        self.mcp.tool()(self.get_intraday_volumes)
        self.mcp.tool()(self.get_snapshot_quotes)
        self.mcp.tool()(self.get_snapshot_movers)
        self.mcp.tool()(self.get_snapshot_actives)
        self.mcp.tool()(self.get_historical_stats)
        self.mcp.tool()(self.get_realtime_quotes)
        self.mcp.tool()(self.query_symbol_snapshot)
        self.mcp.tool()(self.margin_quota)
        self.mcp.tool()(self.daytrade_and_stock_info)
        self.mcp.tool()(self.query_symbol_quote)
        self.mcp.tool()(self.get_market_overview)

        # 期貨/選擇權市場數據工具
        self.mcp.tool()(self.get_intraday_futopt_products)
        self.mcp.tool()(self.get_intraday_futopt_tickers)
        self.mcp.tool()(self.get_intraday_futopt_ticker)
        self.mcp.tool()(self.get_intraday_futopt_quote)
        self.mcp.tool()(self.get_intraday_futopt_candles)
        self.mcp.tool()(self.get_intraday_futopt_volumes)
        self.mcp.tool()(self.get_intraday_futopt_trades)

        # 技術指標工具
        self.mcp.tool()(self.get_trading_signals)

    def historical_candles(self, args: Dict) -> dict:
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
            local_result = self._get_local_historical_data(symbol, from_date, to_date)
            if local_result:
                return local_result

            # 本地沒有數據，使用 API 獲取
            api_data = self._fetch_api_historical_data(symbol, from_date, to_date)
            if api_data:
                # 處理並保存數據
                df = pd.DataFrame(api_data)
                df = self._process_historical_data(df)
                self._save_to_local_csv(symbol, api_data)
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

    def _get_local_historical_data(
        self, symbol: str, from_date: str, to_date: str
    ) -> dict:
        """從本地數據獲取歷史數據"""
        local_data = self._read_local_stock_data(symbol)
        if local_data is None:
            return None

        df = local_data
        mask = (df["date"] >= from_date) & (df["date"] <= to_date)
        df = df[mask]

        if df.empty:
            return None

        df = self._process_historical_data(df)
        return {
            "status": "success",
            "data": df.to_dict("records"),
            "message": f"成功從本地數據獲取 {symbol} 從 {from_date} 到 {to_date} 的數據",
        }

    def _fetch_api_historical_data(
        self, symbol: str, from_date: str, to_date: str
    ) -> list:
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
                segment_data = self._fetch_historical_data_segment(
                    symbol,
                    current_from.strftime("%Y-%m-%d"),
                    current_to.strftime("%Y-%m-%d"),
                )
                all_data.extend(segment_data)
                current_from = current_to + pd.Timedelta(days=1)
        else:
            # 直接獲取數據
            all_data = self._fetch_historical_data_segment(symbol, from_date, to_date)

        return all_data

    def _fetch_historical_data_segment(
        self, symbol: str, from_date: str, to_date: str
    ) -> list:
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
            response = self.reststock.historical.candles(**params)
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

    def _process_historical_data(self, df: pd.DataFrame) -> pd.DataFrame:
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

    def _save_to_local_csv(self, symbol: str, new_data: list):
        """
        將新的股票數據保存到SQLite數據庫，避免重複數據。

        參數:
            symbol (str): 股票代碼
            new_data (list): 新的股票數據列表
        """
        try:
            import sqlite3
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 準備插入數據
                for record in new_data:
                    # 確保日期格式正確
                    date_str = str(record.get("date", ""))
                    if isinstance(record.get("date"), pd.Timestamp):
                        date_str = record["date"].strftime("%Y-%m-%d")
                    
                    # 使用INSERT OR REPLACE來處理重複數據
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_historical_data 
                        (symbol, date, open, high, low, close, volume, vol_value, price_change, change_ratio)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        symbol,
                        date_str,
                        record.get("open"),
                        record.get("high"),
                        record.get("low"),
                        record.get("close"),
                        record.get("volume"),
                        record.get("vol_value"),
                        record.get("price_change"),
                        record.get("change_ratio")
                    ))
                
                conn.commit()
                print(f"成功保存數據到SQLite: {symbol}, {len(new_data)} 筆記錄", file=sys.stderr)
                
        except Exception as e:
            print(f"保存SQLite數據時發生錯誤: {str(e)}", file=sys.stderr)

    def get_intraday_tickers(self, args: Dict) -> dict:
        """
        獲取股票或指數列表（依條件查詢）

        對應富邦官方 API: intraday/tickers/{market}

        Args:
            market (str): 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
            type (str, optional): 類型，可選 EQUITY 股票；INDEX 指數；WARRANT 權證；ODDLOT 盤中零股
            exchange (str, optional): 交易所，可選 TWSE 臺灣證券交易所；TPEx 證券櫃檯買賣中心
            industry (str, optional): 產業別
            isNormal (bool, optional): 查詢正常股票
            isAttention (bool, optional): 查詢注意股票
            isDisposition (bool, optional): 查詢處置股票
            isHalted (bool, optional): 查詢暫停交易股票

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
                "type": "EQUITY",
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

            result = self.reststock.intraday.tickers(**api_params)
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

    def get_intraday_ticker(self, args: Dict) -> dict:
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

            result = self.reststock.intraday.ticker(**api_params)

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

    def get_intraday_quote(self, args: Dict) -> dict:
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

            result = self.reststock.intraday.quote(**api_params)
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

    def get_intraday_candles(self, args: Dict) -> dict:
        """
        獲取股票價格 K 線（依代碼查詢）

        Args:
            symbol (str): 股票代碼
        """
        try:
            validated_args = GetIntradayCandlesArgs(**args)
            symbol = validated_args.symbol

            result = self.reststock.intraday.candles(symbol=symbol)
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

    def get_intraday_trades(self, args: Dict) -> dict:
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

            result = self.reststock.intraday.trades(**api_params)
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

    def get_intraday_volumes(self, args: Dict) -> dict:
        """
        獲取股票分價量表（依代碼查詢）

        Args:
            symbol (str): 股票代碼
        """
        try:
            validated_args = GetIntradayVolumesArgs(**args)
            symbol = validated_args.symbol

            result = self.reststock.intraday.volumes(symbol=symbol)
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

    def get_snapshot_quotes(self, args: Dict) -> dict:
        """
        獲取股票行情快照（依市場別）

        Args:
            market (str): 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
            type (str): 標的類型，可選 ALLBUT0999 包含一般股票、特別股及ETF ； COMMONSTOCK 為一般股票
        """
        try:
            validated_args = GetSnapshotQuotesArgs(**args)
            market = validated_args.market
            type_param = validated_args.type

            # 構建API調用參數
            api_params = {"market": market}
            if type_param:
                api_params["type"] = type_param

            result = self.reststock.snapshot.quotes(**api_params)

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

    def get_snapshot_movers(self, args: Dict) -> dict:
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
            type (str): 標的類型，可選 ALLBUT0999 包含一般股票、特別股及ETF ； COMMONSTOCK 為一般股票
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

            result = self.reststock.snapshot.movers(**api_params)

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

    def get_snapshot_actives(self, args: Dict) -> dict:
        """
        獲取股票成交量值排行（依市場別）

        對應富邦官方 API: snapshot/actives/{market}

        Args:
            market (str): 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
            trade (str): 成交量／成交值，可選 volume 成交量；value 成交值，預設 "volume"
            type (str, optional): 標的類型，可選 ALLBUT0999 包含一般股票、特別股及ETF；COMMONSTOCK 為一般股票

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

            result = self.reststock.snapshot.actives(**api_params)

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

    def get_historical_stats(self, args: Dict) -> dict:
        """
        獲取近 52 週股價數據（依代碼查詢）

        Args:
            symbol (str): 股票代碼
        """
        try:
            validated_args = GetHistoricalStatsArgs(**args)
            symbol = validated_args.symbol

            # 檢查 reststock 是否已初始化
            if self.reststock is None:
                return {
                    "status": "error",
                    "data": None,
                    "message": "歷史數據服務未初始化，請先登入系統",
                }

            # 使用正確的 historical.stats API
            result = self.reststock.historical.stats(symbol=symbol)

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

    def get_realtime_quotes(self, args: Dict) -> dict:
        """
        獲取即時行情

        Args:
            symbol (str): 股票代碼
        """
        try:
            validated_args = GetRealtimeQuotesArgs(**args)
            symbol = validated_args.symbol

            # 檢查 reststock 是否已初始化
            if self.reststock is None:
                return {
                    "status": "error",
                    "data": None,
                    "message": "股票行情服務未初始化，請先登入系統",
                }

            # 使用 intraday API 獲取即時行情
            from fubon_neo.fugle_marketdata.rest.base_rest import FugleAPIError

            try:
                result = self.reststock.intraday.quote(symbol=symbol)
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

    def get_intraday_futopt_products(self, args: Dict) -> dict:
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
            result = self.restfutopt.intraday.products(**api_params)

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

    def get_intraday_futopt_tickers(self, args: Dict) -> dict:
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
            if self.restfutopt is None:
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
            result = self.restfutopt.intraday.tickers(**api_params)

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

    def get_intraday_futopt_ticker(self, args: Dict) -> dict:
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
            if self.restfutopt is None:
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

            result = self.restfutopt.intraday.ticker(**api_params)

            # 期貨API直接返回字典格式的數據
            if result and isinstance(result, dict):
                return {
                    "status": "success",
                    "data": result,
                    "message": f"成功獲取合約 {symbol} 基本資訊",
                }
            else:
                error_msg = "API 調用失敗"
                if result and hasattr(result, "message"):
                    if isinstance(result.message, list):
                        error_msg = f"API 調用失敗: {', '.join(result.message)}"
                    else:
                        error_msg = f"API 調用失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取合約基本資訊失敗: {str(e)}",
            }

    def get_intraday_futopt_quote(self, args: Dict) -> dict:
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
            if self.restfutopt is None:
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

            result = self.restfutopt.intraday.quote(**api_params)

            # 期貨API直接返回字典格式的數據
            if result and isinstance(result, dict):
                return {
                    "status": "success",
                    "data": result,
                    "message": f"成功獲取合約 {symbol} 即時報價",
                }
            else:
                error_msg = "API 調用失敗"
                if result:
                    if hasattr(result, "message") and result.message:
                        error_msg = f"API 調用失敗: {result.message}"
                    else:
                        # 顯示 result 對象的詳細信息
                        error_msg = f"API 調用失敗，結果對象: {type(result)} - {result}"
                        if hasattr(result, "__dict__"):
                            error_msg += f"，屬性: {result.__dict__}"
                else:
                    error_msg = "API 調用失敗，返回結果為 None"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取合約即時報價失敗: {str(e)}",
            }

    def get_intraday_futopt_candles(self, args: Dict) -> dict:
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
            if self.restfutopt is None:
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

            result = self.restfutopt.intraday.candles(**api_params)

            # 期貨API直接返回字典格式的數據
            if result and isinstance(result, dict):
                return {
                    "status": "success",
                    "data": result,
                    "message": f"成功獲取合約 {symbol} K 線數據",
                }
            else:
                error_msg = "API 調用失敗"
                if result:
                    if hasattr(result, "message") and result.message:
                        error_msg = f"API 調用失敗: {result.message}"
                    else:
                        # 顯示 result 對象的詳細信息
                        error_msg = f"API 調用失敗，結果對象: {type(result)} - {result}"
                        if hasattr(result, "__dict__"):
                            error_msg += f"，屬性: {result.__dict__}"
                else:
                    error_msg = "API 調用失敗，返回結果為 None"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取合約 K 線數據失敗: {str(e)}",
            }

    def get_intraday_futopt_volumes(self, args: Dict) -> dict:
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
            if self.restfutopt is None:
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

            result = self.restfutopt.intraday.volumes(**api_params)

            # 期貨API直接返回字典格式的數據
            if result and isinstance(result, dict):
                return {
                    "status": "success",
                    "data": result,
                    "message": f"成功獲取合約 {symbol} 成交量數據",
                }
            else:
                error_msg = "API 調用失敗"
                if result:
                    if hasattr(result, "message") and result.message:
                        error_msg = f"API 調用失敗: {result.message}"
                    else:
                        # 顯示 result 對象的詳細信息
                        error_msg = f"API 調用失敗，結果對象: {type(result)} - {result}"
                        if hasattr(result, "__dict__"):
                            error_msg += f"，屬性: {result.__dict__}"
                else:
                    error_msg = "API 調用失敗，返回結果為 None"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取合約成交量數據失敗: {str(e)}",
            }

    def get_intraday_futopt_trades(self, args: Dict) -> dict:
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
            if self.restfutopt is None:
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

            result = self.restfutopt.intraday.trades(**api_params)

            # 期貨API直接返回字典格式的數據
            if result and isinstance(result, dict):
                return {
                    "status": "success",
                    "data": result,
                    "message": f"成功獲取合約 {symbol} 成交明細數據",
                }
            else:
                error_msg = "API 調用失敗"
                if result:
                    if hasattr(result, "message") and result.message:
                        error_msg = f"API 調用失敗: {result.message}"
                    else:
                        # 顯示 result 對象的詳細信息
                        error_msg = f"API 調用失敗，結果對象: {type(result)} - {result}"
                        if hasattr(result, "__dict__"):
                            error_msg += f"，屬性: {result.__dict__}"
                else:
                    error_msg = "API 調用失敗，返回結果為 None"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取合約成交明細數據失敗: {str(e)}",
            }

    def get_trading_signals(self, args: Dict) -> dict:
        """綜合技術指標生成交易訊號 (Bollinger / RSI / MACD / KD / 量比)

        返回統一格式: {status,data,message}
        data 包含:
          symbol, analysis_date, overall_signal, signal_score, confidence,
          indicators(各指標細節), reasons(文字理由列表), recommendations(建議)
        """
        try:
            params = GetTradingSignalsArgs(**args)
            df = self._read_local_stock_data(params.symbol)
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

            close = df["close"]
            high = df["high"] if "high" in df.columns else close
            low = df["low"] if "low" in df.columns else close
            volume = (
                df["volume"] if "volume" in df.columns else pd.Series([0] * len(df))
            )

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

            signal_pack = self._compute_signals(latest_row, prev_row)

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
            return {
                "status": "error",
                "data": None,
                "message": f"交易訊號計算失敗: {e}",
            }

    def query_symbol_snapshot(self, args: Dict) -> Dict[str, Any]:
        """查詢股票快照報價

        批量查詢股票快照報價，可依據市場別與股票類型進行過濾。

        Args:
            account: 帳號
            market_type: 市場別，可選 "Common", "IntradayOdd", "Fixing"
            stock_type: 股票類型列表，可選 "Stock", "CovertBond", "EtfAndEtn"

        Returns:
            dict: 成功時返回快照報價列表，每筆記錄包含：
                - symbol (str): 股票代碼
                - name (str): 股票名稱
                - price (float): 成交價
                - change (float): 漲跌價
                - change_ratio (float): 漲跌幅(%)
                - volume (int): 成交量
                - amount (float): 成交金額
                - open (float): 開盤價
                - high (float): 最高價
                - low (float): 最低價
                - bid_price (float): 買價
                - bid_volume (int): 買量
                - ask_price (float): 賣價
                - ask_volume (int): 賣量
                - status (int): 狀態位掩碼
                - status_desc (str): 狀態說明
                - trading_status (dict): 交易狀態詳情
        """
        try:
            # 驗證參數
            validated_args = QuerySymbolSnapshotArgs(**args)
            account = validated_args.account
            market_type = validated_args.market_type
            stock_type = validated_args.stock_type

            # 驗證帳戶
            account_obj, error = validate_and_get_account(account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 轉換枚舉
            market_type_enum = to_market_type(market_type)
            stock_type_enums = to_stock_types(stock_type)

            # 調用SDK
            result = self.sdk.stock.query_symbol_snapshot(
                account_obj, market_type_enum, stock_type_enums
            )

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": result.data,
                    "message": f"成功查詢快照報價，市場類型: {market_type}，股票類型: {stock_type}",
                }
            else:
                error_msg = "查詢快照報價失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"查詢快照報價失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"查詢快照報價失敗: {str(e)}",
            }

    def query_symbol_quote(self,args: Dict) -> dict:
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
            quote_result = self.sdk.stock.query_symbol_quote(
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

    def margin_quota(self,args: Dict) -> dict:
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
                    - None: 融資暫停 (停資)
                    - 數值: 融資比率（如 0.6 表示60%）
                - short_ratio (float): 融券比率
                    - None: 融券暫停 (停券)
                    - 數值: 融券比率（如 0.4 表示40%）

        Note:
            **資券配額解釋**:
            - **融資額度**: 用於買入股票時向券商借錢
            - **融券額度**: 用於賣出股票時向券商借股票
            - **原始額度 vs 可交易額度**: 原始額度是總額度，可交易額度是扣除已使用後的剩餘額度

            **額度狀態說明**:
            - **額度為 0**: 表示沒有該項資券配額
            - **額度 > 0**: 表示有該項資券配額
            - **額度為 None**: 表示該項資券無上限
            - **餘額皆為 0**: 表示停資或停券

            **比率狀態說明**:
            - **融資成數為 None**: 表示融資暫停 (停資)
            - **融券成數為 None**: 表示融券暫停 (停券)
            - **所有額度為 0 且比率為 None**: 表示該股票資券交易停止

            **權限檢查**:
            - 如果 API 返回"無資料"，表示帳戶沒有資券交易權限或帳戶類型不支援
            - 期貨帳戶通常無法查詢資券配額，只有證券帳戶才支援

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
            margin_quota_result = self.sdk.stock.margin_quota(account_obj, stock_no)

            # 檢查 API 返回結果 - 類似於股票API的處理方式
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
            elif isinstance(margin_quota_result, dict) and margin_quota_result:
                # 如果API直接返回字典格式的數據
                return {
                    "status": "success",
                    "data": margin_quota_result,
                    "message": f"成功獲取帳戶 {account} 股票 {stock_no} 資券配額",
                }
            else:
                error_msg = "無法獲取資券配額"
                if margin_quota_result and hasattr(margin_quota_result, "message"):
                    if isinstance(margin_quota_result.message, list):
                        error_msg = f"API 調用失敗: {', '.join(margin_quota_result.message)}"
                    else:
                        error_msg = f"API 調用失敗: {margin_quota_result.message}"
                        # 檢查是否為權限相關的錯誤
                        if "無資料" in str(margin_quota_result.message):
                            error_msg += " (可能原因：帳戶沒有資券交易權限、帳戶類型不支援或股票不支援資券交易)"
                elif margin_quota_result is None:
                    error_msg = "API 返回結果為 None，可能的原因：帳戶類型不支援、股票不支援資券交易、或非交易時段"
                return {
                    "status": "error",
                    "data": None,
                    "message": f"{error_msg} (帳戶: {account}, 股票: {stock_no})",
                }

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取資券配額失敗: {str(e)}",
            }

    def daytrade_and_stock_info(self,args: Dict) -> dict:
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
            daytrade_info = self.sdk.stock.daytrade_and_stock_info(account_obj, stock_no)

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

    def get_market_overview(self) -> dict:
        """
        獲取台灣股市整體概況

        整合台股指數行情、漲跌家數統計、成交量統計等市場整體資訊。

        Returns:
            dict: 成功時返回市場概況數據，包含：
                - index: 台股指數資訊 (名稱、代碼、價格、漲跌、成交量等)
                - statistics: 市場統計數據 (上漲/下跌家數、總成交量、市場狀態)
        """
        try:
            # 獲取台股指數行情
            tse_result = self.reststock.intraday.quote(symbol="IX0001")  # 台股指數
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
                movers_result = self.reststock.snapshots.movers(
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
                movers_result = self.reststock.snapshots.movers(
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
                actives_result = self.reststock.snapshots.actives(
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

            return {
                "status": "success",
                "data": market_data,
                "message": "成功獲取台灣股市整體概況",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取市場概況時發生錯誤: {str(e)}",
            }

    def _bb_position(
        self, close: float, upper: float, middle: float, lower: float
    ) -> str:
        if close > upper:
            return "突破上軌"
        if close > middle:
            return "上半軌"
        if close >= lower:
            return "下半軌"
        return "跌破下軌"

    def _rsi_level(self, rsi: float) -> str:
        if rsi >= 70:
            return "超買"
        if rsi <= 30:
            return "超賣"
        if rsi >= 60:
            return "偏強"
        if rsi <= 40:
            return "偏弱"
        return "中性"

    def _macd_cross(self, latest: Dict, prev: Dict | None) -> str:
        if not prev:
            return "無"
        if (
            latest["macd"] > latest["macd_signal"]
            and prev["macd"] <= prev["macd_signal"]
        ):
            return "金叉"
        if (
            latest["macd"] < latest["macd_signal"]
            and prev["macd"] >= prev["macd_signal"]
        ):
            return "死叉"
        return "無"

    def _kd_cross(self, latest: Dict, prev: Dict | None) -> str:
        if not prev:
            return "無"
        if latest["k"] > latest["d"] and prev["k"] <= prev["d"]:
            return "K上穿D"
        if latest["k"] < latest["d"] and prev["k"] >= prev["d"]:
            return "K下穿D"
        return "無"

    def _volume_strength(self, rate: float) -> str:
        if rate >= 2.0:
            return "爆量"
        if rate >= 1.5:
            return "量增"
        if rate >= 0.8:
            return "正常"
        if rate >= 0.5:
            return "量縮"
        return "極度萎縮"

    def _compute_signals(self, latest: Dict, prev: Dict | None) -> Dict:
        score = 0
        reasons: List[str] = []

        # Bollinger (±30)
        bb_pos = self._bb_position(
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
        rsi_level = self._rsi_level(latest["rsi"])
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
        macd_cross = self._macd_cross(latest, prev)
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
        kd_cross = self._kd_cross(latest, prev)
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
        vol_strength = self._volume_strength(latest["volume_rate"])
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


# 參數模型定義
class HistoricalCandlesArgs(BaseModel):
    symbol: str
    from_date: str
    to_date: str


class GetIntradayTickersArgs(BaseModel):
    market: str
    type: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None
    isNormal: Optional[bool] = None
    isAttention: Optional[bool] = None
    isDisposition: Optional[bool] = None
    isHalted: Optional[bool] = None


class GetIntradayTickerArgs(BaseModel):
    symbol: str
    type: Optional[str] = None


class GetIntradayQuoteArgs(BaseModel):
    symbol: str
    type: Optional[str] = None


class GetIntradayCandlesArgs(BaseModel):
    symbol: str


class GetIntradayTradesArgs(BaseModel):
    symbol: str
    type: Optional[str] = None
    offset: Optional[int] = None
    limit: Optional[int] = None


class GetIntradayVolumesArgs(BaseModel):
    symbol: str


class GetSnapshotQuotesArgs(BaseModel):
    market: str
    type: Optional[str] = None


class GetSnapshotMoversArgs(BaseModel):
    market: str
    direction: str = "up"
    change: str = "percent"
    gt: Optional[float] = None
    gte: Optional[float] = None
    lt: Optional[float] = None
    lte: Optional[float] = None
    eq: Optional[float] = None
    type: Optional[str] = None


class GetSnapshotActivesArgs(BaseModel):
    market: str
    trade: str = "volume"
    type: Optional[str] = None


class GetHistoricalStatsArgs(BaseModel):
    symbol: str


class GetIntradayProductsArgs(BaseModel):
    type: Optional[str] = None
    exchange: Optional[str] = None
    session: Optional[str] = None
    contractType: Optional[str] = None
    status: Optional[str] = None


class GetIntradayFutOptTickersArgs(BaseModel):
    type: str
    exchange: Optional[str] = None
    session: Optional[str] = None
    product: Optional[str] = None
    contractType: Optional[str] = None


class GetIntradayFutOptTickerArgs(BaseModel):
    symbol: str
    session: Optional[str] = None


class GetIntradayFutOptQuoteArgs(BaseModel):
    symbol: str
    session: Optional[str] = None


class GetIntradayFutOptCandlesArgs(BaseModel):
    symbol: str
    session: Optional[str] = None
    timeframe: Optional[str] = None


class GetIntradayFutOptTradesArgs(BaseModel):
    symbol: str
    session: Optional[str] = None
    offset: Optional[int] = None
    limit: Optional[int] = None


class GetIntradayFutOptVolumesArgs(BaseModel):
    symbol: str
    session: Optional[str] = None


class GetRealtimeQuotesArgs(BaseModel):
    symbol: str


class GetTradingSignalsArgs(BaseModel):
    symbol: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None


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
