#!/usr/bin/env python3
"""
FUBON MCP 銀行水位查詢演示
展示如何使用 MCP 工具查詢帳戶銀行水位
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

# 獲取帳戶號碼
account = os.getenv("FUBON_USERNAME")
if not account:
    raise ValueError("FUBON_USERNAME environment variable is required")


def demo_bank_balance():
    """演示銀行水位查詢"""
    print("🏦 FUBON 銀行水位查詢演示")
    print("=" * 50)

    try:
        # 模擬 MCP 工具調用
        from server import get_bank_balance

        print(f"📋 查詢帳戶: {account} (戶名(人名))")
        print("🔍 正在查詢銀行水位...")

        # 調用銀行水位查詢
        result = get_bank_balance({"account": account})

        if result["status"] == "success":
            balance_data = result["data"]
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
            print(f"❌ 查詢失敗: {result['message']}")

    except Exception as e:
        print(f"❌ 演示過程中發生錯誤: {str(e)}")


def demo_all_account_info():
    """演示完整帳戶資訊查詢"""
    print("\n📊 完整帳戶資訊查詢演示")
    print("=" * 50)

    try:
        from server import get_account_info

        print(f"📋 查詢帳戶: {account} (戶名(人名))")
        print("🔍 正在查詢完整帳戶資訊...")

        result = get_account_info({"account": account})

        if result["status"] == "success":
            account_data = result["data"]
            print("\n✅ 查詢成功！")
            print("-" * 30)

            # 基本資訊
            if "basic_info" in account_data:
                basic = account_data["basic_info"]
                print("👤 基本資訊:")
                print(f"   姓名: {basic.get('name', 'N/A')}")
                print(f"   分行: {basic.get('branch_no', 'N/A')}")
                print(f"   帳戶: {basic.get('account', 'N/A')}")
                print(f"   類型: {basic.get('account_type', 'N/A')}")

            # 銀行水位
            if "bank_balance" in account_data:
                balance = account_data["bank_balance"]
                print("\n💰 銀行水位:")
                print(f"   餘額: {getattr(balance, 'balance', 0):,} 元")
                print(f"   可用: {getattr(balance, 'available_balance', 0):,} 元")
            else:
                print("\n⚠️ 銀行水位資訊不可用")

            # 庫存資訊
            if "inventories" in account_data and account_data["inventories"]:
                print("\n📈 庫存資訊:")
                inventories = account_data["inventories"]
                if isinstance(inventories, list):
                    for item in inventories[:3]:  # 只顯示前3筆
                        print(f"   {getattr(item, 'symbol', 'N/A')}: {getattr(item, 'quantity', 0)} 股")
                else:
                    print(f"   {inventories}")
            else:
                print("\n📭 目前無庫存")

        else:
            print(f"❌ 查詢失敗: {result['message']}")

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
