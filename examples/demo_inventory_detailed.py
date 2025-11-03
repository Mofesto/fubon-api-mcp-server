#!/usr/bin/env python3
"""
FUBON MCP 庫存 vs 未實現損益對比演示
展示庫存資訊與未實現損益的區別
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


def demo_inventory_vs_pnl():
    """對比展示庫存資訊與未實現損益"""
    print("📊 FUBON 庫存 vs 未實現損益對比")
    print("=" * 80)

    try:
        from server import get_inventory, get_unrealized_pnl

        print(f"📋 查詢帳戶: {account} (戶名(人名))")
        print()

        # 獲取庫存資訊
        print("📦 庫存資訊 (Inventory) - 實際持股狀況:")
        print("-" * 80)
        inventory_result = get_inventory({"account": account})

        if inventory_result["status"] == "success":
            inventory_data = inventory_result["data"]
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
            print(f"❌ 庫存查詢失敗: {inventory_result['message']}")

        print("\n💰 未實現損益 (Unrealized P&L) - 盈虧狀況:")
        print("-" * 80)
        pnl_result = get_unrealized_pnl({"account": account})

        if pnl_result["status"] == "success":
            pnl_data = pnl_result["data"]
            if isinstance(pnl_data, list) and pnl_data:
                print(f"{'股票代號':<8} {'持股數量':<8} {'成本價':<8} {'未實現盈虧':<12} {'金額':<10}")
                print("-" * 80)

                total_profit = 0
                total_loss = 0

                # 股票名稱映射
                stock_names = {"0050": "台灣50", "1301": "台塑", "1303": "南亞", "6505": "台塑化"}

                for item in pnl_data:
                    stock_no = getattr(item, "stock_no", "N/A")
                    stock_name = stock_names.get(stock_no, "未知")
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
            print(f"❌ 未實現損益查詢失敗: {pnl_result['message']}")

    except Exception as e:
        print(f"❌ 演示過程中發生錯誤: {str(e)}")


def demo_detailed_inventory():
    """展示詳細庫存資訊"""
    print("\n🔍 詳細庫存資訊 (每筆持倉的完整交易狀態)")
    print("=" * 80)

    try:
        from server import get_inventory

        result = get_inventory({"account": account})

        if result["status"] == "success":
            inventory_data = result["data"]

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
