"""API023～026：HR批量上传、轮询与重试；不接收任意后台任务参数。"""
from fastapi import APIRouter,Depends,File,Form,Header,Path,Query,Request,Response,UploadFile
from starlette.concurrency import run_in_threadpool
from app.core.types import ApiEnvelope,Page,PageQuery,TaskAccepted
from app.files.router import file_service
from app.files.service import UploadDescriptor
from app.identity.router import require_staff,require_staff_write
from app.ingestion.schemas import ImportBatchView,BatchDetail,RetryImport
from app.ingestion.service import ImportService

router=APIRouter(prefix='/api/v1')
def service(request):
    """复用当前应用的文件服务和独立事务工厂。"""
    return ImportService(file_service(request),request.app.state.identity.uow_factory)
def envelope(request,response,value):
    """导入数据禁止缓存；统一返回带request_id的响应。"""
    response.headers['Cache-Control']='private, no-store'
    return ApiEnvelope(data=value,request_id=request.state.request_id)
@router.post('/imports',status_code=202,response_model=ApiEnvelope[ImportBatchView])
async def create_import(request: Request,response: Response,files: list[UploadFile]=File(...),job_id: int|None=Form(default=None,gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """读取实际multipart文件，在线程池受理；每份上传流始终关闭。"""
    try:
        uploads=[UploadDescriptor(f.filename or 'upload',f.content_type or 'application/octet-stream',f.size or 0,f.file) for f in files]
        value=await run_in_threadpool(service(request).create,actor,uploads,job_id,idempotency_key)
        return envelope(request,response,value)
    finally:
        for file in files: await file.close()
@router.get('/imports',response_model=ApiEnvelope[Page[ImportBatchView]])
def list_imports(request: Request,response: Response,page: int=Query(default=1,ge=1),page_size: int=Query(default=20,ge=1,le=100),actor=Depends(require_staff)):
    """HR按权限范围分页读取，不展示其他部门批次。"""
    return envelope(request,response,service(request).list_batches(actor,PageQuery(page=page,page_size=page_size)))
@router.get('/imports/{batch_id}',response_model=ApiEnvelope[BatchDetail])
def read_import(request: Request,response: Response,batch_id: int=Path(gt=0),actor=Depends(require_staff)):
    """读取安全条目状态及对应后台任务状态。"""
    return envelope(request,response,service(request).get_batch(actor,batch_id))
@router.post('/import-items/{item_id}/retry',status_code=202,response_model=ApiEnvelope[TaskAccepted])
def retry_import(cmd: RetryImport,request: Request,response: Response,item_id: int=Path(gt=0),actor=Depends(require_staff_write)):
    """显式重试只返回受控任务引用；成功条目不能重跑。"""
    return envelope(request,response,service(request).retry_item(actor,item_id,cmd.reason))
