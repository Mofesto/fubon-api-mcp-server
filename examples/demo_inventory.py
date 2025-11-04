#!/usr/bin/env python3
"""
FUBON MCP 庫存查詢演示
展示如何查詢帳戶持倉明細（未實現損益資訊）
"""

import os

from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

# 獲取帳戶號碼 - 將從SDK登入中動態獲取
account = None  # 將在函數中設置


def demo_inventory():
    """演示庫存查詢（未實現損益）"""
    print("📊 FUBON 庫存查詢演示")
    print("=" * 60)

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
        print("🔍 正在查詢未實現損益（庫存明細）...")

        # 直接使用SDK查詢未實現損益
        pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)

        if pnl and hasattr(pnl, "is_success") and pnl.is_success:
            pnl_data = pnl.data
            print("\n✅ 查詢成功！")
            print("-" * 80)

            if isinstance(pnl_data, list) and pnl_data:
                print(f"{'股票代號':<8} {'名稱':<10} {'持股數量':<8} {'成本價':<8} {'未實現盈虧':<12} {'盈虧金額':<10}")
                print("-" * 80)

                total_profit = 0
                total_loss = 0
                total_value = 0

                # 股票名稱映射
                stock_names = {"0050": "台灣50", "1301": "台塑", "1303": "南亞", "6505": "台塑化"}

                for item in pnl_data:
                    stock_no = getattr(item, "stock_no", "N/A")
                    stock_name = stock_names.get(stock_no, "未知")
                    quantity = getattr(item, "tradable_qty", 0)
                    cost_price = getattr(item, "cost_price", 0)
                    profit = getattr(item, "unrealized_profit", 0)
                    loss = getattr(item, "unrealized_loss", 0)

                    # 計算盈虧
                    net_pnl = profit - loss
                    total_value += net_pnl

                    if net_pnl > 0:
                        total_profit += net_pnl
                        pnl_str = f"+{net_pnl:,}"
                    else:
                        total_loss += abs(net_pnl)
                        pnl_str = f"{net_pnl:,}"

                    print(
                        f"{stock_no:<8} {stock_name:<10} {quantity:<8,} {cost_price:<8.2f} {'利潤' if profit > 0 else '損失':<12} {pnl_str:<10}"
                    )

                print("-" * 80)
                print(f"總計 - 利潤: +{total_profit:,} 元 | 損失: -{total_loss:,} 元 | 淨盈虧: {total_value:,} 元")
                print(f"持股總市值變化: {total_value:,} 元")

            else:
                print("📭 目前無持倉")

        else:
            print(f"❌ 查詢失敗: {getattr(pnl, 'message', 'Unknown error')}")

    except Exception as e:
        print(f"❌ 演示過程中發生錯誤: {str(e)}")


def demo_detailed_inventory():
    """演示詳細庫存資訊"""
    print("\n🔍 詳細庫存資訊")
    print("=" * 60)

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

        # 直接使用SDK查詢未實現損益
        pnl = sdk.accounting.unrealized_gains_and_loses(account_obj)

        if pnl and hasattr(pnl, "is_success") and pnl.is_success:
            pnl_data = pnl.data

            if isinstance(pnl_data, list) and pnl_data:
                for i, item in enumerate(pnl_data, 1):
                    print(f"\n📈 持倉 {i}:")
                    print(f"   股票代號: {getattr(item, 'stock_no', 'N/A')}")
                    print(f"   日期: {getattr(item, 'date', 'N/A')}")
                    print(f"   分行: {getattr(item, 'branch_no', 'N/A')}")
                    print(f"   帳戶: {getattr(item, 'account', 'N/A')}")
                    print(f"   買賣別: {getattr(item, 'buy_sell', 'N/A')}")
                    print(f"   委託類型: {getattr(item, 'order_type', 'N/A')}")
                    print(f"   成本價: {getattr(item, 'cost_price', 0):.4f}")
                    print(f"   可交易數量: {getattr(item, 'tradable_qty', 0):,}")
                    print(f"   今日數量: {getattr(item, 'today_qty', 0):,}")
                    print(f"   未實現利潤: {getattr(item, 'unrealized_profit', 0):,}")
                    print(f"   未實現損失: {getattr(item, 'unrealized_loss', 0):,}")

                    profit = getattr(item, "unrealized_profit", 0)
                    loss = getattr(item, "unrealized_loss", 0)
                    net = profit - loss
                    print(f"   淨盈虧: {net:,} 元")
                    print("-" * 40)

    except Exception as e:
        print(f"❌ 詳細查詢過程中發生錯誤: {str(e)}")


if __name__ == "__main__":
    demo_inventory()
    demo_detailed_inventory()

    print("\n🎯 MCP 工具使用提示:")
    print("- 使用 get_unrealized_pnl() 查詢完整庫存明細")
    print("- 使用 get_inventory() 查詢基本庫存資訊")
    print("- 使用 get_account_info() 獲取帳戶總覽（包含庫存）")
