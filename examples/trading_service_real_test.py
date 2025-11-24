#!/usr/bin/env python3
"""
富邦 API MCP Server - Trading Service 真實 API 手動測試

此腳本用於手動測試 Trading Service 的讀取型功能，使用真實的富邦 API。
預設不會執行任何會送單/改單/取消的操作；如需開啟，請閱讀下方⚠️注意事項。

⚠️ 重要注意事項：
- 此腳本會調用真實的富邦 API
- 需要正確的環境變數設定
- 預設僅執行查詢類（唯讀）API，安全無風險
- 如需測試送單/改單/取消/條件單，請設定環境變數 ENABLE_LIVE_TRADING_TESTS=1 並審慎評估風險

使用前準備：
1. 設定環境變數：
   - FUBON_USERNAME=您的帳號
   - FUBON_PASSWORD=您的密碼
   - FUBON_PFX_PATH=PFX憑證檔案路徑
   - FUBON_PFX_PASSWORD=PFX密碼（可選）

2. 安裝依賴：
   pip install python-dotenv fubon-neo mcp

3. 運行測試：
   python examples/trading_service_real_test.py

測試涵蓋範圍（預設唯讀）：
- 委託結果清單（get_order_results）
- 委託結果詳細（get_order_results_detail）
- 條件單清單（get_condition_order）
- 條件單詳細查詢（get_condition_order_by_id，需要有條件單資料）
- 移動鎖利單清單（get_trail_order）

可選（需設定 ENABLE_LIVE_TRADING_TESTS=1）：
- 下單/取消/改價/改量（place/cancel/modify）
- 單一/多條件/當沖/分時分量/停損停利 條件單
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
from fubon_api_mcp_server.trading_service import TradingService
from fubon_neo.sdk import FubonSDK


def print_section(title: str):
    print(f"\n{'='*70}")
    print(f"🧪 {title}")
    print('='*70)


def print_test_result(test_name: str, result: dict, expected_success: bool = True):
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

    if 'data' in result:
        data = result['data']
        if isinstance(data, list):
            print(f"   📊 資料筆數: {len(data)}")
        elif isinstance(data, dict):
            print(f"   📊 資料字段: {list(data.keys())}")
        else:
            print(f"   📊 資料類型: {type(data).__name__}")


def run_test(test_name: str, test_func, *args, **kwargs):
    try:
        print(f"\n🔍 執行測試: {test_name}")
        result = test_func(*args, **kwargs)
        print_test_result(test_name, result)
        return result
    except Exception as e:
        error_result = {"status": "error", "message": f"測試執行失敗: {str(e)}"}
        print_test_result(test_name, error_result)
        return error_result


def main():
    print("🚀 富邦 API MCP Server - Trading Service 真實 API 手動測試")
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
            print(f"   set {env}=<您的{env.replace('FUBON_', '')}>")
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
        test_account = accounts.data[0].account
        print(f"📋 測試帳戶: {test_account}")

        # 初始化即時資料連線（部分交易通道會用到）
        sdk.init_realtime()
        print("✅ 即時資料連線初始化成功")

        # 初始化 REST 客戶端（雖然交易主要用不到，保持與其他服務一致）
        reststock = sdk.marketdata.rest_client.stock
        restfutopt = sdk.marketdata.rest_client.futopt
        if reststock is None:
            print("❌ 股票行情服務未初始化")
            return
        if restfutopt is None:
            print("❌ 期貨/選擇權行情服務未初始化")
            return
        print("✅ REST 客戶端初始化成功")
    except Exception as e:
        print(f"❌ SDK 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. 初始化 Trading Service
    print_section("Trading Service 初始化")
    try:
        class MockMCP:
            def tool(self):
                def decorator(func):
                    return func
                return decorator

        mock_mcp = MockMCP()
        base_data_dir = config.BASE_DATA_DIR
        base_data_dir.mkdir(exist_ok=True)

        trading_service = TradingService(
            mock_mcp, sdk, [a.account for a in accounts.data], base_data_dir, reststock, restfutopt
        )
        print("✅ Trading Service 初始化成功")
    except Exception as e:
        print(f"❌ Trading Service 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 執行唯讀測試
    print_section("唯讀查詢測試")
    test_results = []

    result = run_test(
        "獲取委託結果清單",
        trading_service.get_order_results,
        {"account": test_account}
    )
    test_results.append(("get_order_results", result))

    result = run_test(
        "獲取委託結果詳細資訊",
        trading_service.get_order_results_detail,
        {"account": test_account}
    )
    test_results.append(("get_order_results_detail", result))

    result = run_test(
        "查詢條件單清單",
        trading_service.get_condition_order,
        {"account": test_account}
    )
    test_results.append(("get_condition_order", result))

    # 測試條件單ID查詢（如果有條件單資料）
    if result.get('status') == 'success' and result.get('data'):
        condition_orders = result['data']
        if isinstance(condition_orders, list) and len(condition_orders) > 0:
            first_condition_id = condition_orders[0].get('condition_id')
            if first_condition_id:
                result = run_test(
                    f"查詢條件單詳細 (ID: {first_condition_id})",
                    trading_service.get_condition_order_by_id,
                    {"account": test_account, "condition_id": first_condition_id}
                )
                test_results.append(("get_condition_order_by_id", result))

    result = run_test(
        "查詢移動鎖利單清單",
        trading_service.get_trail_order,
        {"account": test_account}
    )
    test_results.append(("get_trail_order", result))

    # 測試當沖條件單查詢（如果有資料且有condition_no）
    # 注意：get_daytrade_condition_by_id 需要具體的 condition_no，此處跳過
    # 如果需要測試，請手動指定 condition_no
    print("⏭️  跳過 get_daytrade_condition_by_id 測試（需要指定 condition_no）")

    # 5. 可選：執行送單/改單/取消/條件單（需顯式開啟）
    if os.getenv('ENABLE_LIVE_TRADING_TESTS') == '1':
        print_section("⚠️ 實單操作測試（高風險，請務必確認！）")
        print("已啟用 ENABLE_LIVE_TRADING_TESTS=1，將進行真實下單相關操作。")

        # 範例：下單（請務必調整為您可接受的商品與數量）
        # result = run_test(
        #     "下單測試（示範，請自行調整）",
        #     trading_service.place_order,
        #     {
        #         "account": test_account,
        #         "buy_sell": "Buy",
        #         "symbol": "2330",
        #         "price": "1.00",  # 請自行設定合理價格
        #         "quantity": 1000,
        #         "market_type": "Common",
        #         "price_type": "Limit",
        #         "time_in_force": "ROD",
        #         "order_type": "Stock",
        #     },
        # )
        # test_results.append(("place_order", result))

        # --- 進階條件單範例 (Cookbook) ---
        # 以下範例展示如何使用進階條件單功能，請根據需求取消註解並修改參數

        # 1. 多條件單 (Multi-Condition Order)
        # 情境：當台積電(2330)成交價大於 1000 且 總量大於 50000 張時，以 1005 元買進 1000 股
        # result = run_test(
        #     "多條件單測試",
        #     trading_service.place_multi_condition_order,
        #     {
        #         "account": test_account,
        #         "start_date": datetime.now().strftime("%Y%m%d"),
        #         "end_date": datetime.now().strftime("%Y%m%d"),
        #         "stop_sign": "Full",
        #         "conditions": [
        #             {
        #                 "market_type": "Reference",
        #                 "symbol": "2330",
        #                 "trigger": "MatchedPrice",
        #                 "trigger_value": "1000",
        #                 "comparison": "Greater"
        #             },
        #             {
        #                 "market_type": "Reference",
        #                 "symbol": "2330",
        #                 "trigger": "TotalQuantity",
        #                 "trigger_value": "50000",
        #                 "comparison": "Greater"
        #             }
        #         ],
        #         "order": {
        #             "buy_sell": "Buy",
        #             "symbol": "2330",
        #             "price": "1005",
        #             "quantity": 1000
        #         }
        #     }
        # )
        # test_results.append(("place_multi_condition_order", result))

        # 2. 分時分量單 (Time-Slice Order)
        # 情境：將 5000 股 (5張) 台積電，每 30 秒下 1000 股 (1張)，共分 5 次
        # result = run_test(
        #     "分時分量單測試",
        #     trading_service.place_time_slice_order,
        #     {
        #         "account": test_account,
        #         "start_date": datetime.now().strftime("%Y%m%d"),
        #         "end_date": datetime.now().strftime("%Y%m%d"),
        #         "stop_sign": "Full",
        #         "split": {
        #             "method": "Type1",
        #             "interval": 30,
        #             "single_quantity": 1000,
        #             "total_quantity": 5000,
        #             "start_time": "090000"
        #         },
        #         "order": {
        #             "buy_sell": "Buy",
        #             "symbol": "2330",
        #             "price": "1000",
        #             "quantity": 5000
        #         }
        #     }
        # )
        # test_results.append(("place_time_slice_order", result))

        # 3. 停損停利條件單 (TPSL Order)
        # 情境：當台積電成交價大於 1000 時買進，並設定停利 1050，停損 950
        # result = run_test(
        #     "停損停利條件單測試",
        #     trading_service.place_tpsl_condition_order,
        #     {
        #         "account": test_account,
        #         "start_date": datetime.now().strftime("%Y%m%d"),
        #         "end_date": datetime.now().strftime("%Y%m%d"),
        #         "stop_sign": "Full",
        #         "condition": {
        #             "market_type": "Reference",
        #             "symbol": "2330",
        #             "trigger": "MatchedPrice",
        #             "trigger_value": "1000",
        #             "comparison": "Greater"
        #         },
        #         "order": {
        #             "buy_sell": "Buy",
        #             "symbol": "2330",
        #             "price": "1005",
        #             "quantity": 1000
        #         },
        #         "tpsl": {
        #             "stop_sign": "Full",
        #             "tp": {
        #                 "time_in_force": "ROD",
        #                 "price_type": "Limit",
        #                 "order_type": "Stock",
        #                 "target_price": "1050",
        #                 "price": "1050"
        #             },
        #             "sl": {
        #                 "time_in_force": "ROD",
        #                 "price_type": "Limit",
        #                 "order_type": "Stock",
        #                 "target_price": "950",
        #                 "price": "950"
        #             }
        #         }
        #     }
        # )
        # test_results.append(("place_tpsl_condition_order", result))

    else:
        print_section("實單操作測試（已停用）")
        print("未設定 ENABLE_LIVE_TRADING_TESTS=1，略過所有送單/改單/取消/條件單測試。")

    # 6. 測試總結
    print_section("測試總結")
    successful_tests = 0
    failed_tests = 0
    print("📊 測試結果詳情：")
    for test_name, result in test_results:
        status = result.get('status', 'unknown') if isinstance(result, dict) else 'unknown'
        if status == 'success':
            successful_tests += 1
            print(f"   ✅ {test_name}")
        else:
            failed_tests += 1
            msg = result.get('message', '未知錯誤') if isinstance(result, dict) else str(result)
            print(f"   ❌ {test_name}: {msg}")

    total = len(test_results)
    print(f"\n🎯 測試統計:")
    print(f"   總測試數: {total}")
    print(f"   成功: {successful_tests}")
    print(f"   失敗: {failed_tests}")
    if total:
        print(f"   成功率: {(successful_tests / total * 100):.1f}%")

    print(f"\n⏰ 測試結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if failed_tests == 0:
        print("\n🎉 唯讀測試全部通過！")
    else:
        print(f"\n⚠️  有 {failed_tests} 個測試失敗，請檢查上面的詳細資訊")

    print("\n💡 提示：")
    print("   • 此測試使用真實 API，結果可能受網路/市場影響")
    print("   • 實單操作請務必審慎，建議先驗證唯讀接口與參數")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用戶中斷測試執行")
    except Exception as e:
        print(f"\n\n❌ 測試過程中發生未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()
