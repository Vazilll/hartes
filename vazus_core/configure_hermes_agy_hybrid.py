"""
vazus_core.configure_hermes_agy_hybrid
Automated configuration script linking Hermes Agent app settings to the Hermes-AGY REST Bridge.
"""

import os
import sys
import yaml

def patch_config_file(cfg_path: str):
    if not os.path.exists(cfg_path):
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        config_data = {}
    else:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}

    # Update model provider block to route to local AGY bridge
    if 'model' not in config_data:
        config_data['model'] = {}

    config_data['model']['default'] = 'vazus-agy-hybrid'
    config_data['model']['provider'] = 'custom'
    config_data['model']['base_url'] = 'http://127.0.0.1:11434/v1'

    with open(cfg_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config_data, f, default_flow_style=False, allow_unicode=True)

    print(f"✅ Successfully patched Hermes configuration at: {cfg_path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    appdata_cfg = r"C:\Users\Vaz\AppData\Local\hermes\config.yaml"
    home_cfg = os.path.expanduser("~/.hermes/config.yaml")

    patch_config_file(appdata_cfg)
    patch_config_file(home_cfg)
    print("SUCCESS: Hermes is now configured to use Antigravity AGY & vazus SuperGraph OS as its primary backend!")
