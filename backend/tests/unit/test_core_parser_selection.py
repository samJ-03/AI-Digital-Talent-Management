"""格式选择、实际字节限制与隔离边界单元测试。"""
from io import BytesIO
import json,subprocess
import pytest
from app.core.errors import DomainError

def descriptor(name,mime,size=10):
    from app.files.service import FileView
    return FileView(id='1',name=name,mime=mime,size=size,sha256='0'*64)

@pytest.mark.parametrize('name,mime,parser',[('CV.PDF','application/pdf','PdfParser'),('CV.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document','DocxParser')])
def test_registered_core_formats(name,mime,parser):
    from app.ingestion.parsers import ParserRegistry
    assert type(ParserRegistry().select(descriptor(name,mime))).__name__==parser

@pytest.mark.parametrize('name,mime',[('CV.pdf','image/png'),('CV.docx','application/pdf'),('CV.doc','application/msword'),('CV.png','image/png')])
def test_unsupported_or_mismatched_types_explicit(name,mime):
    from app.ingestion.parsers import ParserRegistry
    with pytest.raises(DomainError) as error: ParserRegistry().select(descriptor(name,mime))
    assert error.value.code in {'DOCUMENT_TYPE_MISMATCH','DOCUMENT_FORMAT_UNAVAILABLE'}

def test_descriptor_size_limit():
    from app.ingestion.parsers import ParserRegistry
    from app.ingestion.document_types import ParserLimits
    with pytest.raises(DomainError) as error: ParserRegistry(ParserLimits(max_file_bytes=1)).select(descriptor('CV.pdf','application/pdf'))
    assert error.value.code=='FILE_SIZE_LIMIT'

def test_timeout_terminates_with_safe_error(monkeypatch):
    from app.ingestion.parsers import PdfParser
    def timeout(*args,**kwargs): raise subprocess.TimeoutExpired(args[0],kwargs['timeout'])
    monkeypatch.setattr(subprocess,'run',timeout)
    with pytest.raises(DomainError) as error: PdfParser().parse(BytesIO(b'%PDF-test'))
    assert error.value.code=='DOCUMENT_PARSE_TIMEOUT'

def test_worker_environment_excludes_credentials(monkeypatch):
    from app.ingestion.parsers import PdfParser
    monkeypatch.setenv('TALENT_DATABASE_URL','synthetic-db-secret')
    monkeypatch.setenv('DEEPSEEK_API_KEY','synthetic-model-secret')
    def run(args,**kwargs):
        assert 'TALENT_DATABASE_URL' not in kwargs['env'] and 'DEEPSEEK_API_KEY' not in kwargs['env']
        assert kwargs['shell'] is False and kwargs['timeout']>0
        return subprocess.CompletedProcess(args,0,json.dumps({'ok':True,'document':{'pages':[{'number':1,'paragraphs':[{'id':'pdf:p1:l1','text':'Python'}]}],'pagination':'physical','parser_revision':'test-worker'}}).encode(),b'')
    monkeypatch.setattr(subprocess,'run',run)
    assert PdfParser().parse(BytesIO(b'%PDF-test')).pages[0].paragraphs[0].text=='Python'

def test_crashed_worker_is_not_success(monkeypatch):
    from app.ingestion.parsers import PdfParser
    monkeypatch.setattr(subprocess,'run',lambda *args,**kw:subprocess.CompletedProcess(args,-9,b'',b'private diagnostic'))
    with pytest.raises(DomainError) as error: PdfParser().parse(BytesIO(b'%PDF-test'))
    assert error.value.code=='DOCUMENT_PARSE_FAILED' and 'private' not in error.value.message
