import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dnts_core.unified_graph import unified_graph

async def run_test():
    # Provide the initial state
    initial_state = {
        "task": "Исследуй новые модели CodeGemma",
        "messages": [],
        "complexity": "",
        "generated_code": "",
        "verifier_output": "",
        "debate_iterations": 0,
        "final_response": ""
    }
    
    print("Starting Unified LangGraph Test Execution...")
    
    # We can stream the state transitions to see the graph working
    async for event in unified_graph.astream(initial_state):
        for node_name, state_update in event.items():
            print(f"\n[{node_name.upper()} COMPLETED]")
            if "intent" in state_update and node_name == "unified_router":
                print(f"-> Selected Route: {state_update['intent']}")
            if "final_response" in state_update and state_update["final_response"]:
                print(f"-> FINAL RESPONSE ACQUIRED!")
                
    print("\nExecution Finished.")

if __name__ == "__main__":
    asyncio.run(run_test())
