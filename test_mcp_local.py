#!/usr/bin/env python3
"""
簡單的MCP服務器測試腳本
用於驗證本地MCP服務器是否正常工作
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加項目根目錄到Python路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fubon_api_mcp_server.server import mcp

async def test_mcp_server():
    """測試MCP服務器基本功能"""
    print("🔍 測試MCP服務器...")

    # 測試服務器初始化
    try:
        # 獲取可用工具列表
        tools = await mcp.list_tools()
        print(f"✅ 找到 {len(tools)} 個工具")

        # 顯示前5個工具名稱
        tool_names = [tool.name for tool in tools[:5]]
        print(f"📋 前5個工具: {', '.join(tool_names)}")

        # 測試基本工具調用 (如果有get_realtime_quotes)
        if any(tool.name == "get_realtime_quotes" for tool in tools):
            print("🧪 測試 get_realtime_quotes 工具...")
            try:
                result = await mcp.call_tool("get_realtime_quotes", {"args": {"symbol": "2330"}})
                print(f"✅ 工具調用成功: {result}")
            except Exception as e:
                print(f"⚠️ 工具調用失敗 (可能是因為未登入): {e}")

        print("🎉 MCP服務器測試完成!")

    except Exception as e:
        print(f"❌ MCP服務器測試失敗: {e}")
        return False

    return True

if __name__ == "__main__":
    print("🚀 啟動MCP服務器測試...")
    success = asyncio.run(test_mcp_server())
    sys.exit(0 if success else 1)