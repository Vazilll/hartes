#!/bin/sh
cd /c/vazus || exit 1
echo "=== ARE L1-L3 MODULES WIRED IN (imported outside tests)? ==="
for m in dynamic_trace_collector ast_grep_runner libcst_pruner codemod_router supergraph_bridge upstream_scanner candidate_harvester whitelist_manager smt_equivalence_prover; do
  n=$(grep -rl "$m" --include=*.py . 2>/dev/null | grep -v "__pycache__" | grep -v "^./tests/" | grep -v "$m.py" | tr '\n' ' ')
  echo "$m <- ${n:-ORPHAN}"
done
echo ""
echo "=== VACUOUS TEST CHECK (staged tests) ==="
for f in tests/test_closed_loop_5layers.py tests/test_codemod_router.py tests/test_dynamic_trace_collector.py tests/test_evidence_jury.py tests/test_smt_equivalence_prover.py; do
  t=$(grep -c "def test_" "$f")
  a=$(grep -c "assert True" "$f")
  p=$(grep -cE "^[[:space:]]+pass[[:space:]]*$" "$f")
  s=$(grep -cE "skipif|skip\(" "$f")
  echo "$f : tests=$t assertTrue=$a barepass=$p skips=$s"
done
