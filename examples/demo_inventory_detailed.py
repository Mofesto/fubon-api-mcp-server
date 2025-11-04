#!/usr/bin/env python3
"""
FUBON MCP 庫存 vs 未實現損益對比演示
展示庫存資訊與未實現損益的區別
"""

import os

from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

# 獲取帳戶號碼 - 將從SDK登入中動態獲取
account = None  # 將在函數中設置


def demo_inventory_vs_pnl():
    """對比展示庫存資訊與未實現損益"""
    print("📊 FUBON 庫存 vs 未實現損益對比")
    print("=" * 80)

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
        print()

        # 獲取庫存資訊
        print("📦 庫存資訊 (Inventory) - 實際持股狀況:")
        print("-" * 80)
        inventory = sdk.accounting.inventories(account_obj)

        if inventory and hasattr(inventory, "is_success") and inventory.is_success:
            inventory_data = inventory.data
            if isinstance(inventory_data, list) and inventory_data:
                print(f"{'股票代號':<8} {'昨餘股數':<8} {'今日股數':<8} {'可交易股數':<10} {'買進':<8} {'賣出':<8}")
                print("-" * 80)

                for item in inventory_data:
                    stock_no = getattr(item, "stock_no", "N/A")
                    lastday_qty = getattr(item, "lastday_qty", 0)
                    today_qty = getattr(item, "today_qty", 0)
                    tradable_qty = getattr(item, "tradable_qty", 0)
                    buy_qty = getattr(item, "buy_qty", 0)
                    sell_qty = getattr(item, "sell_qty", 0)

                    print(f"{stock_no:<8} {lastday_qty:<8,} {today_qty:<8,} {tradable_qty:<10,} {buy_qty:<8,} {sell_qty:<8,}")

                print("-" * 80)
                total_stocks = len(inventory_data)
                total_qty = sum(getattr(item, "tradable_qty", 0) for item in inventory_data)
                print(f"總計: {total_stocks} 檔股票，共 {total_qty:,} 股可交易")
            else:
                print("📭 目前無庫存")
        else:
            print(f"❌ 庫存查詢失敗: {getattr(inventory, 'message', 'Unknown error')}")

        print("\n💰 未實現損益 (Unrealized P&L) - 盈虧狀況:")
        print("-" * 80)
        pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)

        if pnl and hasattr(pnl, "is_success") and pnl.is_success:
            pnl_data = pnl.data
            if isinstance(pnl_data, list) and pnl_data:
                print(f"{'股票代號':<8} {'持股數量':<8} {'成本價':<8} {'未實現盈虧':<12} {'金額':<10}")
                print("-" * 80)

                total_profit = 0
                total_loss = 0

                for item in pnl_data:
                    stock_no = getattr(item, "stock_no", "N/A")
                    quantity = getattr(item, "tradable_qty", 0)
                    cost_price = getattr(item, "cost_price", 0)
                    profit = getattr(item, "unrealized_profit", 0)
                    loss = getattr(item, "unrealized_loss", 0)

                    net_pnl = profit - loss
                    if net_pnl > 0:
                        total_profit += net_pnl
                        pnl_type = "利潤"
                        amount_str = f"+{net_pnl:,}"
                    else:
                        total_loss += abs(net_pnl)
                        pnl_type = "損失"
                        amount_str = f"{net_pnl:,}"

                    print(f"{stock_no:<8} {quantity:<8,} {cost_price:<8.2f} {pnl_type:<12} {amount_str:<10}")

                print("-" * 80)
                print(
                    f"總計 - 利潤: +{total_profit:,} 元 | 損失: -{total_loss:,} 元 | 淨盈虧: {total_profit - total_loss:,} 元"
                )

        else:
            print(f"❌ 未實現損益查詢失敗: {getattr(pnl, 'message', 'Unknown error')}")

    except Exception as e:
        print(f"❌ 演示過程中發生錯誤: {str(e)}")


def demo_detailed_inventory():
    """展示詳細庫存資訊"""
    print("\n🔍 詳細庫存資訊 (每筆持倉的完整交易狀態)")
    print("=" * 80)

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

        # 直接使用SDK查詢庫存
        inventory = sdk.accounting.inventories(account_obj)

        if inventory and hasattr(inventory, "is_success") and inventory.is_success:
            inventory_data = inventory.data

            if isinstance(inventory_data, list) and inventory_data:
                for i, item in enumerate(inventory_data, 1):
                    print(f"\n📦 持倉 {i} - {getattr(item, 'stock_no', 'N/A')}:")
                    print(f"   日期: {getattr(item, 'date', 'N/A')}")
                    print(f"   帳戶: {getattr(item, 'account', 'N/A')}")
                    print(f"   分行: {getattr(item, 'branch_no', 'N/A')}")
                    print(f"   委託類型: {getattr(item, 'order_type', 'N/A')}")
                    print(f"   ┌─ 昨餘股數: {getattr(item, 'lastday_qty', 0):,}")
                    print(f"   ├─ 買進股數: {getattr(item, 'buy_qty', 0):,} (成交: {getattr(item, 'buy_filled_qty', 0):,})")
                    print(f"   ├─ 買進金額: {getattr(item, 'buy_value', 0):,}")
                    print(f"   ├─ 今日股數: {getattr(item, 'today_qty', 0):,}")
                    print(f"   ├─ 可交易股數: {getattr(item, 'tradable_qty', 0):,}")
                    print(f"   ├─ 賣出股數: {getattr(item, 'sell_qty', 0):,} (成交: {getattr(item, 'sell_filled_qty', 0):,})")
                    print(f"   └─ 賣出金額: {getattr(item, 'sell_value', 0):,}")

                    # 零股資訊
                    odd = getattr(item, "odd", None)
                    if odd and getattr(odd, "tradable_qty", 0) > 0:
                        print(f"   💰 零股: {getattr(odd, 'tradable_qty', 0):,} 股可交易")
                    print("-" * 60)

    except Exception as e:
        print(f"❌ 詳細查詢過程中發生錯誤: {str(e)}")


if __name__ == "__main__":
    demo_inventory_vs_pnl()
    demo_detailed_inventory()

    print("\n🎯 功能說明:")
    print("📦 get_inventory() - 查詢實際庫存數量和交易狀態")
    print("💰 get_unrealized_pnl() - 查詢盈虧狀況和成本資訊")
    print("📊 get_account_info() - 獲取完整的帳戶總覽")
