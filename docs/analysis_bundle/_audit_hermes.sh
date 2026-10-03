#!/bin/sh
echo "=== HERMES CONFIG (providers/model) ==="
CFG="$LOCALAPPDATA/hermes/config.yaml"
ls -la "$CFG" 2>&1 | head -2
grep -nE "^(provider|model|providers|mcp|terminal)|^  [a-z_]+:" "$CFG" 2>/dev/null | head -50
echo ""
echo "=== LEGACY ~/.hermes ==="
ls -la ~/.hermes/ 2>&1 | head -10
echo ""
echo "=== HERMES .env TERMINAL_CWD leftovers ==="
grep -nE "TERMINAL_CWD" "$LOCALAPPDATA/hermes/.env" 2>/dev/null | head -5
echo "(empty = cleaned)"
echo ""
echo "=== MCP SERVERS configured ==="
grep -nA3 -E "vazus-organic|ckb|sequential-thinking|playwright|colab" "$CFG" 2>/dev/null | head -60
