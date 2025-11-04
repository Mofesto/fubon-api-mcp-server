#!/usr/bin/env python3
"""
直接測試 FUBON API 帳戶資訊查詢
"""

import os

from dotenv import load_dotenv
from fubon_neo.sdk import FubonSDK

# 加載環境變數
load_dotenv()


def authenticate_sdk():
    """認證並初始化 SDK"""
    username = os.getenv("FUBON_USERNAME")
    password = os.getenv("FUBON_PASSWORD")
    pfx_path = os.getenv("FUBON_PFX_PATH")
    pfx_password = os.getenv("FUBON_PFX_PASSWORD")

    if not all([username, password, pfx_path]):
        print("❌ 缺少必要的環境變數")
        return None, None

    sdk = FubonSDK()
    accounts = sdk.login(username, password, pfx_path, pfx_password or "")

    if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
        print("❌ 帳戶認證失敗")
        return None, None

    print("✅ 帳戶認證成功")
    return sdk, accounts


def query_balance_apis(sdk, acc):
    """查詢各種資金餘額 API"""
    balance_apis = [
        "bank_remain",
        "balances",
        "cash_balance",
        "cash",
        "funds",
        "account_balance",
        "margin_balance",
        "equity",
        "portfolio_balance",
        "bank_balance",
    ]

    found_balance = False
    for api_name in balance_apis:
        if hasattr(sdk.accounting, api_name):
            try:
                api_method = getattr(sdk.accounting, api_name)
                result = api_method(acc)
                if result and hasattr(result, "is_success") and result.is_success:
                    print(f"💰 發現 {api_name} API - 銀行水位資訊:")
                    print(f"   {result.data}")
                    found_balance = True
                    break
                else:
                    print(f"⚠️ {api_name} API 返回失敗")
            except Exception as api_error:
                print(f"⚠️ {api_name} API 呼叫錯誤: {str(api_error)}")

    if not found_balance:
        print("⚠️ 未找到可用的資金餘額 API")


def check_accounting_methods(sdk):
    """檢查 accounting 模組的所有可用方法"""
    print("🔍 檢查所有可用的 accounting API 方法...")
    accounting_methods = [method for method in dir(sdk.accounting) if not method.startswith("_")]
    print(f"   可用的方法: {accounting_methods}")


def query_settlement_info(sdk, acc):
    """查詢交割資訊"""
    print("🔍 查詢交割資訊...")
    settlement = sdk.accounting.query_settlement(acc, "0d")
    if settlement and hasattr(settlement, "is_success") and settlement.is_success:
        print("📊 今日交割資訊:")
        print(f"   {settlement.data}")
    else:
        print("❌ 無法獲取交割資訊")


def test_account_balance():
    """測試帳戶餘額查詢"""
    print("=== 查詢帳戶銀行水位 ===")

    try:
        sdk, accounts = authenticate_sdk()
        if not sdk or not accounts:
            return

        # 查找帳戶
        if hasattr(accounts, "data") and accounts.data:
            for acc in accounts.data:
                account_no = getattr(acc, "account", "N/A")
                account_name = getattr(acc, "name", "N/A")
                print(f"\n📋 帳戶資訊: {account_name} ({account_no})")

                try:
                    # 嘗試獲取資金餘額/銀行水位
                    print("🔍 查詢資金餘額...")
                    query_balance_apis(sdk, acc)
                    import time

                    time.sleep(0.5)  # Add delay to avoid rate limiting
                    check_accounting_methods(sdk)
                    time.sleep(0.5)  # Add delay to avoid rate limiting
                    query_settlement_info(sdk, acc)

                except Exception as e:
                    print(f"❌ 查詢過程中發生錯誤: {str(e)}")
        else:
            print("❌ 找不到帳戶資訊")

    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")


if __name__ == "__main__":
    test_account_balance()
