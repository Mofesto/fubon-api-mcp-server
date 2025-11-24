#!/usr/bin/env python3
"""
富邦 API MCP Server - Account Service 真實 API 手動測試

此腳本用於手動測試 Account Service 的所有功能，使用真實的富邦 API。
包含完整的真實 API 測試案例，涵蓋所有 Account Service 方法。

⚠️ 重要注意事項：
- 此腳本會調用真實的富邦 API
- 需要正確的環境變數設定
- 會產生網路請求和 API 調用
- 請確保有足夠的 API 調用額度

使用前準備：
1. 設定環境變數：
   - FUBON_USERNAME=您的帳號
   - FUBON_PASSWORD=您的密碼
   - FUBON_PFX_PATH=PFX憑證檔案路徑
   - FUBON_PFX_PASSWORD=PFX密碼（可選）

2. 安裝依賴：
   pip install python-dotenv fubon-neo mcp

3. 運行測試：
   python examples/account_service_real_test.py

測試涵蓋範圍：
- 帳戶基本資訊查詢
- 庫存查詢
- 銀行餘額查詢
- 維持率查詢
- 結算資訊查詢
- 移動鎖利歷史查詢
- 條件單歷史查詢
- 已實現損益查詢
- 已實現損益摘要查詢
- 未實現損益查詢
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加載環境變數
load_dotenv()

from fubon_api_mcp_server.config import config
from unittest.mock import Mock
from fubon_api_mcp_server.account_service import AccountService
from fubon_neo.sdk import FubonSDK


def print_section(title: str):
    """列印區段標題"""
    print(f"\n{'='*70}")
    print(f"🧪 {title}")
    print('='*70)


def print_test_result(test_name: str, result: dict, expected_success: bool = True):
    """列印測試結果"""
    status = result.get('status', 'unknown')
    message = result.get('message', '')

    if status == 'success':
        if expected_success:
            print(f"✅ {test_name}: {message}")
        else:
            print(f"⚠️  {test_name}: 預期失敗但成功 - {message}")
    else:
        if expected_success:
            print(f"❌ {test_name}: {message}")
        else:
            print(f"✅ {test_name}: 預期失敗 - {message}")

    # 顯示資料摘要
    if 'data' in result:
        data = result['data']
        if isinstance(data, list):
            print(f"   📊 資料筆數: {len(data)}")
        elif isinstance(data, dict):
            print(f"   📊 資料字段: {list(data.keys())}")
        else:
            print(f"   📊 資料類型: {type(data).__name__}")


def run_test(test_name: str, test_func, *args, **kwargs):
    """運行單個測試"""
    try:
        print(f"\n🔍 執行測試: {test_name}")
        result = test_func(*args, **kwargs)
        print_test_result(test_name, result)
        return result
    except Exception as e:
        error_result = {
            "status": "error",
            "message": f"測試執行失敗: {str(e)}"
        }
        print_test_result(test_name, error_result)
        return error_result


def main():
    """主測試函數"""
    print("🚀 富邦 API MCP Server - Account Service 真實 API 手動測試")
    print("="*70)
    print(f"⏰ 測試開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 環境檢查
    print_section("環境檢查")
    required_env = ['FUBON_USERNAME', 'FUBON_PASSWORD', 'FUBON_PFX_PATH']
    missing_env = [env for env in required_env if not os.getenv(env)]

    if missing_env:
        print(f"❌ 缺少必要的環境變數: {missing_env}")
        print("\n請設定以下環境變數：")
        for env in missing_env:
            print(f"   export {env}=<您的{env.replace('FUBON_', '')}>")
        print("\n💡 提示：您也可以在 .env 檔案中設定這些變數")
        return

    print("✅ 環境變數檢查通過")

    # 2. 初始化 SDK
    print_section("SDK 初始化")
    try:
        sdk = FubonSDK()
        accounts = sdk.login(
            config.username,
            config.password,
            config.pfx_path,
            config.pfx_password or ""
        )

        if not accounts or not hasattr(accounts, 'is_success') or not accounts.is_success:
            print("⚠️ SDK 登入失敗，將使用範例帳戶 (非真實環境)")
            # fallback to sample accounts for local development
            SAMPLE_ACCOUNTS = [
                {
                    "account": "C04",
                    "name": "Sample C04",
                    "branch_no": "99999",
                    "account_type": "stock",
                }
            ]

            # Convert sample account dicts to simple objects used by services
            class SimpleObj:
                def __init__(self, d):
                    for k, v in d.items():
                        setattr(self, k, v)

            accounts = Mock()
            accounts.is_success = True
            accounts.data = [SimpleObj(a) for a in SAMPLE_ACCOUNTS]

        print(f"✅ SDK 初始化成功，獲取到 {len(accounts.data)} 個帳戶")

        # 選擇第一個帳戶作為測試帳戶
        test_account = accounts.data[0].account
        print(f"📋 測試帳戶: {test_account}")

    except Exception as e:
        print(f"❌ SDK 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. 初始化 Account Service
    print_section("Account Service 初始化")
    try:
        # 創建模擬 MCP 實例
        class MockMCP:
            def tool(self):
                def decorator(func):
                    return func
                return decorator

        mock_mcp = MockMCP()
        account_service = AccountService(mock_mcp, sdk, accounts.data)
        print("✅ Account Service 初始化成功")

    except Exception as e:
        print(f"❌ Account Service 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 執行所有測試
    test_results = []

    # 4.1 帳戶資訊測試
    print_section("帳戶資訊測試")

    # 測試：獲取帳戶資訊
    result = run_test(
        "獲取帳戶資訊",
        account_service.get_account_info,
        {"account": test_account}
    )
    test_results.append(("get_account_info", result))

    # 4.2 庫存測試
    print_section("庫存測試")

    # 測試：獲取庫存
    result = run_test(
        "獲取庫存",
        account_service.get_inventory,
        {"account": test_account}
    )
    test_results.append(("get_inventory", result))

    # 4.3 資金測試
    print_section("資金測試")

    # 測試：獲取銀行餘額
    result = run_test(
        "獲取銀行餘額",
        account_service.get_bank_balance,
        {"account": test_account}
    )
    test_results.append(("get_bank_balance", result))

    # 測試：獲取維持率
    result = run_test(
        "獲取維持率",
        account_service.get_maintenance,
        {"account": test_account}
    )
    test_results.append(("get_maintenance", result))

    # 測試：獲取結算資訊（當日）
    result = run_test(
        "獲取結算資訊（當日）",
        account_service.get_settlement_info,
        {"account": test_account}
    )
    test_results.append(("get_settlement_info_today", result))

    # 測試：獲取結算資訊（3日）
    result = run_test(
        "獲取結算資訊（3日）",
        account_service.get_settlement_info,
        {"account": test_account, "range": "3d"}
    )
    test_results.append(("get_settlement_info_3d", result))

    # 4.4 損益測試
    print_section("損益測試")

    # 測試：獲取未實現損益
    result = run_test(
        "獲取未實現損益",
        account_service.get_unrealized_pnl,
        {"account": test_account}
    )
    test_results.append(("get_unrealized_pnl", result))

    # 測試：獲取已實現損益
    result = run_test(
        "獲取已實現損益",
        account_service.get_realized_pnl,
        {"account": test_account}
    )
    test_results.append(("get_realized_pnl", result))

    # 測試：獲取已實現損益摘要
    result = run_test(
        "獲取已實現損益摘要",
        account_service.get_realized_pnl_summary,
        {"account": test_account}
    )
    test_results.append(("get_realized_pnl_summary", result))

    # 4.5 歷史記錄測試
    print_section("歷史記錄測試")

    # 計算日期範圍（近3個月）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")

    # 測試：獲取移動鎖利歷史
    result = run_test(
        f"獲取移動鎖利歷史 ({start_date_str} - {end_date_str})",
        account_service.get_trail_history,
        {
            "account": test_account,
            "start_date": start_date_str,
            "end_date": end_date_str
        }
    )
    test_results.append(("get_trail_history", result))

    # 測試：獲取條件單歷史
    result = run_test(
        f"獲取條件單歷史 ({start_date_str} - {end_date_str})",
        account_service.get_condition_history,
        {
            "account": test_account,
            "start_date": start_date_str,
            "end_date": end_date_str
        }
    )
    test_results.append(("get_condition_history", result))

    # 5. 測試總結
    print_section("測試總結")

    successful_tests = 0
    failed_tests = 0

    print("📊 測試結果詳情：")
    for test_name, result in test_results:
        status = result.get('status', 'unknown')
        if status == 'success':
            successful_tests += 1
            print(f"   ✅ {test_name}")
        else:
            failed_tests += 1
            print(f"   ❌ {test_name}: {result.get('message', '未知錯誤')}")

    print(f"\n🎯 測試統計:")
    print(f"   總測試數: {len(test_results)}")
    print(f"   成功: {successful_tests}")
    print(f"   失敗: {failed_tests}")
    print(f"   成功率: {(successful_tests / len(test_results) * 100):.1f}%")

    print(f"\n⏰ 測試結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if failed_tests == 0:
        print("\n🎉 所有測試都通過了！")
    else:
        print(f"\n⚠️  有 {failed_tests} 個測試失敗，請檢查上面的詳細資訊")

    print("\n💡 提示：")
    print("   • 此測試使用真實 API，可能會因網路狀況而有所差異")
    print("   • 部分測試可能因帳戶狀態而返回空資料，這是正常現象")
    print("   • 建議在開發測試時優先使用模擬數據")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用戶中斷測試執行")
    except Exception as e:
        print(f"\n\n❌ 測試過程中發生未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()