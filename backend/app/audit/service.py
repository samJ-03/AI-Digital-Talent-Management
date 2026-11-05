from dataclasses import dataclass
import re
from typing import Any
from uuid import UUID
from app.core.access import ActorContext, ResourceScope
from app.core.uow import SqlAlchemyUow
from app.audit.models import AuditLog

@dataclass(frozen=True, slots=True)
class AuditEvent:
    action: str
    resource: ResourceScope
    summary: dict[str, Any]
    result: str
    request_id: str

SENSITIVE=re.compile(r'password|passwd|secret|credential|token|cookie|authorization|answer|rubric|ciphertext|resume_text|prompt|body',re.I)
SAFE_KEYS=frozenset({'reason','changed_fields','before','after','state','status','version','previous_version',
    'source_id','target_id','department_id','job_id','attempt_id','count','error_code','enabled','result','revision','role_ids'})

def redact_summary(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return '[REDACTED]'
    if isinstance(value,dict):
        return {str(k)[:100]: ('[REDACTED]' if SENSITIVE.search(str(k)) or k not in SAFE_KEYS else redact_summary(v,depth+1)) for k,v in list(value.items())[:50]}
    if isinstance(value,list):
        return [redact_summary(v,depth+1) for v in value[:100]]
    if isinstance(value,str):
        value=re.sub(r'(?i)bearer\s+\S+', 'Bearer [REDACTED]', value)
        value=re.sub(r'(?i)(password|secret|token|api_key)\s*[:=]\s*[^\s,;]+', r'\1=[REDACTED]', value)
        return value[:500]
    if value is None or isinstance(value,(bool,int,float)):
        return value
    return '[REDACTED]'

class AuditService:
    def append(self, uow: SqlAlchemyUow, actor: ActorContext, event: AuditEvent) -> None:
        if uow.session is None:
            raise RuntimeError('Audit requires an active unit of work')
        if event.result not in {'success','denied','failed'}:
            raise ValueError('Invalid audit result')
        if not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,100}',event.action) or not re.fullmatch(r'[a-zA-Z0-9_]{1,50}',event.resource.kind):
            raise ValueError('Invalid audit resource')
        request_id=str(UUID(event.request_id))
        uow.session.add(AuditLog(actor_type=actor.actor_type,actor_user_id=actor.user_id,
            actor_candidate_id=actor.candidate_id,action=event.action,entity_type=event.resource.kind,
            entity_id=event.resource.id,request_id=request_id,change_summary=redact_summary(event.summary),result=event.result))
