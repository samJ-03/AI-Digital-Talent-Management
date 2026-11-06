"""私有文件：声明HTTP入口、身份依赖和响应封装。"""
from urllib.parse import quote
from fastapi import APIRouter,Depends,Path,Request
from fastapi.responses import StreamingResponse
from app.files.storage import S3FileStore
from app.files.service import FileService
from app.identity.router import require_staff

router=APIRouter(prefix='/api/v1')

def file_service(request: Request) -> FileService:
    """从当前请求获取私有文件服务依赖。"""
    service=request.app.state.file_service
    if service is None:
        from app.core.errors import DomainError
        raise DomainError('FILE_STORAGE_UNAVAILABLE',503,'文件服务未配置')
    return service

@router.get('/files/{file_id}/download',response_class=StreamingResponse)
def download_file(request: Request,file_id: int=Path(gt=0),actor=Depends(require_staff)):
    """从业务持久化归属验证权限后返回私有附件流，禁止缓存。"""
    if actor.actor_type!='hr':
        from app.core.errors import DomainError
        raise DomainError('PERMISSION_DENIED',403,'无下载权限')
    grant=file_service(request).authorized_download(actor,file_id)
    def chunks():
        try:
            while True:
                chunk=grant.stream.read(65536)
                if not chunk: break
                yield chunk
        finally: grant.stream.close()
    name=grant.name.replace('\\','/').rsplit('/',1)[-1] or 'download'
    return StreamingResponse(chunks(),media_type=grant.mime,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name,safe=''),
        'Content-Length':str(grant.size),'Cache-Control':'private, no-store'})
