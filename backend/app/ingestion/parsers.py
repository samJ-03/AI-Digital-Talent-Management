"""文本PDF/DOCX固定适配器及有时间/资源预算的进程边界。

调用者必须先完成文件授权。本模块不调用模型、OCR或外部地址；不支持
的布局明确失败。独立进程提供资源保护，不等同于完整恶意文档安全沙箱。
"""
from io import BytesIO
import json
import os
from pathlib import Path,PurePosixPath
import subprocess
import sys
from typing import BinaryIO,Protocol,TYPE_CHECKING
from app.core.errors import DomainError
from app.ingestion.document_types import ParserLimits,ParsedDocument,DocumentPage,DocumentParagraph
if TYPE_CHECKING:
    from app.files.service import FileView

ERRORS={
    'EMPTY_FILE':(422,'文档内容为空'),
    'FILE_SIZE_LIMIT':(413,'文档超过大小限制'),
    'FILE_PAGE_LIMIT':(413,'文档超过页数限制'),
    'FILE_EXPANSION_LIMIT':(413,'文档展开大小超过限制'),
    'ENCRYPTED_FILE':(422,'请上传未加密文件'),
    'DOCUMENT_NEEDS_OCR':(422,'文件含无法提取文本的页，需要OCR或人工补录'),
    'DOCUMENT_NO_TEXT':(422,'文档没有可提取文本，请检查或人工补录'),
    'DOCUMENT_COMPLEX_LAYOUT':(422,'文档包含暂不支持的布局或图像，请转换格式或人工补录'),
    'DOCUMENT_TEXT_LIMIT':(413,'文档文本或段落数量超过解析限制'),
    'DOCUMENT_PARSE_INVALID':(422,'文档格式损坏或不符合解析要求'),
    'DOCUMENT_PARSE_TIMEOUT':(422,'文档解析超时，请转换格式或人工补录'),
    'DOCUMENT_PARSE_FAILED':(422,'文档解析进程未成功，请转换格式或人工补录'),
    'DOCUMENT_RESOURCE_LIMIT':(413,'文档解析资源超过限制'),
}

def parse_error(code: str) -> DomainError:
    """只输出固定安全消息，不反射文件字节、库异常或进程日志。"""
    code=code if code in ERRORS else 'DOCUMENT_PARSE_FAILED'
    status,message=ERRORS[code]
    return DomainError(code,status,message)

class ResumeParser(Protocol):
    """所有简历解析适配器的内部契约。"""
    def parse(self,source: BinaryIO) -> ParsedDocument:
        """读取二进制文件，返回完整原文或明确失败，不返回部分成功。"""
        ...

class _IsolatedParser:
    """固定格式子进程适配器；stdin/stdout仅传递受限文件和文档JSON。"""
    kind: str
    def __init__(self,limits: ParserLimits|None=None):
        self.limits=limits or ParserLimits()

    def parse(self,source: BinaryIO) -> ParsedDocument:
        """限制真实字节并隔离解析；超时由subprocess.run终止回收子进程。"""
        chunks=[];size=0
        while True:
            chunk=source.read(min(65536,self.limits.max_file_bytes+1-size))
            if not isinstance(chunk,bytes): raise parse_error('DOCUMENT_PARSE_INVALID')
            if not chunk: break
            chunks.append(chunk);size+=len(chunk)
            if size>self.limits.max_file_bytes: raise parse_error('FILE_SIZE_LIMIT')
        data=b''.join(chunks)
        if not data: raise parse_error('EMPTY_FILE')
        if len(data)>self.limits.max_file_bytes: raise parse_error('FILE_SIZE_LIMIT')
        # Deliberately exclude application credentials from the parser environment.
        env={key:os.environ[key] for key in ('PATH','SystemRoot','WINDIR','LANG','LC_ALL','TEMP','TMP','TMPDIR') if key in os.environ}
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[2])
        env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONIOENCODING']='utf-8'
        args=[sys.executable,'-m','app.ingestion.parse_worker',self.kind,self.limits.model_dump_json()]
        try:
            result=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=self.limits.timeout_seconds,env=env,shell=False)
        except subprocess.TimeoutExpired: raise parse_error('DOCUMENT_PARSE_TIMEOUT') from None
        except OSError: raise parse_error('DOCUMENT_PARSE_FAILED') from None
        if result.returncode!=0: raise parse_error('DOCUMENT_PARSE_FAILED')
        try:
            value=json.loads(result.stdout)
            if value.get('ok') is not True: raise parse_error(value.get('code'))
            return ParsedDocument.model_validate(value['document'])
        except DomainError: raise
        except (ValueError,TypeError,KeyError,AttributeError): raise parse_error('DOCUMENT_PARSE_FAILED') from None

