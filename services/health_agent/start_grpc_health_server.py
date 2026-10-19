import sys
import asyncio
import grpc
from concurrent import futures

sys.path.append(r"/home/tarhes/Проекты/vazus")
sys.path.append(r"/home/tarhes/Проекты/vazus/vazus_core")

import health_telemetry_pb2_grpc
from vazus_core.grpc_health_servicer import AsyncHealthTelemetryServicer

async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    health_telemetry_pb2_grpc.add_HealthTelemetryServiceServicer_to_server(
        AsyncHealthTelemetryServicer(), server
    )
    
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    print(f"🚀 Async gRPC Health Telemetry Server started on {listen_addr}...")
    await server.start()
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        print("\nStopping gRPC Server...")
        await server.stop(5)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(serve())
