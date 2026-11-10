"""可重建的共享画像索引：外部I/O不持身份锁，提交前复验来源和模型代际。"""
import json
from dataclasses import dataclass
from sqlalchemy import select
from app.core.uow import make_uow
from app.core.errors import DomainError
from app.core.settings import Settings
from app.core.secrets import SecretCipher
from app.ai_runtime.gateway import ModelGateway
from app.ai_runtime.models import ModelConfig,WorkflowConfig
from app.talents.models import Candidate,CandidateProfile
from app.talents.profile_service import ProfileService
from app.evaluation.service import fingerprint
from app.search.models import IndexRecord
from app.search.schemas import VectorRecord,IndexSyncResult


def default_gateway(factory):
    """沿用已授权的私有加密配置，不读取其他项目env。"""
    settings=Settings.load();cipher=SecretCipher(settings.encryption_key.get_secret_value()) if settings.encryption_key else None
    return ModelGateway(factory,cipher)


def embedding_identity(uow,model_id=None):
    """只选当前启用的embedding连接，不用另一个模型填补故障。"""
    flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='embedding'))
    model=uow.session.get(ModelConfig,flow.model_config_id) if flow and flow.model_config_id else None
    if flow is None or not flow.enabled or model is None or not model.enabled or not model.embedding_dimension or model.capabilities.get('verified') is not True or model.capabilities.get('embedding') is not True or model_id is not None and model.id!=model_id:raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'语义模型配置尚未就绪')
    return (model.id,model.revision_no,model.embedding_dimension,model.model_digest,model.model_name,flow.config_revision)


def shared_content(profile):
    """只拼接已验证共享事实；不另取联系方式、面试或考试信息。"""
    return json.dumps({'summary':profile.summary,'skills':profile.skills,'experiences':profile.experiences},ensure_ascii=False,sort_keys=True,separators=(',',':'))


def profile_hash(profile):
    """同一文字不同来源也必须重建，避免旧证据混用。"""
    return fingerprint([profile.id,profile.resume_version_id,shared_content(profile),profile.evidence,profile.source_record_refs])

@dataclass(frozen=True)
class PreparedIndex:
    """SDK写入后的派生引用，只有有效租约事务可发布为可信ready。"""
    profile_id: int
    identity: tuple
    content_hash: str
    collection: str
    key: str
    failure: str|None

class IndexService:
    """SDK产物与可信状态分离；任何迟到失败均不能降级已有成功结果。"""
    def __init__(self,uow_factory=make_uow,gateway=None,store=None):
        self.uow_factory=uow_factory;self.gateway=gateway;self.store=store;self.profiles=ProfileService(uow_factory)

    def _source(self,uow,pid):
        profile=uow.session.get(CandidateProfile,pid)
        if profile is None:raise DomainError('PROFILE_NOT_READY',409,'画像不存在')
        current=self.profiles.current(uow,profile.candidate_id,profile.resume_version_id)
        if current is None or current.id!=pid:raise DomainError('PROFILE_SOURCE_STALE',409,'画像已过期')
        return profile

    def prepare(self,entity,model_config_id):
        """外部I/O不持事务或身份锁，不在此处发布ready/failed。"""
        if entity.type!='profile' or type(entity.id) is not int or entity.id<=0:raise DomainError('INVALID_INDEX_ENTITY',422,'索引类型无效')
        with self.uow_factory() as uow:
            identity=embedding_identity(uow,model_config_id);profile=self._source(uow,entity.id);text=shared_content(profile);digest=profile_hash(profile)
        from app.search.milvus_store import MilvusStore
        store=self.store or MilvusStore();own=self.store is None
        try:
            collection=store.collection(*identity[:4]);key=f'profile:{entity.id}:{digest}'
            batch=(self.gateway or default_gateway(self.uow_factory)).embed([text],model_config_id)
            if (batch.model_config_id,batch.revision_no,batch.dimension,batch.model_digest,batch.model_name)!=identity[:5]:raise DomainError('AI_CONFIG_STALE',409,'向量模型代际已改变')
            store.upsert(collection,[VectorRecord(key,entity.id,'profile','shared',None,digest,batch.vectors[0])])
            return PreparedIndex(entity.id,identity,digest,collection,key,None)
        except Exception:
            return PreparedIndex(entity.id,identity,digest,collection,key,'SEMANTIC_INDEX_UNAVAILABLE')
        finally:
            if own:store.close()

    def finalize(self,uow,prepared):
        """由调用方身份锁及事务保护；worker必须复用有效租约事务。"""
        if embedding_identity(uow,prepared.identity[0])!=prepared.identity or profile_hash(self._source(uow,prepared.profile_id))!=prepared.content_hash:raise DomainError('PROFILE_SOURCE_STALE',409,'索引期间来源或模型已变化')
        row=uow.session.scalar(select(IndexRecord).where(IndexRecord.entity_type=='profile',IndexRecord.entity_id==prepared.profile_id,IndexRecord.model_config_id==prepared.identity[0]).with_for_update().execution_options(populate_existing=True))
        # 并发同代际成功结果可以复用；迟到失败不覆盖它。
        same_ready=row is not None and row.state=='ready' and (row.content_hash,row.collection_name,row.vector_key)==(prepared.content_hash,prepared.collection,prepared.key)
        if row is None:
            row=IndexRecord(entity_type='profile',entity_id=prepared.profile_id,model_config_id=prepared.identity[0],collection_name=prepared.collection,vector_key=prepared.key,content_hash=prepared.content_hash,state='pending');uow.session.add(row)
        if not same_ready or not prepared.failure:
            row.collection_name=prepared.collection;row.vector_key=prepared.key;row.content_hash=prepared.content_hash;row.state='failed' if prepared.failure else 'ready'
        uow.session.flush()
        return IndexSyncResult(row.state,row.id,row.collection_name)

    def sync(self,entity,model_config_id):
        """显式内部重建入口；失败不破坏同代际另一执行的已成功索引。"""
        prepared=self.prepare(entity,model_config_id)
        with self.profiles.candidates.identity_write(),self.uow_factory() as uow:
            result=self.finalize(uow,prepared);uow.commit()
        if prepared.failure:raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'索引同步未成功')
        return result
