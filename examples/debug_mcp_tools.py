"""Test script to verify MCP tools registration."""
import asyncio
from fubon_mcp.config import mcp


async def check_tools():
    """Check registered tools."""
    print("Importing server module...")
    import fubon_mcp.server  # noqa: F401
    
    print("Getting tools...")
    tools = await mcp.get_tools()
    
    print(f"\n總共註冊了 {len(tools)} 個工具")
    print("\n已註冊的工具列表:")
    
    # tools 是一個字典，key 是工具名稱
    if isinstance(tools, dict):
        for tool_name, tool_info in tools.items():
            desc = tool_info.get('description', 'No description') if isinstance(tool_info, dict) else str(tool_info)
            desc_short = desc[:80] if len(desc) > 80 else desc
            print(f"  - {tool_name}: {desc_short}...")
    else:
        # 如果是列表
        for tool in tools:
            if hasattr(tool, 'name'):
                desc = tool.description[:80] if tool.description and len(tool.description) > 80 else (tool.description or 'No description')
                print(f"  - {tool.name}: {desc}...")
            else:
                print(f"  - {tool}")
    
    return tools


if __name__ == "__main__":
    asyncio.run(check_tools())
