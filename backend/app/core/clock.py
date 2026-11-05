from datetime import datetime, timezone

class Clock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

class FrozenClock(Clock):
    def __init__(self, instant: datetime):
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError('FrozenClock requires an aware datetime')
        self.instant = instant.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self.instant
