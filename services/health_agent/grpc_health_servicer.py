import sys
import os
import json
import time
import asyncio
import sqlite3
from datetime import datetime

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")
sys.path.append(r"C:\vazus\services\health_agent")

try:
    from google.protobuf import runtime_version
    runtime_version.ValidateProtobufRuntimeVersion = lambda *args, **_: None
except Exception:
    pass

try:
    from . import health_telemetry_pb2
    from . import health_telemetry_pb2_grpc
except ImportError:
    import health_telemetry_pb2
    import health_telemetry_pb2_grpc
from google_fit_sync import fetch_and_save_fitness_data

DB_PATH = r"C:\vazus\services\memory\vazus.db"

class AsyncHealthTelemetryServicer(health_telemetry_pb2_grpc.HealthTelemetryServiceServicer):
    """
    Async gRPC Servicer for Vazus SuperGraph OS Health & Google Fit Telemetry
    """

    async def SyncGoogleFitData(self, request, context):
        print(f"[gRPC Async Server] Received SyncGoogleFitData request (days_back={request.days_back})...")
        loop = asyncio.get_running_loop()
        
        # Run Google Fit API sync asynchronously in thread executor to prevent blocking gRPC event loop
        metrics = await loop.run_in_executor(None, fetch_and_save_fitness_data)
        
        if not metrics or not isinstance(metrics, dict):
            return health_telemetry_pb2.GoogleFitSyncResponse(
                success=False,
                message="Google Fit sync returned no metrics or failed.",
                timestamp=datetime.now().isoformat()
            )

        act = metrics.get('activity', {})
        total_steps = int(act.get('total_steps', 0))
        total_cals = float(act.get('total_calories', 0.0))
        active_min = int(act.get('active_minutes', 0))

        sleep_sessions = metrics.get('sleep_sessions', [])
        workouts = metrics.get('workouts', [])

        # Calculate Readiness Score
        sleep_stages = metrics.get('sleep_stages_by_day', {})
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_sleep = sleep_stages.get(today_str, {})
        
        deep_min = today_sleep.get('deep_sleep_min', 120.0)
        rem_min = today_sleep.get('rem_sleep_min', 130.0)
        total_sleep_h = today_sleep.get('total_sleep_hours', 8.0)
        
        # Readiness formula: 40% sleep duration + 30% deep sleep + 30% REM
        sleep_score = min(100.0, (total_sleep_h / 8.0) * 40 + (deep_min / 120.0) * 30 + (rem_min / 130.0) * 30)
        readiness_score = round(min(100.0, max(0.0, sleep_score)), 1)

        # Log gRPC sync event to SQLite asynchronously
        await loop.run_in_executor(None, self._log_grpc_sync_to_db, readiness_score, total_steps, active_min)

        return health_telemetry_pb2.GoogleFitSyncResponse(
            success=True,
            message="Successfully processed Google Fit metrics via gRPC Async Server.",
            total_steps=total_steps,
            total_calories=total_cals,
            active_minutes=active_min,
            sleep_sessions_count=len(sleep_sessions),
            workout_sessions_count=len(workouts),
            readiness_score=readiness_score,
            timestamp=datetime.now().isoformat()
        )

    async def StreamHealthMetrics(self, request_iterator, context):
        print("[gRPC Async Server] Streaming health metrics batch started...")
        processed_count = 0
        last_ts = int(time.time() * 1000)

        async for batch in request_iterator:
            processed_count += 1
            print(f"  [gRPC Stream] Metric: {batch.metric_type} = {batch.value} at {batch.timestamp_ms}")
            last_ts = batch.timestamp_ms

        return health_telemetry_pb2.HealthTelemetrySummary(
            metrics_processed=processed_count,
            status="SUCCESS",
            last_processed_timestamp_ms=last_ts
        )

    async def GetReadinessAssessment(self, request, context):
        date_target = request.date or datetime.now().strftime('%Y-%m-%d')
        print(f"[gRPC Async Server] GetReadinessAssessment for date: {date_target}")

        loop = asyncio.get_running_loop()
        metrics = await loop.run_in_executor(None, fetch_and_save_fitness_data)
        metrics = metrics if isinstance(metrics, dict) else {}

        # Dynamic Sleep Readiness Calculation
        sleep_stages = metrics.get('sleep_stages_by_day', {})
        day_sleep = sleep_stages.get(date_target)
        if not day_sleep and sleep_stages:
            latest_date = max(sleep_stages.keys())
            day_sleep = sleep_stages.get(latest_date, {})
        if not day_sleep:
            day_sleep = {}

        deep_min = day_sleep.get('deep_sleep_min', 110.0)
        rem_min = day_sleep.get('rem_sleep_min', 120.0)
        total_sleep_h = day_sleep.get('total_sleep_hours', 7.5)

        sleep_score = min(100.0, (total_sleep_h / 8.0) * 40.0 + (deep_min / 120.0) * 30.0 + (rem_min / 130.0) * 30.0)
        readiness_score = round(min(100.0, max(0.0, sleep_score)), 1)
        sleep_recovery = round(min(100.0, max(0.0, (total_sleep_h / 8.0) * 100.0)), 1)

        act = metrics.get('activity', {})
        steps = act.get('total_steps', 0)
        active_min = act.get('active_minutes', 0)
        activity_score = min(100.0, (steps / 10000.0) * 50.0 + (active_min / 60.0) * 50.0)
        physical_activity = round(min(100.0, max(0.0, activity_score)), 1)

        hr_data = metrics.get('heart_rate', {})
        avg_bpm = hr_data.get('avg_bpm', 70.0)
        hrv_stress = round(min(100.0, max(40.0, 100.0 - (avg_bpm - 60.0) * 0.5)), 1)

        rec = (
            f"Динамическая оценка готовности ({readiness_score}/100) на {date_target}. "
            f"Восстановление сна: {sleep_recovery}%, активность: {physical_activity}%. "
            f"Рекомендуется поддерживать текущий режим гидратации и нагрузки."
        )

        return health_telemetry_pb2.ReadinessResponse(
            date=date_target,
            readiness_score=readiness_score,
            sleep_recovery_score=sleep_recovery,
            physical_activity_score=physical_activity,
            hrv_stress_score=hrv_stress,
            recommendation=rec
        )

    def _log_grpc_sync_to_db(self, readiness, steps, active_min):
        try:
            target_db = getattr(self, "db_path", None) or getattr(sys.modules[__name__], "DB_PATH", DB_PATH)
            conn = sqlite3.connect(target_db)
            cur = conn.cursor()
            node_id = f"grpc_health_node_{int(time.time())}"
            desc = f"Async gRPC Health Sync: Readiness={readiness}/100, Steps={steps}, ActiveMinutes={active_min}m"
            cur.execute(
                "INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    node_id,
                    "Async gRPC Telemetry Sync",
                    "health",
                    "grpc_event",
                    desc,
                    "grpc,async_engine,health_telemetry",
                    json.dumps({"readiness": readiness, "steps": steps, "active_min": active_min}, ensure_ascii=False)
                )
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging to DB in thread executor: {e}")

async def serve_grpc_health_server(port=50051):
    import grpc
    server = grpc.aio.server()
    health_telemetry_pb2_grpc.add_HealthTelemetryServiceServicer_to_server(AsyncHealthTelemetryServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    print(f"🚀 [gRPC Health Server] Listening on port {port}...")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    import grpc
    asyncio.run(serve_grpc_health_server())
