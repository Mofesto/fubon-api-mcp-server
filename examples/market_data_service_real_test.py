#!/usr/bin/env python3
"""
富邦 API MCP Server - Market Data Service 真實 API 手動測試

此腳本用於手動測試 Market Data Service 的所有功能，使用真實的富邦 API。
包含完整的真實 API 測試案例，涵蓋所有 Market Data Service 方法。

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
   python examples/market_data_service_real_test.py

測試涵蓋範圍：
- 歷史數據查詢
- 即時行情數據獲取
- 市場統計數據
- 技術指標計算
- 期貨/選擇權市場數據
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
from fubon_api_mcp_server.market_data_service import MarketDataService
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
    print("🚀 富邦 API MCP Server - Market Data Service 真實 API 手動測試")
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

        # 初始化即時資料連線
        sdk.init_realtime()
        print("✅ 即時資料連線初始化成功")

        # 初始化 REST 客戶端
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

    # 3. 初始化 Market Data Service
    print_section("Market Data Service 初始化")
    try:
        # 創建模擬 MCP 實例
        class MockMCP:
            def tool(self):
                def decorator(func):
                    return func
                return decorator

        mock_mcp = MockMCP()
        base_data_dir = config.BASE_DATA_DIR
        base_data_dir.mkdir(exist_ok=True)

        market_data_service = MarketDataService(
            mock_mcp, base_data_dir, reststock, restfutopt, sdk
        )
        print("✅ Market Data Service 初始化成功")

    except Exception as e:
        print(f"❌ Market Data Service 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 執行所有測試
    test_results = []

    # 4.1 歷史數據測試
    print_section("歷史數據測試")

    # 測試：獲取歷史數據（台積電）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    result = run_test(
        "獲取歷史數據（台積電）",
        market_data_service.historical_candles,
        {
            "symbol": "2330",
            "from_date": start_date.strftime("%Y-%m-%d"),
            "to_date": end_date.strftime("%Y-%m-%d")
        }
    )
    test_results.append(("historical_candles", result))

    # 4.2 股票即時行情測試
    print_section("股票即時行情測試")

    # 測試：獲取股票列表
    result = run_test(
        "獲取股票列表（上市）",
        market_data_service.get_intraday_tickers,
        {"market": "TSE"}
    )
    test_results.append(("get_intraday_tickers", result))

    # 測試：獲取股票基本資料
    result = run_test(
        "獲取股票基本資料（台積電）",
        market_data_service.get_intraday_ticker,
        {"symbol": "2330"}
    )
    test_results.append(("get_intraday_ticker", result))

    # 測試：獲取股票即時報價
    result = run_test(
        "獲取股票即時報價（台積電）",
        market_data_service.get_intraday_quote,
        {"symbol": "2330"}
    )
    test_results.append(("get_intraday_quote", result))

    # 測試：獲取股票 K 線
    result = run_test(
        "獲取股票 K 線（台積電）",
        market_data_service.get_intraday_candles,
        {"symbol": "2330"}
    )
    test_results.append(("get_intraday_candles", result))

    # 測試：獲取股票成交明細
    result = run_test(
        "獲取股票成交明細（台積電）",
        market_data_service.get_intraday_trades,
        {"symbol": "2330"}
    )
    test_results.append(("get_intraday_trades", result))

    # 測試：獲取股票分價量表
    result = run_test(
        "獲取股票分價量表（台積電）",
        market_data_service.get_intraday_volumes,
        {"symbol": "2330"}
    )
    test_results.append(("get_intraday_volumes", result))

    # 4.3 市場快照測試
    print_section("市場快照測試")

    # 測試：獲取股票行情快照
    result = run_test(
        "獲取股票行情快照（上市）",
        market_data_service.get_snapshot_quotes,
        {"market": "TSE"}
    )
    test_results.append(("get_snapshot_quotes", result))

    # 測試：獲取股票漲跌幅排行
    result = run_test(
        "獲取股票漲跌幅排行（上市）",
        market_data_service.get_snapshot_movers,
        {"market": "TSE"}
    )
    test_results.append(("get_snapshot_movers", result))

    # 測試：獲取股票成交量值排行
    result = run_test(
        "獲取股票成交量值排行（上市）",
        market_data_service.get_snapshot_actives,
        {"market": "TSE"}
    )
    test_results.append(("get_snapshot_actives", result))

    # 4.4 統計數據測試
    print_section("統計數據測試")

    # 測試：獲取近52週股價數據
    result = run_test(
        "獲取近52週股價數據（台積電）",
        market_data_service.get_historical_stats,
        {"symbol": "2330"}
    )
    test_results.append(("get_historical_stats", result))

    # 測試：獲取即時行情
    result = run_test(
        "獲取即時行情（台積電）",
        market_data_service.get_realtime_quotes,
        {"symbol": "2330"}
    )
    test_results.append(("get_realtime_quotes", result))

    # 4.5 期貨/選擇權測試
    print_section("期貨/選擇權測試")

    # 測試：獲取期貨/選擇權合約列表
    result = run_test(
        "獲取期貨合約列表",
        market_data_service.get_intraday_futopt_products,
        {"type": "FUTURE"}
    )
    test_results.append(("get_intraday_futopt_products_future", result))

    # 測試：獲取期貨/選擇權列表
    result = run_test(
        "獲取期貨列表",
        market_data_service.get_intraday_futopt_tickers,
        {"type": "FUTURE"}
    )
    test_results.append(("get_intraday_futopt_tickers", result))

    # 測試：獲取期貨/選擇權基本資料
    result = run_test(
        "獲取期貨基本資料（台指期）",
        market_data_service.get_intraday_futopt_ticker,
        {"symbol": "TXFK5"}
    )
    test_results.append(("get_intraday_futopt_ticker", result))

    # 測試：獲取期貨/選擇權即時報價
    result = run_test(
        "獲取期貨即時報價（台指期）",
        market_data_service.get_intraday_futopt_quote,
        {"symbol": "TXFK5"}
    )
    test_results.append(("get_intraday_futopt_quote", result))

    # 測試：獲取期貨/選擇權 K 線
    result = run_test(
        "獲取期貨 K 線（台指期）",
        market_data_service.get_intraday_futopt_candles,
        {"symbol": "TXFK5"}
    )
    test_results.append(("get_intraday_futopt_candles", result))

    # 測試：獲取期貨/選擇權成交明細
    result = run_test(
        "獲取期貨成交明細（台指期）",
        market_data_service.get_intraday_futopt_trades,
        {"symbol": "TXFK5"}
    )
    test_results.append(("get_intraday_futopt_trades", result))

    # 測試：獲取期貨/選擇權分價量表
    result = run_test(
        "獲取期貨分價量表（台指期）",
        market_data_service.get_intraday_futopt_volumes,
        {"symbol": "TXFK5"}
    )
    test_results.append(("get_intraday_futopt_volumes", result))

    # 4.6 技術指標測試
    print_section("技術指標測試")

    # 測試：獲取交易信號
    result = run_test(
        "獲取交易信號（台積電）",
        market_data_service.get_trading_signals,
        {"symbol": "2330"}
    )
    test_results.append(("get_trading_signals", result))

    # 4.7 需要帳戶的測試
    print_section("需要帳戶的測試")

    # 測試：查詢股票快照
    result = run_test(
        "查詢股票快照",
        market_data_service.query_symbol_snapshot,
        {"account": test_account, "market_type": "Common", "stock_type": ["Stock"]}
    )
    test_results.append(("query_symbol_snapshot", result))

    # 測試：查詢股票報價
    result = run_test(
        "查詢股票報價",
        market_data_service.query_symbol_quote,
        {"account": test_account, "symbol": "2330"}
    )
    test_results.append(("query_symbol_quote", result))

    # 測試：保證金配額查詢
    result = run_test(
        "保證金配額查詢",
        market_data_service.margin_quota,
        {"account": test_account, "stock_no": "2330"}
    )
    test_results.append(("margin_quota", result))

    # 測試：當沖與股票資訊
    result = run_test(
        "當沖與股票資訊",
        market_data_service.daytrade_and_stock_info,
        {"account": test_account, "stock_no": "2330"}
    )
    test_results.append(("daytrade_and_stock_info", result))

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
    print("   • 部分測試可能因市場狀況而返回空資料，這是正常現象")
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