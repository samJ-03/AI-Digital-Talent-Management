"""公共基础设施：统一服务端UTC时间来源。"""
from datetime import datetime, timezone

class Clock:
    """Clock：公共基础设施中的协作类型。"""
    def now(self) -> datetime:
        """取得服务端UTC时间。"""
        return datetime.now(timezone.utc)

class FrozenClock(Clock):
    """FrozenClock：公共基础设施中的协作类型。"""
    def __init__(self, instant: datetime):
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError('FrozenClock requires an aware datetime')
        self.instant = instant.astimezone(timezone.utc)

    def now(self) -> datetime:
        """取得服务端UTC时间。"""
        return self.instant
