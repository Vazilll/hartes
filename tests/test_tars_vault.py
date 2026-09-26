"""
Tests for 30 TB Tars Vault Offload Engine in vazus_autonomous_harness.
"""

import pytest
from pathlib import Path
from vazus_autonomous_harness.flywheel.tars_vault_bridge import TarsVaultBridge, VAULT_BUCKETS


def test_tars_vault_initialization_and_buckets(tmp_path):
    bridge = TarsVaultBridge(vault_root=tmp_path)
    assert bridge.root == tmp_path

    # Verify all bucket subfolders exist
    for b in VAULT_BUCKETS.values():
        assert (tmp_path / b).is_dir()


def test_tars_vault_offload_and_retrieval(tmp_path):
    bridge = TarsVaultBridge(vault_root=tmp_path)

    sample_weights = b"BINARY_WEIGHTS_TENSOR_MOCK_FLOAT32" * 100
    res = bridge.offload_artifact(
        bucket_key="checkpoints",
        filename="model_checkpoint_epoch_1.pt",
        data=sample_weights,
        metadata={"epoch": 1, "loss": 0.042},
    )

    assert res.success is True
    assert res.bytes_written == len(sample_weights)
    assert res.target_path.exists()
    assert (tmp_path / "01_model_checkpoints" / "model_checkpoint_epoch_1.pt.meta.json").exists()

    # List bucket items
    items = bridge.list_bucket_items("checkpoints")
    assert len(items) == 1
    assert items[0]["name"] == "model_checkpoint_epoch_1.pt"
    assert items[0]["size_bytes"] == len(sample_weights)


def test_tars_vault_invalid_bucket(tmp_path):
    bridge = TarsVaultBridge(vault_root=tmp_path)
    res = bridge.offload_artifact(
        bucket_key="non_existent_bucket",
        filename="data.bin",
        data=b"hello",
    )
    assert res.success is False
    assert "Invalid bucket key" in res.error
