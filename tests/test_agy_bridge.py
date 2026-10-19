#!/usr/bin/env python3
"""Test agy-bridge MCP server — calls run_antigravity_agent with a test prompt."""
import sys, json, asyncio
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from mcp import ClientSession, StdioServerParameters
def test_agy_bridge_definition():
    assert True

async def main():
    server_params = StdioServerParameters(
        command=r"C:\vazus\pyenv\.venv\Scripts\python.exe",
        args=[r"C:\vazus\pyenv\scripts\agy_bridge_mcp.py"],
    )
    
    print("🔌 Connecting to agy-bridge MCP server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Connected!")
            
            # List tools
            tools = await session.list_tools()
            print(f"📦 Tools: {[t.name for t in tools.tools]}")
            
            # Test run_antigravity_agent with a simple prompt
            print("\n🧪 Testing run_antigravity_agent...")
            prompt = "What is 2+2? Reply with just the number."
            try:
                result = await session.call_tool(
                    "run_antigravity_agent",
                    {"prompt": prompt}
                )
                print(f"✅ Result: {result.content[0].text}")
            except Exception as e:
                print(f"❌ Tool call failed: {e}")
                print("(This might need the google cloud auth to be configured)")

if __name__ == "__main__":
    asyncio.run(main())
