"""
測試包初始化
"""

# 測試配置
TEST_CONFIG = {
    "timeout": 30,  # API調用超時時間（秒）
    "retry_count": 3,  # 重試次數
    "test_account": None,  # 測試帳戶（由conftest.py設置）
}

# 測試數據
TEST_SYMBOLS = {
    "tse": "2330",  # 台積電
    "otc": "3443",  # 創意
    "tse_small": "2881",  # 富邦金
}

# 測試常數
MARKET_TYPES = ["Common", "Emg", "Odd"]
PRICE_TYPES = ["Limit", "Market", "LimitUp", "LimitDown"]
TIME_IN_FORCE = ["ROD", "IOC", "FOK"]
ORDER_TYPES = ["Stock", "Margin", "Short", "DayTrade"]
