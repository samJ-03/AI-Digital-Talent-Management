"""将授权文件的解析原文送入固定extract图，返回已校验事实。

这是内部能力；调用方必须先按持久化stored_file关系完成授权。本模块不
接受客户端自报的来源类型，不建档、不发信，也不自动发布提示词配置。
"""
import json
from app.ai_runtime.generation_types import AiConfigSnapshot
from app.ai_runtime.graphs import FixedGraphRunner
from app.core.errors import DomainError
from app.ingestion.document_types import ParsedDocument
from app.ingestion.extraction_types import ResumeFacts,ExtractedResume

class ResumeExtractor:
    """依赖已装配网关和调用方已授权文件ID；避免另建供应商连接。"""
    def __init__(self,gateway,source_file_id: int):
        if type(source_file_id) is not int or not 0<source_file_id<2**64:
            raise ValueError('A persisted authorized file ID is required')
        self.source_id=str(source_file_id)
        self.runner=FixedGraphRunner(gateway,{'extract':ResumeFacts})

    def extract(self,document: ParsedDocument,config: AiConfigSnapshot) -> ExtractedResume:
        """完整传入段落证据；超预算拒绝，禁止截断后假称全文提取。"""
        paragraphs=[p for page in document.pages for p in page.paragraphs]
        if not paragraphs or len(paragraphs)>100:
            raise DomainError('AI_INPUT_TOO_LARGE',422,'简历段落超出当前提取预算，请人工处理或拆分')
        source={'source_type':'stored_file','source_id':self.source_id}
        evidence=[{**source,'locator':p.id,'quote':p.text} for p in paragraphs]
        payload={'input_refs':[source],'evidence':evidence,'output_schema':ResumeFacts.model_json_schema()}
        if len(json.dumps(payload,ensure_ascii=False).encode('utf8'))>250*1024:
            raise DomainError('AI_INPUT_TOO_LARGE',422,'简历文本超出当前提取预算')
        # Gateway rechecks enabled workflow, snapshot, published schema and citations.
        result=self.runner.run('extract',payload,config)
        return ExtractedResume.model_validate({**result.output,'ai_run_id':result.ai_run_id})
