#!/usr/bin/env python3
"""
Unit tests for Vazus Autonomous Infrastructure Fabric (vazus_core.infra).
Validates ASTInfraMiner, VPSFabricGenerator, VPSDeployer, and HealthSupervisor.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from vazus_core.infra.infra_miner import ASTInfraMiner, InfraTopologySpec
from vazus_core.infra.vps_fabric_generator import VPSFabricGenerator, GeneratedInfraBundle
from vazus_core.infra.vps_deployer import VPSDeployer, VPSHostConfig, DeploymentResult
from vazus_core.infra.health_supervisor import HealthSupervisor, ServiceHealthStatus


@pytest.fixture
def sample_python_project(tmp_path):
    """Creates a temporary sample FastAPI service with SQLite and os.getenv."""
    main_py = tmp_path / "main.py"
    main_py.write_text("""
import os
import sqlite3
from fastapi import FastAPI

app = FastAPI()
DB_URL = os.getenv("DATABASE_URL", "sqlite:///vazus.db")
SECRET_KEY = os.environ.get("JWT_SECRET", "default_secret")

@app.get("/healthz")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
""", encoding="utf-8")
    return tmp_path


def test_ast_infra_miner_python_service(sample_python_project):
    """Tests AST topology discovery on a Python FastAPI service."""
    miner = ASTInfraMiner(sample_python_project)
    spec = miner.mine_service()

    assert spec.language == "python"
    assert "FastAPI" in spec.frameworks
    assert "sqlite" in spec.databases
    assert 8080 in spec.ports
    assert "DATABASE_URL" in spec.env_vars
    assert "JWT_SECRET" in spec.env_vars
    assert spec.estimated_ram_mb >= 256


def test_vps_fabric_generator_manifests(sample_python_project):
    """Tests generation of Dockerfile, Compose, Caddy, and Systemd manifests."""
    miner = ASTInfraMiner(sample_python_project)
    spec = miner.mine_service()

    generator = VPSFabricGenerator(domain="api.vazus.io")
    bundle = generator.generate_bundle(spec)

    assert isinstance(bundle, GeneratedInfraBundle)
    assert "FROM python:3.12-slim" in bundle.dockerfile
    assert "HEALTHCHECK" in bundle.dockerfile
    assert "version: '3.8'" in bundle.docker_compose
    assert "8080" in bundle.docker_compose
    assert "api.vazus.io" in bundle.caddyfile
    assert "reverse_proxy 127.0.0.1:8080" in bundle.caddyfile
    assert "[Service]" in bundle.systemd_unit
    assert "DATABASE_URL=" in bundle.env_example

    out_dir = sample_python_project / "deploy"
    written = bundle.write_to_directory(out_dir)
    assert written["Dockerfile"].exists()
    assert written["docker-compose.prod.yml"].exists()
    assert written["Caddyfile"].exists()


def test_vps_deployer_ssh_command_and_preflight():
    """Tests SSH command formatting and preflight verification."""
    cfg = VPSHostConfig(host="192.168.1.100", user="deploy", port=2222)
    cmd = cfg.to_ssh_cmd("uptime")
    assert "ssh" in cmd
    assert "deploy@192.168.1.100" in cmd
    assert "-p" in cmd and "2222" in cmd

    deployer = VPSDeployer(cfg)
    with patch.object(deployer, "execute_ssh", return_value=(0, "Docker version 24.0.5", "")):
        ok, checks = deployer.preflight_check()
        assert ok is True
        assert any("Docker available" in c for c in checks)


def test_vps_deployer_successful_deployment(sample_python_project):
    """Tests simulated deployment cycle with manifest transfer and healthcheck."""
    miner = ASTInfraMiner(sample_python_project)
    spec = miner.mine_service()
    bundle = VPSFabricGenerator(domain="test.domain").generate_bundle(spec)

    cfg = VPSHostConfig(host="10.0.0.5", user="root")
    deployer = VPSDeployer(cfg)

    with patch.object(deployer, "execute_ssh", return_value=(0, "Container vazus-test Up", "")), \
         patch.object(deployer, "_verify_remote_health", return_value=True), \
         patch("subprocess.run") as mock_sub:
        mock_sub.return_value.returncode = 0

        res = deployer.deploy_bundle(
            service_name="test-service",
            bundle=bundle,
            env_secrets={"API_KEY": "secret123"},
            health_port=8080
        )
        assert res.success is True
        assert res.health_checked is True
        assert res.service_name == "test-service"


def test_health_supervisor_lifecycle():
    """Tests HealthSupervisor probing, failure tracking, and remediation trigger."""
    remediation_events = []

    def on_failure(svc, reason):
        remediation_events.append((svc, reason))

    supervisor = HealthSupervisor(failure_threshold=2, remediation_callback=on_failure)

    with patch.object(supervisor, "_safe_socket_probe", side_effect=[
        (True, 200, None),
        (False, 500, "Internal Server Error"),
        (False, 0, "Connection refused"),
    ]):
        # 1. Success probe
        s1 = supervisor.probe_service("auth-service", "http://localhost:8000/healthz")
        assert s1.healthy is True
        assert s1.consecutive_failures == 0
        assert supervisor.get_uptime_ratio("auth-service") == 100.0

        # 2. Failure probe 1
        s2 = supervisor.probe_service("auth-service", "http://localhost:8000/healthz")
        assert s2.healthy is False
        assert s2.consecutive_failures == 1
        assert len(remediation_events) == 0

        # 3. Failure probe 2 (Reaches threshold=2)
        s3 = supervisor.probe_service("auth-service", "http://localhost:8000/healthz")
        assert s3.healthy is False
        assert s3.consecutive_failures == 2
        assert len(remediation_events) == 1
        assert remediation_events[0][0] == "auth-service"
        assert supervisor.get_uptime_ratio("auth-service") == 33.33
