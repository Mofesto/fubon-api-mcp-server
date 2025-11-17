#!/usr/bin/env python3
"""
富邦 API MCP Server - 高級指標真實數據測試

此腳本用於測試高級風險管理和市場分析功能，使用真實的市場數據。
包含完整的真實數據測試案例，展示如何在實際市場數據上計算高級指標。

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
   pip install python-dotenv fubon-neo mcp scipy pandas numpy

3. 運行測試：
   python examples/indicators_advanced_real_test.py

測試涵蓋範圍：
- 風險管理工具 (VaR, CVaR, 最大回撤, 尾部風險)
- 市場分析工具 (市場廣度, 資金流向, 恐懼貪婪指數)
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
from fubon_api_mcp_server.indicators_advanced import (
    calculate_portfolio_returns,
    calculate_historical_var, calculate_parametric_var, calculate_monte_carlo_var,
    calculate_max_drawdown, calculate_tail_risk, assess_risk_level,
    calculate_market_breadth, calculate_money_flow, calculate_fear_greed_index
)
from fubon_neo.sdk import FubonSDK


def print_section(title: str):
    """列印區段標題"""
    print(f"\n{'='*70}")
    print(f"🧪 {title}")
    print('='*70)


def print_indicator_result(indicator_name: str, result, description: str = ""):
    """列印指標計算結果"""
    print(f"\n📊 {indicator_name}")
    if description:
        print(f"   {description}")

    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, (int, float)):
                if key.endswith('_pct') or key in ['tail_ratio', 'composite_score']:
                    print(f"   {key}: {value:.4f}")
                elif key in ['var', 'cvar', 'max_dd', 'expected_shortfall']:
                    print(f"   {key}: {value:,.2f}")
                else:
                    print(f"   {key}: {value}")
            else:
                print(f"   {key}: {value}")
    else:
        print(f"   結果: {result}")


def run_risk_test(test_name: str, test_func, *args, **kwargs):
    """運行風險指標測試"""
    try:
        print(f"\n🔍 計算指標: {test_name}")
        result = test_func(*args, **kwargs)
        print_indicator_result(test_name, result)
        return {"status": "success", "result": result, "test_name": test_name}
    except Exception as e:
        error_msg = f"指標計算失敗: {str(e)}"
        print(f"❌ {test_name}: {error_msg}")
        return {"status": "error", "message": error_msg, "test_name": test_name}


def main():
    """主測試函數"""
    print("🚀 富邦 API MCP Server - 高級指標真實數據測試")
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

    # 4. 準備測試數據
    print_section("準備測試數據")

    # 測試股票清單 (台股大型權值股)
    test_symbols = ["2330", "2454", "2317", "6505", "2412"]  # 台積電、聯發科、鴻海、台塑、中華電
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365-1)  # 獲取一年的數據

    print(f"📈 獲取測試股票的歷史數據 ({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')})")

    # 讀取數據函數
    def read_data_func(symbol):
        try:
            result = market_data_service.historical_candles({
                "symbol": symbol,
                "from_date": start_date.strftime("%Y-%m-%d"),
                "to_date": end_date.strftime("%Y-%m-%d")
            })

            if result.get('status') == 'success' and result.get('data'):
                df = pd.DataFrame(result['data'])
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                return df
            else:
                return None
        except Exception as e:
            print(f"獲取 {symbol} 數據失敗: {e}")
            return None

    # 模擬投資組合持倉
    mock_positions = [
        {"stock_no": "2330", "quantity": 1000, "market_value": 1500000},  # 台積電
        {"stock_no": "2454", "quantity": 500, "market_value": 750000},    # 聯發科
        {"stock_no": "2317", "quantity": 2000, "market_value": 600000},   # 鴻海
        {"stock_no": "6505", "quantity": 3000, "market_value": 450000},   # 台塑
        {"stock_no": "2412", "quantity": 1500, "market_value": 300000},   # 中華電
    ]
    total_portfolio_value = sum(pos["market_value"] for pos in mock_positions)

    print(f"📊 模擬投資組合: {len(mock_positions)} 檔股票，總市值: {total_portfolio_value:,.0f}")

    # 5. 執行風險管理測試
    test_results = []

    print_section("風險管理指標測試")

    # 5.1 投資組合收益率計算
    print("\n📈 投資組合分析")

    portfolio_returns = calculate_portfolio_returns(
        mock_positions, lookback_period=252, read_data_func=read_data_func
    )

    if portfolio_returns is not None:
        print(f"✅ 成功計算投資組合收益率: {len(portfolio_returns)} 個數據點")
        print(f"   年化波動率: {portfolio_returns.std() * np.sqrt(252):.4f}")
        print(f"   年化收益率: {portfolio_returns.mean() * 252:.4f}")

        # 5.2 VaR 和 CVaR 計算
        confidence_levels = [0.95, 0.99]

        for conf in confidence_levels:
            test_results.append(run_risk_test(
                f"歷史模擬 VaR/CVaR ({conf:.0%})",
                calculate_historical_var,
                portfolio_returns, conf, total_portfolio_value
            ))

            test_results.append(run_risk_test(
                f"參數法 VaR/CVaR ({conf:.0%})",
                calculate_parametric_var,
                portfolio_returns, conf, total_portfolio_value
            ))

            test_results.append(run_risk_test(
                f"蒙地卡羅 VaR/CVaR ({conf:.0%})",
                calculate_monte_carlo_var,
                portfolio_returns, conf, total_portfolio_value, n_simulations=10000
            ))

        # 5.3 最大回撤分析
        test_results.append(run_risk_test(
            "最大回撤分析",
            calculate_max_drawdown,
            portfolio_returns, total_portfolio_value
        ))

        # 5.4 尾部風險評估
        test_results.append(run_risk_test(
            "尾部風險評估 (95% 信心水準)",
            calculate_tail_risk,
            portfolio_returns, 0.95
        ))

        # 5.5 風險等級評估
        # 找到成功的 VaR 和最大回撤結果
        var_result = None
        max_dd_result = None
        
        for result in test_results:
            if result.get('status') == 'success':
                test_name = result.get('test_name', '')
                if 'VaR' in test_name and var_result is None:
                    var_result = result['result']
                elif '最大回撤' in test_name:
                    max_dd_result = result['result']
        
        if var_result and max_dd_result:
            annual_vol = portfolio_returns.std() * np.sqrt(252)
            
            risk_level = assess_risk_level(
                var_result['var_pct'], annual_vol, max_dd_result['max_dd_pct']
            )
            
            print_indicator_result("風險等級評估", {
                "var_percentage": var_result['var_pct'],
                "annual_volatility": annual_vol,
                "max_drawdown_pct": max_dd_result['max_dd_pct'],
                "risk_level": risk_level
            })
        else:
            print("⚠️ 無法進行風險等級評估，缺少必要的指標數據")

    else:
        print("❌ 無法計算投資組合收益率，跳過風險指標測試")

    # 6. 市場分析測試
    print_section("市場分析指標測試")

    # 6.1 市場廣度指標
    test_results.append(run_risk_test(
        "市場廣度指標",
        calculate_market_breadth,
        test_symbols, read_data_func
    ))

    # 6.2 資金流向分析 (使用台積電數據)
    tsmc_data = read_data_func("2330")
    if tsmc_data is not None and len(tsmc_data) >= 14:
        test_results.append(run_risk_test(
            "資金流向指標 (台積電)",
            calculate_money_flow,
            tsmc_data
        ))
    else:
        print("❌ 台積電數據不足，跳過資金流向測試")

    # 6.3 恐懼貪婪指數
    # 計算各項分數 (簡化版本)
    breadth_result = test_results[-1]['result'] if test_results else {"composite_score": 0.5}
    technical_score = 0.6  # 假設技術指標分數
    volume_score = 0.7     # 假設成交量指標分數

    test_results.append(run_risk_test(
        "恐懼貪婪指數",
        calculate_fear_greed_index,
        technical_score, breadth_result.get('composite_score', 0.5), volume_score
    ))

    # 7. 測試總結
    print_section("測試總結")

    successful_tests = sum(1 for result in test_results if result.get('status') == 'success')
    failed_tests = len(test_results) - successful_tests

    print("📊 高級指標計算結果詳情：")
    for i, result in enumerate(test_results, 1):
        status = result.get('status', 'unknown')
        if status == 'success':
            print(f"   ✅ 指標 {i}: 計算成功")
        else:
            print(f"   ❌ 指標 {i}: {result.get('message', '未知錯誤')}")

    print(f"\n🎯 測試統計:")
    print(f"   總指標數: {len(test_results)}")
    print(f"   計算成功: {successful_tests}")
    print(f"   計算失敗: {failed_tests}")
    print(f"   成功率: {(successful_tests / len(test_results) * 100):.1f}%" if test_results else "   成功率: 0%")

    print(f"\n⏰ 測試結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if failed_tests == 0 and successful_tests > 0:
        print("\n🎉 所有高級指標計算都成功了！")
        print(f"💡 測試數據: {len(test_symbols)} 檔股票，一年歷史數據")
        print("💡 高級指標提供專業的風險管理和市場分析功能")
    else:
        print(f"\n⚠️  有 {failed_tests} 個指標計算失敗，請檢查上面的詳細資訊")

    print("\n💡 使用提示：")
    print("   • 高級指標需要大量的歷史數據，建議至少 200 個數據點")
    print("   • 投資組合分析需要多檔股票的歷史數據")
    print("   • VaR/CVaR 計算使用不同的方法，各有優缺點")
    print("   • 市場廣度指標反映整體市場健康狀況")
    print("   • 恐懼貪婪指數綜合多項指標評估市場情緒")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用戶中斷測試執行")
    except Exception as e:
        print(f"\n\n❌ 測試過程中發生未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()