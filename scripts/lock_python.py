"""Resolve the Linux runtime lock inside the pinned Python image."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', 'pip-tools==7.6.2'], check=True)
subprocess.run([sys.executable, '-m', 'piptools', 'compile', '--resolver=backtracking', '--strip-extras', '--no-emit-index-url', '--no-emit-trusted-host', '--output-file', str(root / 'backend/requirements.lock'), str(root / 'backend/requirements.in')], check=True)
