from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import timedelta, timezone
import re
from typing import Callable
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from app.core.access import ActorContext
from app.core.clock import Clock
from app.core.errors import DomainError
from app.core.models import IdempotencyRecord
from app.core.uow import SqlAlchemyUow, make_uow

@dataclass(frozen=True, slots=True)
class ResultRef:
    entity_type: str
    entity_id: int
    response_code: int

    def __post_init__(self):
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,49}', self.entity_type):
            raise ValueError('Invalid result entity type')
        if type(self.entity_id) is not int or self.entity_id <= 0 or not 200 <= self.response_code < 400:
            raise ValueError('Invalid result reference')

class IdempotencyService:
    def __init__(self, uow_factory: Callable[[], SqlAlchemyUow] = make_uow, clock: Clock | None = None):
        self.uow_factory = uow_factory
        self.clock = clock or Clock()

    def execute(self, actor: ActorContext, operation: str, key: str, payload_hash: str,
                command: Callable[[SqlAlchemyUow], ResultRef]) -> ResultRef:
        if (not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,100}',operation)
            or not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,100}',key)
            or not re.fullmatch(r'[a-f0-9]{64}',payload_hash)):
            raise DomainError('INVALID_IDEMPOTENCY_KEY',422,'幂等参数无效')
        now=self.clock.now().astimezone(timezone.utc).replace(tzinfo=None)
        with self.uow_factory() as uow:
            session=uow.session
            record=IdempotencyRecord(actor_scope=actor.scope_key,operation=operation,
                request_key=key,request_hash=payload_hash,state='processing',expires_at=now+timedelta(hours=24))
            fresh=True
            try:
                # The unique insert serializes duplicates until the winning outer transaction ends.
                with session.begin_nested():
                    session.add(record)
                    session.flush()
            except IntegrityError as error:
                if error.orig.args[0] != 1062:
                    raise
                fresh=False
                record=session.scalar(select(IdempotencyRecord).where(
                    IdempotencyRecord.actor_scope==actor.scope_key,
                    IdempotencyRecord.operation==operation,
                    IdempotencyRecord.request_key==key).with_for_update())
                if record is None:
                    raise RuntimeError('Unique idempotency record unavailable') from None
            if not fresh and record.expires_at > now:
                if record.request_hash != payload_hash:
                    raise DomainError('IDEMPOTENCY_CONFLICT',409,'相同幂等键对应不同请求')
                if record.state == 'completed':
                    return ResultRef(**record.result_refs)
                raise DomainError('IDEMPOTENCY_IN_PROGRESS',409,'请求正在处理')
            if not fresh:
                record.request_hash=payload_hash
                record.state='processing'
                record.result_refs=None
                record.expires_at=now+timedelta(hours=24)
            transaction=session.get_transaction()
            def forbid_commit(session):
                raise RuntimeError('callback cannot commit')
            event.listen(session,'before_commit',forbid_commit)
            try:
                result=command(uow)
                if not isinstance(result,ResultRef):
                    raise TypeError('Command must return a ResultRef')
                if session.get_transaction() is not transaction:
                    raise RuntimeError('callback cannot end its transaction')
            finally:
                event.remove(session,'before_commit',forbid_commit)
            record.state='completed'
            record.result_refs=asdict(result)
            uow.commit()
            return result
