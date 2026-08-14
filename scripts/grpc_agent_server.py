import sys
import asyncio
import uuid
import grpc
from concurrent import futures
import orchestrator_pb2
import orchestrator_pb2_grpc

sys.path.insert(0, "C:/vazus/pyenv")
sys.path.insert(0, "C:/vazus")

from scripts.subagent_rlm_bridge import RLMSubagentBridge

def _run_rlm_sync(prompt, complexity, max_iterations, max_depth):
    print(f"[gRPC-RLM] Starting task: '{prompt[:40]}...' (Complexity: {complexity})")
    bridge = RLMSubagentBridge(backend="openai", environment="local")
    
    if not bridge.is_rlm_available:
        return "Error: RLM module not found in path."
    
    try:
        rlm_instance = bridge.initialize_rlm_engine(max_depth=max_depth, max_iterations=max_iterations)
        completion_result = rlm_instance.completion(prompt=prompt)
        print(f"[gRPC-RLM] Finished task: '{prompt[:40]}...'")
        return str(completion_result)
    except Exception as e:
        print(f"[gRPC-RLM] Error on task '{prompt[:40]}...': {e}")
        return f"Error: {e}"

class AgentDispatcherServicer(orchestrator_pb2_grpc.AgentDispatcherServicer):
    async def DispatchRLM(self, request, context):
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        print(f"[gRPC] Received request. Dispatching thread for task_id: {task_id}")
        
        # Run blocking RLM completion in a separate thread so it doesn't block the async event loop
        result = await asyncio.to_thread(
            _run_rlm_sync,
            request.prompt, 
            request.complexity, 
            request.max_iterations, 
            request.max_depth
        )
        
        status = "SUCCESS" if not result.startswith("Error") else "FAILED"
        return orchestrator_pb2.RLMResponse(
            task_id=task_id,
            status=status,
            result=result
        )

async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=50))
    orchestrator_pb2_grpc.add_AgentDispatcherServicer_to_server(AgentDispatcherServicer(), server)
    listen_addr = '[::]:50055'
    server.add_insecure_port(listen_addr)
    print(f"🚀 gRPC Agent Orchestrator Server listening on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())
