"""人才事务服务：建档、邮箱门槛、疑似重复和不可变人工修订。

模型结果必须绑定本条目文件的成功AiRun。身份写入以数据库级短锁串行，
文件/模型I/O在锁外完成；内部finalize从不提交调用者的事务。
"""
from contextlib import contextmanager
from copy import deepcopy
import json
import re
from sqlalchemy import select, text, or_
from pydantic import ValidationError
from email_validator import validate_email
from app.core.access import ActorContext, ResourceScope
from app.core.errors import DomainError
from app.core.hr_service import HrServiceBase
from app.core.idempotency import ResultRef
from app.core.uow import make_uow
from app.core.resource_scope import ResourceResolver
from app.identity.models import User
from app.identity.views import resolve_user
from app.ai_runtime.models import AiRun
from app.ingestion.models import ImportBatch, ImportItem
from app.ingestion.extraction_types import ExtractedResume, ResumeFacts
from app.files.models import StoredFile
from app.recruitment.models import Application
from app.runtime.job_service import BackgroundJobService, JobSpec
from app.runtime.models import BackgroundJob
from app.talents.models import Candidate, ResumeVersion, DuplicateCase
from app.talents.identity_resolver import CanonicalResolver
from app.talents.schemas import ContactsPatch, ResumeCorrection, MaterializationResult, TalentView, ResumeVersionView


def normalize_email(value):
    """保留邮箱本地部分点号、加号和大小写，不推断身份。"""
    return validate_email(value,check_deliverability=False).normalized if value else None


def normalize_phone(value):
    """只清理常见排版字符，不补国家码或猜测号码。"""
    return re.sub(r'[\s().-]','',value) or None if value else None


