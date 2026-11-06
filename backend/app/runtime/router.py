"""持久后台任务与Outbox：声明HTTP入口、身份依赖和响应封装。"""
from fastapi import APIRouter,Depends,Request,Response,Path
from app.core.types import ApiEnvelope
from app.identity.router import require_staff
from app.runtime.queries import RuntimeQueries,TaskView

router=APIRouter(prefix='/api/v1')

@router.get('/tasks/{task_id}',response_model=ApiEnvelope[TaskView])
def get_task(request: Request,response: Response,task_id: int=Path(gt=0),actor=Depends(require_staff)):
    """HTTP入口：读取task，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    view=RuntimeQueries(request.app.state.identity.uow_factory).task(actor,task_id)
    response.headers['Cache-Control']='no-store'
    return ApiEnvelope(data=view,request_id=request.state.request_id)

@router.get('/admin/runtime')
def get_admin_runtime(request: Request,response: Response,task_id: int|None=None,actor=Depends(require_staff)):
    """HTTP入口：读取admin runtime，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    from app.runtime.admin_queries import RuntimeAdminQueries
    response.headers['Cache-Control']='no-store'
    return ApiEnvelope(data=RuntimeAdminQueries(request.app.state.identity.uow_factory).report(actor,task_id),request_id=request.state.request_id)
