"""Actual HR-authorized binary download through the local same-origin proxy."""
import base64
import http.cookiejar
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
from urllib.error import HTTPError

def main():
    root=Path(__file__).resolve().parents[1]
    command=[sys.executable,str(root/'scripts/compose.py'),'exec','-T','api','python','-m','app.files.verify_storage']
    created=subprocess.run(command,capture_output=True,text=True,check=True)
    file_id=json.loads(created.stdout)['file_id']
    accounts=json.loads((root/'.execution/local-accounts.json').read_text(encoding='utf-8'))
    expected=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
    checks={}
    try:
        for name in ('hr-tech','admin'):
            opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            body=json.dumps({'login_name':name,'password':accounts[name]}).encode()
            with opener.open(urllib.request.Request('http://localhost:13000/api/v1/auth/login',data=body,headers={'Content-Type':'application/json'}),timeout=10) as response:
                login=json.load(response)['data']
            url='http://localhost:13000/api/v1/files/'+file_id+'/download'
            try:
                with opener.open(url,timeout=10) as response:
                    checks['hr_binary_roundtrip']=name=='hr-tech' and response.read()==expected
                    checks['private_no_store']=response.headers.get('Cache-Control')=='private, no-store'
                    checks['attachment']=response.headers.get('Content-Disposition','').startswith('attachment;')
            except HTTPError as error:
                checks['admin_denied']=name=='admin' and error.code==403
            logout=urllib.request.Request('http://localhost:13000/api/v1/auth/logout',data=b'{}',headers={'Content-Type':'application/json','X-CSRF-Token':login['csrf_token']})
            with opener.open(logout,timeout=10): pass
        print(json.dumps({'ready':all(checks.values()) and len(checks)==4,'checks':checks},indent=2))
        return 0 if all(checks.values()) and len(checks)==4 else 1
    finally:
        subprocess.run(command+['cleanup',file_id],capture_output=True,text=True,check=True)

if __name__=='__main__': raise SystemExit(main())