class PdfParser(_IsolatedParser):
    """文本PDF解析器；物理页中任一无文本页都要求OCR，避免混合页丢失。"""
    kind='pdf'

class DocxParser(_IsolatedParser):
    """文本DOCX解析器；保留正文/表格/页眉页脚，以逻辑块定位。"""
    kind='docx'

class ParserRegistry:
    """只注册已实现并验证的格式；图片、扫描件与旧DOC留后续适配器。"""
    def __init__(self,limits: ParserLimits|None=None):
        self.limits=limits or ParserLimits()

    def select(self,descriptor: 'FileView') -> ResumeParser:
        """按扩展名和真实MIME共同选择；实际字节在parse阶段再次限制。"""
        suffix=PurePosixPath(descriptor.name.replace('\\','/')).suffix.lower()
        allowed={'.pdf':('application/pdf',PdfParser),'.docx':('application/vnd.openxmlformats-officedocument.wordprocessingml.document',DocxParser)}
        if suffix not in allowed: raise DomainError('DOCUMENT_FORMAT_UNAVAILABLE',422,'该格式需要后续解析适配器或人工补录')
        mime,parser=allowed[suffix]
        if descriptor.mime!=mime: raise DomainError('DOCUMENT_TYPE_MISMATCH',422,'文档类型与扩展名不一致')
        if descriptor.size>self.limits.max_file_bytes: raise parse_error('FILE_SIZE_LIMIT')
        return parser(self.limits)

class _DocumentBuilder:
    """集中限制文本总量/段落数，在任何超限时拒绝整个文档。"""
    def __init__(self,limits):
        self.limits=limits;self.chars=0;self.count=0
    def paragraph(self,locator,text):
        """保持原文内容，仅规范化换行及边缘空白。"""
        text=text.replace('\r\n','\n').replace('\r','\n').strip()
        if not text: return None
        self.chars+=len(text);self.count+=1
        if self.chars>self.limits.max_chars or self.count>self.limits.max_paragraphs or len(text)>20000:
            raise parse_error('DOCUMENT_TEXT_LIMIT')
        return DocumentParagraph(id=locator,text=text)

def parse_pdf(data: bytes,limits: ParserLimits) -> ParsedDocument:
    """仅在受限worker中运行pypdf，不触发OCR，不静默丢页。"""
    from importlib.metadata import version
    from pypdf import PdfReader
    if not data.startswith(b'%PDF-'): raise parse_error('DOCUMENT_PARSE_INVALID')
    pdf=PdfReader(BytesIO(data),strict=True)
    if pdf.is_encrypted: raise parse_error('ENCRYPTED_FILE')
    if len(pdf.pages)>limits.max_pages: raise parse_error('FILE_PAGE_LIMIT')
    if not pdf.pages: raise parse_error('DOCUMENT_NO_TEXT')
    builder=_DocumentBuilder(limits);pages=[]
    for number,page in enumerate(pdf.pages,1):
        text=page.extract_text() or ''
        rows=[]
        for line,value in enumerate(text.splitlines(),1):
            paragraph=builder.paragraph(f'pdf:p{number}:l{line}',value)
            if paragraph is not None: rows.append(paragraph)
        if not rows: raise parse_error('DOCUMENT_NEEDS_OCR')
        pages.append(DocumentPage(number=number,paragraphs=tuple(rows)))
    return ParsedDocument(pages=tuple(pages),parser_revision='core-v1:pypdf-'+version('pypdf'),pagination='physical')

