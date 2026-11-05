"""Run this project's Compose file with its explicit local environment."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call(['docker', 'compose', '--env-file', str(root / '.env'), '-f', str(root / 'infra/compose.yaml'), *sys.argv[1:]], cwd=root))
