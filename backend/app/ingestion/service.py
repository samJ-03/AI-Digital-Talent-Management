"""HR批量导入：独立文件失败、幂等受理、部门查询和防重重试。

文件存储在数据库事务外；关联、任务、Outbox和审计同事务。实际解析与
人才建档由T15处理器承接，不能把本模块的202受理当成解析成功。
"""
from contextlib import ExitStack,contextmanager
from datetime import timezone
from tempfile import SpooledTemporaryFile
from pathlib import PurePosixPath
import hashlib,json,re
from sqlalchemy import select,func,or_,and_
from app.core.access import ResourceScope
from app.core.errors import DomainError
from app.core.hr_service import HrServiceBase
from app.core.idempotency import ResultRef
from app.core.models import IdempotencyRecord
from app.core.resource_scope import ResourceResolver
from app.core.types import Page,PageQuery,TaskAccepted
from app.core.uow import make_uow
from app.files.models import StoredFile
from app.files.service import UploadDescriptor
from app.identity.models import User
from app.jobs.models import Job
from app.ingestion.models import ImportBatch,ImportItem
from app.ingestion.schemas import ImportBatchView,BatchDetail,ImportItemView
from app.runtime.models import BackgroundJob
from app.runtime.job_service import BackgroundJobService,JobSpec

SAFE_ERRORS={
    'INVALID_FILE_FORMAT':'文件格式或内容无效，请更换文件',
    'FILE_SIZE_LIMIT':'文件超过大小限制，请更换文件',
    'FILE_PAGE_LIMIT':'文件超过页数限制，请更换文件',
    'ENCRYPTED_FILE':'文件已加密，请上传未加密版本',
    'EMPTY_FILE':'文件内容为空，请更换文件',
    'FILE_EXPANSION_LIMIT':'文档展开大小超过限制，请更换文件',
    'IMAGE_PIXEL_LIMIT':'图片尺寸超过限制，请更换文件',
    'FILE_UPLOAD_FAILED':'文件暂未成功存储，请重新上传',
    'HANDLER_NOT_REGISTERED':'解析处理器尚未就绪，可稍后重试',
    'HANDLER_FAILED':'解析任务未成功，可重试或人工处理',
    'DEPENDENCY_UNAVAILABLE':'处理依赖暂不可用，可稍后重试',
    'INVALID_OUTPUT':'提取结果未通过校验，可重试或人工处理',
}

