"""
富邦證券 Model Context Protocol (MCP) 服務器包

此包提供完整的富邦證券交易和數據服務，通過 MCP 協議與 AI 助手集成。

主要功能:
- 股票歷史數據查詢（支援本地快取）
- 即時行情數據獲取
- 股票交易下單（買賣、改價、改量、取消）
- 帳戶資訊查詢（資金餘額、庫存、損益）
- 主動回報監聽（委託、成交、事件通知）
- 批量並行下單功能

使用方式:
    from fubon_api_mcp_server.server import main, mcp
    main()  # 啟動 MCP 服務器

或通過命令行:
    python -m fubon_api_mcp_server.server

環境變數:
- FUBON_USERNAME: 富邦證券帳號
- FUBON_PASSWORD: 登入密碼
- FUBON_PFX_PATH: PFX 憑證檔案路徑
- FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）
- FUBON_DATA_DIR: 本地數據儲存目錄（可選）

版本: 1.6.0
作者: Fubon MCP Team
"""

__version__ = "2.2.3"
__author__ = "Fubon MCP Team"
