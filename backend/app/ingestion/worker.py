"""受控简历解析任务：授权/下载/解析/模型在短事务外，建档原子完成。

队列仅传递任务ID。固定处理器重新读取持久化来源，不接受队列指定的
任意对象路径；永久错误保存安全条目原因，瞬时故障交持久任务有界重试。
"""
from tempfile import SpooledTemporaryFile
import hashlib
from sqlalchemy import select
from app.core.errors import DomainError
from app.core.idempotency import ResultRef
from app.core.uow import make_uow
from app.files.service import FileView, FileService
from app.files.storage import S3FileStore
from app.ai_runtime.models import WorkflowConfig
from app.ai_runtime.generation_types import AiConfigSnapshot
from app.ingestion.models import ImportItem, ImportBatch
from app.ingestion.parsers import ParserRegistry, ERRORS
from app.ingestion.document_types import ParserLimits
from app.ingestion.extraction import ResumeExtractor
from app.runtime.job_service import BackgroundJobService, JobRunner, TerminalJobFailure
from app.runtime.models import BackgroundJob
from app.talents.candidate_service import CandidateService

PERMANENT={**{code:message for code,(_,message) in ERRORS.items()},
    'DOCUMENT_FORMAT_UNAVAILABLE':'该格式尚未接入解析，请转换为文本PDF或DOCX',
    'DOCUMENT_TYPE_MISMATCH':'文档格式与类型不符，请更换文件',
    'FILE_INTEGRITY_MISMATCH':'原文件校验不一致，请重新上传',
    'FILE_UNAVAILABLE':'原文件不可用，请重新上传',
    'AI_WORKFLOW_UNAVAILABLE':'简历提取模型流程尚未启用，请联系管理员',
    'AI_CONFIG_STALE':'提取配置已更新，请重新处理',
    'AI_CONFIG_INVALID':'提取配置无效，请联系管理员',
    'AI_PROMPT_MISMATCH':'提取提示词配置不匹配，请联系管理员',
    'AI_SCHEMA_MISMATCH':'提取输出格式配置不匹配，请联系管理员',
    'AI_CAPABILITY_MISMATCH':'提取模型能力不匹配，请联系管理员',
    'SECRET_KEY_UNAVAILABLE':'模型加密配置不可用，请联系管理员',
    'MODEL_AUTH_FAILED':'提取模型鉴权未通过，请联系管理员',
    'MODEL_SECRET_MISSING':'提取模型凭据未配置，请联系管理员',
    'MODEL_OUTPUT_INVALID':'提取结果未通过校验，请重试或人工处理',
    'AI_INPUT_TOO_LARGE':'简历超过提取预算，请人工处理或拆分',
    'PERMISSION_DENIED':'导入账号当前无处理权限，请联系HR',
    'RESOURCE_NOT_FOUND':'导入来源或账号授权已失效',
    'SESSION_REQUIRED':'导入账号已失效，请联系HR',
}


