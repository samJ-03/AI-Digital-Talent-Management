"""批量导入的安全响应契约；不返回对象key、原始异常或简历正文。"""
from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field
class ImportBatchView(BaseModel):
    """批次元数据及当前处理汇总。"""
    id: str
    job_id: str|None
    created_by: str
    file_count: int
    status: str
    created_at: datetime
class ImportItemView(BaseModel):
    """单文件状态；前置失败无file_id，需要换文件重传。"""
    id: str
    source_order: int
    file_id: str|None
    filename: str|None
    status: str
    error_code: str|None
    error_detail_safe: str|None
    task_id: str|None
    task_state: str|None
    resume_version_id: str|None
class BatchDetail(ImportBatchView):
    """按原上传顺序列出条目，任务失败通过安全投影显示。"""
    items: list[ImportItemView]
class RetryImport(BaseModel):
    """显式重试必须记录原因，不接受任意任务参数。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason: str=Field(min_length=1,max_length=500)
