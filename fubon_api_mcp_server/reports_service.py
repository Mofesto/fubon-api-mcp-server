#!/usr/bin/env python3
"""
富邦證券報告服務

此模組提供交易報告和事件報告的查詢功能，包括：
- 所有報告總覽
- 委託報告
- 委託變更報告
- 成交報告
- 事件報告

主要組件：
- ReportsService: 報告服務類
- 報告數據管理
- 事件監聽和記錄
"""

from typing import Dict, List, Optional

from fubon_neo.sdk import FubonSDK
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .utils import validate_and_get_account

# 從 server.py 導入全局報告變數
# 注意：這些變數在 server.py 中定義，並由 SDK 回調函數更新
try:
    from .server import server_state
except ImportError:
    # 如果無法導入（例如在單獨測試時），創建空的列表
    class MockServerState:
        def __init__(self):
            self.latest_order_reports = []
            self.latest_order_changed_reports = []
            self.latest_filled_reports = []
            self.latest_event_reports = []

    server_state = MockServerState()


class ReportsService:
    """報告服務類"""

    def __init__(self, mcp: FastMCP, sdk: FubonSDK, accounts: List[str]):
        self.mcp = mcp
        self.sdk = sdk
        self.accounts = accounts

        # 注意：報告數據由 server.py 中的全局變數和 SDK 回調函數管理
        # 此處不維護自己的報告存儲

        self._register_tools()
        # 注意：回調函數已在 server.py 的 MCPServerState.initialize_sdk() 中設定

    def _register_tools(self):
        """註冊所有報告相關的工具"""
        self.mcp.tool()(self.get_all_reports)
        self.mcp.tool()(self.get_order_reports)
        self.mcp.tool()(self.get_order_changed_reports)
        self.mcp.tool()(self.get_filled_reports)
        self.mcp.tool()(self.get_event_reports)

    def get_all_reports(self, args: Dict) -> dict:
        """
        獲取所有報告

        返回所有類型的最新報告總覽。

        Returns:
            dict: 包含所有報告類型的字典
                - order_reports: 委託報告列表
                - order_changed_reports: 委託變更報告列表
                - filled_reports: 成交報告列表
                - event_reports: 事件報告列表

        Example:
            {}  # 無參數
        """
        try:
            return {
                "status": "success",
                "data": {
                    "order_reports": server_state.latest_order_reports.copy(),
                    "order_changed_reports": server_state.latest_order_changed_reports.copy(),
                    "filled_reports": server_state.latest_filled_reports.copy(),
                    "event_reports": server_state.latest_event_reports.copy(),
                },
                "message": "成功獲取所有報告",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取所有報告時發生錯誤: {str(e)}",
            }

    def get_order_reports(self, args: Dict) -> dict:
        """
        獲取委託報告

        獲取最新的委託報告列表。

        Returns:
            dict: 委託報告列表

        Example:
            {}  # 無參數
        """
        try:
            return {
                "status": "success",
                "data": server_state.latest_order_reports.copy(),
                "message": f"成功獲取委託報告，共 {len(server_state.latest_order_reports)} 筆",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取委託報告時發生錯誤: {str(e)}",
            }

    def get_order_changed_reports(self, args: Dict) -> dict:
        """
        獲取委託變更報告

        獲取最新的委託變更報告列表。

        Returns:
            dict: 委託變更報告列表

        Example:
            {}  # 無參數
        """
        try:
            return {
                "status": "success",
                "data": server_state.latest_order_changed_reports.copy(),
                "message": f"成功獲取委託變更報告，共 {len(server_state.latest_order_changed_reports)} 筆",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取委託變更報告時發生錯誤: {str(e)}",
            }

    def get_filled_reports(self, args: Dict) -> dict:
        """
        獲取成交報告

        獲取最新的成交報告列表。

        Returns:
            dict: 成交報告列表

        Example:
            {}  # 無參數
        """
        try:
            return {
                "status": "success",
                "data": server_state.latest_filled_reports.copy(),
                "message": f"成功獲取成交報告，共 {len(server_state.latest_filled_reports)} 筆",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取成交報告時發生錯誤: {str(e)}",
            }

    def get_event_reports(self, args: Dict) -> dict:
        """
        獲取事件報告

        獲取最新的系統事件報告列表。

        Returns:
            dict: 事件報告列表

        Example:
            {}  # 無參數
        """
        try:
            return {
                "status": "success",
                "data": server_state.latest_event_reports.copy(),
                "message": f"成功獲取事件報告，共 {len(server_state.latest_event_reports)} 筆",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取事件報告時發生錯誤: {str(e)}",
            }


# 參數模型定義
class GetOrderResultsArgs(BaseModel):
    account: str


class GetOrderResultsDetailArgs(BaseModel):
    account: str
    order_no: str
