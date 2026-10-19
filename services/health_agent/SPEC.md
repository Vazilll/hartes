# Domain Specification: Health & Bio-Analytics Subsystem
**Module Path**: services/health_agent  
**Domain Lead Archetype**: azus-health-agent / worker_implementer  
**Current Skill Rank**: Level 4 (Multi-Agent Health Pipeline & TRIMP)  

## 1. Core Mission & Boundaries
### 1.1 Primary Mission
The Health & Bio-Analytics Subsystem ingests, processes, and analyzes human physiological telemetry. It provides Xiaomi Body Composition Scale 2 BLE packet decoding, reverse-engineered Bioelectrical Impedance Analysis (BIA), Google Fit activity synchronization, Training Impulse (TRIMP) computation, daily Readiness Score (0-100) evaluation, and gRPC telemetry serving.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Decoding Xiaomi Body Composition Scale 2 (UUID 0x181B) BLE broadcast advertisement packets.
  - Calculating full BIA body composition metrics (BMI, Body Fat %, Muscle Mass, Water %, Visceral Fat, BMR).
  - Syncing Google Fit step counts, active calories, sleep duration, and heart rate telemetry.
  - Computing daily composite Readiness Score (0-100) and TRIMP workout strain metrics.
  - Serving telemetry via async gRPC server on port 50051.
- **PROHIBITED**:
  - Storing corrupted or out-of-range bioimpedance metrics (e.g. impedance <= 0 or > 3000 Ohm without fallback).
  - Blocking main thread on BLE scanning loops (must use syncio.sleep with timeout).
  - Fabricating health telemetry without clear source attribution tag.
  - Modifying user profile baseline constants without validation.

## 2. Public Typed Interface Contracts
### 2.1 Primary Classes & Signatures
`python
from typing import Dict, Any, Optional
import asyncio

def calculate_bia_metrics(
    weight_kg: float,
    impedance_ohms: int,
    height_cm: int = 178,
    age: int = 24,
    gender: str = 'male'
) -> Dict[str, Any]: ...

def parse_mi_scale_v2_data(service_data: bytes) -> Optional[Dict[str, Any]]: ...

async def scan_mi_scale(scan_seconds: int = 30) -> None: ...

class VazusHealthPipelineManager:
    def __init__(self, db_path: Optional[str] = None) -> None: ...
    def execute_pipeline(self) -> Dict[str, Any]: ...
    def compute_readiness_score(self) -> Dict[str, Any]: ...

class GoogleFitSync:
    def __init__(self, db_path: Optional[str] = None) -> None: ...
    def fetch_and_save_fitness_data(self, days: int = 7) -> Dict[str, Any]: ...

class HealthTelemetryServicer:
    def RecordWeighIn(self, request: Any, context: Any) -> Any: ...
    def GetReadinessScore(self, request: Any, context: Any) -> Any: ...
`

### 2.2 Invariant Guarantees
- Invariant 1: Body fat percentage is strictly bounded between 5.0% and 55.0%.
- Invariant 2: Visceral fat rating is strictly bounded between 1 and 30.
- Invariant 3: Weigh-in records are saved with ISO-8601 UTC timestamps.
- Invariant 4: Readiness Score outputs a normalized integer between 0 and 100.

## 3. Progressive Skill Level (Level 1..5) & Upgrade Criteria
- **Level 1 (Static Metrics)**: Manual weight and step logging into SQLite.  
  *Upgrade criteria*: Implement reverse-engineered Xiaomi BIA mathematical equations.
- **Level 2 (Direct BLE Decoding)**: Real-time BLE advertisement sniffing for Mi Body Composition Scale 2.  
  *Upgrade criteria*: Implement Google Fit OAuth synchronization and multi-metric aggregation.
- **Level 3 (TRIMP & Readiness Score Engine)**: Composite physical readiness calculation, training impulse load, and Telegram bot notifications.  
  *Upgrade criteria*: Implement asynchronous gRPC telemetry service and automated pipeline orchestration.
- **Level 4 (Multi-Agent Health Pipeline & TRIMP)**: Full pipeline integration (health_telemetry_pipeline), LangGraph workflow, gRPC server on port 50051, SQLite WAL persistence.  
  *Upgrade criteria*: Implement high-throughput async gRPC streaming server with continuous biometric telemetry.
- **Level 5 (Biometric Closed-Loop OS)**: Continuous wearable BLE streaming, real-time HRV circadian rhythm modeling, predictive burnout prevention, and autonomous recovery scheduling.

## 4. Known Bottlenecks & Optimization Backlog
- [ ] Windows BLE adapter availability and intermittent Bluetooth driver timeouts.
- [ ] Google Fit OAuth token expiration requiring local refresh token flow.
- [ ] gRPC server port 50051 conflict with other local development services.
