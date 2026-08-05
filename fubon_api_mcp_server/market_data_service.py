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

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from . import indicators
from .enums import to_market_type, to_stock_types
from .utils import validate_and_get_account


class MarketDataService:
    """市場數據服務類"""

    def __init__(self, mcp: MCPServer, base_data_dir: Path, reststock, restfutopt, sdk):
        self.mcp = mcp
        self.base_data_dir = base_data_dir
        self.reststock = reststock
        self.restfutopt = restfutopt
        self.sdk = sdk
        self.logger = logging.getLogger(__name__)
        # 確保 base_data_dir 存在
        try:
            self.base_data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # 若目錄建立失敗，記錄並繼續，_create_tables 會在連線時暴露錯誤
            self.logger.debug("無法建立 base_data_dir: %s", self.base_data_dir, exc_info=True)

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
                cursor.execute(
                    """
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
                """
                )

                # 創建索引以提高查詢性能
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_symbol_date 
                    ON stock_historical_data(symbol, date)
                """
                )

                conn.commit()
                self.logger.info("數據庫表創建成功: %s", self.db_path)

        except Exception:
            self.logger.exception("創建數據庫表時發生錯誤")
            raise

    def _normalize_result(self, obj) -> dict:
        """
        Normalize SDK return objects (dict, SDK object, or string) into a plain dict.
        This handles the common SDK pattern of returning an object with .data
        or nested attributes, and also attempts to parse simple string reprs.
        """
        try:
            import dataclasses
            import re

            def to_snake_case(s: str) -> str:
                # Convert camelCase or PascalCase to snake_case
                s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", s)
                s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
                return s2.replace("-", "_").lower()

            def normalize_value(v):
                # Primitive types
                if v is None or isinstance(v, (bool, int, float, str)):
                    return v
                # Mapping
                if isinstance(v, dict):
                    return normalize_dict(v)
                # Iterable
                if isinstance(v, (list, tuple, set)):
                    return [normalize_value(x) for x in v]
                # Dataclass
                if dataclasses.is_dataclass(v):
                    return normalize_dict(dataclasses.asdict(v))
                # Namedtuple or object with _asdict
                if hasattr(v, "_asdict") and callable(v._asdict):
                    return normalize_dict(v._asdict())
                # Object with dict() or to_dict()
                if hasattr(v, "dict") and callable(getattr(v, "dict")):
                    try:
                        return normalize_value(v.dict())
                    except Exception:
                        pass
                if hasattr(v, "to_dict") and callable(getattr(v, "to_dict")):
                    try:
                        return normalize_value(v.to_dict())
                    except Exception:
                        pass
                # Object with __dict__
                if hasattr(v, "__dict__"):
                    try:
                        return normalize_dict({k: getattr(v, k) for k in v.__dict__ if not k.startswith("_")})
                    except Exception:
                        pass
                # Fallback: try to parse simple dict-like string
                if isinstance(v, str):
                    pairs = re.findall(r"(\w+):\s*(?:\"([^\"]*)\"|(None)|(-?\d+(?:\.\d+)?))", v)
                    if pairs:
                        result = {}
                        for key, quoted, none_val, num_val in pairs:
                            if quoted:
                                result[key] = quoted
                            elif none_val:
                                result[key] = None
                            elif num_val:
                                result[key] = float(num_val) if "." in num_val else int(num_val)
                        return result
                # final fallback: string repr
                try:
                    return str(v)
                except Exception:
                    return repr(v)

            def normalize_dict(d: dict) -> dict:
                out = {}
                for k, v in d.items():
                    if k is None:
                        continue
                    nk = to_snake_case(str(k))
                    out[nk] = normalize_value(v)
                return out

            # start of main function
            if obj is None:
                return {}
            # dict
            if isinstance(obj, dict):
                return normalize_dict(obj)
            # list-like
            if isinstance(obj, (list, tuple, set)):
                return [self._normalize_result(x) for x in obj]
            import unittest.mock as _unittest_mock

            # Dataclass, namedtuple, or object with _asdict
            if dataclasses.is_dataclass(obj):
                return normalize_dict(dataclasses.asdict(obj))
            if hasattr(obj, "_asdict") and callable(getattr(obj, "_asdict")):
                return normalize_dict(obj._asdict())
            # SDK-provided dict or to_dict or dict methods
            if hasattr(obj, "dict") and callable(getattr(obj, "dict")) and not isinstance(obj, _unittest_mock.Mock):
                try:
                    return normalize_value(obj.dict())
                except Exception:
                    pass
            if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")) and not isinstance(obj, _unittest_mock.Mock):
                try:
                    return normalize_value(obj.to_dict())
                except Exception:
                    pass
            # If object has 'data' attribute, unpack and normalize
            if hasattr(obj, "data") and not isinstance(obj, _unittest_mock.Mock):
                return normalize_value(getattr(obj, "data"))
            # If object has __dict__ (usual case for objects with attributes)
            if hasattr(obj, "__dict__") and not isinstance(obj, _unittest_mock.Mock):
                try:
                    return normalize_dict({k: getattr(obj, k) for k in obj.__dict__ if not k.startswith("_")})
                except Exception:
                    pass
            # As a last effort, inspect public non-callable attributes (works for Mock and other objects)
            try:
                import types

                attrs = {}
                for attr in dir(obj):
                    if attr.startswith("_"):
                        continue
                    try:
                        val = getattr(obj, attr)
                    except Exception:
                        continue
                    if callable(val) or isinstance(val, types.MethodType):
                        continue
                    attrs[attr] = val
                if attrs:
                    return normalize_dict(attrs)
            except Exception:
                pass
            # If it is a string repr like 'MarginShortQuota {\n    stock_no: "2330",\n    ...}',
            # try to extract simple key: value pairs
            if isinstance(obj, str):
                pairs = re.findall(r"(\w+):\s*(?:\"([^\"]*)\"|(None)|(-?\d+(?:\.\d+)?))", obj)
                result = {}
                for key, quoted, none_val, num_val in pairs:
                    if quoted:
                        result[key] = quoted
                    elif none_val:
                        result[key] = None
                    elif num_val:
                        if "." in num_val:
                            result[key] = float(num_val)
                        else:
                            try:
                                result[key] = int(num_val)
                            except Exception:
                                result[key] = float(num_val)
                if result:
                    return normalize_dict(result)
        except Exception:
            # Fallback: return raw repr
            try:
                return {"raw": str(obj)}
            except Exception:
                return {"raw": "<unserializable>"}
        # Final fallback
        try:
            return {"raw": str(obj)}
        except Exception:
            return {"raw": "<unserializable>"}

    def _register_tools(self):
        """註冊所有市場數據相關的工具"""
        # 股票市場數據工具
        self.mcp.tool()(self.historical_candles)
        self.mcp.tool()(self.get_capital_changes)
        self.mcp.tool()(self.get_dividends)
        self.mcp.tool()(self.get_listing_applicants)
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
        獲取歷史數據，優先使用本地數據，如果本地沒有或資料過舊則自動從 API 更新

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
            adjusted = validated_args.adjusted
            timeframe = validated_args.timeframe
            fields = validated_args.fields
            sort = validated_args.sort

            # SQLite 快取目前只保存日線、未還原且完整欄位的資料。其他查詢
            # 必須直接走 SDK，避免將不同語意的 K 線混在同一張表中。
            use_cache = self._historical_cache_compatible(adjusted, timeframe, fields)

            if use_cache:
                # 確保資料是最新的（檢查並自動更新過舊資料）
                self._ensure_fresh_data(symbol, to_date)

                # 嘗試從本地數據獲取
                local_result = self._get_local_historical_data(symbol, from_date, to_date, sort=sort)
                if local_result:
                    return local_result

            # 本地沒有數據，使用 API 獲取
            api_data = self._fetch_api_historical_data(
                symbol,
                from_date,
                to_date,
                timeframe=timeframe,
                adjusted=adjusted,
                fields=fields,
                sort=sort,
            )
            if api_data:
                # 處理並保存數據
                df = pd.DataFrame(api_data)
                df = self._process_historical_data(df, sort=sort)
                # 僅保存與既有快取語意一致的查詢結果。
                if use_cache:
                    self._save_to_local_db(symbol, df.to_dict("records"))
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

    def _get_corporate_action_data(self, method_name: str, args: Dict, args_model, message: str) -> dict:
        """Call a v2.2.8 corporate-actions endpoint with consistent MCP output."""
        try:
            validated_args = args_model(**args)
            if self.reststock is None:
                return {
                    "status": "error",
                    "data": None,
                    "message": "股票行情服務未初始化，請先登入系統",
                }

            # Support both Pydantic v1 and v2 without emitting a deprecation
            # warning on the v2 runtime used by the release build.
            if hasattr(validated_args, "model_dump"):
                api_params = validated_args.model_dump(exclude_none=True)
            else:
                api_params = validated_args.dict(exclude_none=True)
            corporate_actions = getattr(self.reststock, "corporate_actions", None)
            if corporate_actions is None:
                return {
                    "status": "error",
                    "data": None,
                    "message": "目前 SDK 不支援 v2.2.8 股務事件 API",
                }

            result = getattr(corporate_actions, method_name)(**api_params)
            if result is None:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"{message}失敗: API 沒有回傳資料",
                }

            if isinstance(result, dict):
                status_code = result.get("statusCode", result.get("status_code"))
                try:
                    if status_code is not None and int(status_code) >= 400:
                        return {
                            "status": "error",
                            "data": None,
                            "message": f"{message}失敗: {result.get('message', result)}",
                        }
                except (TypeError, ValueError):
                    # Keep unknown vendor status formats visible as data rather
                    # than failing normalization itself.
                    pass

            # v2.2.8 REST client returns a JSON dict. Keep that wire shape intact
            # so camelCase fields such as effectiveDate remain available to callers.
            if not isinstance(result, (dict, list, str, int, float, bool)):
                if hasattr(result, "dict") and callable(result.dict):
                    result = result.dict()
                else:
                    result = self._normalize_result(result)

            return {
                "status": "success",
                "data": result,
                "message": message,
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"{message}失敗: {str(e)}",
            }

    def get_capital_changes(self, args: Dict) -> dict:
        """取得上市櫃股票及 ETF 的資本變動資料（v2.2.8）。"""
        return self._get_corporate_action_data(
            "capital_changes",
            args,
            CapitalChangesArgs,
            "成功獲取資本變動資料",
        )

    def get_dividends(self, args: Dict) -> dict:
        """取得上市櫃股票的除權息資料（v2.2.8）。"""
        return self._get_corporate_action_data(
            "dividends",
            args,
            DividendsArgs,
            "成功獲取除權息資料",
        )

    def get_listing_applicants(self, args: Dict) -> dict:
        """取得申請上市櫃公司資料（v2.2.8）。"""
        return self._get_corporate_action_data(
            "listing_applicants",
            args,
            ListingApplicantsArgs,
            "成功獲取申請上市櫃公司資料",
        )

    @staticmethod
    def _historical_cache_compatible(adjusted: Optional[bool], timeframe: Optional[str], fields: Optional[str]) -> bool:
        """Return whether a historical query can use the legacy daily cache."""
        return adjusted is not True and (timeframe is None or timeframe == "D") and fields is None

    def _get_local_historical_data(self, symbol: str, from_date: str, to_date: str, sort: str = "desc") -> dict:
        """從本地數據獲取歷史數據"""
        local_data = self._read_local_stock_data(symbol)
        if local_data is None:
            return None

        df = local_data.copy()
        # 確保 date 欄為 datetime
        df["date"] = pd.to_datetime(df["date"]) if df["date"].dtype != "datetime64[ns]" else df["date"]
        # 將查詢日期轉為 datetime 再比較
        from_dt = pd.to_datetime(from_date)
        to_dt = pd.to_datetime(to_date)
        mask = (df["date"] >= from_dt) & (df["date"] <= to_dt)
        df = df.loc[mask]

        if df.empty:
            return None

        df = self._process_historical_data(df, sort=sort)
        return {
            "status": "success",
            "data": df.to_dict("records"),
            "message": f"成功從本地數據獲取 {symbol} 從 {from_date} 到 {to_date} 的數據",
        }

    def _ensure_fresh_data(self, symbol: str, to_date: str = None, min_days: int = 0):
        """
        確保本地資料是最新的，如果過舊則自動從 API 更新。

        此方法會檢查本地快取的最新日期，如果距離目標日期超過 1 天（排除週末），
        則自動從 API 取得缺失的資料並合併到本地快取。

        Args:
            symbol (str): 股票代碼
            to_date (str, optional): 目標結束日期，格式 YYYY-MM-DD，預設為今天
            min_days (int, optional): 最少需要的資料天數，如果本地資料不足會嘗試補齊
        """
        import datetime

        try:
            # 設定目標日期
            if to_date:
                target_date = pd.to_datetime(to_date).date()
            else:
                target_date = datetime.date.today()

            # 讀取本地資料
            local_data = self._read_local_stock_data(symbol)

            need_fetch = False
            fetch_from = None
            fetch_to = target_date.strftime("%Y-%m-%d")

            if local_data is None or local_data.empty:
                # 本地沒有資料，需要從 API 獲取
                need_fetch = True
                # 預設獲取一年的資料
                fetch_from = (target_date - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
                self.logger.info(f"本地無 {symbol} 資料，將從 API 獲取")
            else:
                # 檢查本地資料的最新日期
                latest_local_date = local_data["date"].max()
                if hasattr(latest_local_date, "date"):
                    latest_local_date = latest_local_date.date()
                elif isinstance(latest_local_date, str):
                    latest_local_date = datetime.datetime.strptime(latest_local_date, "%Y-%m-%d").date()

                # 計算日期差距（排除週末的簡單判斷）
                days_diff = (target_date - latest_local_date).days

                # 如果最新資料日期比目標日期早超過 1 天（考慮週末為 3 天），則更新
                # 週一到週五，如果差距 > 1 天就更新
                # 週末則允許差距 > 3 天
                weekday = target_date.weekday()
                max_allowed_diff = 3 if weekday == 0 else 1  # 週一允許 3 天差距

                if days_diff > max_allowed_diff:
                    need_fetch = True
                    # 從本地最新日期的下一天開始取
                    fetch_from = (latest_local_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    self.logger.info(f"{symbol} 本地資料過舊（最新: {latest_local_date}），將更新至 {fetch_to}")

                # 檢查資料是否足夠
                if min_days > 0 and len(local_data) < min_days:
                    need_fetch = True
                    # 計算需要多少天的資料
                    oldest_local_date = local_data["date"].min()
                    if hasattr(oldest_local_date, "date"):
                        oldest_local_date = oldest_local_date.date()
                    # 往前取更多資料
                    extra_days = min_days - len(local_data) + 30  # 多取 30 天緩衝
                    new_from = (oldest_local_date - datetime.timedelta(days=extra_days)).strftime("%Y-%m-%d")
                    if fetch_from is None or new_from < fetch_from:
                        fetch_from = new_from
                    self.logger.info(f"{symbol} 資料不足 {min_days} 天，將補充資料")

            # 如果需要更新，從 API 取得新資料
            if need_fetch and fetch_from:
                try:
                    new_data = self._fetch_api_historical_data(symbol, fetch_from, fetch_to)

                    if new_data and len(new_data) > 0:
                        # 處理並保存到本地
                        df = pd.DataFrame(new_data)
                        df = self._process_historical_data(df)
                        self._save_to_local_db(symbol, df.to_dict("records"))
                        self.logger.info(f"成功更新 {symbol} 資料，新增 {len(new_data)} 筆")

                except Exception as e:
                    self.logger.warning(f"從 API 更新 {symbol} 資料失敗: {e}")
                    # 更新失敗不拋出異常，繼續使用現有資料

        except Exception as e:
            self.logger.warning(f"檢查資料新鮮度時發生錯誤: {e}")
            # 不拋出異常，繼續使用現有資料

    def _fetch_api_historical_data(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        *,
        timeframe: Optional[str] = None,
        adjusted: Optional[bool] = None,
        fields: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> list:
        """從 API 獲取歷史數據"""
        from_datetime = pd.to_datetime(from_date)
        to_datetime = pd.to_datetime(to_date)
        date_diff = (to_datetime - from_datetime).days

        all_data = []

        if date_diff > 365 - 1:
            # 分段獲取數據
            current_from = from_datetime
            while current_from < to_datetime:
                current_to = min(current_from + pd.Timedelta(days=365 - 1), to_datetime)
                segment_data = self._fetch_historical_data_segment(
                    symbol,
                    current_from.strftime("%Y-%m-%d"),
                    current_to.strftime("%Y-%m-%d"),
                    timeframe=timeframe,
                    adjusted=adjusted,
                    fields=fields,
                    sort=sort,
                )
                all_data.extend(segment_data)
                current_from = current_to + pd.Timedelta(days=1)
        else:
            # 直接獲取數據
            all_data = self._fetch_historical_data_segment(
                symbol,
                from_date,
                to_date,
                timeframe=timeframe,
                adjusted=adjusted,
                fields=fields,
                sort=sort,
            )

        return all_data

    def _fetch_historical_data_segment(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        *,
        timeframe: Optional[str] = None,
        adjusted: Optional[bool] = None,
        fields: Optional[str] = None,
        sort: Optional[str] = None,
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
            if timeframe is not None:
                params["timeframe"] = timeframe
            if adjusted is not None:
                params["adjusted"] = "true" if adjusted else "false"
            if fields is not None:
                params["fields"] = fields
            if sort is not None:
                params["sort"] = sort
            self.logger.debug("正在獲取 %s 從 %s 到 %s 的數據...", symbol, params["from"], params["to"])
            response = self.reststock.historical.candles(**params)
            self.logger.debug("API 回應內容: %s", response)

            # 支援 SDK 物件回傳 (is_success/.data) 與 dict 形式回傳
            if hasattr(response, "is_success"):
                if response.is_success:
                    data = response.data if hasattr(response, "data") else getattr(response, "result", None)
                    if data:
                        segment_data = data
                        self.logger.info("成功獲取 %d 筆資料", len(segment_data))
                        return segment_data
                    else:
                        self.logger.warning("API 回應無資料 (object): %s", response)
                else:
                    # 嘗試從 message 獲取錯誤資訊
                    msg = getattr(response, "message", None)
                    self.logger.warning("API 回應失敗 (object): %s", msg)
            elif isinstance(response, dict):
                if "data" in response and response["data"]:
                    segment_data = response["data"]
                    self.logger.info("成功獲取 %d 筆資料", len(segment_data))
                    return segment_data
                else:
                    self.logger.warning("API 回應無資料 (dict): %s", response)
            else:
                self.logger.warning("API 回應格式錯誤: %s", response)
        except Exception as segment_error:
            self.logger.exception("獲取分段資料時發生錯誤: %s", segment_error)

        return []

    def _process_historical_data(self, df: pd.DataFrame, sort: str = "desc") -> pd.DataFrame:
        """
        處理歷史數據，添加計算欄位。

        Args:
            df (pd.DataFrame): 原始數據

        Returns:
            pd.DataFrame: 處理後的數據
        """
        df = df.sort_values(by="date", ascending=sort == "asc")
        # 添加更多資訊欄位；當 API 使用 fields 過濾欄位時，不因缺少
        # open/close/volume 而讓整個查詢失敗。
        if "close" in df.columns and "volume" in df.columns:
            df["vol_value"] = df["close"] * df["volume"]  # 成交值
        if "close" in df.columns and "open" in df.columns:
            df["price_change"] = df["close"] - df["open"]  # 漲跌
            df["change_ratio"] = np.where(
                df["open"] == 0,
                0.0,
                (df["price_change"] / df["open"]) * 100,
            )
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

        except Exception:
            self.logger.exception("讀取SQLite數據時發生錯誤")
            return None

    def _save_to_local_db(self, symbol: str, new_data: list):
        """
        將新的股票數據保存到本地 SQLite 數據庫(stock_historical_data)，避免重複數據。

        參數:
            symbol (str): 股票代碼
            new_data (list): 新的股票數據列表 (dict 序列)
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
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO stock_historical_data 
                        (symbol, date, open, high, low, close, volume, vol_value, price_change, change_ratio)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            symbol,
                            date_str,
                            record.get("open"),
                            record.get("high"),
                            record.get("low"),
                            record.get("close"),
                            record.get("volume"),
                            record.get("vol_value"),
                            record.get("price_change"),
                            record.get("change_ratio"),
                        ),
                    )

                conn.commit()
                self.logger.info("成功保存數據到SQLite: %s, %d 筆記錄", symbol, len(new_data))

        except Exception:
            self.logger.exception("保存SQLite數據時發生錯誤")

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
                data["securityTypeName"] = security_type_mapping.get(security_type_code, f"未知代碼({security_type_code})")

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
            self.logger.debug("API params: %s", api_params)

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
                        product_info = {k: v for k, v in product_info.items() if v is not None}
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
                        ticker_info = {k: v for k, v in ticker_info.items() if v is not None}
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
            symbol (str): 合約代碼，例如 "XAFF6" 等
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
        """
        專業級多因子交易訊號引擎（量化交易增強版）

        整合多時間框架分析、多因子評分系統、風險評估、進出場策略建議。
        自動確保資料是最新的，如果本地資料過舊或不足會自動從 API 更新。

        Returns:
            dict: 成功時返回完整的交易分析報告，包含：
                - overall_signal: 整體訊號 (strong_buy/buy/neutral/sell/strong_sell)
                - signal_score: 綜合評分 (-100 到 +100)
                - confidence: 信心度 (high/medium/low)
                - trend_analysis: 多時間框架趨勢分析
                - technical_indicators: 完整技術指標數據
                - momentum_analysis: 動量分析
                - volume_analysis: 成交量分析
                - support_resistance: 支撐壓力位
                - risk_metrics: 風險指標
                - entry_exit_strategy: 進出場策略
                - multi_factor_scores: 多因子評分詳情
                - pattern_recognition: K線型態識別
        """
        try:
            params = GetTradingSignalsArgs(**args)
            symbol = params.symbol

            # 技術指標分析需要的最少資料天數
            MIN_REQUIRED_DAYS = 220  # 200日均線 + 20天緩衝

            # 確保資料是最新且足夠的（自動從 API 更新）
            self._ensure_fresh_data(symbol, min_days=MIN_REQUIRED_DAYS)

            # 讀取更長週期的資料
            df_daily = self._read_local_stock_data(symbol)
            if df_daily is None or df_daily.empty:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"無法取得 {symbol} 歷史資料，請確認股票代碼正確且 API 服務正常",
                }

            if len(df_daily) < 50:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"資料筆數不足（目前 {len(df_daily)} 筆，需要至少 50 筆），可能是新上市股票或 API 暫時無法取得資料",
                }

            # 確保有 open 欄位
            if "open" not in df_daily.columns:
                df_daily = df_daily.copy()
                df_daily["open"] = df_daily["close"]

            # === 建立多時間框架資料 ===
            df_weekly = (
                df_daily.resample("W-FRI", on="date")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
                .reset_index()
            )

            df_monthly = (
                df_daily.resample("ME", on="date")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
                .reset_index()
            )

            # 日期過濾
            df = df_daily.sort_values("date")
            if getattr(params, "from_date", None):
                df = df[df["date"] >= pd.to_datetime(params.from_date)]
            if getattr(params, "to_date", None):
                df = df[df["date"] <= pd.to_datetime(params.to_date)]
            if len(df) < 50:
                return {"status": "error", "data": None, "message": f"指定日期範圍內資料筆數不足 50 筆（目前 {len(df)} 筆）"}

            close = df["close"]
            high = df["high"]
            low = df["low"]
            open_price = df["open"]
            volume = df["volume"]
            dates = df["date"]

            # === 計算完整技術指標 ===
            # 布林通道
            bb = indicators.calculate_bollinger_bands(close, period=20, stddev=2.0)

            # RSI 多週期
            rsi_14 = indicators.calculate_rsi(close, period=14)
            rsi_7 = indicators.calculate_rsi(close, period=7)
            rsi_21 = indicators.calculate_rsi(close, period=21)

            # MACD
            macd_res = indicators.calculate_macd(close, fast=12, slow=26, signal=9)

            # KD 隨機指標
            kd = indicators.calculate_kd(high, low, close, period=9, smooth_k=3, smooth_d=3)

            # 移動平均線系統
            ema5 = close.ewm(span=5, adjust=False).mean()
            ema10 = close.ewm(span=10, adjust=False).mean()
            ema20 = close.ewm(span=20, adjust=False).mean()
            ema50 = close.ewm(span=50, adjust=False).mean()
            ema60 = close.ewm(span=60, adjust=False).mean()
            ema120 = close.ewm(span=120, adjust=False).mean()
            ema200 = close.ewm(span=200, adjust=False).mean()
            sma20 = close.rolling(20).mean()
            sma60 = close.rolling(60).mean()

            # ATR 波動率
            atr = indicators.calculate_atr(high, low, close, period=14)
            atr_percent = atr / close * 100

            # ADX 趨勢強度
            adx = indicators.calculate_adx(high, low, close, period=14)

            # Williams %R
            williams_r = indicators.calculate_williams_r(high, low, close, period=14)

            # CCI 順勢指標
            cci = indicators.calculate_cci(high, low, close, period=20)

            # ROC 變動率
            roc = indicators.calculate_roc(close, period=10)

            # OBV 能量潮
            obv = indicators.calculate_obv(close, volume)
            obv_ema = obv.ewm(span=20, adjust=False).mean()

            # 成交量分析
            vol_sma20 = volume.rolling(20).mean()
            vol_sma5 = volume.rolling(5).mean()
            vol_rate = volume / vol_sma20.replace(0, np.nan)

            # === 計算支撐壓力位 ===
            recent_high = high.tail(60).max()
            recent_low = low.tail(60).min()
            pivot = (recent_high + recent_low + close.iloc[-1]) / 3
            r1 = 2 * pivot - recent_low
            r2 = pivot + (recent_high - recent_low)
            r3 = recent_high + 2 * (pivot - recent_low)
            s1 = 2 * pivot - recent_high
            s2 = pivot - (recent_high - recent_low)
            s3 = recent_low - 2 * (recent_high - pivot)

            # === 多時間框架趨勢分析 ===
            # 日線趨勢
            daily_trend = "up" if close.iloc[-1] > ema20.iloc[-1] else "down"
            daily_trend_strength = abs(close.iloc[-1] - ema20.iloc[-1]) / ema20.iloc[-1] * 100

            # 週線趨勢
            weekly_close = df_weekly["close"].iloc[-1] if len(df_weekly) > 0 else close.iloc[-1]
            weekly_ma10 = df_weekly["close"].rolling(10).mean().iloc[-1] if len(df_weekly) >= 10 else weekly_close
            weekly_trend = "up" if weekly_close > weekly_ma10 else "down"

            # 月線趨勢
            monthly_close = df_monthly["close"].iloc[-1] if len(df_monthly) > 0 else close.iloc[-1]
            monthly_ma6 = df_monthly["close"].rolling(6).mean().iloc[-1] if len(df_monthly) >= 6 else monthly_close
            monthly_trend = "up" if monthly_close > monthly_ma6 else "down"

            # 均線多頭/空頭排列
            ma_alignment = self._check_ma_alignment(
                close.iloc[-1], ema5.iloc[-1], ema10.iloc[-1], ema20.iloc[-1], ema60.iloc[-1]
            )

            # === 構建最新數據快照 ===
            latest = {
                "date": dates.iloc[-1],
                "close": float(close.iloc[-1]),
                "open": float(open_price.iloc[-1]),
                "high": float(high.iloc[-1]),
                "low": float(low.iloc[-1]),
                "volume": int(volume.iloc[-1]),
                "change_percent": float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) > 1 else 0,
            }

            # === 多因子評分系統 ===
            factor_scores = {}
            reasons = []
            total_score = 0

            # 1. 趨勢因子 (權重: 30%)
            trend_score = self._calculate_trend_score(
                close=close.iloc[-1],
                ema20=ema20.iloc[-1],
                ema50=ema50.iloc[-1],
                ema200=ema200.iloc[-1],
                adx=adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20,
                weekly_trend=weekly_trend,
                monthly_trend=monthly_trend,
                ma_alignment=ma_alignment,
            )
            factor_scores["trend"] = trend_score
            total_score += trend_score["score"] * 0.30

            # 2. 動量因子 (權重: 25%)
            momentum_score = self._calculate_momentum_score(
                rsi=rsi_14.iloc[-1],
                rsi_prev=rsi_14.iloc[-2] if len(rsi_14) > 1 else 50,
                macd=macd_res["macd"].iloc[-1],
                macd_signal=macd_res["signal"].iloc[-1],
                macd_hist=macd_res["histogram"].iloc[-1],
                macd_hist_prev=macd_res["histogram"].iloc[-2] if len(macd_res["histogram"]) > 1 else 0,
                k=kd["k"].iloc[-1],
                d=kd["d"].iloc[-1],
                k_prev=kd["k"].iloc[-2] if len(kd["k"]) > 1 else 50,
                d_prev=kd["d"].iloc[-2] if len(kd["d"]) > 1 else 50,
                williams_r=williams_r.iloc[-1] if not pd.isna(williams_r.iloc[-1]) else -50,
                cci=cci.iloc[-1] if not pd.isna(cci.iloc[-1]) else 0,
                roc=roc.iloc[-1] if not pd.isna(roc.iloc[-1]) else 0,
            )
            factor_scores["momentum"] = momentum_score
            total_score += momentum_score["score"] * 0.25

            # 3. 波動率/布林因子 (權重: 15%)
            volatility_score = self._calculate_volatility_score(
                close=close.iloc[-1],
                bb_upper=bb["upper"].iloc[-1],
                bb_middle=bb["middle"].iloc[-1],
                bb_lower=bb["lower"].iloc[-1],
                bb_width=bb["width"].iloc[-1],
                bb_width_avg=bb["width"].rolling(20).mean().iloc[-1] if len(bb["width"]) >= 20 else bb["width"].iloc[-1],
                atr_percent=atr_percent.iloc[-1] if not pd.isna(atr_percent.iloc[-1]) else 2.0,
            )
            factor_scores["volatility"] = volatility_score
            total_score += volatility_score["score"] * 0.15

            # 4. 成交量因子 (權重: 15%)
            volume_score = self._calculate_volume_score(
                volume=volume.iloc[-1],
                vol_sma20=vol_sma20.iloc[-1] if not pd.isna(vol_sma20.iloc[-1]) else volume.iloc[-1],
                vol_rate=vol_rate.iloc[-1] if not pd.isna(vol_rate.iloc[-1]) else 1.0,
                obv=obv.iloc[-1],
                obv_ema=obv_ema.iloc[-1] if not pd.isna(obv_ema.iloc[-1]) else obv.iloc[-1],
                price_change=latest["change_percent"],
            )
            factor_scores["volume"] = volume_score
            total_score += volume_score["score"] * 0.15

            # 5. 價格位置因子 (權重: 15%)
            price_position_score = self._calculate_price_position_score(
                close=close.iloc[-1], recent_high=recent_high, recent_low=recent_low, pivot=pivot, r1=r1, s1=s1
            )
            factor_scores["price_position"] = price_position_score
            total_score += price_position_score["score"] * 0.15

            # === 綜合訊號判定 ===
            overall_signal, confidence, action_desc = self._determine_overall_signal(total_score, factor_scores)

            # 收集所有理由
            for factor_name, factor_data in factor_scores.items():
                reasons.extend(factor_data.get("reasons", []))

            # === K線型態識別 ===
            pattern = self._identify_candlestick_pattern(
                open_prices=open_price.tail(5).values,
                high_prices=high.tail(5).values,
                low_prices=low.tail(5).values,
                close_prices=close.tail(5).values,
            )

            # === 進出場策略建議 ===
            entry_exit = self._calculate_entry_exit_strategy(
                close=close.iloc[-1],
                atr=atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else close.iloc[-1] * 0.02,
                signal=overall_signal,
                s1=s1,
                s2=s2,
                r1=r1,
                r2=r2,
                recent_high=recent_high,
                recent_low=recent_low,
            )

            # === 風險指標 ===
            risk_metrics = self._calculate_risk_metrics(
                close=close,
                atr=atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else close.iloc[-1] * 0.02,
                atr_percent=atr_percent.iloc[-1] if not pd.isna(atr_percent.iloc[-1]) else 2.0,
                adx=adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20,
                bb_width=bb["width"].iloc[-1] if not pd.isna(bb["width"].iloc[-1]) else 0.1,
            )

            # === 組裝返回結果 ===
            return {
                "status": "success",
                "message": f"交易訊號分析成功: {symbol}",
                "data": {
                    "symbol": symbol,
                    "analysis_date": (
                        latest["date"].isoformat() if hasattr(latest["date"], "isoformat") else str(latest["date"])
                    ),
                    "current_price": latest["close"],
                    "change_percent": round(latest["change_percent"], 2),
                    # 核心訊號
                    "overall_signal": overall_signal,
                    "signal_score": round(total_score, 2),
                    "confidence": confidence,
                    "action_description": action_desc,
                    # 多時間框架趨勢
                    "trend_analysis": {
                        "daily_trend": daily_trend,
                        "daily_trend_strength": round(daily_trend_strength, 2),
                        "weekly_trend": weekly_trend,
                        "monthly_trend": monthly_trend,
                        "ma_alignment": ma_alignment,
                        "trend_consistency": self._check_trend_consistency(daily_trend, weekly_trend, monthly_trend),
                    },
                    # 完整技術指標
                    "technical_indicators": {
                        "moving_averages": {
                            "ema5": round(ema5.iloc[-1], 2),
                            "ema10": round(ema10.iloc[-1], 2),
                            "ema20": round(ema20.iloc[-1], 2),
                            "ema50": round(ema50.iloc[-1], 2) if not pd.isna(ema50.iloc[-1]) else None,
                            "ema60": round(ema60.iloc[-1], 2) if not pd.isna(ema60.iloc[-1]) else None,
                            "ema120": round(ema120.iloc[-1], 2) if not pd.isna(ema120.iloc[-1]) else None,
                            "ema200": round(ema200.iloc[-1], 2) if not pd.isna(ema200.iloc[-1]) else None,
                            "sma20": round(sma20.iloc[-1], 2) if not pd.isna(sma20.iloc[-1]) else None,
                            "sma60": round(sma60.iloc[-1], 2) if not pd.isna(sma60.iloc[-1]) else None,
                        },
                        "bollinger_bands": {
                            "upper": round(bb["upper"].iloc[-1], 2),
                            "middle": round(bb["middle"].iloc[-1], 2),
                            "lower": round(bb["lower"].iloc[-1], 2),
                            "width": round(bb["width"].iloc[-1], 4) if not pd.isna(bb["width"].iloc[-1]) else None,
                            "position": round(
                                (close.iloc[-1] - bb["lower"].iloc[-1]) / (bb["upper"].iloc[-1] - bb["lower"].iloc[-1] + 1e-8),
                                2,
                            ),
                        },
                        "oscillators": {
                            "rsi_7": round(rsi_7.iloc[-1], 2) if not pd.isna(rsi_7.iloc[-1]) else None,
                            "rsi_14": round(rsi_14.iloc[-1], 2) if not pd.isna(rsi_14.iloc[-1]) else None,
                            "rsi_21": round(rsi_21.iloc[-1], 2) if not pd.isna(rsi_21.iloc[-1]) else None,
                            "stoch_k": round(kd["k"].iloc[-1], 2) if not pd.isna(kd["k"].iloc[-1]) else None,
                            "stoch_d": round(kd["d"].iloc[-1], 2) if not pd.isna(kd["d"].iloc[-1]) else None,
                            "williams_r": round(williams_r.iloc[-1], 2) if not pd.isna(williams_r.iloc[-1]) else None,
                            "cci": round(cci.iloc[-1], 2) if not pd.isna(cci.iloc[-1]) else None,
                        },
                        "macd": {
                            "macd": round(macd_res["macd"].iloc[-1], 4) if not pd.isna(macd_res["macd"].iloc[-1]) else None,
                            "signal": (
                                round(macd_res["signal"].iloc[-1], 4) if not pd.isna(macd_res["signal"].iloc[-1]) else None
                            ),
                            "histogram": (
                                round(macd_res["histogram"].iloc[-1], 4)
                                if not pd.isna(macd_res["histogram"].iloc[-1])
                                else None
                            ),
                            "status": "bullish" if macd_res["histogram"].iloc[-1] > 0 else "bearish",
                        },
                        "trend_strength": {
                            "adx": round(adx.iloc[-1], 2) if not pd.isna(adx.iloc[-1]) else None,
                            "roc": round(roc.iloc[-1], 2) if not pd.isna(roc.iloc[-1]) else None,
                        },
                        "volatility": {
                            "atr": round(atr.iloc[-1], 2) if not pd.isna(atr.iloc[-1]) else None,
                            "atr_percent": round(atr_percent.iloc[-1], 2) if not pd.isna(atr_percent.iloc[-1]) else None,
                        },
                    },
                    # 成交量分析
                    "volume_analysis": {
                        "current_volume": int(volume.iloc[-1]),
                        "volume_sma20": int(vol_sma20.iloc[-1]) if not pd.isna(vol_sma20.iloc[-1]) else None,
                        "volume_ratio": round(vol_rate.iloc[-1], 2) if not pd.isna(vol_rate.iloc[-1]) else None,
                        "obv": int(obv.iloc[-1]),
                        "obv_trend": "up" if obv.iloc[-1] > obv_ema.iloc[-1] else "down",
                        "volume_status": self._get_volume_status_desc(
                            vol_rate.iloc[-1] if not pd.isna(vol_rate.iloc[-1]) else 1.0
                        ),
                    },
                    # 支撐壓力位
                    "support_resistance": {
                        "pivot": round(pivot, 2),
                        "resistance_1": round(r1, 2),
                        "resistance_2": round(r2, 2),
                        "resistance_3": round(r3, 2),
                        "support_1": round(s1, 2),
                        "support_2": round(s2, 2),
                        "support_3": round(s3, 2),
                        "recent_high_60d": round(recent_high, 2),
                        "recent_low_60d": round(recent_low, 2),
                    },
                    # 多因子評分詳情
                    "multi_factor_scores": factor_scores,
                    # K線型態
                    "pattern_recognition": pattern,
                    # 風險指標
                    "risk_metrics": risk_metrics,
                    # 進出場策略
                    "entry_exit_strategy": entry_exit,
                    # 分析理由
                    "reasons": reasons,
                },
            }

        except Exception as e:
            return {"status": "error", "data": None, "message": f"交易訊號計算失敗: {str(e)}"}

    def _check_ma_alignment(self, close: float, ema5: float, ema10: float, ema20: float, ema60: float) -> str:
        """檢查均線排列"""
        if close > ema5 > ema10 > ema20 > ema60:
            return "perfect_bullish"  # 完美多頭排列
        elif close > ema5 > ema10 > ema20:
            return "bullish"  # 多頭排列
        elif close < ema5 < ema10 < ema20 < ema60:
            return "perfect_bearish"  # 完美空頭排列
        elif close < ema5 < ema10 < ema20:
            return "bearish"  # 空頭排列
        else:
            return "mixed"  # 糾結

    def _check_trend_consistency(self, daily: str, weekly: str, monthly: str) -> str:
        """檢查多時間框架趨勢一致性"""
        trends = [daily, weekly, monthly]
        up_count = trends.count("up")
        if up_count == 3:
            return "strong_uptrend"
        elif up_count == 2:
            return "moderate_uptrend"
        elif up_count == 1:
            return "moderate_downtrend"
        else:
            return "strong_downtrend"

    def _calculate_trend_score(
        self,
        close: float,
        ema20: float,
        ema50: float,
        ema200: float,
        adx: float,
        weekly_trend: str,
        monthly_trend: str,
        ma_alignment: str,
    ) -> dict:
        """計算趨勢因子評分"""
        score = 0
        reasons = []

        # 價格與均線關係
        if close > ema200:
            score += 20
            reasons.append("價格站上200日均線（長期多頭）")
        else:
            score -= 20
            reasons.append("價格跌破200日均線（長期空頭）")

        if close > ema50:
            score += 15
            reasons.append("價格站上50日均線（中期多頭）")
        else:
            score -= 15

        if close > ema20:
            score += 10
            reasons.append("價格站上20日均線（短期多頭）")
        else:
            score -= 10

        # 均線排列
        if ma_alignment == "perfect_bullish":
            score += 25
            reasons.append("完美多頭排列")
        elif ma_alignment == "bullish":
            score += 15
            reasons.append("多頭排列")
        elif ma_alignment == "perfect_bearish":
            score -= 25
            reasons.append("完美空頭排列")
        elif ma_alignment == "bearish":
            score -= 15
            reasons.append("空頭排列")

        # ADX 趨勢強度
        if adx > 25:
            if score > 0:
                score += 10
                reasons.append(f"ADX={adx:.1f}，趨勢明確")
            else:
                score -= 10

        # 多時間框架確認
        if weekly_trend == "up" and monthly_trend == "up":
            score += 15
            reasons.append("週線月線同步向上")
        elif weekly_trend == "down" and monthly_trend == "down":
            score -= 15
            reasons.append("週線月線同步向下")

        return {"score": max(-100, min(100, score)), "reasons": reasons}

    def _calculate_momentum_score(
        self,
        rsi: float,
        rsi_prev: float,
        macd: float,
        macd_signal: float,
        macd_hist: float,
        macd_hist_prev: float,
        k: float,
        d: float,
        k_prev: float,
        d_prev: float,
        williams_r: float,
        cci: float,
        roc: float,
    ) -> dict:
        """計算動量因子評分"""
        score = 0
        reasons = []

        # RSI 分析
        if rsi < 30:
            score += 20
            reasons.append(f"RSI={rsi:.1f} 超賣區，反彈機會高")
        elif rsi > 70:
            score -= 20
            reasons.append(f"RSI={rsi:.1f} 超買區，回檔風險高")
        elif 40 <= rsi <= 60:
            reasons.append(f"RSI={rsi:.1f} 中性區間")

        # RSI 背離
        if rsi > rsi_prev and rsi < 40:
            score += 10
            reasons.append("RSI 低檔向上翻揚")
        elif rsi < rsi_prev and rsi > 60:
            score -= 10
            reasons.append("RSI 高檔向下翻轉")

        # MACD 分析
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            score += 20
            reasons.append("MACD 柱狀圖正值且放大（多頭動能增強）")
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            score -= 20
            reasons.append("MACD 柱狀圖負值且放大（空頭動能增強）")

        # MACD 金叉死叉
        if macd > macd_signal and macd_hist > 0 and macd_hist_prev <= 0:
            score += 15
            reasons.append("MACD 金叉確認")
        elif macd < macd_signal and macd_hist < 0 and macd_hist_prev >= 0:
            score -= 15
            reasons.append("MACD 死叉確認")

        # KD 分析
        if k < 20 and k > d and k_prev <= d_prev:
            score += 18
            reasons.append("KD 低檔金叉（強力買訊）")
        elif k > 80 and k < d and k_prev >= d_prev:
            score -= 18
            reasons.append("KD 高檔死叉（強力賣訊）")

        # Williams %R
        if williams_r < -80:
            score += 8
            reasons.append("Williams %R 超賣")
        elif williams_r > -20:
            score -= 8
            reasons.append("Williams %R 超買")

        # CCI
        if cci < -100:
            score += 8
            reasons.append("CCI 超賣區")
        elif cci > 100:
            score -= 8
            reasons.append("CCI 超買區")

        # ROC
        if roc > 5:
            score += 5
            reasons.append(f"ROC={roc:.1f}% 動能強勁")
        elif roc < -5:
            score -= 5
            reasons.append(f"ROC={roc:.1f}% 動能衰弱")

        return {"score": max(-100, min(100, score)), "reasons": reasons}

    def _calculate_volatility_score(
        self,
        close: float,
        bb_upper: float,
        bb_middle: float,
        bb_lower: float,
        bb_width: float,
        bb_width_avg: float,
        atr_percent: float,
    ) -> dict:
        """計算波動率/布林因子評分"""
        score = 0
        reasons = []

        # 布林通道位置
        bb_position = (close - bb_lower) / (bb_upper - bb_lower + 1e-8)

        if bb_position < 0.1:
            score += 20
            reasons.append("價格觸及布林下軌（超賣反彈機會）")
        elif bb_position > 0.9:
            score -= 20
            reasons.append("價格觸及布林上軌（超買回檔風險）")
        elif 0.4 <= bb_position <= 0.6:
            reasons.append("價格位於布林通道中軌附近")

        # 布林通道寬度變化（收窄後擴張是突破訊號）
        width_ratio = bb_width / bb_width_avg if bb_width_avg > 0 else 1

        if width_ratio < 0.7:
            score += 10
            reasons.append("布林通道收窄（醞釀突破）")
        elif width_ratio > 1.5:
            if bb_position > 0.7:
                score += 15
                reasons.append("布林通道擴張向上突破")
            elif bb_position < 0.3:
                score -= 15
                reasons.append("布林通道擴張向下突破")

        # ATR 波動率
        if atr_percent > 5:
            reasons.append(f"ATR%={atr_percent:.1f}% 高波動（風險較高）")
        elif atr_percent < 1.5:
            reasons.append(f"ATR%={atr_percent:.1f}% 低波動")

        return {"score": max(-100, min(100, score)), "reasons": reasons}

    def _calculate_volume_score(
        self, volume: int, vol_sma20: float, vol_rate: float, obv: float, obv_ema: float, price_change: float
    ) -> dict:
        """計算成交量因子評分"""
        score = 0
        reasons = []

        # 量比分析
        if vol_rate > 2.0:
            if price_change > 0:
                score += 25
                reasons.append(f"爆量上漲（量比={vol_rate:.1f}），多頭強勢")
            else:
                score -= 15
                reasons.append(f"爆量下跌（量比={vol_rate:.1f}），可能出貨")
        elif vol_rate > 1.5:
            if price_change > 0:
                score += 15
                reasons.append(f"量增價漲（量比={vol_rate:.1f}）")
            else:
                score -= 10
                reasons.append(f"量增價跌（量比={vol_rate:.1f}）")
        elif vol_rate < 0.5:
            score -= 5
            reasons.append(f"量能萎縮（量比={vol_rate:.1f}）")

        # OBV 趨勢
        if obv > obv_ema:
            score += 10
            reasons.append("OBV 向上（資金流入）")
        else:
            score -= 10
            reasons.append("OBV 向下（資金流出）")

        return {"score": max(-100, min(100, score)), "reasons": reasons}

    def _calculate_price_position_score(
        self, close: float, recent_high: float, recent_low: float, pivot: float, r1: float, s1: float
    ) -> dict:
        """計算價格位置因子評分"""
        score = 0
        reasons = []

        # 相對位置
        price_range = recent_high - recent_low
        if price_range > 0:
            position_percent = (close - recent_low) / price_range * 100

            if position_percent > 90:
                score -= 15
                reasons.append(f"價格位於近期高點附近（{position_percent:.0f}%），追高風險")
            elif position_percent < 10:
                score += 15
                reasons.append(f"價格位於近期低點附近（{position_percent:.0f}%），逢低機會")
            elif 40 <= position_percent <= 60:
                reasons.append(f"價格位於近期區間中部（{position_percent:.0f}%）")

        # 支撐壓力分析
        if close > r1:
            score += 10
            reasons.append("價格突破第一壓力位")
        elif close < s1:
            score -= 10
            reasons.append("價格跌破第一支撐位")
        elif close > pivot:
            score += 5
            reasons.append("價格站上樞紐點")
        else:
            score -= 5
            reasons.append("價格位於樞紐點下方")

        return {"score": max(-100, min(100, score)), "reasons": reasons}

    def _determine_overall_signal(self, total_score: float, factor_scores: dict) -> tuple:
        """根據總分決定整體訊號"""
        # 計算因子一致性
        positive_factors = sum(1 for f in factor_scores.values() if f["score"] > 10)
        negative_factors = sum(1 for f in factor_scores.values() if f["score"] < -10)

        if total_score >= 50:
            signal = "strong_buy"
            confidence = "high" if positive_factors >= 4 else "medium"
            desc = "強烈買進訊號，多項指標同步看多"
        elif total_score >= 25:
            signal = "buy"
            confidence = "medium" if positive_factors >= 3 else "low"
            desc = "偏多操作，可分批布局"
        elif total_score <= -50:
            signal = "strong_sell"
            confidence = "high" if negative_factors >= 4 else "medium"
            desc = "強烈賣出訊號，多項指標同步看空"
        elif total_score <= -25:
            signal = "sell"
            confidence = "medium" if negative_factors >= 3 else "low"
            desc = "偏空操作，建議減碼或觀望"
        else:
            signal = "neutral"
            confidence = "low"
            desc = "觀望為主，等待更明確訊號"

        return signal, confidence, desc

    def _identify_candlestick_pattern(
        self, open_prices: np.ndarray, high_prices: np.ndarray, low_prices: np.ndarray, close_prices: np.ndarray
    ) -> dict:
        """識別K線型態"""
        patterns = []

        if len(close_prices) < 3:
            return {"patterns": patterns, "signal": "none"}

        # 最近一根K線
        body = close_prices[-1] - open_prices[-1]
        upper_shadow = high_prices[-1] - max(open_prices[-1], close_prices[-1])
        lower_shadow = min(open_prices[-1], close_prices[-1]) - low_prices[-1]
        body_size = abs(body)
        total_range = high_prices[-1] - low_prices[-1]

        # 錘子線/吊人線
        if lower_shadow > body_size * 2 and upper_shadow < body_size * 0.5 and total_range > 0:
            if close_prices[-1] < close_prices[-2]:  # 下跌趨勢後
                patterns.append({"name": "hammer", "signal": "bullish", "description": "錘子線（反轉買訊）"})
            else:
                patterns.append({"name": "hanging_man", "signal": "bearish", "description": "吊人線（反轉賣訊）"})

        # 倒錘子線/射擊之星
        if upper_shadow > body_size * 2 and lower_shadow < body_size * 0.5 and total_range > 0:
            if close_prices[-1] < close_prices[-2]:
                patterns.append({"name": "inverted_hammer", "signal": "bullish", "description": "倒錘子線"})
            else:
                patterns.append({"name": "shooting_star", "signal": "bearish", "description": "射擊之星（反轉賣訊）"})

        # 十字星
        if body_size < total_range * 0.1 and total_range > 0:
            patterns.append({"name": "doji", "signal": "neutral", "description": "十字星（猶豫訊號）"})

        # 吞噬型態
        if len(close_prices) >= 2:
            prev_body = close_prices[-2] - open_prices[-2]
            curr_body = close_prices[-1] - open_prices[-1]

            if prev_body < 0 and curr_body > 0 and abs(curr_body) > abs(prev_body):
                if open_prices[-1] <= close_prices[-2] and close_prices[-1] >= open_prices[-2]:
                    patterns.append({"name": "bullish_engulfing", "signal": "bullish", "description": "多頭吞噬（強力買訊）"})

            if prev_body > 0 and curr_body < 0 and abs(curr_body) > abs(prev_body):
                if open_prices[-1] >= close_prices[-2] and close_prices[-1] <= open_prices[-2]:
                    patterns.append({"name": "bearish_engulfing", "signal": "bearish", "description": "空頭吞噬（強力賣訊）"})

        # 判斷整體型態訊號
        bullish_count = sum(1 for p in patterns if p["signal"] == "bullish")
        bearish_count = sum(1 for p in patterns if p["signal"] == "bearish")

        if bullish_count > bearish_count:
            overall_signal = "bullish"
        elif bearish_count > bullish_count:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        return {"patterns": patterns, "signal": overall_signal}

    def _calculate_entry_exit_strategy(
        self,
        close: float,
        atr: float,
        signal: str,
        s1: float,
        s2: float,
        r1: float,
        r2: float,
        recent_high: float,
        recent_low: float,
    ) -> dict:
        """計算進出場策略"""
        strategy = {}

        if signal in ["strong_buy", "buy"]:
            strategy["action"] = "買進"
            strategy["entry_price"] = round(close, 2)
            strategy["stop_loss"] = round(max(close - 2 * atr, s1), 2)
            strategy["stop_loss_percent"] = round((close - strategy["stop_loss"]) / close * 100, 2)
            strategy["target_1"] = round(min(close + 1.5 * atr, r1), 2)
            strategy["target_2"] = round(min(close + 3 * atr, r2), 2)
            strategy["risk_reward_ratio"] = (
                round((strategy["target_1"] - close) / (close - strategy["stop_loss"]), 2)
                if close > strategy["stop_loss"]
                else 0
            )
            strategy["position_suggestion"] = "建議分批進場，首次進場 1/3 倉位"
        elif signal in ["strong_sell", "sell"]:
            strategy["action"] = "賣出/放空"
            strategy["entry_price"] = round(close, 2)
            strategy["stop_loss"] = round(min(close + 2 * atr, r1), 2)
            strategy["stop_loss_percent"] = round((strategy["stop_loss"] - close) / close * 100, 2)
            strategy["target_1"] = round(max(close - 1.5 * atr, s1), 2)
            strategy["target_2"] = round(max(close - 3 * atr, s2), 2)
            strategy["risk_reward_ratio"] = (
                round((close - strategy["target_1"]) / (strategy["stop_loss"] - close), 2)
                if strategy["stop_loss"] > close
                else 0
            )
            strategy["position_suggestion"] = "建議減碼或分批放空"
        else:
            strategy["action"] = "觀望"
            strategy["entry_price"] = None
            strategy["stop_loss"] = None
            strategy["target_1"] = None
            strategy["target_2"] = None
            strategy["position_suggestion"] = "等待更明確訊號再進場"

        strategy["key_levels"] = {
            "nearest_support": round(s1, 2),
            "nearest_resistance": round(r1, 2),
            "strong_support": round(recent_low, 2),
            "strong_resistance": round(recent_high, 2),
        }

        return strategy

    def _calculate_risk_metrics(self, close: pd.Series, atr: float, atr_percent: float, adx: float, bb_width: float) -> dict:
        """計算風險指標"""
        # 計算最近的波動率
        returns = close.pct_change().dropna()
        volatility_20d = returns.tail(20).std() * np.sqrt(252) * 100 if len(returns) >= 20 else 0

        # 計算最大回撤
        rolling_max = close.expanding().max()
        drawdown = (close - rolling_max) / rolling_max
        max_drawdown = abs(drawdown.min()) * 100

        # 風險等級評估
        risk_score = 0
        if atr_percent > 4:
            risk_score += 2
        elif atr_percent > 2.5:
            risk_score += 1

        if volatility_20d > 40:
            risk_score += 2
        elif volatility_20d > 25:
            risk_score += 1

        if adx > 40:
            risk_score += 1  # 趨勢明確但波動大

        if risk_score >= 4:
            risk_level = "high"
        elif risk_score >= 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "volatility_20d": round(volatility_20d, 2),
            "max_drawdown_percent": round(max_drawdown, 2),
            "atr_percent": round(atr_percent, 2),
            "suggested_position_size": (
                "小倉位" if risk_level == "high" else ("中倉位" if risk_level == "medium" else "正常倉位")
            ),
        }

    def _get_volume_status_desc(self, vol_rate: float) -> str:
        """獲取成交量狀態描述"""
        if vol_rate >= 2.5:
            return "爆量"
        elif vol_rate >= 1.5:
            return "量增"
        elif vol_rate >= 0.8:
            return "正常"
        elif vol_rate >= 0.5:
            return "量縮"
        else:
            return "極度萎縮"

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
            result = self.sdk.stock.query_symbol_snapshot(account_obj, market_type_enum, stock_type_enums)

            if result and hasattr(result, "is_success") and result.is_success:
                data = self._normalize_result(result.data if hasattr(result, "data") else result)
                return {
                    "status": "success",
                    "data": data,
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

    def query_symbol_quote(self, args: Dict) -> dict:
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
            quote_result = self.sdk.stock.query_symbol_quote(account_obj, symbol, market_type_enum)

            if quote_result and hasattr(quote_result, "is_success") and quote_result.is_success:
                data = self._normalize_result(quote_result.data if hasattr(quote_result, "data") else quote_result)
                return {
                    "status": "success",
                    "data": data,
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

    def margin_quota(self, args: Dict) -> dict:
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
            if margin_quota_result and hasattr(margin_quota_result, "is_success") and margin_quota_result.is_success:
                data = self._normalize_result(
                    margin_quota_result.data if hasattr(margin_quota_result, "data") else margin_quota_result
                )
                return {
                    "status": "success",
                    "data": data,
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

    def daytrade_and_stock_info(self, args: Dict) -> dict:
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

            if daytrade_info and hasattr(daytrade_info, "is_success") and daytrade_info.is_success:
                data = self._normalize_result(daytrade_info.data if hasattr(daytrade_info, "data") else daytrade_info)
                return {
                    "status": "success",
                    "data": data,
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
        獲取台灣股市整體概況（量化交易增強版）

        整合台股指數行情、漲跌家數統計、成交量統計、市場廣度指標、
        趨勢判斷等量化交易者需要的市場整體資訊。

        Returns:
            dict: 成功時返回市場概況數據，包含：
                - index: 台股指數資訊 (名稱、代碼、價格、漲跌、成交量、開高低等)
                - statistics: 市場統計數據 (上漲/下跌家數、總成交量、市場狀態)
                - breadth: 市場廣度指標 (漲跌比、ADL、市場強度)
                - volume_analysis: 成交量分析 (量能狀態、量比、大戶動向)
                - trend: 趨勢指標 (短中長期趨勢、趨勢強度)
                - sentiment: 市場情緒指標 (恐懼貪婪指數、多空比)
                - signals: 量化交易訊號 (建議操作、信心度)
        """
        try:
            # 獲取台股指數行情
            tse_result = None
            try:
                tse_result = self.reststock.intraday.quote(symbol="IX0001")
            except Exception:
                try:
                    tse_result = self.reststock.intraday.ticker(symbol="IX0001")
                except Exception:
                    tse_result = None

            if (
                not tse_result
                or (hasattr(tse_result, "is_success") and not tse_result.is_success)
                or (isinstance(tse_result, dict) and not tse_result)
            ):
                return {
                    "status": "error",
                    "data": None,
                    "message": "無法獲取台股指數行情",
                }

            # 解析指數數據
            index_data = self._normalize_result(tse_result.data if hasattr(tse_result, "data") else tse_result)

            # 提取指數關鍵價格
            price = float(index_data.get("price") or index_data.get("close") or index_data.get("lastPrice") or 0)
            open_price = float(index_data.get("open") or index_data.get("openPrice") or 0)
            high_price = float(index_data.get("high") or index_data.get("highPrice") or 0)
            low_price = float(index_data.get("low") or index_data.get("lowPrice") or 0)
            prev_close = float(
                index_data.get("previousClose") or index_data.get("referencePrice") or index_data.get("prevClose") or 0
            )
            change = float(index_data.get("change") or index_data.get("chg") or 0)
            change_percent = float(
                index_data.get("change_percent") or index_data.get("chg_percent") or index_data.get("changePercent") or 0
            )

            # 獲取成交量
            volume_val = 0
            if isinstance(index_data.get("total"), dict):
                volume_val = int(
                    index_data.get("total", {}).get("trade_volume", 0)
                    or index_data.get("total", {}).get("tradeVolume", 0)
                    or 0
                )
            else:
                volume_val = int(
                    index_data.get("trade_volume") or index_data.get("tradeVolume") or index_data.get("volume") or 0
                )

            trade_value = 0
            if isinstance(index_data.get("total"), dict):
                trade_value = float(
                    index_data.get("total", {}).get("trade_value", 0) or index_data.get("total", {}).get("tradeValue", 0) or 0
                )
            else:
                trade_value = float(index_data.get("trade_value") or index_data.get("tradeValue") or 0)

            # === 獲取上漲/下跌股票數據（含詳細資訊）===
            up_stocks = []
            down_stocks = []
            up_count = 0
            down_count = 0

            # 上漲股票（使用漲跌幅排序）
            try:
                movers_up = self.reststock.snapshot.movers(market="TSE", direction="up", change="percent", type="COMMONSTOCK")
                if movers_up:
                    if isinstance(movers_up, dict) and "data" in movers_up:
                        up_stocks = movers_up["data"]
                    elif hasattr(movers_up, "data"):
                        up_stocks = movers_up.data if movers_up.data else []
                    up_count = len(up_stocks)
            except Exception:
                up_count = 0
                up_stocks = []

            # 下跌股票
            try:
                movers_down = self.reststock.snapshot.movers(
                    market="TSE", direction="down", change="percent", type="COMMONSTOCK"
                )
                if movers_down:
                    if isinstance(movers_down, dict) and "data" in movers_down:
                        down_stocks = movers_down["data"]
                    elif hasattr(movers_down, "data"):
                        down_stocks = movers_down.data if movers_down.data else []
                    down_count = len(down_stocks)
            except Exception:
                down_count = 0
                down_stocks = []

            # === 獲取成交量排行（分析大戶動向）===
            volume_leaders = []
            total_market_volume = 0
            try:
                actives_result = self.reststock.snapshot.actives(market="TSE", trade="volume", type="COMMONSTOCK")
                if actives_result:
                    if isinstance(actives_result, dict) and "data" in actives_result:
                        volume_leaders = actives_result["data"][:20] if actives_result["data"] else []
                    elif hasattr(actives_result, "data") and actives_result.data:
                        volume_leaders = list(actives_result.data)[:20]

                    # 計算前20大成交量總和
                    for item in volume_leaders:
                        if isinstance(item, dict):
                            vol = item.get("tradeVolume") or item.get("trade_volume") or 0
                        else:
                            vol = getattr(item, "tradeVolume", None) or getattr(item, "trade_volume", 0)
                        total_market_volume += int(vol)
            except Exception:
                volume_leaders = []

            # === 獲取成交值排行 ===
            value_leaders = []
            total_market_value = 0
            try:
                actives_value = self.reststock.snapshot.actives(market="TSE", trade="value", type="COMMONSTOCK")
                if actives_value:
                    if isinstance(actives_value, dict) and "data" in actives_value:
                        value_leaders = actives_value["data"][:20] if actives_value["data"] else []
                    elif hasattr(actives_value, "data") and actives_value.data:
                        value_leaders = list(actives_value.data)[:20]

                    for item in value_leaders:
                        if isinstance(item, dict):
                            val = item.get("tradeValue") or item.get("trade_value") or 0
                        else:
                            val = getattr(item, "tradeValue", None) or getattr(item, "trade_value", 0)
                        total_market_value += float(val)
            except Exception:
                value_leaders = []

            # === 計算市場廣度指標 ===
            total_stocks = up_count + down_count
            if total_stocks == 0:
                total_stocks = 1  # 避免除以零

            # 漲跌比 (Advance/Decline Ratio)
            ad_ratio = up_count / down_count if down_count > 0 else (float("inf") if up_count > 0 else 1.0)

            # 漲跌線 (ADL - Advance/Decline Line) - 簡化計算
            adl_value = up_count - down_count

            # 市場寬度 (Market Breadth) - 上漲股票佔比
            market_breadth = up_count / total_stocks

            # 上漲強度分析（計算平均漲跌幅）
            avg_up_pct = 0
            avg_down_pct = 0

            if up_stocks:
                up_pcts = []
                for stock in up_stocks[:50]:  # 取前50檔計算
                    if isinstance(stock, dict):
                        pct = stock.get("changePercent") or stock.get("change_percent") or 0
                    else:
                        pct = getattr(stock, "changePercent", None) or getattr(stock, "change_percent", 0)
                    up_pcts.append(float(pct))
                avg_up_pct = sum(up_pcts) / len(up_pcts) if up_pcts else 0

            if down_stocks:
                down_pcts = []
                for stock in down_stocks[:50]:
                    if isinstance(stock, dict):
                        pct = stock.get("changePercent") or stock.get("change_percent") or 0
                    else:
                        pct = getattr(stock, "changePercent", None) or getattr(stock, "change_percent", 0)
                    down_pcts.append(abs(float(pct)))
                avg_down_pct = sum(down_pcts) / len(down_pcts) if down_pcts else 0

            # 漲停/跌停數量
            limit_up_count = sum(1 for s in up_stocks if self._is_limit_up(s))
            limit_down_count = sum(1 for s in down_stocks if self._is_limit_down(s))

            # === 計算趨勢指標 ===
            # 日內趨勢判斷
            intraday_trend = "盤整"
            trend_strength = 0

            if price > 0 and open_price > 0:
                day_range = high_price - low_price if high_price > low_price else 0.01
                price_position = (price - low_price) / day_range if day_range > 0 else 0.5

                if price > open_price:
                    if price_position > 0.7:
                        intraday_trend = "強勢上漲"
                        trend_strength = 80 + (price_position - 0.7) * 66
                    else:
                        intraday_trend = "上漲"
                        trend_strength = 50 + price_position * 30
                elif price < open_price:
                    if price_position < 0.3:
                        intraday_trend = "強勢下跌"
                        trend_strength = -(80 + (0.3 - price_position) * 66)
                    else:
                        intraday_trend = "下跌"
                        trend_strength = -(50 + (1 - price_position) * 30)
                else:
                    intraday_trend = "盤整"
                    trend_strength = 0

            # === 計算市場情緒指標 ===
            # 多空比
            bull_bear_ratio = ad_ratio if ad_ratio != float("inf") else 10.0

            # 恐懼貪婪指數（0-100，50為中性）
            fear_greed_index = self._calculate_fear_greed(
                ad_ratio=ad_ratio,
                market_breadth=market_breadth,
                avg_up_pct=avg_up_pct,
                avg_down_pct=avg_down_pct,
                limit_up_count=limit_up_count,
                limit_down_count=limit_down_count,
                change_percent=change_percent,
            )

            # 情緒等級
            sentiment_level = self._get_sentiment_level(fear_greed_index)

            # === 量化交易訊號 ===
            signal_score = self._calculate_market_signal_score(
                change_percent=change_percent,
                ad_ratio=ad_ratio,
                market_breadth=market_breadth,
                fear_greed_index=fear_greed_index,
                trend_strength=trend_strength,
            )

            signal_action = self._get_signal_action(signal_score)
            signal_confidence = min(abs(signal_score), 100)

            # === 判斷市場狀態 ===
            # 根據時間和交易狀況判斷市場是否開盤
            market_status = "closed"
            if price > 0 and (up_count > 0 or down_count > 0):
                market_status = "open"
            elif price > 0:
                # 有價格但無漲跌家數，可能是盤前/盤後
                market_status = "pre_market" if volume_val == 0 else "after_hours"

            # === 組裝返回數據 ===
            market_data = {
                "index": {
                    "name": index_data.get("name", "發行量加權股價指數"),
                    "symbol": index_data.get("symbol", "IX0001"),
                    "price": price,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "prev_close": prev_close,
                    "change": change,
                    "change_percent": change_percent,
                    "volume": volume_val,
                    "trade_value": trade_value,
                    "last_updated": index_data.get("at") or index_data.get("updated_at") or index_data.get("lastUpdated"),
                },
                "statistics": {
                    "up_count": up_count,
                    "down_count": down_count,
                    "unchanged_count": max(0, 1000 - up_count - down_count),  # 估計值
                    "limit_up_count": limit_up_count,
                    "limit_down_count": limit_down_count,
                    "total_volume": total_market_volume,
                    "total_value": total_market_value,
                    "market_status": market_status,
                },
                "breadth": {
                    "advance_decline_ratio": round(ad_ratio, 2) if ad_ratio != float("inf") else "無限大",
                    "advance_decline_line": adl_value,
                    "market_breadth": round(market_breadth * 100, 2),  # 百分比
                    "avg_up_percent": round(avg_up_pct, 2),
                    "avg_down_percent": round(avg_down_pct, 2),
                    "breadth_strength": "強勢" if market_breadth > 0.6 else ("弱勢" if market_breadth < 0.4 else "中性"),
                },
                "volume_analysis": {
                    "volume_status": self._get_volume_status(volume_val, trade_value),
                    "top_volume_concentration": (
                        round(total_market_volume / max(volume_val, 1) * 100, 2) if volume_val > 0 else 0
                    ),
                    "top_value_concentration": (
                        round(total_market_value / max(trade_value, 1) * 100, 2) if trade_value > 0 else 0
                    ),
                    "large_cap_activity": "活躍" if len(value_leaders) > 10 else "低迷",
                },
                "trend": {
                    "intraday_trend": intraday_trend,
                    "trend_strength": round(trend_strength, 1),
                    "price_position": (
                        "高檔" if price > open_price * 1.01 else ("低檔" if price < open_price * 0.99 else "平盤附近")
                    ),
                    "volatility": round(((high_price - low_price) / open_price * 100) if open_price > 0 else 0, 2),
                },
                "sentiment": {
                    "fear_greed_index": round(fear_greed_index, 1),
                    "sentiment_level": sentiment_level,
                    "bull_bear_ratio": round(bull_bear_ratio, 2) if bull_bear_ratio < 100 else ">100",
                    "market_mood": self._get_market_mood(fear_greed_index, change_percent),
                },
                "signals": {
                    "action": signal_action,
                    "score": round(signal_score, 1),
                    "confidence": round(signal_confidence, 1),
                    "reasoning": self._get_signal_reasoning(
                        change_percent=change_percent,
                        ad_ratio=ad_ratio,
                        market_breadth=market_breadth,
                        fear_greed_index=fear_greed_index,
                    ),
                },
            }

            return {
                "status": "success",
                "data": market_data,
                "message": "成功獲取台灣股市整體概況（量化分析版）",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取市場概況時發生錯誤: {str(e)}",
            }

    def _is_limit_up(self, stock) -> bool:
        """判斷是否漲停"""
        if isinstance(stock, dict):
            change_pct = stock.get("changePercent") or stock.get("change_percent") or 0
        else:
            change_pct = getattr(stock, "changePercent", None) or getattr(stock, "change_percent", 0)
        return float(change_pct) >= 9.5  # 台股漲停約10%

    def _is_limit_down(self, stock) -> bool:
        """判斷是否跌停"""
        if isinstance(stock, dict):
            change_pct = stock.get("changePercent") or stock.get("change_percent") or 0
        else:
            change_pct = getattr(stock, "changePercent", None) or getattr(stock, "change_percent", 0)
        return float(change_pct) <= -9.5

    def _calculate_fear_greed(
        self,
        ad_ratio: float,
        market_breadth: float,
        avg_up_pct: float,
        avg_down_pct: float,
        limit_up_count: int,
        limit_down_count: int,
        change_percent: float,
    ) -> float:
        """計算恐懼貪婪指數（0-100）"""
        score = 50  # 基準值

        # 漲跌比貢獻 (±15)
        if ad_ratio != float("inf"):
            if ad_ratio > 2:
                score += 15
            elif ad_ratio > 1.5:
                score += 10
            elif ad_ratio > 1:
                score += 5
            elif ad_ratio < 0.5:
                score -= 15
            elif ad_ratio < 0.67:
                score -= 10
            elif ad_ratio < 1:
                score -= 5

        # 市場寬度貢獻 (±10)
        if market_breadth > 0.7:
            score += 10
        elif market_breadth > 0.6:
            score += 5
        elif market_breadth < 0.3:
            score -= 10
        elif market_breadth < 0.4:
            score -= 5

        # 平均漲跌幅強度 (±10)
        strength_diff = avg_up_pct - avg_down_pct
        if strength_diff > 2:
            score += 10
        elif strength_diff > 1:
            score += 5
        elif strength_diff < -2:
            score -= 10
        elif strength_diff < -1:
            score -= 5

        # 漲跌停貢獻 (±10)
        limit_diff = limit_up_count - limit_down_count
        if limit_diff > 20:
            score += 10
        elif limit_diff > 10:
            score += 5
        elif limit_diff < -20:
            score -= 10
        elif limit_diff < -10:
            score -= 5

        # 指數漲跌幅貢獻 (±5)
        if change_percent > 1:
            score += 5
        elif change_percent > 0.5:
            score += 2
        elif change_percent < -1:
            score -= 5
        elif change_percent < -0.5:
            score -= 2

        return max(0, min(100, score))

    def _get_sentiment_level(self, fear_greed_index: float) -> str:
        """獲取情緒等級"""
        if fear_greed_index >= 80:
            return "極度貪婪"
        elif fear_greed_index >= 60:
            return "貪婪"
        elif fear_greed_index >= 45:
            return "中性"
        elif fear_greed_index >= 25:
            return "恐懼"
        else:
            return "極度恐懼"

    def _get_volume_status(self, volume: int, value: float) -> str:
        """獲取量能狀態"""
        # 這裡可以根據歷史平均成交量來比較，目前簡化處理
        if value > 200000000000:  # 2000億以上
            return "量能充沛"
        elif value > 150000000000:  # 1500億以上
            return "量能正常"
        elif value > 100000000000:  # 1000億以上
            return "量能偏低"
        else:
            return "量能萎縮"

    def _calculate_market_signal_score(
        self, change_percent: float, ad_ratio: float, market_breadth: float, fear_greed_index: float, trend_strength: float
    ) -> float:
        """計算市場訊號分數（-100 到 +100）"""
        score = 0

        # 指數漲跌幅貢獻 (±25)
        score += change_percent * 10
        score = max(-25, min(25, score))

        # 漲跌比貢獻 (±25)
        if ad_ratio != float("inf"):
            ratio_score = (ad_ratio - 1) * 20
            score += max(-25, min(25, ratio_score))

        # 市場寬度貢獻 (±20)
        breadth_score = (market_breadth - 0.5) * 40
        score += max(-20, min(20, breadth_score))

        # 恐懼貪婪指數貢獻 (±15)
        fg_score = (fear_greed_index - 50) * 0.3
        score += max(-15, min(15, fg_score))

        # 趨勢強度貢獻 (±15)
        score += trend_strength * 0.15

        return max(-100, min(100, score))

    def _get_signal_action(self, score: float) -> str:
        """獲取交易訊號建議"""
        if score >= 50:
            return "強烈看多"
        elif score >= 25:
            return "偏多操作"
        elif score >= 10:
            return "謹慎偏多"
        elif score >= -10:
            return "觀望"
        elif score >= -25:
            return "謹慎偏空"
        elif score >= -50:
            return "偏空操作"
        else:
            return "強烈看空"

    def _get_market_mood(self, fear_greed_index: float, change_percent: float) -> str:
        """獲取市場氛圍描述"""
        if fear_greed_index >= 70 and change_percent > 0.5:
            return "亢奮追漲"
        elif fear_greed_index >= 60:
            return "樂觀進取"
        elif fear_greed_index <= 30 and change_percent < -0.5:
            return "恐慌殺跌"
        elif fear_greed_index <= 40:
            return "悲觀保守"
        else:
            return "理性觀望"

    def _get_signal_reasoning(
        self, change_percent: float, ad_ratio: float, market_breadth: float, fear_greed_index: float
    ) -> List[str]:
        """獲取訊號理由"""
        reasons = []

        if change_percent > 1:
            reasons.append("指數強勢上漲")
        elif change_percent < -1:
            reasons.append("指數明顯下跌")

        if ad_ratio != float("inf"):
            if ad_ratio > 2:
                reasons.append("漲跌比極佳，多頭佔優")
            elif ad_ratio < 0.5:
                reasons.append("漲跌比極差，空頭主導")

        if market_breadth > 0.7:
            reasons.append("市場普漲，廣度良好")
        elif market_breadth < 0.3:
            reasons.append("市場普跌，廣度惡化")

        if fear_greed_index >= 75:
            reasons.append("情緒過熱，注意回調風險")
        elif fear_greed_index <= 25:
            reasons.append("情緒極度悲觀，可能超跌")

        if not reasons:
            reasons.append("市場表現中性，建議觀望")

        return reasons

    def _bb_position(self, close: float, upper: float, middle: float, lower: float) -> str:
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
        if latest["macd"] > latest["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
            return "金叉"
        if latest["macd"] < latest["macd_signal"] and prev["macd"] >= prev["macd_signal"]:
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
        bb_pos = self._bb_position(latest["close"], latest["bb_upper"], latest["bb_middle"], latest["bb_lower"])
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
    timeframe: Optional[str] = None
    adjusted: Optional[bool] = None
    fields: Optional[str] = None
    sort: str = Field(default="desc", pattern="^(asc|desc)$")


class CapitalChangesArgs(BaseModel):
    start_date: str
    end_date: str
    sort: Optional[str] = Field(default=None, pattern="^(asc|desc)$")


class DividendsArgs(BaseModel):
    start_date: str
    end_date: str


class ListingApplicantsArgs(BaseModel):
    start_date: str
    end_date: str
    sort: Optional[str] = Field(default=None, pattern="^(asc|desc)$")


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


class QuerySymbolSnapshotArgs(BaseModel):
    account: str
    market_type: str = "Common"
    stock_type: List[str] = Field(default_factory=lambda: ["Stock"])
