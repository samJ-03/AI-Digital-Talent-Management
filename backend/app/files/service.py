from dataclasses import dataclass,field
from datetime import datetime,timedelta
import hashlib
import re
from tempfile import SpooledTemporaryFile
from typing import BinaryIO
from uuid import uuid4
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from app.audit.service import AuditService,AuditEvent
from app.core.access import ResourceScope
from app.core.clock import Clock
from app.core.db import Base
from app.core.errors import DomainError
from app.core.request_context import request_id_context
from app.core.resource_scope import ResourceResolver
from app.core.uow import make_uow
from app.files.models import StoredFile
from app.files.validation import validate_upload
from app.ingestion.models import ImportItem
from app.knowledge.models import KnowledgeDocument
from app.talents.models import ResumeVersion
from app.models import register_models
from app.runtime.job_service import utc_naive

@dataclass(frozen=True,slots=True)
class UploadDescriptor:
    name: str
    content_type: str
    size: int
    stream: BinaryIO=field(repr=False)

class FileView(BaseModel):
    id: str
    name: str
    mime: str
    size: int
    sha256: str

@dataclass(frozen=True,slots=True)
class DownloadGrant:
    name: str
    mime: str
    size: int
    stream: BinaryIO=field(repr=False)

class FileService:
    def __init__(self,store,uow_factory=make_uow,clock=None,max_file_bytes=20*1024*1024,max_pages=100):
        self.store=store;self.uow_factory=uow_factory;self.clock=clock or Clock()
        self.max_file_bytes=max_file_bytes;self.max_pages=max_pages
        self.resources=ResourceResolver()
        register_models()

    def stage(self,actor,upload: UploadDescriptor) -> FileView:
        if actor.actor_type!='hr' or not actor.permissions&{'import.write','knowledge.write'}:
            raise DomainError('PERMISSION_DENIED',403,'无上传权限')
        if type(upload.size) is not int or upload.size<0:
            raise DomainError('INVALID_FILE_SIZE',422,'文件大小无效')
        if upload.size>self.max_file_bytes:
            raise DomainError('FILE_SIZE_LIMIT',413,'文件超过大小限制')
        with SpooledTemporaryFile(max_size=2*1024*1024,mode='w+b') as content:
            total=0;digest=hashlib.sha256()
            while True:
                chunk=upload.stream.read(65536)
                if not chunk: break
                if not isinstance(chunk,bytes): raise DomainError('INVALID_FILE_STREAM',422,'上传内容无效')
                total+=len(chunk)
                if total>self.max_file_bytes:
                    raise DomainError('FILE_SIZE_LIMIT',413,'文件超过大小限制')
                content.write(chunk);digest.update(chunk)
            if total==0: raise DomainError('EMPTY_FILE',422,'文件内容为空')
            mime=validate_upload(upload.name,upload.content_type,content,self.max_pages)
            key='staged/'+uuid4().hex
            self.store.put(key,content,mime)
            try:
                with self.uow_factory() as uow:
                    row=StoredFile(bucket=self.store.bucket,object_key=key,sha256=digest.hexdigest(),original_name=upload.name,
                        mime_type=mime,size_bytes=total,uploader_id=actor.user_id,status='staged')
                    uow.session.add(row);uow.session.flush()
                    AuditService().append(uow,actor,AuditEvent('file.stage',ResourceScope('file',id=row.id),
                        {'changed_fields':['mime_type','size_bytes']},'success',request_id_context.get() or str(uuid4())))
                    view=FileView(id=str(row.id),name=row.original_name,mime=row.mime_type,size=row.size_bytes,sha256=row.sha256)
                    uow.commit()
                    return view
            except DBAPIError:
                # A lost commit response is ambiguous. Keep the object; age-gated orphan cleanup reconciles it.
                raise DomainError('FILE_METADATA_UNAVAILABLE',503,'文件记录暂时无法保存') from None

    def _links(self,session,file_id):
        links=[]
        for model,kind in [(ResumeVersion,'resume_version'),(ImportItem,'import_item'),(KnowledgeDocument,'knowledge_document')]:
            links.extend((kind,row_id) for row_id in session.scalars(select(model.id).where(model.file_id==file_id)))
        return links

    def authorized_download(self,actor,file_id: int) -> DownloadGrant:
        if actor.actor_type!='hr': raise DomainError('PERMISSION_DENIED',403,'无下载权限')
        with self.uow_factory() as uow:
            row=uow.session.get(StoredFile,file_id)
            if row is None or row.status in {'deleted','quarantined'} or row.bucket!=self.store.bucket:
                raise DomainError('RESOURCE_NOT_FOUND',404,'文件不存在')
            links=self._links(uow.session,file_id)
            allowed=not links and row.status=='staged' and row.uploader_id==actor.user_id and bool(actor.permissions&{'import.read','import.write','knowledge.write'})
            for kind,entity_id in links:
                try:
                    self.resources.require(uow.session,actor,kind,entity_id)
                    allowed=True;break
                except DomainError as error:
                    if error.http_status not in {403,404}: raise
            if not allowed: raise DomainError('RESOURCE_NOT_FOUND',404,'文件不存在')
            key=row.object_key;name=row.original_name;mime=row.mime_type;size=row.size_bytes
        return DownloadGrant(name,mime,size,self.store.get(key))

    def attach(self,uow,actor,file_id: int) -> StoredFile:
        row=uow.session.scalar(select(StoredFile).where(StoredFile.id==file_id).with_for_update())
        if (actor.actor_type!='hr' or row is None or row.bucket!=self.store.bucket or row.uploader_id!=actor.user_id or row.status!='staged'):
            raise DomainError('FILE_NOT_STAGED',409,'文件不处于可关联状态')
        row.status='ready'
        return row

    def _has_refs(self,session,file_id):
        # Include every registered FK so future file-linked tables cannot be deleted accidentally.
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if any(fk.column.table.name=='stored_files' for fk in column.foreign_keys):
                    if session.scalar(select(table.c.id).where(column==file_id).limit(1)) is not None: return True
        return False

    def cleanup_orphans(self,before: datetime) -> int:
        cutoff=utc_naive(before)
        if cutoff>utc_naive(self.clock.now())-timedelta(hours=1):
            raise ValueError('Orphan cleanup requires at least one hour of grace')
        removed=0
        with self.uow_factory() as uow:
            rows=list(uow.session.scalars(select(StoredFile).where(StoredFile.bucket==self.store.bucket,StoredFile.status=='staged',StoredFile.created_at<cutoff)
                .order_by(StoredFile.created_at,StoredFile.id).limit(100).with_for_update(skip_locked=True)))
            for row in rows:
                if self._has_refs(uow.session,row.id): continue
                self.store.delete(row.object_key)
                row.status='deleted';removed+=1
            uow.commit()
        # Reconcile objects from a crash before metadata commit, only under this application's UUID prefix.
        for key in self.store.expired_staged_objects(before):
            if removed>=100: break
            if not re.fullmatch(r'staged/[a-f0-9]{32}',key): continue
            with self.uow_factory() as uow:
                row=uow.session.scalar(select(StoredFile).where(StoredFile.bucket==self.store.bucket,StoredFile.object_key==key))
                if row is None:
                    self.store.delete(key);removed+=1
        return removed