class ImportService(HrServiceBase):
    """构造参数可降低批次上限；文件/页数上限沿用FileService配置。"""
    def __init__(self,file_service,uow_factory=make_uow,max_files=50):
        super().__init__(uow_factory)
        if type(max_files) is not int or not 1<=max_files<=50: raise ValueError('Import limit must be 1..50')
        self.files=file_service;self.max_files=max_files
        self.tasks=BackgroundJobService(uow_factory)

    def _creation_scope(self,uow,actor,job_id):
        if job_id is not None:
            if type(job_id) is not int or job_id<=0: raise DomainError('INVALID_JOB',422,'岗位参数无效')
            job=uow.session.get(Job,job_id)
            if job is None: raise DomainError('RESOURCE_NOT_FOUND',404,'岗位不存在')
            scope=ResourceScope('import_batch',department_id=job.department_id)
        else:
            user=uow.session.get(User,actor.user_id)
            scope=ResourceScope('import_batch',department_id=user.department_id if user else None)
        fresh=self.authorize(uow,actor,'import.write',scope)
        self.authorize(uow,fresh,'import.read',scope)
        if job_id is not None: self.authorize(uow,fresh,'job.read',scope)
        return scope,fresh

    def _scope(self,uow,batch_id):
        return ResourceResolver().resolve(uow.session,'import_batch',batch_id).scope

    def _prepare(self,files,stack):
        """有界缓存与真实哈希；超总预算拒绝，单份超限保留失败条目。"""
        if not isinstance(files,list) or not files or len(files)>self.max_files:
            raise DomainError('IMPORT_FILE_LIMIT',413,'文件数量超出批次限制')
        prepared=[];fingerprints=[];total=0
        budget=self.max_files*self.files.max_file_bytes+1024*1024
        for upload in files:
            content=stack.enter_context(SpooledTemporaryFile(max_size=1024*1024,mode='w+b'))
            size=0;digest=hashlib.sha256()
            while True:
                chunk=upload.stream.read(65536)
                if not isinstance(chunk,bytes): raise DomainError('INVALID_FILE_STREAM',422,'上传内容无效')
                if not chunk: break
                total+=len(chunk);size+=len(chunk)
                if total>budget: raise DomainError('IMPORT_BATCH_SIZE_LIMIT',413,'批次总大小超过限制')
                digest.update(chunk)
                if size<=self.files.max_file_bytes: content.write(chunk)
            content.seek(0)
            error='FILE_SIZE_LIMIT' if size>self.files.max_file_bytes else 'EMPTY_FILE' if size==0 else None
            prepared.append((UploadDescriptor(upload.name,upload.content_type,size,content),error))
            fingerprints.append({'name':upload.name,'mime':upload.content_type,'size':size,'sha256':digest.hexdigest()})
        return prepared,fingerprints

    def create(self,actor,files: list[UploadDescriptor],job_id: int|None,request_key: str) -> ImportBatchView:
        """按有序实际内容幂等建批次，每文件校验独立，不自动创建邀请。"""
        if not request_key or not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,100}',request_key):
            raise DomainError('INVALID_IDEMPOTENCY_KEY',422,'需要合法的幂等键')
        with self.uow_factory() as uow: scope,fresh=self._creation_scope(uow,actor,job_id)
        with ExitStack() as stack:
            prepared,fingerprints=self._prepare(files,stack)
            payload={'job_id':job_id,'files':fingerprints}
            digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
            with self.uow_factory() as uow:
                existing=uow.session.scalar(select(ImportBatch).where(ImportBatch.created_by==fresh.user_id,ImportBatch.request_key==request_key))
                if existing is not None:
                    record=uow.session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.actor_scope==fresh.scope_key,IdempotencyRecord.operation=='import.create',IdempotencyRecord.request_key==request_key))
                    if record is None or record.state!='completed' or not record.result_refs or record.result_refs.get('entity_id')!=existing.id:
                        raise DomainError('IMPORT_KEY_EXPIRED',409,'此批次请求键已使用，请换新键')
                    if record.request_hash!=digest: raise DomainError('IDEMPOTENCY_CONFLICT',409,'相同幂等键对应不同文件')
                    return ImportBatchView.model_validate(self.get_batch(actor,existing.id).model_dump())
            staged=[]
            for upload,error in prepared:
                file_id=None
                if error is None:
                    try: file_id=int(self.files.stage(fresh,upload).id)
                    except DomainError as exc: error=exc.code if exc.code in SAFE_ERRORS else 'FILE_UPLOAD_FAILED'
                    except Exception: error='FILE_UPLOAD_FAILED'
                staged.append((file_id,error))
            def command(uow,current):
                self._creation_scope(uow,current,job_id)
                batch=ImportBatch(job_id=job_id,created_by=current.user_id,request_key=request_key,file_count=len(files),status='partial_failed' if any(error for _,error in staged) else 'queued')
                uow.session.add(batch);uow.session.flush()
                for order,(file_id,error) in enumerate(staged):
                    if file_id is not None: self.files.attach(uow,current,file_id)
                    item=ImportItem(batch_id=batch.id,file_id=file_id,source_order=order,status='failed' if error else 'queued',error_code=error,error_detail_safe=SAFE_ERRORS.get(error))
                    uow.session.add(item);uow.session.flush()
                    if file_id is not None:
                        refs={'file_id':file_id,'import_item_id':item.id}
                        if job_id is not None: refs['job_id']=job_id
                        self.tasks.enqueue(uow,JobSpec('resume.parse','import_item',item.id,f'resume.parse:{item.id}:initial',refs))
                self.audit(uow,current,'import.create','import_batch',batch.id,{'file_count':batch.file_count,'failed_count':sum(bool(error) for _,error in staged)})
                return ResultRef('import_batch',batch.id,202)
            result=HrServiceBase(self.uow_factory,request_key).execute(fresh,'import.write',scope,'import.create',payload,command,response_permission='import.read')
            return ImportBatchView.model_validate(self.get_batch(actor,result.entity_id).model_dump())

    def _detail(self,session,batch):
        items=list(session.scalars(select(ImportItem).where(ImportItem.batch_id==batch.id).order_by(ImportItem.source_order)))
        ids=[i.id for i in items]
        latest={}
        for task in session.scalars(select(BackgroundJob).where(BackgroundJob.entity_type=='import_item',BackgroundJob.entity_id.in_(ids)).order_by(BackgroundJob.id.desc())):
            latest.setdefault(task.entity_id,task)
        file_ids=[i.file_id for i in items if i.file_id]
        stored={f.id:f for f in session.scalars(select(StoredFile).where(StoredFile.id.in_(file_ids)))}
        views=[]
        for item in items:
            task=latest.get(item.id);state=item.status;code=item.error_code
            if state!='parsed' and task:
                if task.state in {'failed','cancelled'}: state='failed';code=task.error_code or 'HANDLER_FAILED'
                elif task.state=='running': state='parsing'
            code=code if code in SAFE_ERRORS else ('HANDLER_FAILED' if state=='failed' else None)
            file=stored.get(item.file_id)
            name=PurePosixPath(file.original_name.replace('\\','/')).name if file else None
            views.append(ImportItemView(id=str(item.id),source_order=item.source_order,file_id=str(item.file_id) if item.file_id else None,filename=name,status=state,
                error_code=code,error_detail_safe=SAFE_ERRORS.get(code),task_id=str(task.id) if task else None,task_state=task.state if task else None,resume_version_id=str(item.resume_version_id) if item.resume_version_id else None))
        status='completed' if views and all(i.status=='parsed' for i in views) else 'partial_failed' if any(i.status=='failed' for i in views) else 'processing' if any(i.status=='parsing' for i in views) else 'queued'
        return BatchDetail(id=str(batch.id),job_id=str(batch.job_id) if batch.job_id else None,created_by=str(batch.created_by),file_count=batch.file_count,status=status,created_at=batch.created_at.replace(tzinfo=timezone.utc),items=views)

    def get_batch(self,actor,batch_id: int) -> BatchDetail:
        """复验HR部门权限后投影条目及任务状态，不返回内部错误。"""
        with self.uow_factory() as uow:
            scope=self._scope(uow,batch_id);self.authorize(uow,actor,'import.read',scope)
            return self._detail(uow.session,uow.session.get(ImportBatch,batch_id))

    def list_batches(self,actor,query: PageQuery) -> Page[ImportBatchView]:
        """同一权限过滤同时应用于总数和稳定ID分页。"""
        with self.uow_factory() as uow:
            user=uow.session.get(User,actor.user_id)
            scope=ResourceScope('import_batch',department_id=user.department_id if user else None)
            fresh=self.authorize(uow,actor,'import.read',scope)
            stmt=select(ImportBatch).join(User,User.id==ImportBatch.created_by).outerjoin(Job,Job.id==ImportBatch.job_id)
            if 'import.read' not in fresh.company_permissions:
                stmt=stmt.where(or_(Job.department_id.in_(fresh.department_ids),and_(ImportBatch.job_id.is_(None),User.department_id.in_(fresh.department_ids))))
            total=uow.session.scalar(select(func.count()).select_from(stmt.subquery()))
            rows=list(uow.session.scalars(stmt.order_by(ImportBatch.id.desc()).offset((query.page-1)*query.page_size).limit(query.page_size)))
            return Page(items=[ImportBatchView.model_validate(self._detail(uow.session,row).model_dump()) for row in rows],total=total,page=query.page,page_size=query.page_size)

    def retry_item(self,actor,item_id: int,reason: str) -> TaskAccepted:
        """失败解析追加新任务；并发/重复重试复用已有活动任务。"""
        if not reason or not reason.strip() or len(reason)>500: raise DomainError('REASON_REQUIRED',422,'重试原因无效')
        with self.uow_factory() as uow:
            item=uow.session.get(ImportItem,item_id)
            if item is None: raise DomainError('RESOURCE_NOT_FOUND',404,'导入条目不存在')
            batch_id=item.batch_id;scope=self._scope(uow,batch_id)
        # Worker completion locks its task before domain rows. Do not lock the
        # task in reverse order here; READ COMMITTED sees serialized retries.
        @contextmanager
        def retry_uow():
            with self.uow_factory() as uow:
                uow.session.connection(execution_options={'isolation_level':'READ COMMITTED'})
                yield uow
        with HrServiceBase(retry_uow).transaction(actor,'import.write',scope,response_permission='import.read') as (uow,fresh):
            batch=uow.session.scalar(select(ImportBatch).where(ImportBatch.id==batch_id).with_for_update().execution_options(populate_existing=True))
            self.authorize(uow,fresh,'import.write',self._scope(uow,batch_id))
            item=uow.session.scalar(select(ImportItem).where(ImportItem.id==item_id).with_for_update().execution_options(populate_existing=True))
            if item.file_id is None: raise DomainError('FILE_REPLACEMENT_REQUIRED',422,'原文件未通过上传校验，请更换文件重新上传')
            task=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.entity_type=='import_item',BackgroundJob.entity_id==item_id).order_by(BackgroundJob.id.desc()).limit(1))
            if item.status=='parsed' or task and task.state=='succeeded': raise DomainError('IMPORT_ALREADY_PARSED',409,'成功条目不能重复解析')
            if task and task.state in {'queued','running','retry'}:
                task_id=task.id;state=task.state
            else:
                if task is None or task.state not in {'failed','cancelled'}: raise DomainError('IMPORT_NOT_RETRYABLE',409,'条目当前不可重试')
                file=uow.session.get(StoredFile,item.file_id)
                if file is None or file.status!='ready' or file.bucket!=self.files.store.bucket: raise DomainError('FILE_REPLACEMENT_REQUIRED',422,'原文件已不可用，请重新上传')
                refs={'file_id':item.file_id,'import_item_id':item.id}
                if batch.job_id: refs['job_id']=batch.job_id
                task_id=self.tasks.enqueue(uow,JobSpec('resume.parse','import_item',item.id,f'resume.parse:{item.id}:after:{task.id}',refs))
                item.status='queued';item.error_code=None;item.error_detail_safe=None
                self.audit(uow,fresh,'import.retry','import_item',item.id,{'reason':reason,'task_id':task_id})
                state='queued'
        return TaskAccepted(task_id=str(task_id),state=state,poll_url='/api/v1/imports/'+str(batch_id))
