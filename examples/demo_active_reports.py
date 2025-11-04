#!/usr/bin/env python3
"""
FUBON MCP Server 主動回報功能演示
展示如何使用主動回報查詢功能
"""

import os
import sys

from dotenv import load_dotenv
from fubon_neo.sdk import FubonSDK

# 加載環境變數
load_dotenv()


def main():
    print("🎯 FUBON MCP Server 主動回報功能演示")
    print("=" * 60)

    try:
        # 初始化 SDK
        username = os.getenv("FUBON_USERNAME")
        password = os.getenv("FUBON_PASSWORD")
        pfx_path = os.getenv("FUBON_PFX_PATH")
        pfx_password = os.getenv("FUBON_PFX_PASSWORD")

        sdk = FubonSDK()
        accounts = sdk.login(username, password, pfx_path, pfx_password or "")
        sdk.init_realtime()

        print("✅ API 連線成功")
        print(f"📊 帳戶: {accounts.data[0].name} ({accounts.data[0].account})")

        # 模擬一些主動回報數據（實際使用中會由SDK自動觸發）
        print("\n📡 主動回報功能說明:")
        print("  • 委託回報：當有新的委託單時自動通知")
        print("  • 成交回報：當委託單成交時自動通知")
        print("  • 改價/改量回報：當委託單被修改時自動通知")
        print("  • 事件通知：連線狀態、登入狀態等系統事件")

        print("\n🔧 MCP 工具說明:")
        print("  • get_order_reports() - 查詢最新的委託回報")
        print("  • get_filled_reports() - 查詢最新的成交回報")
        print("  • get_order_changed_reports() - 查詢改價/改量回報")
        print("  • get_event_reports() - 查詢系統事件通知")
        print("  • get_all_reports() - 查詢所有類型的主動回報")

        print("\n📋 事件代碼說明:")
        print("  • 100: 連線建立成功")
        print("  • 200: 登入成功")
        print("  • 201: 登入警示 (90天未更換密碼)")
        print("  • 300: 斷線")
        print("  • 301: 未收到連線pong回傳")
        print("  • 302: 登出並斷線")
        print("  • 500: 錯誤")

        print("\n⚡ 即時監控:")
        print("  MCP server會自動接收並存儲最新的回報數據")
        print("  每種類型保留最新的10筆記錄")
        print("  可通過MCP工具隨時查詢最新狀態")

        print("\n🎉 主動回報功能設置完成！")
        print("   現在您可以通過MCP工具查詢各種主動回報數據")

    except Exception as e:
        print(f"❌ 錯誤: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
