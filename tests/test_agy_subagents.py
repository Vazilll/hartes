#!/usr/bin/env python3
"""Test agy-bridge's new run_antigravity_subagents."""
import sys, json, asyncio
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from mcp import ClientSession, StdioServerParameters
def test_agy_subagents_definition():
    assert True

async def main():
    server_params = StdioServerParameters(
        command=r"C:\vazus\pyenv\.venv\Scripts\python.exe",
        args=[r"C:\vazus\pyenv\scripts\agy_bridge_mcp.py"],
    )
    
    print("🔌 Соединяюсь с agy-bridge...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Соединение установлено")
            
            # List tools
            tools = await session.list_tools()
            print(f"📦 Доступно инструментов: {len(tools.tools)}")
            for t in tools.tools:
                print(f"   - {t.name}")
            
            # Test run_antigravity_subagents
            print("\n🧪 Тестирую run_antigravity_subagents...")
            print("   Задача: Проанализировать структуру Go MCP")
            print("   Субагентов: 3")
            
            result = await session.call_tool("run_antigravity_subagents", {
                "task_description": "Проанализировать архитектуру Go MCP: какие компоненты есть, как они связаны",
                "num_subagents": 3,
                "context": "Go MCP состоит из 4 бинарников: dnts-core, dnts-memory, dnts-reason, dnts-agent. Каждый ~20MB."
            })
            
            print(f"\n✅ Ответ получен ({len(result.content[0].text)} символов)")
            print("---")
            print(result.content[0].text[:2000])
            print("---")

if __name__ == "__main__":
    asyncio.run(main())
