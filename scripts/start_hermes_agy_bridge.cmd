@echo off
echo ======================================================================
echo  Starting Hermes-AGY Hybrid Bridge Server (Antigravity + SuperGraph OS)
echo ======================================================================
echo  Endpoint: http://127.0.0.1:11434/v1
echo  Routing: Hermes Client requests -> Antigravity (AGY) & SuperGraph Core
echo ======================================================================

C:\vazus\.venv\Scripts\python.exe C:\vazus\vazus_core\hermes_agy_bridge_server.py 11434
