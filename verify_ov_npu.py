import sys
import openvino as ov

sys.stdout.reconfigure(encoding='utf-8')

print("Python version:", sys.version)
print("OpenVINO version:", ov.__version__)

try:
    core = ov.Core()
    devices = core.available_devices
    print("\nAvailable OpenVINO Devices:")
    for d in devices:
        print(f" - {d}: {core.get_property(d, 'FULL_DEVICE_NAME')}")
    
    if "NPU" in devices:
        print("\n[VERIFIED] OpenVINO runtime detects Intel NPU acceleration!")
    else:
        print("\n[NOTICE] OpenVINO initialized successfully (Available devices:", devices, ")")
except Exception as e:
    print("\n[ERROR] OpenVINO Core initialization error:", e)
