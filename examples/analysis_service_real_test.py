#!/usr/bin/env python3
"""
富邦 API MCP Server - Indicators Service 真實數據測試

此腳本用於測試 Indicators Service 的所有功能，使用真實的市場數據。
包含完整的真實數據測試案例，展示如何在實際市場數據上進行高級金融分析。

⚠️ 重要注意事項：
- 此腳本會調用真實的富邦 API 獲取市場數據
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
   pip install python-dotenv fubon-neo mcp pandas numpy

3. 運行測試：
   python examples/indicators_service_real_test.py

測試涵蓋範圍：
- 市場情緒指數生成
- 投資組合 VaR 計算
- 投資組合壓力測試
- 投資組合優化
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

import pandas as pd
import numpy as np

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加載環境變數
load_dotenv()

from fubon_api_mcp_server.config import config
from fubon_api_mcp_server.market_data_service import MarketDataService
from fubon_api_mcp_server.analysis_service import AnalysisService
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
        if isinstance(data, dict):
            print(f"   📊 資料字段: {list(data.keys())}")
            # 顯示具體數值
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    if 'var' in key.lower() or 'return' in key.lower() or 'volatility' in key.lower():
                        print(f"      {key}: {value:.4f}")
                    else:
                        print(f"      {key}: {value}")
                elif isinstance(value, list) and len(value) > 0:
                    print(f"      {key}: {len(value)} 筆資料")
        elif isinstance(data, list):
            print(f"   📊 資料筆數: {len(data)}")
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


def create_sample_portfolio(symbols_data: dict):
    """創建示例投資組合"""
    portfolio = []

    # 為每個股票創建持倉
    for symbol, data in symbols_data.items():
        if len(data['close']) > 0:
            current_price = data['close'].iloc[-1]
            # 隨機分配權重
            weight = np.random.uniform(0.05, 0.25)
            shares = np.random.randint(100, 1000)

            portfolio.append({
                "symbol": symbol,
                "shares": shares,
                "current_price": current_price,
                "weight": weight
            })

    # 正規化權重
    total_weight = sum(p['weight'] for p in portfolio)
    for p in portfolio:
        p['weight'] = p['weight'] / total_weight

    return portfolio


def main():
    """主測試函數"""
    print("🚀 富邦 API MCP Server - Indicators Service 真實數據測試")
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

        # 初始化即時資料連線
        sdk.init_realtime()
        print("✅ 即時資料連線初始化成功")

        # 初始化 REST 客戶端
        reststock = sdk.marketdata.rest_client.stock
        restfutopt = sdk.marketdata.rest_client.futopt

        if reststock is None:
            print("❌ 股票行情服務未初始化")
            return

        print("✅ REST 客戶端初始化成功")

    except Exception as e:
        print(f"❌ SDK 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. 初始化服務
    print_section("服務初始化")
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

        # 初始化 Market Data Service
        market_data_service = MarketDataService(
            mock_mcp, base_data_dir, reststock, restfutopt, sdk
        )
        print("✅ Market Data Service 初始化成功")

        # 初始化 Indicators Service
        indicators_service = AnalysisService(mock_mcp, sdk, accounts.data, reststock, restfutopt)
        print("✅ Indicators Service 初始化成功")

        # 獲取真實帳戶號碼用於測試
        if accounts.data and len(accounts.data) > 0:
            real_account = getattr(accounts.data[0], 'account', 'test_account')
            print(f"📋 使用真實帳戶進行測試: {real_account}")
        else:
            real_account = "test_account"
            print("⚠️ 無法獲取真實帳戶，使用測試帳戶")

    except Exception as e:
        print(f"❌ 服務初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 獲取真實市場數據
    print_section("獲取真實市場數據")

    # 測試股票清單
    test_symbols = ["2330", "2454", "2317", "6505", "2881"]  # 台積電、聯發科、鴻海、台塑、國泰金
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)  # 獲取120天的數據

    symbols_data = {}

    print(f"📈 獲取 {len(test_symbols)} 支股票的歷史數據 ({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')})")

    for symbol in test_symbols:
        try:
            print(f"   獲取 {symbol} 數據...")
            result = market_data_service.historical_candles({
                "symbol": symbol,
                "from_date": start_date.strftime("%Y-%m-%d"),
                "to_date": end_date.strftime("%Y-%m-%d")
            })

            if result.get('status') == 'success' and len(result.get('data', [])) >= 50:
                data = result.get('data', [])
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')

                symbols_data[symbol] = {
                    'close': df['close'],
                    'high': df['high'],
                    'low': df['low'],
                    'volume': df['volume'],
                    'data_points': len(df)
                }
                print(f"   ✅ {symbol}: {len(df)} 筆數據")
            else:
                print(f"   ⚠️  {symbol}: 數據不足 ({len(result.get('data', []))} 筆)，跳過此股票")

        except Exception as e:
            print(f"   ❌ {symbol}: 獲取失敗 - {e}")

    # 如果沒有足夠的真實數據，報錯退出
    if len(symbols_data) < 2:
        print("❌ 沒有足夠的真實市場數據進行測試，至少需要2支股票的數據")
        print("請檢查：")
        print("1. 環境變數是否正確設置")
        print("2. 網路連接是否正常")
        print("3. API 調用額度是否充足")
        print("4. 數據庫中是否有足夠的歷史數據")
        return

    total_data_points = sum(data['data_points'] for data in symbols_data.values())
    print(f"📊 總數據點數: {total_data_points}")

    # 5. 創建示例投資組合
    print_section("創建示例投資組合")
    portfolio = create_sample_portfolio(symbols_data)

    print("📊 投資組合組成:")
    total_value = 0
    for position in portfolio:
        value = position['shares'] * position['current_price']
        total_value += value
        print(f"   {position['symbol']}: {position['shares']} 股 @ {position['current_price']:.2f} = {value:,.0f} ({position['weight']:.1%})")

    print(f"   💰 總價值: {total_value:,.0f}")

    # 6. 執行所有測試
    test_results = []

    # 6.1 市場情緒指數測試
    print_section("市場情緒指數測試")

    # 測試：生成市場情緒指數
    result = run_test(
        "生成市場情緒指數",
        indicators_service.generate_market_sentiment_index,
        {"index_components": ["technical", "volume"], "lookback_period": 30}
    )
    test_results.append(("generate_market_sentiment_index", result))

    # 6.2 VaR 計算測試
    print_section("VaR 計算測試")

    # 測試：計算投資組合 VaR
    result = run_test(
        "計算投資組合 VaR",
        indicators_service.calculate_portfolio_var,
        {"account": real_account, "confidence_level": 0.95}
    )
    test_results.append(("calculate_portfolio_var", result))

    # 6.3 壓力測試
    print_section("壓力測試")

    # 測試：運行投資組合壓力測試
    result = run_test(
        "運行投資組合壓力測試",
        indicators_service.run_portfolio_stress_test,
        {"account": real_account, "scenarios": [
            {"name": "market_crash", "equity_drop": -0.2},
            {"name": "rate_hike", "rate_increase": 0.025}
        ]}
    )
    test_results.append(("run_portfolio_stress_test", result))

    # 6.4 投資組合優化測試
    print_section("投資組合優化測試")

    # 測試：優化投資組合
    result = run_test(
        "優化投資組合",
        indicators_service.optimize_portfolio_allocation,
        {"account": real_account, "target_return": 0.08}
    )
    test_results.append(("optimize_portfolio", result))

    # 7. 測試總結
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
        print(f"💡 測試數據: {len(symbols_data)} 支股票，總共 {total_data_points} 筆歷史數據")
        print("💡 所有分析都基於真實技術指標計算，提供專業的風險管理和投資組合分析")
    else:
        print(f"\n⚠️  有 {failed_tests} 個測試失敗，請檢查上面的詳細資訊")

    print("\n💡 使用提示：")
    print("   • 高級分析需要足夠的歷史數據，建議至少 50 個數據點")
    print("   • VaR 和壓力測試結果會因市場波動而變化")
    print("   • 投資組合優化可能需要調整目標回報率")
    print("   • 真實市場數據可能因交易時段而有所差異")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用戶中斷測試執行")
    except Exception as e:
        print(f"\n\n❌ 測試過程中發生未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()