"""
測試配置和共享fixtures
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# 只有在需要真實 SDK 時才載入 fubon_neo
USE_REAL_SDK = os.getenv("USE_REAL_SDK", "false").lower() == "true"

if USE_REAL_SDK:
    try:
        from fubon_neo.sdk import FubonSDK
    except ImportError:
        FubonSDK = None
else:
    FubonSDK = None

# 加載環境變數
load_dotenv()


@pytest.fixture(scope="session")
def fubon_credentials():
    """獲取富邦API認證資訊"""
    username = os.getenv("FUBON_USERNAME")
    password = os.getenv("FUBON_PASSWORD")
    pfx_path = os.getenv("FUBON_PFX_PATH")
    pfx_password = os.getenv("FUBON_PFX_PASSWORD")

    if not all([username, password, pfx_path]):
        pytest.skip("缺少必要的環境變數: FUBON_USERNAME, FUBON_PASSWORD, FUBON_PFX_PATH")

    return {"username": username, "password": password, "pfx_path": pfx_path, "pfx_password": pfx_password}


@pytest.fixture(scope="session")
def fubon_sdk(fubon_credentials):
    """初始化富邦SDK實例 - 使用正式環境"""
    if not FubonSDK:
        pytest.skip("FubonSDK not available")

    # 使用正式環境 URL (生產環境)
    sdk = FubonSDK()
    accounts = sdk.login(
        fubon_credentials["username"],
        fubon_credentials["password"],
        fubon_credentials["pfx_path"],
        fubon_credentials["pfx_password"] or "",
    )

    # 檢查登入是否成功
    if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
        pytest.skip("無法登入到富邦SDK - 請檢查憑證")

    # 初始化即時連線
    try:
        sdk.init_realtime()
    except Exception as e:
        print(f"Warning: 無法初始化即時連線: {e}", file=__import__("sys").stderr)

    # 返回 SDK 和帳戶資訊的元組
    yield sdk, accounts

    # 清理：關閉連線
    try:
        sdk.logout()
    except Exception:
        pass


@pytest.fixture(scope="session")
def rest_client(fubon_sdk):
    """獲取REST客戶端 - 嘗試獲取，實際測試時再決定是否跳過"""
    sdk, accounts = fubon_sdk
    try:
        return sdk.marketdata.rest_client.stock
    except AttributeError:
        return None


@pytest.fixture(scope="session")
def test_account(fubon_credentials):
    """測試帳戶號碼"""
    return fubon_credentials["username"]


@pytest.fixture(scope="session")
def data_dir():
    """測試數據目錄"""
    data_path = Path(os.getenv("FUBON_DATA_DIR", "./data"))
    data_path.mkdir(exist_ok=True)
    return data_path


@pytest.fixture(autouse=True)
def skip_if_not_trading_hours():
    """在非交易時段跳過某些測試 - 正式環境 9:00~15:00"""
    import datetime

    now = datetime.datetime.now()
    current_time = now.time()

    # 正式環境開盤時間：09:00~15:00 (週一到週五)
    is_weekday = now.weekday() < 5  # 0-4 是週一到週五
    trading_start = datetime.time(9, 0)
    trading_end = datetime.time(15, 0)

    is_trading_hours = is_weekday and (trading_start <= current_time <= trading_end)

    return is_trading_hours
