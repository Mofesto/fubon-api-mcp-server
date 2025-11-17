#!/usr/bin/env python3
"""
富邦 API MCP Server - Reports Service 真實 API 手動測試

此腳本用於手動測試 Reports Service 的所有功能，使用真實的富邦 API。
包含完整的真實 API 測試案例，涵蓋所有 Reports Service 方法。

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
   python examples/reports_service_real_test.py

測試涵蓋範圍：
- 所有報告總覽
- 委託報告
- 委託變更報告
- 成交報告
- 事件報告
- 委託結果查詢
- 委託結果詳細資訊查詢
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加載環境變數
load_dotenv()

from fubon_api_mcp_server.config import config
from fubon_api_mcp_server.reports_service import ReportsService
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
            if 'order_reports' in data:
                print(f"   📊 委託報告: {len(data['order_reports'])} 筆")
                print(f"   📊 委託變更報告: {len(data['order_changed_reports'])} 筆")
                print(f"   📊 成交報告: {len(data['filled_reports'])} 筆")
                print(f"   📊 事件報告: {len(data['event_reports'])} 筆")
            else:
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
    print("🚀 富邦 API MCP Server - Reports Service 真實 API 手動測試")
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
            print("❌ SDK 登入失敗")
            if hasattr(accounts, 'message'):
                print(f"   錯誤訊息: {accounts.message}")
            return

        print(f"✅ SDK 初始化成功，獲取到 {len(accounts.data)} 個帳戶")

        # 選擇第一個帳戶作為測試帳戶
        test_account = accounts.data[0].account
        print(f"📋 測試帳戶: {test_account}")

    except Exception as e:
        print(f"❌ SDK 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. 初始化 Reports Service
    print_section("Reports Service 初始化")
    try:
        # 創建模擬 MCP 實例
        class MockMCP:
            def tool(self):
                def decorator(func):
                    return func
                return decorator

        mock_mcp = MockMCP()
        reports_service = ReportsService(mock_mcp, sdk, accounts.data)
        print("✅ Reports Service 初始化成功")

    except Exception as e:
        print(f"❌ Reports Service 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 執行所有測試
    test_results = []

    # 4.1 報告總覽測試
    print_section("報告總覽測試")

    # 測試：獲取所有報告
    result = run_test(
        "獲取所有報告",
        reports_service.get_all_reports,
        {}
    )
    test_results.append(("get_all_reports", result))

    # 4.2 個別報告測試
    print_section("個別報告測試")

    # 測試：獲取委託報告
    result = run_test(
        "獲取委託報告",
        reports_service.get_order_reports,
        {}
    )
    test_results.append(("get_order_reports", result))

    # 測試：獲取委託變更報告
    result = run_test(
        "獲取委託變更報告",
        reports_service.get_order_changed_reports,
        {}
    )
    test_results.append(("get_order_changed_reports", result))

    # 測試：獲取成交報告
    result = run_test(
        "獲取成交報告",
        reports_service.get_filled_reports,
        {}
    )
    test_results.append(("get_filled_reports", result))

    # 測試：獲取事件報告
    result = run_test(
        "獲取事件報告",
        reports_service.get_event_reports,
        {}
    )
    test_results.append(("get_event_reports", result))

    # 4.3 委託結果測試
    print_section("委託結果測試")

    # 測試：獲取委託結果
    result = run_test(
        "獲取委託結果",
        reports_service.get_order_results,
        {"account": test_account}
    )
    test_results.append(("get_order_results", result))

    # 如果有委託結果，測試詳細資訊
    if result.get('status') == 'success' and result.get('data'):
        order_results = result['data']
        if order_results:
            # 選擇第一筆委託單進行詳細測試
            first_order = order_results[0]
            # 檢查 OrderResult 對象的屬性
            if hasattr(first_order, 'order_no'):
                order_no = first_order.order_no
            elif hasattr(first_order, 'OrderNo'):
                order_no = first_order.OrderNo
            else:
                print("⚠️  無法獲取委託單號，跳過詳細資訊測試")
                order_no = None

            if order_no:
                result_detail = run_test(
                    f"獲取委託結果詳細資訊 (單號: {order_no})",
                    reports_service.get_order_results_detail,
                    {"account": test_account, "order_no": order_no}
                )
                test_results.append(("get_order_results_detail", result_detail))
            else:
                print("⚠️  無法獲取委託單號，跳過詳細資訊測試")
        else:
            print("⚠️  無委託結果資料，跳過詳細資訊測試")
    else:
        print("⚠️  委託結果查詢失敗，跳過詳細資訊測試")

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
    print("   • 報告資料取決於帳戶的交易活動，可能為空")
    print("   • 委託結果詳細資訊測試需要有現有的委託單")
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