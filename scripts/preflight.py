"""Fail-closed runtime and protocol readiness checks. Never serialize raw subprocess output."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

VERSION = re.compile(r"(?<![0-9])([0-9]+\.[0-9]+(?:\.[0-9]+)?)(?![0-9])")


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    version: str | None = None
    reason: str | None = None
    evidence_path: str | None = None


@dataclass
class PreflightConfig:
    profile: str = "bootstrap"
    required_services: tuple[str, ...] = ()
    services: dict[str, str] = field(default_factory=dict)
    executables: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.profile not in {"bootstrap", "dev", "test", "production"}:
            raise ValueError("Unknown preflight profile")


@dataclass(frozen=True)
class PreflightReport:
    profile: str
    checks: list[CheckResult]
    ready: bool
    blocked_reasons: list[str]


class PreflightChecker:
    def __init__(self, runner: Callable = subprocess.run, service_probe: Callable | None = None):
        self.runner = runner
        self.service_probe = service_probe or self._http_protocol_probe

    def _execute(self, executable: str, args: list[str]):
        return self.runner([executable, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15, shell=False)

    def check_runtime(self, executable: str, args: list[str]) -> CheckResult:
        name = Path(executable).stem.lower()
        try:
            result = self._execute(executable, args)
        except FileNotFoundError:
            return CheckResult(name, False, reason="RUNTIME_NOT_FOUND")
        except subprocess.TimeoutExpired:
            return CheckResult(name, False, reason="RUNTIME_TIMEOUT")
        except OSError:
            return CheckResult(name, False, reason="RUNTIME_EXECUTION_DENIED")
        if result.returncode != 0:
            return CheckResult(name, False, reason="RUNTIME_COMMAND_FAILED")
        match = VERSION.search(result.stdout or "")
        if not match:
            return CheckResult(name, False, reason="RUNTIME_VERSION_UNVERIFIED")
        return CheckResult(name, True, version=match.group(1))

    def check_service(self, name: str, endpoint: str) -> CheckResult:
        try:
            result = self.service_probe(name, endpoint)
            if not isinstance(result, CheckResult) or result.name != name:
                return CheckResult(name, False, reason="SERVICE_PROBE_IDENTITY_MISMATCH")
            return result
        except Exception:
            # Credentials, endpoints, driver exceptions and server payloads never enter reports.
            return CheckResult(name, False, reason="SERVICE_PROBE_FAILED")

    @staticmethod
    def _http_protocol_probe(name: str, endpoint: str) -> CheckResult:
        parts = urlsplit(endpoint)
        if parts.scheme not in {"http", "https"} or parts.username or parts.password:
            return CheckResult(name, False, reason="PROTOCOL_PROBE_REQUIRED")
        request = Request(endpoint, headers={"Accept": "application/json"})
        with urlopen(request, timeout=5) as response:
            if response.status != 200:
                return CheckResult(name, False, reason="SERVICE_NOT_READY")
            data = json.loads(response.read(65537))
        if not isinstance(data, dict) or data.get("service") != name or data.get("ready") is not True:
            return CheckResult(name, False, reason="SERVICE_READINESS_UNVERIFIED")
        version = data.get("version")
        safe_version = VERSION.fullmatch(version) if isinstance(version, str) else None
        return CheckResult(name, True, version=safe_version.group(1) if safe_version else None)

    def run(self, config: PreflightConfig) -> PreflightReport:
        checks, blocked = [], []
        runtime_specs = [
            ("python", ["--version"], (3, 11), "PYTHON_311_REQUIRED"),
            ("node", ["--version"], (24,), "NODE_24_REQUIRED"),
            ("git", ["--version"], None, None),
            ("docker", ["version", "--format", "{{.Server.Version}}"], None, None),
            ("compose", ["compose", "version"], None, None),
        ]
        for name, args, required, version_error in runtime_specs:
            executable_name = "docker" if name == "compose" else name
            executable = config.executables.get(executable_name, executable_name)
            result = self.check_runtime(executable, args)
            if result.ok and required:
                actual = tuple(int(n) for n in result.version.split("."))
                if actual[:len(required)] != required:
                    result = CheckResult(name, False, result.version, version_error)
            reason = result.reason
            if not result.ok:
                code = version_error if reason == version_error else name.upper() + "_UNAVAILABLE"
                blocked.append(code)
            checks.append(CheckResult(name, result.ok, result.version, reason))
        docker = config.executables.get("docker", "docker")
        try:
            info = self._execute(docker, ["info", "--format", "{{.OSType}}"])
            linux = info.returncode == 0 and (info.stdout or "").strip() == "linux"
        except (OSError, subprocess.TimeoutExpired):
            linux = False
        checks.append(CheckResult("docker_linux", linux, reason=None if linux else "LINUX_ENGINE_REQUIRED"))
        if not linux:
            blocked.append("LINUX_ENGINE_REQUIRED")
        required_services = config.required_services
        if not required_services and config.profile != "bootstrap":
            required_services = ("mysql", "redis", "minio", "milvus", "model", "mail")
        for name in required_services:
            endpoint = config.services.get(name)
            if not endpoint:
                result = CheckResult(name, False, reason=name.upper() + "_ENDPOINT_REQUIRED")
            else:
                result = self.check_service(name, endpoint)
            checks.append(result)
            if not result.ok:
                blocked.append(result.reason or name.upper() + "_NOT_READY")
        return PreflightReport(config.profile, checks, all(c.ok for c in checks), list(dict.fromkeys(blocked)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("bootstrap", "dev", "test", "production"), default="bootstrap")
    parser.add_argument("--report", type=Path, default=Path("artifacts/preflight.json"))
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    data = json.loads(args.config.read_text("utf-8")) if args.config else {}
    executables = {"python": sys.executable, **data.get("executables", {})}
    config = PreflightConfig(profile=args.profile, required_services=tuple(data.get("required_services", [])),
                             services=data.get("services", {}), executables=executables)
    report = PreflightChecker().run(config)
    payload = {"checked_at": datetime.now(timezone.utc).isoformat(), **asdict(report)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"profile": report.profile, "ready": report.ready, "blocked_reasons": report.blocked_reasons}))
    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
