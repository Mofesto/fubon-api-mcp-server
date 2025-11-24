#!/usr/bin/env python3
"""
富邦證券帳戶服務

此模組提供帳戶相關的查詢功能，包括：
- 帳戶基本資訊查詢
- 庫存查詢
- 銀行餘額查詢
- 維持率查詢
- 結算資訊查詢
- 當沖條件單查詢
- 移動鎖利歷史查詢
- 條件單歷史查詢

主要組件：
- AccountService: 帳戶服務類
- 帳戶資訊管理
- 庫存和餘額查詢
- 歷史記錄查詢
"""

from typing import Dict, List, Optional

from fubon_neo.sdk import FubonSDK
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .utils import validate_and_get_account


class AccountService:
    """帳戶服務類"""

    def __init__(self, mcp: FastMCP, sdk: FubonSDK, accounts: List[str]):
        self.mcp = mcp
        self.sdk = sdk
        self.accounts = accounts
        self._register_tools()

    def _to_dict(self, obj):
        """將 SDK 物件轉換為字典"""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, list):
            return [self._to_dict(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        try:
            # Try vars() first
            return {k: self._to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
        except Exception:
            # Fallback: try to extract common attributes using getattr
            common_attrs = [
                "name",
                "account",
                "branch_no",
                "account_type",
                "id_no",
                "status",
                "date",
                "stock_no",
                "order_type",
                "lastday_qty",
                "buy_qty",
                "buy_filled_qty",
                "buy_value",
                "today_qty",
                "tradable_qty",
                "sell_qty",
                "sell_filled_qty",
                "sell_value",
                "odd",
                "balance",
                "available_balance",
                "currency",
                "maintenance_ratio",
                "maintenance_summary",
                "maintenance_detail",
                "account_obj",
                "details",
                "settlement_date",
                "buy_value",
                "buy_fee",
                "buy_settlement",
                "buy_tax",
                "sell_value",
                "sell_fee",
                "sell_settlement",
                "sell_tax",
                "total_bs_value",
                "total_fee",
                "total_tax",
                "total_settlement_amount",
                "start_date",
                "end_date",
                "buy_sell",
                "filled_qty",
                "filled_price",
                "realized_profit",
                "realized_loss",
                "cost_price",
                "tradable_qty",
                "unrealized_profit",
                "unrealized_loss",
                "filled_avg_price",
                "realized_profit_and_loss",
            ]
            result = {}
            for attr in common_attrs:
                if hasattr(obj, attr):
                    result[attr] = self._to_dict(getattr(obj, attr))
            if result:
                return result
            else:
                return str(obj)

    def _register_tools(self):
        """註冊所有帳戶相關的工具"""
        self.mcp.tool()(self.get_account_info)
        self.mcp.tool()(self.get_inventory)
        self.mcp.tool()(self.get_bank_balance)
        self.mcp.tool()(self.get_maintenance)
        self.mcp.tool()(self.get_settlement_info)
        self.mcp.tool()(self.get_realized_pnl)
        self.mcp.tool()(self.get_realized_pnl_summary)
        self.mcp.tool()(self.get_unrealized_pnl)

    def get_account_info(self, args: Dict) -> dict:
        """
        獲取帳戶基本資訊

        Args:
            account (str): 帳戶號碼，如果為空則返回所有帳戶基本資訊
        """
        try:
            validated_args = GetAccountInfoArgs(**args)
            account = validated_args.account

            # 如果沒有指定帳戶，返回所有帳戶基本資訊
            if not account:
                # 初始化SDK來獲取帳戶列表
                _, error = validate_and_get_account("")  # 傳空字串來初始化
                from .config import accounts

                if not accounts or not hasattr(accounts, "data"):
                    return {
                        "status": "error",
                        "data": None,
                        "message": error or "帳戶資訊未初始化",
                    }
                return {
                    "status": "success",
                    "data": self._to_dict(accounts.data),
                    "message": "成功獲取所有帳戶基本資訊",
                }

            # 指定帳戶時，驗證並返回該帳戶資訊
            account_obj, error = validate_and_get_account(account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 返回帳戶對象的基本資訊
            account_info = self._to_dict(account_obj)

            return {
                "status": "success",
                "data": account_info,
                "message": f"成功獲取帳戶 {account} 基本資訊",
            }

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取帳戶資訊時發生錯誤: {str(e)}",
            }

    def get_inventory(self, args: Dict) -> dict:
        """
        獲取帳戶庫存資訊

        Args:
            account (str): 帳戶號碼
        """
        try:
            validated_args = GetInventoryArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取庫存
            result = self.sdk.accounting.inventories(account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": self._to_dict(result.data),
                    "message": f"成功獲取帳戶 {validated_args.account} 庫存明細",
                }
            else:
                error_msg = "獲取庫存明細失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取庫存明細失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取庫存明細時發生錯誤: {str(e)}",
            }

    def get_bank_balance(self, args: Dict) -> dict:
        """
        獲取帳戶銀行水位（資金餘額）

        Args:
            account (str): 帳戶號碼
        """
        try:
            validated_args = GetBankBalanceArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取銀行餘額
            result = self.sdk.accounting.bank_remain(account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": self._to_dict(result.data),
                    "message": f"成功獲取帳戶 {validated_args.account} 銀行餘額",
                }
            else:
                error_msg = "獲取銀行餘額失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取銀行餘額失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取銀行餘額時發生錯誤: {str(e)}",
            }

    def get_maintenance(self, args: Dict) -> dict:
        """
        獲取維持率資訊

        Args:
            account (str): 帳戶號碼

        """
        try:
            validated_args = GetMaintenanceArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取維持率
            result = self.sdk.accounting.maintenance(account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": self._to_dict(result.data),
                    "message": f"成功獲取帳戶 {validated_args.account} 維持率資訊",
                }
            else:
                error_msg = "獲取維持率資訊失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取維持率資訊失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取維持率資訊時發生錯誤: {str(e)}",
            }

    def get_settlement_info(self, args: Dict) -> dict:
        """
        獲取交割資訊（應收付金額）

        Args:
            account (str): 帳戶號碼
            range (str): 查詢範圍，預設 "0d" (當日)，可選 "3d" (3日)
        """
        try:
            validated_args = GetSettlementInfoArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取結算資訊
            result = self.sdk.accounting.query_settlement(account_obj, validated_args.range)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": self._to_dict(result.data),
                    "message": f"成功獲取帳戶 {validated_args.account} 結算資訊",
                }
            else:
                error_msg = "獲取結算資訊失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取結算資訊失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取結算資訊時發生錯誤: {str(e)}",
            }

    def get_realized_pnl(self, args: Dict) -> dict:
        """
        獲取已實現損益資訊


        Args:
            account (str): 帳戶號碼

        """
        try:
            validated_args = GetRealizedPnlArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取已實現損益
            result = self.sdk.accounting.realized_gains_and_loses(account=account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": self._to_dict(result.data),
                    "message": f"成功獲取已實現損益",
                }
            else:
                error_msg = "獲取已實現損益失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取已實現損益失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取已實現損益時發生錯誤: {str(e)}",
            }

    def get_realized_pnl_summary(self, args: Dict) -> dict:
        """
        獲取已實現損益摘要

        Args:
            account (str): 帳戶號碼

        """
        try:
            validated_args = GetRealizedPnlSummaryArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取已實現損益摘要
            result = self.sdk.accounting.realized_gains_and_loses_summary(account=account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": self._to_dict(result.data),
                    "message": f"成功獲取已實現損益摘要",
                }
            else:
                error_msg = "獲取已實現損益摘要失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取已實現損益摘要失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取已實現損益摘要時發生錯誤: {str(e)}",
            }

    def get_unrealized_pnl(self, args: Dict) -> dict:
        """
        獲取未實現損益

        Args:
            account (str): 帳戶號碼

        """
        try:
            validated_args = GetUnrealizedPnlArgs(**args)
            account_obj, error = validate_and_get_account(validated_args.account)
            if error:
                return {"status": "error", "data": None, "message": error}

            # 調用 SDK 獲取未實現損益
            result = self.sdk.accounting.unrealized_gains_and_loses(account=account_obj)

            if result and hasattr(result, "is_success") and result.is_success:
                return {
                    "status": "success",
                    "data": self._to_dict(result.data),
                    "message": f"成功獲取未實現損益",
                }
            else:
                error_msg = "獲取未實現損益失敗"
                if result and hasattr(result, "message"):
                    error_msg = f"獲取未實現損益失敗: {result.message}"
                return {"status": "error", "data": None, "message": error_msg}

        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取未實現損益時發生錯誤: {str(e)}",
            }


# 參數模型定義
class GetAccountInfoArgs(BaseModel):
    account: Optional[str] = None


class GetInventoryArgs(BaseModel):
    account: str


class GetBankBalanceArgs(BaseModel):
    account: str


class GetMaintenanceArgs(BaseModel):
    account: str


class GetSettlementInfoArgs(BaseModel):
    account: str
    range: Optional[str] = "0d"


class GetRealizedPnlArgs(BaseModel):
    account: str


class GetRealizedPnlSummaryArgs(BaseModel):
    account: str


class GetUnrealizedPnlArgs(BaseModel):
    account: str
