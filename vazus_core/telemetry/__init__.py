"""
vazus_core.telemetry - Runtime Telemetry & Execution Dynamics Engine (Layer 2)
Provides PEP 669 sys.monitoring bytecode tracing, coverage analysis, and upstream API diffing.
"""

from .causal_tracer import CausalGraphTracer, CausalNode
from .dynamic_trace_collector import DynamicTraceCollector, get_global_trace_collector
from .upstream_scanner import UpstreamScanner

__all__ = [
    "CausalGraphTracer",
    "CausalNode",
    "DynamicTraceCollector",
    "get_global_trace_collector",
    "UpstreamScanner",
]

