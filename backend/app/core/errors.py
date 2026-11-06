"""公共基础设施：定义可安全对外返回的领域异常。"""
from typing import Any

class DomainError(Exception):
    """DomainError：公共基础设施中的协作类型。"""
    def __init__(self, code: str, http_status: int, message: str, safe_details: dict[str, Any] | None = None):
        self.code, self.http_status, self.message, self.safe_details = code, http_status, message, safe_details
        super().__init__(code)
