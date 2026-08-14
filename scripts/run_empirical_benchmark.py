#!/usr/bin/env python3
"""
scripts/run_empirical_benchmark.py
CLI runner for vazus SuperGraph OS v4.0 Empirical Benchmark Harness.
Measures execution speed, memory footprint (tracemalloc), and AST signature compression (>75%),
persisting metrics + 768D float vector embeddings to vazus.db and generating BENCHMARK_REPORT.md.
"""

import sys
import os
import argparse
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from vazus_core.verification.empirical_benchmark import EmpiricalBenchmarkRunner, DEFAULT_VAZUS_DB


def main():
    parser = argparse.ArgumentParser(description="vazus Empirical Benchmark Harness CLI Runner")
    parser.add_argument("--db-path", type=str, default=os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB), help="Path to vazus.db")
    parser.add_argument("--report-path", type=str, default=r"C:\vazus\BENCHMARK_REPORT.md", help="Path to BENCHMARK_REPORT.md")
    parser.add_argument("--iterations", type=int, default=10, help="Number of benchmark iterations")
    parser.add_argument("--warmup", type=int, default=3, help="Number of warmup iterations")

    args = parser.parse_args()

    print("[*] Starting vazus SuperGraph OS v4.0 Empirical Benchmark Harness...")
    runner = EmpiricalBenchmarkRunner(
        db_path=args.db_path,
        report_path=args.report_path,
        num_iterations=args.iterations,
        warmup_runs=args.warmup,
        root_dir=str(root_dir)
    )

    results = runner.run_all_benchmarks()
    dashboard = runner.generate_visual_dashboard(results)
    print("\n" + dashboard + "\n")

    print(f"[+] Empirical benchmark report generated and saved to: {args.report_path}")
    print(f"[+] Verified metrics & 768D vector embeddings logged to database: {args.db_path}")

    # Check that all modules passed the >75% AST reduction requirement
    all_passed = all(r.get("ast_reduction_pct", 0) >= 75.0 and r.get("is_valid", True) for r in results)
    if all_passed:
        print("[+] SUCCESS: All target modules achieved >75% AST signature token reduction target!")
        sys.exit(0)
    else:
        print("[!] WARNING: One or more target modules fell below the >75% AST reduction target!")
        sys.exit(1)


if __name__ == "__main__":
    main()