class ResumeParseHandler:
    """可注入存储、网关和事务工厂，普通测试不访问付费供应商。"""
    def __init__(self,file_service,gateway,uow_factory=make_uow):
        self.files=file_service;self.gateway=gateway;self.uow_factory=uow_factory
        self.candidates=CandidateService(uow_factory)

    def finalization_context(self):
        """必须覆盖整个run_atomic直到commit，防止身份锁过早释放。"""
        return self.candidates.identity_write()

    def prepare(self,lease):
        """租约和来源预检后执行外部I/O；返回只做数据库工作的回调。"""
        with self.uow_factory() as uow:
            job=BackgroundJobService(self.uow_factory)._owned(uow,lease)
            if job.job_type!='resume.parse' or job.entity_type!='import_item':raise ValueError('Invalid parse task')
            item_id=job.entity_id;refs=dict(job.input_refs)
        snapshot=None;document=None;extracted=None;failure=None
        try:
            with self.uow_factory() as uow:
                batch,item,file,actor=self.candidates.import_context(uow,item_id)
                if refs.get('file_id')!=file.id or refs.get('import_item_id')!=item.id or refs.get('job_id')!=batch.job_id:
                    raise DomainError('FILE_INTEGRITY_MISMATCH',409,'任务来源不一致')
                snapshot=(batch.id,file.id,file.sha256,file.size_bytes,file.object_key,file.bucket,batch.job_id,batch.created_by)
                descriptor=FileView(id=str(file.id),name=file.original_name,mime=file.mime_type,size=file.size_bytes,sha256=file.sha256)
            parser=ParserRegistry(ParserLimits(max_file_bytes=self.files.max_file_bytes,max_pages=self.files.max_pages)).select(descriptor)
            grant=self.files.authorized_download(actor,int(descriptor.id))
            with grant.stream, SpooledTemporaryFile(max_size=2*1024*1024,mode='w+b') as content:
                digest=hashlib.sha256();size=0
                while True:
                    chunk=grant.stream.read(65536)
                    if not chunk:break
                    if not isinstance(chunk,bytes):raise DomainError('FILE_INTEGRITY_MISMATCH',409,'原文件校验失败')
                    size+=len(chunk)
                    if size>self.files.max_file_bytes:raise DomainError('FILE_SIZE_LIMIT',413,'文件超过大小限制')
                    digest.update(chunk);content.write(chunk)
                if size!=descriptor.size or digest.hexdigest()!=descriptor.sha256:
                    raise DomainError('FILE_INTEGRITY_MISMATCH',409,'原文件校验失败')
                content.seek(0);document=parser.parse(content)
            with self.uow_factory() as uow:
                # Recheck current authority immediately before sending text to the model.
                current_job=BackgroundJobService(self.uow_factory)._owned(uow,lease)
                batch,item,file,_=self.candidates.import_context(uow,item_id)
                current=(batch.id,file.id,file.sha256,file.size_bytes,file.object_key,file.bucket,batch.job_id,batch.created_by)
                if snapshot!=current or current_job.input_refs!=refs or current_job.entity_id!=item_id:
                    raise DomainError('IMPORT_SOURCE_CHANGED',409,'模型调用前简历来源已变化')
                flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='extract'))
                if flow is None or not flow.enabled or not flow.model_config_id or not flow.prompt_version_id:
                    raise DomainError('AI_WORKFLOW_UNAVAILABLE',409,'简历提取流程未就绪')
                config=AiConfigSnapshot(flow.model_config_id,flow.prompt_version_id,flow.timeout_seconds,flow.max_retries,flow.config_revision)
            extracted=ResumeExtractor(self.gateway,int(descriptor.id)).extract(document,config)
        except DomainError as error:
            if error.code not in PERMANENT:raise
            failure=error.code

        def finalize(uow,job):
            """同事务复验权限/来源并完成业务；异常由外层整体回滚。"""
            if job.entity_id!=item_id or job.input_refs!=refs:raise DomainError('IMPORT_SOURCE_CHANGED',409,'任务来源已变化')
            if failure:
                self._failure(uow,item_id,snapshot,failure)
                return TerminalJobFailure('INVALID_OUTPUT')
            batch,item,file,_=self.candidates.import_context(uow,item_id,True)
            current=(batch.id,file.id,file.sha256,file.size_bytes,file.object_key,file.bucket,batch.job_id,batch.created_by)
            if snapshot!=current:raise DomainError('IMPORT_SOURCE_CHANGED',409,'文件来源已变化')
            result=self.candidates.finalize_materialization(uow,item_id,extracted,document)
            return ResultRef('resume_version',result.resume_version_id,200)
        return finalize

    def _failure(self,uow,item_id,snapshot,code):
        """系统仅记录固定失败说明，不在错误中保存原文、密钥或模型响应。"""
        item=uow.session.get(ImportItem,item_id)
        if item is None:raise DomainError('RESOURCE_NOT_FOUND',404,'导入条目不存在')
        batch=uow.session.scalar(select(ImportBatch).where(ImportBatch.id==item.batch_id).with_for_update())
        item=uow.session.scalar(select(ImportItem).where(ImportItem.id==item_id).with_for_update().execution_options(populate_existing=True))
        if item.resume_version_id:raise DomainError('IMPORT_ALREADY_PARSED',409,'条目已经解析成功')
        if snapshot and (item.batch_id,item.file_id)!=(snapshot[0],snapshot[1]):raise DomainError('IMPORT_SOURCE_CHANGED',409,'导入来源已变化')
        item.status='failed';item.error_code=code;item.error_detail_safe=PERMANENT[code];batch.status='partial_failed'


def handle_resume_parse(job_id: int) -> ResultRef:
    """独立受控入口；失败明确抛错，绝不伪造成功引用。"""
    from app.core.settings import Settings
    from app.core.secrets import SecretCipher
    from app.ai_runtime.gateway import ModelGateway
    settings=Settings.load();store=S3FileStore.from_settings(settings)
    try:
        cipher=SecretCipher(settings.encryption_key.get_secret_value()) if settings.encryption_key else None
        handler=ResumeParseHandler(FileService(store,max_file_bytes=settings.max_file_bytes,max_pages=settings.max_file_pages),ModelGateway(make_uow,cipher))
        JobRunner(BackgroundJobService(),{'resume.parse':handler}).execute(job_id)
        with make_uow() as uow:
            job=uow.session.get(BackgroundJob,job_id)
            if job is None or job.state!='succeeded' or job.entity_type!='import_item':raise DomainError('PARSE_NOT_COMPLETED',409,'解析任务未成功完成')
            item=uow.session.get(ImportItem,job.entity_id)
            if item is None or not item.resume_version_id:raise DomainError('PARSE_NOT_COMPLETED',409,'解析任务尚无简历结果')
            return ResultRef('resume_version',item.resume_version_id,200)
    finally:store.close()