def parse_docx(data: bytes,limits: ParserLimits) -> ParsedDocument:
    """仅在受限worker中读取OOXML，复杂图像/文本框明确交给后续适配器。"""
    from importlib.metadata import version
    from zipfile import ZipFile
    from xml.etree import ElementTree
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    with ZipFile(BytesIO(data)) as package:
        entries=package.infolist();names=[e.filename for e in entries]
        if len(entries)>5000 or sum(e.file_size for e in entries)>limits.max_docx_expanded_bytes: raise parse_error('FILE_EXPANSION_LIMIT')
        if len(names)!=len(set(names)) or not {'[Content_Types].xml','word/document.xml'}<=set(names): raise parse_error('DOCUMENT_PARSE_INVALID')
        if any('vbaProject' in n or '..' in PurePosixPath(n).parts or n.startswith('/') for n in names): raise parse_error('DOCUMENT_PARSE_INVALID')
        if any(e.flag_bits&1 for e in entries): raise parse_error('ENCRYPTED_FILE')
        forbidden={'txbxContent','altChunk','object','drawing','pict','footnoteReference','endnoteReference'}
        for name in names:
            if name=='word/document.xml' or name.startswith(('word/header','word/footer')) and name.endswith('.xml'):
                tree=ElementTree.fromstring(package.read(name))
                if any(node.tag.rsplit('}',1)[-1] in forbidden for node in tree.iter()): raise parse_error('DOCUMENT_COMPLEX_LAYOUT')
                # python-docx skips runs/paragraphs inside unsupported wrappers.
                # Check every visible text node's ancestor chain before trusting it.
                ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                supported={ns+n for n in ('document','body','hdr','ftr','p','r','t','tbl','tr','tc','hyperlink')}
                parents={child:parent for parent in tree.iter() for child in parent}
                for node in tree.iter(ns+'t'):
                    while node is not None:
                        if node.tag not in supported: raise parse_error('DOCUMENT_COMPLEX_LAYOUT')
                        node=parents.get(node)
    doc=Document(BytesIO(data));builder=_DocumentBuilder(limits);rows=[];seen_cells=set()
    def walk(container,prefix,depth=0):
        if depth>16: raise parse_error('DOCUMENT_COMPLEX_LAYOUT')
        for index,block in enumerate(container.iter_inner_content(),1):
            path=f'{prefix}:b{index}'
            if isinstance(block,Paragraph):
                paragraph=builder.paragraph(path,block.text)
                if paragraph is not None: rows.append(paragraph)
            elif isinstance(block,Table):
                for r,row in enumerate(block.rows,1):
                    for c,cell in enumerate(row.cells,1):
                        if cell._tc in seen_cells: continue
                        seen_cells.add(cell._tc);walk(cell,f'{path}:r{r}:c{c}',depth+1)
    walk(doc,'docx:body')
    seen_parts=set()
    for section in doc.sections:
        for kind in ('header','first_page_header','even_page_header','footer','first_page_footer','even_page_footer'):
            container=getattr(section,kind)
            if container.is_linked_to_previous: continue
            key=str(container.part.partname)
            if key in seen_parts: continue
            seen_parts.add(key);walk(container,'docx:'+key.removeprefix('/word/'))
    if not rows: raise parse_error('DOCUMENT_NO_TEXT')
    return ParsedDocument(pages=(DocumentPage(number=1,paragraphs=tuple(rows)),),parser_revision='core-v1:python-docx-'+version('python-docx'),pagination='logical')
