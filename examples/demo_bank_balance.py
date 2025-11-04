#!/usr/bin/env python3
"""
FUBON MCP 銀行水位查詢演示
展示如何使用 MCP 工具查詢帳戶銀行水位
"""

import os

from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

# 獲取帳戶號碼 - 將從SDK登入中動態獲取
account = None  # 將在函數中設置


def demo_bank_balance():
    """演示銀行水位查詢"""
    print("🏦 FUBON 銀行水位查詢演示")
    print("=" * 50)

    try:
        # 初始化 SDK 並登入
        username = os.getenv("FUBON_USERNAME")
        password = os.getenv("FUBON_PASSWORD")
        pfx_path = os.getenv("FUBON_PFX_PATH")
        pfx_password = os.getenv("FUBON_PFX_PASSWORD")

        from fubon_neo.sdk import FubonSDK

        sdk = FubonSDK()
        accounts = sdk.login(username, password, pfx_path, pfx_password or "")

        if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
            print("❌ 登入失敗")
            return

        # 使用第一個帳戶
        account_obj = accounts.data[0]
        account = account_obj.account

        print(f"📋 查詢帳戶: {account_obj.name} ({account})")
        print("🔍 正在查詢銀行水位...")

        # 直接使用SDK查詢銀行水位
        balance = sdk.accounting.bank_remain(account_obj)

        if balance and hasattr(balance, "is_success") and balance.is_success:
            balance_data = balance.data
            print("\n✅ 查詢成功！")
            print("-" * 30)
            print("💰 銀行水位資訊:")
            print(f"   分行代號: {getattr(balance_data, 'branch_no', 'N/A')}")
            print(f"   帳戶號碼: {getattr(balance_data, 'account', 'N/A')}")
            print(f"   貨幣種類: {getattr(balance_data, 'currency', 'N/A')}")
            print(f"   總餘額: {getattr(balance_data, 'balance', 0):,} 元")
            print(f"   可用餘額: {getattr(balance_data, 'available_balance', 0):,} 元")
            print("-" * 30)
            print("💡 提示: 可用餘額可用於買入股票或進行交易")
        else:
            print(f"❌ 查詢失敗: {getattr(balance, 'message', 'Unknown error')}")

    except Exception as e:
        print(f"❌ 演示過程中發生錯誤: {str(e)}")
        import traceback

        traceback.print_exc()


def demo_all_account_info():
    """演示完整帳戶資訊查詢"""
    print("\n📊 完整帳戶資訊查詢演示")
    print("=" * 50)

    try:
        # 初始化 SDK 並登入
        username = os.getenv("FUBON_USERNAME")
        password = os.getenv("FUBON_PASSWORD")
        pfx_path = os.getenv("FUBON_PFX_PATH")
        pfx_password = os.getenv("FUBON_PFX_PASSWORD")

        from fubon_neo.sdk import FubonSDK

        sdk = FubonSDK()
        accounts = sdk.login(username, password, pfx_path, pfx_password or "")

        if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
            print("❌ 登入失敗")
            return

        # 使用第一個帳戶
        account_obj = accounts.data[0]
        account = account_obj.account

        print(f"📋 查詢帳戶: {account_obj.name} ({account})")
        print("🔍 正在查詢完整帳戶資訊...")

        # 直接使用SDK查詢完整帳戶資訊
        balance = sdk.accounting.bank_remain(account_obj)
        inventory = sdk.accounting.inventories(account_obj)
        pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)

        account_data = {
            "balance": balance.data if hasattr(balance, "data") else balance,
            "inventory": inventory.data if hasattr(inventory, "data") else inventory,
            "pnl": pnl.data if hasattr(pnl, "data") else pnl,
        }

        # 檢查是否包含基本資訊
        if "balance" in account_data:
            balance_data = account_data["balance"]
            print("\n✅ 查詢成功！")
            print("-" * 30)

            # 基本資訊
            print("👤 基本資訊:")
            print(f"   姓名: {account_obj.name}")
            print(f"   分行: {getattr(account_obj, 'branch_no', 'N/A')}")
            print(f"   帳戶: {account}")
            print(f"   類型: {getattr(account_obj, 'account_type', 'N/A')}")

            # 銀行水位
            print("\n💰 銀行水位:")
            print(f"   餘額: {getattr(balance_data, 'balance', 0):,} 元")
            print(f"   可用: {getattr(balance_data, 'available_balance', 0):,} 元")
            print("-" * 30)
        else:
            print("❌ 無法獲取帳戶資訊")

    except Exception as e:
        print(f"❌ 演示過程中發生錯誤: {str(e)}")


if __name__ == "__main__":
    demo_bank_balance()
    demo_all_account_info()

    print("\n🎯 MCP 工具使用提示:")
    print("- 使用 get_bank_balance() 查詢資金餘額")
    print("- 使用 get_account_info() 獲取完整帳戶概覽")
    print("- 使用 get_inventory() 查詢持股明細")
    print("- 使用 get_unrealized_pnl() 查詢未實現損益")
