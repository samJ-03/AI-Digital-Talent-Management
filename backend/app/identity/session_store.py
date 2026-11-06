"""后台身份认证与权限：在Redis保存和撤销后台会话及CSRF状态。"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import secrets
from redis import Redis
from redis.exceptions import RedisError
from app.core.errors import DomainError

@dataclass(frozen=True)
class StaffSession:
    """StaffSession：后台身份认证与权限中的协作类型。"""
    user_id: int
    auth_version: int
    csrf_token: str
    expires_at: datetime

class StaffSessionStore:
    """StaffSessionStore：后台身份认证与权限中的协作类型。"""
    TTL=8*60*60
    def __init__(self,redis: Redis,namespace: str='talent:staff'):
        self.redis=redis
        self.namespace=namespace

    def _key(self,session_id: str) -> str:
        return self.namespace+':sessions:'+hashlib.sha256(session_id.encode()).hexdigest()

    def create(self,user_id: int,auth_version: int) -> tuple[str,StaffSession]:
        """创建经过校验的领域对象，并返回其视图。"""
        sid=secrets.token_urlsafe(32)
        data=StaffSession(user_id,auth_version,secrets.token_urlsafe(32),datetime.fromtimestamp(datetime.now(timezone.utc).timestamp()+self.TTL,timezone.utc))
        try:
            self.redis.setex(self._key(sid),self.TTL,json.dumps({'user_id':user_id,'auth_version':auth_version,'csrf_token':data.csrf_token,'expires_at':data.expires_at.isoformat()}))
        except RedisError:
            raise DomainError('SESSION_STORE_UNAVAILABLE',503,'会话服务暂不可用') from None
        return sid,data

    def get(self,session_id: str) -> StaffSession:
        """读取指定私有对象或会话。"""
        if not 40<=len(session_id)<=100:
            raise DomainError('SESSION_REQUIRED',401,'请重新登录')
        try:
            raw=self.redis.get(self._key(session_id))
        except RedisError:
            raise DomainError('SESSION_STORE_UNAVAILABLE',503,'会话服务暂不可用') from None
        if not raw:
            raise DomainError('SESSION_REQUIRED',401,'请重新登录')
        try:
            value=json.loads(raw)
            result=StaffSession(int(value['user_id']),int(value['auth_version']),str(value['csrf_token']),datetime.fromisoformat(value['expires_at']))
            if result.expires_at<=datetime.now(timezone.utc): raise ValueError()
            return result
        except (ValueError,KeyError,TypeError):
            raise DomainError('SESSION_REQUIRED',401,'请重新登录') from None

    def delete(self,session_id: str) -> None:
        """删除当前对象存储适配器指定的私有对象。"""
        try:
            self.redis.delete(self._key(session_id))
        except RedisError:
            raise DomainError('SESSION_STORE_UNAVAILABLE',503,'会话服务暂不可用') from None

    def limit(self,category: str,identifier: str,limit: int,seconds: int=300) -> None:
        """对认证相关操作应用频率限制。"""
        key=self.namespace+':limit:'+category+':'+hashlib.sha256(identifier.encode()).hexdigest()
        script='local n=redis.call("INCR",KEYS[1]); if n==1 then redis.call("EXPIRE",KEYS[1],ARGV[1]) end; return n'
        try:
            count=int(self.redis.eval(script,1,key,seconds))
        except RedisError:
            raise DomainError('SESSION_STORE_UNAVAILABLE',503,'会话服务暂不可用') from None
        if count>limit:
            raise DomainError('LOGIN_RATE_LIMITED',429,'登录尝试过于频繁，请稍后再试')