class CandidateService(HrServiceBase):
    """公开方法拥有事务，finalize_materialization复用任务事务。"""
    def __init__(self,uow_factory=make_uow,idempotency_key=None):
        super().__init__(uow_factory,idempotency_key)
        self.tasks=BackgroundJobService(uow_factory)

    @contextmanager
    def identity_write(self):
        """独立连接持有MySQL命名锁；事务回滚不释放命名锁，故显式释放。"""
        with self.uow_factory() as guard:
            connection=guard.session.connection()
            # Database name separates talent_test from talent_dev.
            name='talent:identity:'+str(connection.scalar(text('SELECT DATABASE()')))
            acquired=connection.scalar(text('SELECT GET_LOCK(:name,10)'),{'name':name})
            if acquired!=1: raise DomainError('RESOURCE_CONFLICT',409,'人才身份正在更新，请稍后重试')
            try: yield
            finally:
                try:
                    if connection.scalar(text('SELECT RELEASE_LOCK(:name)'),{'name':name})!=1: connection.invalidate()
                except Exception:
                    connection.invalidate()
                    raise

    def import_context(self,uow,item_id,lock=False):
        """按batch→item锁序复验导入者当前权限和持久化文件关系。"""
        item=uow.session.get(ImportItem,item_id)
        if item is None: raise DomainError('RESOURCE_NOT_FOUND',404,'导入条目不存在')
        batch_id=item.batch_id
        stmt=select(ImportBatch).where(ImportBatch.id==batch_id)
        if lock:stmt=stmt.with_for_update().execution_options(populate_existing=True)
        batch=uow.session.scalar(stmt)
        stmt=select(ImportItem).where(ImportItem.id==item_id)
        if lock:stmt=stmt.with_for_update().execution_options(populate_existing=True)
        item=uow.session.scalar(stmt)
        if batch is None or item is None or item.batch_id!=batch.id: raise DomainError('IMPORT_SOURCE_CHANGED',409,'导入来源已变化')
        user=uow.session.get(User,batch.created_by)
        if user is None:raise DomainError('SESSION_REQUIRED',401,'导入账号已失效')
        actor=resolve_user(uow.session,user)
        scope=ResourceResolver().resolve(uow.session,'import_batch',batch.id).scope
        self.authorize(uow,actor,'import.write',scope);self.authorize(uow,actor,'import.read',scope)
        if batch.job_id:self.authorize(uow,actor,'job.read',scope)
        file=uow.session.get(StoredFile,item.file_id) if item.file_id else None
        if file is None or file.status!='ready':raise DomainError('FILE_UNAVAILABLE',409,'原简历文件不可用')
        return batch,item,file,actor

    def materialize(self,item_id: int,extracted: ExtractedResume) -> MaterializationResult:
        """幂等建档，缺邮箱仍留库；不创建邮件或考试邀请。"""
        with self.identity_write(),self.uow_factory() as uow:
            result=self.finalize_materialization(uow,item_id,extracted)
            uow.commit();return result

    def finalize_materialization(self,uow,item_id,extracted,document=None):
        """调用者须持有identity_write；所有业务写入与任务终态一起提交。"""
        extracted=ExtractedResume.model_validate(extracted.model_dump(mode='json'))
        batch,item,file,actor=self.import_context(uow,item_id,True)
        facts=extracted.model_dump(mode='json',exclude={'ai_run_id'})
        run=uow.session.get(AiRun,extracted.ai_run_id)
        if (run is None or run.task_type!='extract' or run.state!='succeeded' or run.validated_output!=facts
            or run.source_refs!=[{'source_type':'stored_file','source_id':str(file.id)}]):
            raise DomainError('EXTRACTION_SOURCE_MISMATCH',409,'简历提取证据与导入来源不一致')
        if item.resume_version_id:
            old=uow.session.get(ResumeVersion,item.resume_version_id)
            if old is None or old.file_id!=file.id:raise DomainError('IMPORT_SOURCE_CHANGED',409,'导入来源已变化')
            row=uow.session.get(Candidate,old.candidate_id)
            application=uow.session.scalar(select(Application).where(Application.candidate_id==row.id,Application.job_id==batch.job_id)) if batch.job_id else None
            return MaterializationResult(row.id,old.id,application.id if application else None,row.status,self._existing_profile_task(uow,row.id,old.id))
        row=Candidate(display_name=extracted.identity.name or '待补充姓名',email=extracted.contacts.email,email_normalized=normalize_email(extracted.contacts.email),email_valid=bool(extracted.contacts.email),phone=extracted.contacts.phone,phone_normalized=normalize_phone(extracted.contacts.phone),status='pending_email')
        uow.session.add(row);uow.session.flush()
        sources={'facts':deepcopy(facts['field_sources']),'ai_run_id':run.id,'kind':'model_extraction'}
        resume=ResumeVersion(candidate_id=row.id,file_id=file.id,version_no=1,structured_data=facts,field_sources=sources,parser_revision=document.parser_revision if document else 'validated-extract-v1',raw_text='\n\n'.join(p.text for page in document.pages for p in page.paragraphs) if document else None,state='extracted')
        uow.session.add(resume);uow.session.flush();row.current_resume_version_id=resume.id
        self._refresh_state(uow,row,file.sha256)
        application=None
        if batch.job_id:
            application=Application(candidate_id=row.id,job_id=batch.job_id,source='import',stage='evaluating',current_round=1,relationship_state='active')
            uow.session.add(application);uow.session.flush()
        task=self._enqueue_profile(uow,row)
        item.resume_version_id=resume.id;item.status='parsed';item.error_code=None;item.error_detail_safe=None
        uow.session.flush()
        states=list(uow.session.scalars(select(ImportItem.status).where(ImportItem.batch_id==batch.id)))
        batch.status='completed' if all(s=='parsed' for s in states) else 'partial_failed' if 'failed' in states else 'processing'
        self.audit(uow,actor,'talent.materialize','candidate',row.id,{'state':row.status,'source_id':item.id})
        return MaterializationResult(row.id,resume.id,application.id if application else None,row.status,task)

    def _refresh_state(self,uow,row,file_hash=None):
        """联系方式或同文件仅建立人工去重线索；绝不自动合并身份。"""
        predicates=[]
        if row.email_normalized:predicates.append(Candidate.email_normalized==row.email_normalized)
        if row.phone_normalized:predicates.append(Candidate.phone_normalized==row.phone_normalized)
        matches=set(uow.session.scalars(select(Candidate.id).where(Candidate.id!=row.id,or_(*predicates)))) if predicates else set()
        if file_hash:
            matches.update(uow.session.scalars(select(ResumeVersion.candidate_id).join(StoredFile,StoredFile.id==ResumeVersion.file_id).where(StoredFile.sha256==file_hash,ResumeVersion.candidate_id!=row.id)))
        for other in sorted(matches):
            root=CanonicalResolver().resolve(uow,other).root_id
            if root==row.id:continue
            a,b=sorted((root,row.id))
            case=uow.session.scalar(select(DuplicateCase).where(DuplicateCase.candidate_a_id==a,DuplicateCase.candidate_b_id==b))
            if case is None:
                case=DuplicateCase(candidate_a_id=a,candidate_b_id=b,evidence=[{'source_type':'candidate','source_id':str(root),'locator':'identity_clue','quote':'联系方式或原文件相同，须人工核实'}],status='pending')
                uow.session.add(case)
            if case.status=='pending':
                peer=uow.session.scalar(select(Candidate).where(Candidate.id==root).with_for_update().execution_options(populate_existing=True))
                if peer.status not in {'archived','merged'}:peer.status='duplicate_review'
        uow.session.flush()
        # Historical alias clues remain authoritative after identity merging.
        identity=CanonicalResolver().resolve(uow,row.id)
        identity_ids=(identity.root_id,*identity.alias_ids)
        pending=uow.session.scalar(select(DuplicateCase.id).where(or_(DuplicateCase.candidate_a_id.in_(identity_ids),DuplicateCase.candidate_b_id.in_(identity_ids)),DuplicateCase.status=='pending').limit(1))
        row.status='duplicate_review' if pending else 'ready' if row.email_valid and row.email_normalized else 'pending_email'

    def _existing_profile_task(self,uow,cid,rid):
        return uow.session.scalar(select(BackgroundJob.id).where(BackgroundJob.idempotency_key==f'profile.build:{cid}:{rid}'))

    def _enqueue_profile(self,uow,row):
        if row.status!='ready' or not row.current_resume_version_id:return None
        rid=row.current_resume_version_id
        return self.tasks.enqueue(uow,JobSpec('profile.build','candidate',row.id,f'profile.build:{row.id}:{rid}',{'candidate_id':row.id,'resume_version_id':rid}))

    def _row(self,uow,cid,expected=None):
        row=uow.session.scalar(select(Candidate).where(Candidate.id==cid).with_for_update().execution_options(populate_existing=True))
        if row is None:raise DomainError('RESOURCE_NOT_FOUND',404,'人才不存在')
        if expected is not None and row.row_version!=expected:raise DomainError('VERSION_CONFLICT',409,'人才已更新，请刷新重试')
        if row.status=='merged' or row.merged_into_id:raise DomainError('CANDIDATE_MERGED',409,'人才身份已合并，请使用主档案')
        return row

    def _view(self,uow,row):
        resume=uow.session.get(ResumeVersion,row.current_resume_version_id) if row.current_resume_version_id else None
        facts=resume.structured_data if resume else {};education=facts.get('education',[])
        masked=('*'+'@'+row.email_normalized.rsplit('@',1)[1]) if row.email_normalized else None
        return TalentView(id=str(row.id),canonical_candidate_id=str(row.id),name=row.display_name,email_masked=masked,education=education,major=[e['major'] for e in education if e.get('major')],skills=facts.get('skills',[]),status=row.status,current_profile_id=str(row.current_profile_id) if row.current_profile_id else None,version=row.row_version)

    def update_contacts(self,actor,candidate_id: int,cmd: ContactsPatch,expected_version: int) -> TalentView:
        """CAS补齐联系人，只在ready时幂等追加当前简历画像任务。"""
        scope=ResourceScope('talent',id=candidate_id,shared=True)
        with self.identity_write(),self.transaction(actor,'talent.write',scope,response_permission='talent.read') as (uow,fresh):
            row=self._row(uow,candidate_id,expected_version)
            if row.status=='archived':raise DomainError('CANDIDATE_ARCHIVED',409,'已归档人才不能恢复自动处理')
            values=cmd.model_dump(exclude_unset=True,exclude={'reason'})
            for key,value in values.items():setattr(row,key,value)
            row.email_normalized=normalize_email(row.email);row.email_valid=bool(row.email_normalized);row.phone_normalized=normalize_phone(row.phone)
            self._refresh_state(uow,row);self._enqueue_profile(uow,row)
            self.audit(uow,fresh,'talent.contacts','candidate',row.id,{'changed_fields':sorted(values),'reason':cmd.reason,'state':row.status})
            uow.session.flush();return self._view(uow,row)

    def correct_resume(self,actor,candidate_id: int,cmd: ResumeCorrection) -> ResumeVersionView:
        """追加不可变修订；人工证据以真实HR身份署名，不伪装模型提取。"""
        scope=ResourceScope('talent',id=candidate_id,shared=True)
        def command(uow,fresh):
            row=self._row(uow,candidate_id)
            if row.status=='archived':raise DomainError('CANDIDATE_ARCHIVED',409,'已归档人才不能修订')
            if row.current_resume_version_id!=cmd.base_resume_version_id:raise DomainError('VERSION_CONFLICT',409,'当前简历版本已变化')
            old=uow.session.get(ResumeVersion,cmd.base_resume_version_id)
            if old is None or old.candidate_id!=row.id:raise DomainError('RESOURCE_NOT_FOUND',404,'简历版本不存在')
            facts=self._correct_facts(old.structured_data,cmd.changes,fresh.user_id)
            resume=ResumeVersion(candidate_id=row.id,file_id=old.file_id,version_no=old.version_no+1,parent_version_id=old.id,raw_text=old.raw_text,structured_data=facts,field_sources={'kind':'manual_correction','actor_id':fresh.user_id,'parent_resume_version_id':old.id,'facts':facts['field_sources']},parser_revision=old.parser_revision,state='confirmed',change_reason=cmd.reason)
            uow.session.add(resume);uow.session.flush();row.current_resume_version_id=resume.id;row.current_profile_id=None
            row.display_name=facts['identity']['name'] or '待补充姓名'
            # Only explicitly corrected contacts replace the current contact patch.
            if 'contacts.email' in cmd.changes:row.email=facts['contacts']['email'];row.email_normalized=normalize_email(row.email);row.email_valid=bool(row.email_normalized)
            if 'contacts.phone' in cmd.changes:row.phone=facts['contacts']['phone'];row.phone_normalized=normalize_phone(row.phone)
            self._refresh_state(uow,row);self._enqueue_profile(uow,row)
            self.audit(uow,fresh,'talent.correct','candidate',row.id,{'reason':cmd.reason,'changed_fields':sorted(cmd.changes),'version':resume.version_no,'previous_version':old.version_no})
            return ResultRef('resume_version',resume.id,202)
        with self.identity_write():
            result=self.execute(actor,'talent.write',scope,'talent.correct',{'candidate_id':candidate_id,**cmd.model_dump(mode='json')},command,response_permission='talent.read')
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'talent.read',scope)
            return self._resume_view(uow.session.get(ResumeVersion,result.entity_id))

    def _correct_facts(self,original,changes,actor_id):
        """仅允许替换现有事实叶子或整个事实列表，重新验证结构和证据。"""
        if len(json.dumps(changes,ensure_ascii=False).encode())>64000:raise DomainError('INVALID_CORRECTION',422,'修订内容过大')
        facts=deepcopy(original)
        allowed_groups={'education','employment','projects','skills','certificates'}
        for path,value in changes.items():
            parts=path.split('.')
            if path in {'identity.name','identity.birth_date','contacts.email','contacts.phone'}:
                facts[parts[0]][parts[1]]=value
            elif path in allowed_groups:
                facts[path]=value
            else:raise DomainError('INVALID_CORRECTION',422,'修订字段不受支持')
        # Rebuild source map for changed leaves only; preserve untouched evidence.
        leaves={}
        def walk(value,path):
            if isinstance(value,dict):
                for key,item in value.items():walk(item,path+'.'+key if path else key)
            elif isinstance(value,list):
                for index,item in enumerate(value):walk(item,path+'.'+str(index))
            elif value is not None:leaves[path]=value
        walk({k:v for k,v in facts.items() if k not in {'citations','field_sources'}},'')
        sources={};citations=[]
        for path,value in leaves.items():
            changed=any(path==key or path.startswith(key+'.') for key in changes)
            source=[{'source_type':'manual_correction','source_id':str(actor_id),'locator':path,'quote':value}] if changed else facts['field_sources'].get(path,[])
            sources[path]=source
            for e in source:
                if e not in citations:citations.append(e)
        facts['field_sources']=sources;facts['citations']=citations
        try:return ResumeFacts.model_validate(facts).model_dump(mode='json')
        except (ValidationError,TypeError,ValueError):raise DomainError('INVALID_CORRECTION',422,'修订字段类型或证据无效') from None

    def _resume_view(self,row):
        return ResumeVersionView(id=str(row.id),candidate_id=str(row.candidate_id),file_id=str(row.file_id),version_no=row.version_no,parent_version_id=str(row.parent_version_id) if row.parent_version_id else None,raw_text=row.raw_text,structured_data=row.structured_data,field_sources=row.field_sources,parser_revision=row.parser_revision,state=row.state,change_reason=row.change_reason,version=row.row_version)

    def archive(self,actor,candidate_id: int,reason: str,expected_version: int) -> TalentView:
        """归档只停止后续自动处理，保留简历和招聘历史。"""
        from app.talents.schemas import Command
        reason=Command(reason=reason).reason
        scope=ResourceScope('talent',id=candidate_id,shared=True)
        with self.identity_write(),self.transaction(actor,'talent.write',scope,response_permission='talent.read') as (uow,fresh):
            row=self._row(uow,candidate_id,expected_version);row.status='archived'
            self.audit(uow,fresh,'talent.archive','candidate',row.id,{'reason':reason,'state':'archived'})
            uow.session.flush();return self._view(uow,row)
