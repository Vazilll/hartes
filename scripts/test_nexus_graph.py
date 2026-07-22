import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dnts_core.nexus_graph import nexus_graph
from dnts_core.state import NexusState

async def run_test():
    # Provide the initial state
    initial_state = {
        "task": "Write a python function that sorts an array of integers using bubble sort. Do NOT use built-in sort functions.",
        "messages": [],
        "complexity": "",
        "generated_code": "",
        "verifier_output": "",
        "debate_iterations": 0,
        "final_response": ""
    }
    
    print("Starting NEXUS LangGraph Test Execution...")
    
    # We can stream the state transitions to see the graph working
    async for event in nexus_graph.astream(initial_state):
        for node_name, state_update in event.items():
            print(f"\n[{node_name.upper()} COMPLETED]")
            if "complexity" in state_update and node_name == "analyze_complexity":
                print(f"-> Selected Route: {state_update['complexity']}")
            if "verifier_output" in state_update:
                print(f"-> Verifier Result:\n{state_update['verifier_output']}")
            if "debate_iterations" in state_update:
                print(f"-> Debate Iteration: {state_update['debate_iterations']}")
            if "final_response" in state_update and state_update["final_response"]:
                print(f"-> FINAL RESPONSE ACQUIRED!")
                
    print("\nExecution Finished.")

if __name__ == "__main__":
    asyncio.run(run_test())
