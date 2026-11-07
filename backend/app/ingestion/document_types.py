"""内部解析文档契约：保留原文定位，禁止把Word逻辑块当物理页。"""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

class ParserLimits(BaseModel):
    """解析任务的资源预算；由服务端配置，不能来自候选人自报参数。"""
    model_config=ConfigDict(extra='forbid',frozen=True)
    max_file_bytes: int=Field(default=20*1024*1024,gt=0,le=20*1024*1024,strict=True)
    max_pages: int=Field(default=100,gt=0,le=100,strict=True)
    max_chars: int=Field(default=120000,gt=0,le=120000,strict=True)
    max_paragraphs: int=Field(default=2000,gt=0,le=2000,strict=True)
    max_docx_expanded_bytes: int=Field(default=100*1024*1024,gt=0,le=100*1024*1024,strict=True)
    timeout_seconds: int=Field(default=30,ge=1,le=120,strict=True)

class DocumentParagraph(BaseModel):
    """可引用原文片段；ID由解析器生成，不包含外部文件系统路径。"""
    model_config=ConfigDict(extra='forbid',frozen=True)
    id: str=Field(min_length=1,max_length=200)
    text: str=Field(min_length=1,max_length=20000)

class DocumentPage(BaseModel):
    """物理PDF页或明确标为logical的DOCX容器。"""
    model_config=ConfigDict(extra='forbid',frozen=True)
    number: int=Field(gt=0,strict=True)
    paragraphs: tuple[DocumentParagraph,...]=Field(min_length=1,max_length=2000)

class ParsedDocument(BaseModel):
    """仅承载文件原文，不包含AI推测的身份、邮箱或技能。"""
    model_config=ConfigDict(extra='forbid',frozen=True)
    pages: tuple[DocumentPage,...]=Field(min_length=1,max_length=100)
    parser_revision: str=Field(min_length=1,max_length=100)
    pagination: Literal['physical','logical']
    @model_validator(mode='after')
    def unique_locations(self):
        """拒绝重复定位，避免后续字段证据指向多个不同段落。"""
        numbers=[page.number for page in self.pages]
        ids=[paragraph.id for page in self.pages for paragraph in page.paragraphs]
        if len(set(numbers))!=len(numbers) or len(set(ids))!=len(ids): raise ValueError('Duplicate document source location')
        return self
