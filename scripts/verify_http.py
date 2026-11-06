"""Check same-origin routing and monitoring protection without logging credentials."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import UUID

root=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (root/'.env').read_text('utf-8').splitlines() if line and not line.startswith('#'))
base='http://localhost:13000'

def get(path, headers=None):
    """读取指定私有对象或会话。"""
    try:
        response=urlopen(Request(base+path,headers=headers or {}),timeout=10)
    except HTTPError as error:
        response=error
    with response:
        return response.status,json.loads(response.read())

checks=[]
status,live=get('/api/v1/health/live')
checks.append({'name':'same_origin_api_live','ok':status==200 and live['data']['alive'] is True})
UUID(live['request_id'])
status,denied=get('/api/v1/health/ready')
checks.append({'name':'monitor_auth_required','ok':status==401})
status,ready=get('/api/v1/health/ready',{'X-Monitor-Token':env['TALENT_MONITOR_TOKEN']})
checks.append({'name':'authenticated_core_readiness','ok':status==200 and ready['data']['ready'] is True})
checks.append({'name':'no_monitor_secret_in_response','ok':env['TALENT_MONITOR_TOKEN'] not in json.dumps([live,denied,ready])})
print(json.dumps({'ready':all(c['ok'] for c in checks),'checks':checks},indent=2))
raise SystemExit(0 if all(c['ok'] for c in checks) else 1)
