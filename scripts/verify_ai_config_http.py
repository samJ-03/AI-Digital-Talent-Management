"""Read-only local admin workflow verification; HR model writes must be refused."""
import http.cookiejar
import json
from pathlib import Path
import urllib.request
from urllib.error import HTTPError

def main():
    root=Path(__file__).resolve().parents[1]
    accounts=json.loads((root/'.execution/local-accounts.json').read_text(encoding='utf-8'))
    checks={}
    for name in ('admin','hr-tech'):
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def post(path,body,csrf=None):
            headers={'Content-Type':'application/json'}
            if csrf: headers['X-CSRF-Token']=csrf
            return opener.open(urllib.request.Request('http://localhost:13000/api/v1'+path,data=json.dumps(body).encode(),headers=headers),timeout=10)
        with post('/auth/login',{'login_name':name,'password':accounts[name]}) as response: session=json.load(response)['data']
        if name=='admin':
            with opener.open('http://localhost:13000/api/v1/admin/workflows',timeout=10) as response:
                payload=json.load(response)
                rows=payload['data']
                checks['seven_fixed_workflows']={row['task_type'] for row in rows}=={'extract','profile','match','question_generation','grade','knowledge_ask','embedding'}
                checks['all_disabled_initially']=all(row['enabled'] is False for row in rows)
                checks['no_secret_fields']='secret' not in json.dumps(payload).lower()
        else:
            try:
                with post('/admin/model-configs',{'logical_key':'local-denied-probe','provider_type':'compatible_http','base_url':'https://api.deepseek.com/v1','model_name':'deepseek-flash'},session['csrf_token']):
                    checks['hr_model_write_denied']=False
            except HTTPError as error: checks['hr_model_write_denied']=error.code==403
        with post('/auth/logout',{},session['csrf_token']): pass
    print(json.dumps({'ready':all(checks.values()) and len(checks)==4,'checks':checks},indent=2))
    return 0 if all(checks.values()) and len(checks)==4 else 1

if __name__=='__main__': raise SystemExit(main())
