"""Generate and privately record local demo passwords without displaying them."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

def main():
    root=Path(__file__).resolve().parents[1]
    destination=root/'.execution/local-accounts.json'
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        raise SystemExit('Local credential file already exists; no account was reset.')
    credentials={name:secrets.token_urlsafe(32)+'-Aa9!' for name in ('admin','hr-tech','hr-ops')}
    # Reserve the private, ignored file first so successful DB bootstrap cannot lose credentials.
    with destination.open('x',encoding='utf-8') as stream:
        json.dump(credentials,stream,ensure_ascii=False,indent=2)
    os.chmod(destination,0o600)
    result=subprocess.run([sys.executable,str(root/'scripts/compose.py'),'exec','-T','api','python','-m','app.identity.bootstrap'],input=json.dumps(credentials),capture_output=True,text=True)
    if result.returncode:
        destination.unlink()
        print('Bootstrap refused or failed; existing accounts were not reset.')
        return 1
    print('Created one administrator and two department HR accounts. Generated passwords are in .execution/local-accounts.json (ignored by Git).')
    return 0

if __name__=='__main__': raise SystemExit(main())
