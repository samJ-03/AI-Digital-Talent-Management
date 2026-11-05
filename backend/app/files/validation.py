from pathlib import PurePosixPath
import struct
import zipfile
from xml.etree import ElementTree
from pypdf import PdfReader
from app.core.errors import DomainError

MIMES={'.pdf':'application/pdf','.doc':'application/msword','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}

def invalid(): return DomainError('INVALID_FILE_FORMAT',422,'文件扩展名、内容类型或文件内容不符合要求')

def validate_upload(name: str,mime: str,stream,max_pages: int=100) -> str:
    if not name or len(name)>255 or any(c in name for c in ('\x00','\r','\n')): raise invalid()
    suffix=PurePosixPath(name.replace('\\','/')).suffix.lower()
    expected=MIMES.get(suffix)
    if expected is None: raise invalid()
    declared=mime.split(';',1)[0].strip().lower()
    if declared=='image/jpg': declared='image/jpeg'
    if declared not in {expected,'application/octet-stream'}: raise invalid()
    stream.seek(0);header=stream.read(64);stream.seek(0)
    try:
        if suffix=='.pdf':
            if not header.startswith(b'%PDF-'): raise invalid()
            pdf=PdfReader(stream,strict=False)
            if pdf.is_encrypted: raise DomainError('ENCRYPTED_FILE',422,'请上传未加密文件')
            if len(pdf.pages)>max_pages: raise DomainError('FILE_PAGE_LIMIT',413,'文件超过页数限制')
            if not pdf.pages: raise invalid()
        elif suffix=='.png':
            if not header.startswith(b'\x89PNG\r\n\x1a\n') or header[12:16]!=b'IHDR' or len(header)<24: raise invalid()
            width,height=struct.unpack('>II',header[16:24])
            if width<1 or height<1 or width*height>40_000_000: raise DomainError('IMAGE_PIXEL_LIMIT',413,'图像尺寸超过限制')
        elif suffix in {'.jpg','.jpeg'}:
            if not header.startswith(b'\xff\xd8\xff'): raise invalid()
            stream.seek(-2,2)
            if stream.read(2)!=b'\xff\xd9': raise invalid()
        elif suffix=='.docx':
            if not header.startswith(b'PK\x03\x04'): raise invalid()
            with zipfile.ZipFile(stream) as package:
                entries=package.infolist();names={item.filename for item in entries}
                if not {'[Content_Types].xml','word/document.xml'}<=names: raise invalid()
                if len(entries)>5000 or sum(e.file_size for e in entries)>100*1024*1024:
                    raise DomainError('FILE_EXPANSION_LIMIT',413,'文档展开尺寸超过限制')
                if any('vbaProject' in e.filename or '..' in PurePosixPath(e.filename).parts or e.filename.startswith('/') for e in entries): raise invalid()
                xml=ElementTree.fromstring(package.read('word/document.xml'))
                if xml.tag!='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document': raise invalid()
        else:
            if not header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'): raise invalid()
            stream.seek(0)
            if 'WordDocument'.encode('utf-16le') not in stream.read(): raise invalid()
    except DomainError: raise
    except Exception: raise invalid() from None
    finally: stream.seek(0)
    return expected
