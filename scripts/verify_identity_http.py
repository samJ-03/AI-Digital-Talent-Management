"""Exercise staff auth through Nginx using only this project's generated accounts."""
import http.cookiejar
import json
from pathlib import Path
import sys
import urllib.request
from urllib.error import HTTPError

def main():
    root=Path(__file__).resolve().parents[1]
    credentials=json.loads((root/'.execution/local-accounts.json').read_text(encoding='utf-8'))
    def client(): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(opener,path,body=None,headers=None):
        data=None if body is None else json.dumps(body).encode()
        req=urllib.request.Request('http://localhost:13000/api/v1'+path,data=data,headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with opener.open(req,timeout=10) as response:
                return response.status,json.load(response),response.headers
        except HTTPError as error:
            return error.code,json.load(error),error.headers
    staff=client()
    status,view,headers=call(staff,'/auth/login',{'login_name':'admin','password':credentials['admin']})
    checks={'admin_login':status==200,'http_only_cookie':'HttpOnly' in headers.get('Set-Cookie',''),'no_raw_session_in_json':'session_id' not in view.get('data',{})}
    csrf=view.get('data',{}).get('csrf_token','')
    status,view,_=call(staff,'/admin/users')
    checks['admin_users_read']=status==200 and view.get('data',{}).get('total')==3
    hr=client()
    status,view,_=call(hr,'/auth/login',{'login_name':'hr-tech','password':credentials['hr-tech']})
    checks['hr_login']=status==200
    status,_,_=call(hr,'/admin/users')
    checks['hr_admin_isolation']=status==403
    status,_,_=call(staff,'/auth/logout',{}, {'X-CSRF-Token':csrf})
    checks['logout']=status==200
    status,_,_=call(staff,'/auth/me')
    checks['logout_revoked']=status==401
    print(json.dumps({'ready':all(checks.values()),'checks':checks},indent=2))
    return 0 if all(checks.values()) else 1

if __name__=='__main__': raise SystemExit(main())
