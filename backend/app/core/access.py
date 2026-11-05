from dataclasses import dataclass, field
from app.core.errors import DomainError

@dataclass(frozen=True, slots=True)
class ActorContext:
    actor_type: str
    user_id: int | None = None
    candidate_id: int | None = None
    attempt_id: int | None = None
    department_ids: frozenset[int] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    company_permissions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self):
        if self.actor_type not in {'admin', 'hr', 'candidate', 'system'}:
            raise ValueError('Unknown actor type')
        staff = self.actor_type in {'admin', 'hr'}
        if staff and (not self.user_id or self.candidate_id is not None or self.attempt_id is not None):
            raise ValueError('Staff and candidate identities must be separate')
        if self.actor_type == 'candidate' and (self.user_id is not None or not self.candidate_id or not self.attempt_id):
            raise ValueError('Candidate requires its own attempt identity')
        if self.actor_type == 'system' and any(v is not None for v in (self.user_id,self.candidate_id,self.attempt_id)):
            raise ValueError('System identity cannot impersonate a person')
        for name in ('department_ids','permissions','company_permissions'):
            object.__setattr__(self,name,frozenset(getattr(self,name)))
        if not self.company_permissions <= self.permissions:
            raise ValueError('Company scope must belong to an explicitly granted permission')
        if self.actor_type == 'candidate' and (self.department_ids or self.company_permissions):
            raise ValueError('Candidate cannot have staff data scope')

    @property
    def scope_key(self) -> str:
        if self.actor_type == 'candidate':
            return f'candidate:{self.candidate_id}:attempt:{self.attempt_id}'
        return f'{self.actor_type}:{self.user_id}' if self.user_id is not None else 'system'

@dataclass(frozen=True, slots=True)
class ResourceScope:
    kind: str
    id: int | None = None
    department_id: int | None = None
    shared: bool = False

class PermissionDenied(DomainError):
    def __init__(self):
        super().__init__('PERMISSION_DENIED',403,'无操作权限')

class AccessPolicy:
    SHARED_KINDS = frozenset({'talent','candidate','resume','profile'})
    ADMIN_PREFIXES = frozenset({'user','role','department','model','prompt','workflow','mail_config','runtime','audit','system'})
    CANDIDATE_PERMISSIONS = frozenset({'exam.access','exam.start','exam.read','exam.answer','exam.submit','exam.status'})

    def require(self, actor: ActorContext, permission: str, resource: ResourceScope) -> None:
        if permission not in actor.permissions:
            raise PermissionDenied()
        if actor.actor_type == 'candidate':
            if (permission not in self.CANDIDATE_PERMISSIONS or resource.kind != 'exam_attempt'
                or resource.id != actor.attempt_id or resource.department_id is not None or resource.shared):
                raise PermissionDenied()
            return
        namespace=permission.split('.',1)[0]
        if actor.actor_type == 'admin':
            if namespace not in self.ADMIN_PREFIXES:
                raise PermissionDenied()
            return
        if actor.actor_type == 'hr' and namespace in self.ADMIN_PREFIXES:
            raise PermissionDenied()
        if resource.shared and resource.kind in self.SHARED_KINDS and resource.department_id is None:
            return
        if permission in actor.company_permissions:
            return
        if resource.department_id is not None and resource.department_id in actor.department_ids:
            return
        raise PermissionDenied()
