"""固定格式解析子进程入口；不加载应用Settings或凭据，不调用网络。"""
import json
import logging
import math
import sys
from app.core.errors import DomainError
from app.ingestion.document_types import ParserLimits

def main() -> int:
    """先设置Linux资源上限，再读受限stdin并调用固定解析函数。"""
    logging.disable(logging.CRITICAL)
    try:
        if len(sys.argv)!=3 or sys.argv[1] not in {'pdf','docx'}: raise ValueError('Invalid parser entry')
        limits=ParserLimits.model_validate_json(sys.argv[2])
        if sys.platform.startswith('linux'):
            import resource
            resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
            cpu=math.ceil(limits.timeout_seconds)
            resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu+1))
        data=sys.stdin.buffer.read(limits.max_file_bytes+1)
        from app.ingestion.parsers import parse_pdf,parse_docx,parse_error
        if not data: raise parse_error('EMPTY_FILE')
        if len(data)>limits.max_file_bytes: raise parse_error('FILE_SIZE_LIMIT')
        document=(parse_pdf if sys.argv[1]=='pdf' else parse_docx)(data,limits)
        result={'ok':True,'document':document.model_dump(mode='json')}
    except DomainError as exc: result={'ok':False,'code':exc.code}
    except MemoryError: result={'ok':False,'code':'DOCUMENT_RESOURCE_LIMIT'}
    except Exception: result={'ok':False,'code':'DOCUMENT_PARSE_INVALID'}
    sys.stdout.write(json.dumps(result,ensure_ascii=True,separators=(',',':')))
    return 0

if __name__=='__main__': raise SystemExit(main())
