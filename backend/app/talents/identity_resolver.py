"""解析人才合并链；拒绝损坏引用和环，不以姓名猜测同一身份。"""
from dataclasses import dataclass
from sqlalchemy import select
from app.talents.models import Candidate
from app.core.errors import DomainError


@dataclass(frozen=True)
class CanonicalIdentity:
    """主身份和其全部历史别名ID。"""
    root_id: int
    alias_ids: tuple[int,...]


class CanonicalResolver:
    """供后续合并与读取共用，调用者负责权限与事务。"""
    def resolve(self,uow,candidate_id: int,lock: bool=False) -> CanonicalIdentity:
        """沿持久化链找到根，随后收集全部后代；最多处理10000个节点。"""
        seen=set();current=candidate_id
        while True:
            if current in seen or len(seen)>=10000:
                raise DomainError('IDENTITY_CYCLE',409,'人才身份链存在环或超出限制')
            seen.add(current)
            stmt=select(Candidate).where(Candidate.id==current)
            if lock: stmt=stmt.with_for_update().execution_options(populate_existing=True)
            row=uow.session.scalar(stmt)
            if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'人才身份不存在')
            if row.merged_into_id is None: break
            current=row.merged_into_id
        root=current;aliases=set();frontier={root}
        while frontier:
            stmt=select(Candidate.id).where(Candidate.merged_into_id.in_(frontier)).order_by(Candidate.id)
            if lock: stmt=stmt.with_for_update()
            children=set(uow.session.scalars(stmt))
            if root in children or children & aliases or len(aliases|children)>10000:
                raise DomainError('IDENTITY_CYCLE',409,'人才身份链存在环或超出限制')
            aliases.update(children);frontier=children
        return CanonicalIdentity(root,tuple(sorted(aliases)))
