import sys
import os
import time
import asyncio
import grpc

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

import health_telemetry_pb2
import health_telemetry_pb2_grpc

sys.stdout.reconfigure(encoding='utf-8')

async def run_client():
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = health_telemetry_pb2_grpc.HealthTelemetryServiceStub(channel)

        print("=== 1. CALLING SyncGoogleFitData via gRPC ===")
        req = health_telemetry_pb2.GoogleFitSyncRequest(days_back=3, force_refresh=True)
        res = await stub.SyncGoogleFitData(req)
        
        print("gRPC Sync Response:")
        print(f"  Success: {res.success}")
        print(f"  Message: {res.message}")
        print(f"  Total Steps: {res.total_steps:,}")
        print(f"  Total Calories: {res.total_calories:.1f} kcal")
        print(f"  Active Minutes: {res.active_minutes} min")
        print(f"  Sleep Sessions Count: {res.sleep_sessions_count}")
        print(f"  Workout Sessions Count: {res.workout_sessions_count}")
        print(f"  Readiness Score: {res.readiness_score}/100")
        print(f"  Timestamp: {res.timestamp}")

        print("\n=== 2. CALLING GetReadinessAssessment via gRPC ===")
        readiness_req = health_telemetry_pb2.ReadinessRequest(user_id="user_vaz", date="2026-08-03")
        readiness_res = await stub.GetReadinessAssessment(readiness_req)
        
        print(f"  Date: {readiness_res.date}")
        print(f"  Readiness Score: {readiness_res.readiness_score}/100")
        print(f"  Sleep Recovery: {readiness_res.sleep_recovery_score}/100")
        print(f"  Physical Activity: {readiness_res.physical_activity_score}/100")
        print(f"  HRV Stress: {readiness_res.hrv_stress_score}/100")
        print(f"  AI Recommendation: {readiness_res.recommendation}")

        print("\n=== 3. CALLING StreamHealthMetrics via gRPC ===")
        async def metric_generator():
            now_ms = int(time.time() * 1000)
            metrics = [
                ("heart_rate_bpm", 72.0),
                ("spo2_percentage", 98.5),
                ("hrv_rmssd_ms", 65.0),
                ("body_temp_celsius", 36.6)
            ]
            for name, val in metrics:
                yield health_telemetry_pb2.HealthMetricBatch(
                    metric_type=name,
                    value=val,
                    timestamp_ms=now_ms,
                    metadata={"sensor": "mi_band_10_ppg"}
                )
                await asyncio.sleep(0.1)

        summary = await stub.StreamHealthMetrics(metric_generator())
        print(f"  Stream Processed: {summary.metrics_processed} metrics | Status: {summary.status}")

if __name__ == '__main__':
    asyncio.run(run_client())
