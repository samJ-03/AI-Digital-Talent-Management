from fastapi import APIRouter,Depends,Request,Response,Path
from app.core.types import ApiEnvelope
from app.identity.router import require_staff
from app.runtime.queries import RuntimeQueries,TaskView

router=APIRouter(prefix='/api/v1')

@router.get('/tasks/{task_id}',response_model=ApiEnvelope[TaskView])
def get_task(request: Request,response: Response,task_id: int=Path(gt=0),actor=Depends(require_staff)):
    view=RuntimeQueries(request.app.state.identity.uow_factory).task(actor,task_id)
    response.headers['Cache-Control']='no-store'
    return ApiEnvelope(data=view,request_id=request.state.request_id)
