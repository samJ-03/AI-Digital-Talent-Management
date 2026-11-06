"""公共基础设施：传递当前请求链路标识，避免业务层依赖HTTP对象。"""
from contextvars import ContextVar
request_id_context: ContextVar[str|None]=ContextVar('request_id',default=None)
