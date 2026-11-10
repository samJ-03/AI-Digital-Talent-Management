"""语义检索应用层：授权在外部调用前后复验，召回逐条核对MySQL。"""
from sqlalchemy import select
from app.core.uow import make_uow
from app.core.access import ResourceScope
from app.core.hr_service import HrServiceBase
from app.core.errors import DomainError
from app.talents.models import Candidate,CandidateProfile,ResumeVersion
from app.talents.profile_service import ProfileService
from app.jobs.models import Job,JobVersion
from app.search.models import IndexRecord
from app.search.index_service import embedding_identity,default_gateway,profile_hash
from app.search.schemas import SearchScope,SemanticSearchResult,Recommendation,TalentSearchQuery

class TalentSearchService(HrServiceBase):
    """不从Milvus返回原始文本，不以相似度冒充岗位分数。"""
    def __init__(self,uow_factory=make_uow,gateway=None,store=None,top_k=None,min_relevance=None):
        from app.core.settings import Settings
        settings=Settings.load()
        top_k=settings.semantic_top_k if top_k is None else top_k
        min_relevance=settings.semantic_min_relevance if min_relevance is None else min_relevance
        super().__init__(uow_factory);self.gateway=gateway;self.store=store;self.top_k=top_k;self.min_relevance=min_relevance;self.profiles=ProfileService(uow_factory)
        if not 1<=top_k<=1000 or not -1<=min_relevance<=1:raise ValueError('Invalid retrieval configuration')

    def search(self,actor,cmd):
        """查询向量与索引同代际；归档、别名、旧画像、未决去重均排除。"""
        scope=ResourceScope('talent',shared=True)
        with self.uow_factory() as uow:self.authorize(uow,actor,'talent.read',scope);identity=embedding_identity(uow)
        from app.search.milvus_store import MilvusStore
        store=self.store or MilvusStore();own=self.store is None
        try:
            batch=(self.gateway or default_gateway(self.uow_factory)).embed([cmd.query],identity[0])
            if (batch.model_config_id,batch.revision_no,batch.dimension,batch.model_digest,batch.model_name)!=identity[:5]:raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'索引模型已变更')
            collection=store.collection(*identity[:4]);hits=store.search(collection,batch.vectors[0],SearchScope(),max(self.top_k,cmd.page_size))
            items=[];seen=set()
            with self.uow_factory() as uow:
                self.authorize(uow,actor,'talent.read',scope)
                if embedding_identity(uow)!=identity:raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'索引模型已变更')
                for hit in hits:
                    if hit.relevance<self.min_relevance:continue
                    row=uow.session.scalar(select(IndexRecord).where(IndexRecord.entity_type=='profile',IndexRecord.entity_id==hit.entity_id,IndexRecord.model_config_id==identity[0],IndexRecord.state=='ready',IndexRecord.collection_name==collection,IndexRecord.vector_key==hit.key,IndexRecord.content_hash==hit.content_hash))
                    if row is None:continue
                    profile=uow.session.get(CandidateProfile,hit.entity_id);candidate=uow.session.get(Candidate,profile.candidate_id) if profile else None
                    if candidate is None or candidate.merged_into_id or candidate.id in seen or candidate.status!='ready' or candidate.current_profile_id!=profile.id or profile_hash(profile)!=row.content_hash:continue
                    try:current=self.profiles.current(uow,candidate.id,profile.resume_version_id)
                    except DomainError:continue
                    if current is None or current.id!=profile.id:continue
                    facts=uow.session.get(ResumeVersion,profile.resume_version_id).structured_data
                    filters=cmd.filters
                    if filters.skills and not all(any(skill.casefold()==s.casefold() for s in profile.skills) for skill in filters.skills):continue
                    if filters.education and not any(e.get('degree')==filters.education for e in facts.get('education',[])):continue
                    if filters.major and not any(e.get('major')==filters.major for e in facts.get('education',[])):continue
                    seen.add(candidate.id);items.append(Recommendation(candidate_id=str(candidate.id),profile_id=str(profile.id),semantic_relevance=hit.relevance,matched_evidence=profile.evidence))
                    if len(items)>=cmd.page_size:break
            return SemanticSearchResult(items=items,query=cmd.query)
        except DomainError as error:
            if error.http_status in {401,403,404}:raise
            raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'语义索引暂不可用') from None
        except Exception:raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'语义索引暂不可用') from None
        finally:
            if own:store.close()

    def recommend(self,actor,job_id,query):
        """读取岗位发布描述用于检索；不产生应聘、画像、匹配或邀请写入。"""
        with self.uow_factory() as uow:
            job=uow.session.get(Job,job_id)
            if job is None:raise DomainError('RESOURCE_NOT_FOUND',404,'岗位不存在')
            self.authorize(uow,actor,'job.read',ResourceScope('job',id=job.id,department_id=job.department_id))
            version=uow.session.get(JobVersion,job.current_version_id) if job.current_version_id else None
            if version is None or version.job_id!=job.id or version.status!='published':raise DomainError('JOB_NOT_READY',409,'岗位尚未发布')
            text=version.description[:2000]
        result=self.search(actor,TalentSearchQuery(query=text,filters=query,page_size=query.page_size))
        with self.uow_factory() as uow:
            job=uow.session.get(Job,job_id)
            self.authorize(uow,actor,'job.read',ResourceScope('job',id=job.id,department_id=job.department_id))
        return result.items
