from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict

import pytest

from scripts.preflight import CheckResult, PreflightChecker, PreflightConfig


class RuntimeRunner:
    def __init__(self, missing=None, os_type="linux", python="Python 3.11.17", node="v24.21.0"):
        self.missing, self.os_type, self.python, self.node = missing, os_type, python, node

    def __call__(self, argv, **kwargs):
        name = argv[0]
        if name == self.missing:
            raise FileNotFoundError(name)
        if name == "docker" and "info" in argv:
            out = self.os_type
        elif name == "docker" and "compose" in argv:
            out = "Docker Compose version v5.3.0"
        else:
            out = {"python": self.python, "node": self.node, "git": "git version 2.56.0", "docker": "29.6.1"}.get(name, "")
        return subprocess.CompletedProcess(argv, 0, out, "")


def test_missing_docker_blocks_linux_worker():
    checker = PreflightChecker(runner=RuntimeRunner(missing="docker"))
    report = checker.run(PreflightConfig(profile="bootstrap"))
    assert report.ready is False
    assert "DOCKER_UNAVAILABLE" in report.blocked_reasons


def test_windows_engine_not_accepted():
    report = PreflightChecker(runner=RuntimeRunner(os_type="windows")).run(PreflightConfig(profile="bootstrap"))
    assert report.ready is False
    assert "LINUX_ENGINE_REQUIRED" in report.blocked_reasons


def test_complete_bootstrap_ready_without_claiming_services():
    report = PreflightChecker(runner=RuntimeRunner()).run(PreflightConfig(profile="bootstrap"))
    assert report.ready is True
    assert {c.name for c in report.checks} == {"python", "node", "git", "docker", "compose", "docker_linux"}
    assert all(c.ok for c in report.checks)


@pytest.mark.parametrize("python,node,reason", [
    ("Python 3.10.20", "v24.21.0", "PYTHON_311_REQUIRED"),
    ("Python 3.11.17", "v18.20.0", "NODE_24_REQUIRED"),
])
def test_runtime_version_floor(python, node, reason):
    report = PreflightChecker(runner=RuntimeRunner(python=python, node=node)).run(PreflightConfig(profile="bootstrap"))
    assert report.ready is False
    assert reason in report.blocked_reasons


def test_tcp_open_not_ready():
    def failed_protocol(name, endpoint):
        raise ConnectionError("TCP connected but authentication/protocol failed")
    result = PreflightChecker(service_probe=failed_protocol).check_service("mysql", "tcp://127.0.0.1:3306")
    assert result.ok is False
    assert result.reason == "SERVICE_PROBE_FAILED"


def test_service_requires_successful_protocol_probe():
    def successful_protocol(name, endpoint):
        return CheckResult(name=name, ok=True, version="8.0.27")
    result = PreflightChecker(service_probe=successful_protocol).check_service("mysql", "tcp://127.0.0.1:3306")
    assert result.ok is True
    assert result.version == "8.0.27"


def test_secrets_redacted(monkeypatch):
    secret = "PRECHECK_TEST_SECRET_12345"
    monkeypatch.setenv("SMTP_PASSWORD", secret)
    def unsafe_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, secret, "failed at mysql://root:" + secret + "@localhost")
    report = PreflightChecker(runner=unsafe_runner).run(PreflightConfig(profile="bootstrap"))
    serialized = json.dumps(asdict(report))
    assert report.ready is False
    assert secret not in serialized
    assert "mysql://root" not in serialized


def test_runtime_output_only_records_version():
    checker = PreflightChecker(runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "v24.21.0 PASSWORD_DONT_COPY", ""))
    result = checker.check_runtime("node", ["--version"])
    assert result.version == "24.21.0"
    assert "PASSWORD_DONT_COPY" not in json.dumps(asdict(result))


def test_runtime_timeout_is_controlled():
    def timed_out(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, timeout=2)
    result = PreflightChecker(runner=timed_out).check_runtime("node", ["--version"])
    assert result.ok is False
    assert result.reason == "RUNTIME_TIMEOUT"


def test_runtime_real_python_executes_without_shell():
    result = PreflightChecker().check_runtime(sys.executable, ["--version"])
    assert result.ok is True
    assert result.version.startswith("3.11.")


def test_dev_missing_required_endpoint_blocks():
    report = PreflightChecker(runner=RuntimeRunner()).run(PreflightConfig(profile="dev", required_services=("mysql",)))
    assert report.ready is False
    assert "MYSQL_ENDPOINT_REQUIRED" in report.blocked_reasons


def test_service_probe_identity_cannot_be_substituted():
    checker = PreflightChecker(service_probe=lambda name, endpoint: CheckResult(name="other", ok=True))
    result = checker.check_service("mysql", "tcp://127.0.0.1:3306")
    assert result.ok is False
    assert result.reason == "SERVICE_PROBE_IDENTITY_MISMATCH"


def test_unknown_profile_rejected():
    with pytest.raises(ValueError, match="profile"):
        PreflightConfig(profile="typo")
