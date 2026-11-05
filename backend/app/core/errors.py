from typing import Any

class DomainError(Exception):
    def __init__(self, code: str, http_status: int, message: str, safe_details: dict[str, Any] | None = None):
        self.code, self.http_status, self.message, self.safe_details = code, http_status, message, safe_details
        super().__init__(code)
