import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from open_deep_research.deep_researcher import deep_researcher_builder
from langgraph.checkpoint.memory import MemorySaver

# Load environment variables
load_dotenv()

async def main():
    query = "Latest status and news about RWKV-7 language model as of July 2026"
    print(f"Starting research on: {query}")
    
    checkpointer = MemorySaver()
    graph = deep_researcher_builder.compile(checkpointer=checkpointer)
    
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "max_structured_output_retries": 3,
            "allow_clarification": False,
            "max_concurrent_research_units": 2, # Keep it small for test
            "search_api": "google",             # Use our newly added Google Search Grounding!
            "max_researcher_iterations": 2,     # Short run for quick testing
            "max_react_tool_calls": 3
        }
    }
    
    final_state = await graph.ainvoke(
        {"messages": [{"role": "user", "content": query}]},
        config
    )
    
    report = final_state.get("final_report")
    if report:
        md_filename = "rwkv7_july2026_report.md"
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Google Grounded Deep Research report saved successfully to {md_filename}")
    else:
        print("Error: No final report generated.")

if __name__ == "__main__":
    asyncio.run(main())
