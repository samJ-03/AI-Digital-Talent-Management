"""真实内存PDF/DOCX样本验收；不调用数据库、模型或网络。"""
from io import BytesIO
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from docx import Document
import pytest
from app.core.errors import DomainError

def pdf_bytes(texts,encrypted=False):
    """生成含真实PDF字体与内容流的合成文件，不伪造解析返回值。"""
    writer=PdfWriter()
    for text in texts:
        page=writer.add_blank_page(width=300,height=300)
        if text is not None:
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 10 250 Td ('+text+') Tj ET').encode('ascii'))
            page[NameObject('/Contents')]=writer._add_object(stream)
    if encrypted: writer.encrypt('synthetic-password')
    out=BytesIO();writer.write(out);return out.getvalue()

def docx_bytes(populate=None):
    """生成真实OOXML包，供子进程内的python-docx读取。"""
    document=Document()
    if populate: populate(document)
    out=BytesIO();document.save(out);return out.getvalue()

def test_text_pdf_retains_pages_and_stable_sources():
    from app.ingestion.parsers import PdfParser
    parser=PdfParser();data=pdf_bytes(['Alice Python','alice@example.com'])
    a=parser.parse(BytesIO(data));b=parser.parse(BytesIO(data))
    assert a==b and a.pagination=='physical'
    assert [p.number for p in a.pages]==[1,2]
    assert a.pages[0].paragraphs[0].text=='Alice Python'
    assert a.pages[1].paragraphs[0].id=='pdf:p2:l1'
    assert 'pypdf-' in a.parser_revision

@pytest.mark.parametrize('texts',[[None],['Python',None]])
def test_scan_or_mixed_pdf_does_not_silently_drop_page(texts):
    from app.ingestion.parsers import PdfParser
    with pytest.raises(DomainError) as error: PdfParser().parse(BytesIO(pdf_bytes(texts)))
    assert error.value.code=='DOCUMENT_NEEDS_OCR'

def test_encrypted_pdf_rejected():
    from app.ingestion.parsers import PdfParser
    with pytest.raises(DomainError) as error: PdfParser().parse(BytesIO(pdf_bytes(['Python'],True)))
    assert error.value.code=='ENCRYPTED_FILE'

def test_page_limit():
    from app.ingestion.parsers import PdfParser
    from app.ingestion.document_types import ParserLimits
    with pytest.raises(DomainError) as error: PdfParser(ParserLimits(max_pages=1)).parse(BytesIO(pdf_bytes(['A','B'])))
    assert error.value.code=='FILE_PAGE_LIMIT'

@pytest.mark.parametrize('data',[b'',b'%PDF-corrupt',b'not a pdf'])
def test_malformed_pdf_fails_safely(data):
    from app.ingestion.parsers import PdfParser
    with pytest.raises(DomainError) as error: PdfParser().parse(BytesIO(data))
    assert error.value.code in {'EMPTY_FILE','DOCUMENT_PARSE_INVALID'}
    assert data.decode('ascii',errors='ignore') not in error.value.message or not data

@pytest.mark.parametrize('limit,code',[({'max_file_bytes':32},'FILE_SIZE_LIMIT'),({'max_chars':3},'DOCUMENT_TEXT_LIMIT'),({'max_paragraphs':1},'DOCUMENT_TEXT_LIMIT')])
def test_pdf_resource_bounds(limit,code):
    from app.ingestion.parsers import PdfParser
    from app.ingestion.document_types import ParserLimits
    with pytest.raises(DomainError) as error: PdfParser(ParserLimits(**limit)).parse(BytesIO(pdf_bytes(['Python','Email'])))
    assert error.value.code==code

def test_docx_body_table_header_footer_and_stable_locations():
    from app.ingestion.parsers import DocxParser
    def populate(doc):
        doc.add_paragraph('张三 Python开发')
        table=doc.add_table(rows=1,cols=2);table.cell(0,0).text='专业：软件工程';table.cell(0,1).text='本科'
        doc.add_paragraph('项目：人才平台')
        doc.sections[0].header.paragraphs[0].text='zhangsan@example.com'
        doc.sections[0].footer.paragraphs[0].text='联系电话：13800000000'
    data=docx_bytes(populate);a=DocxParser().parse(BytesIO(data));b=DocxParser().parse(BytesIO(data))
    assert a==b and a.pagination=='logical' and len(a.pages)==1
    rows=a.pages[0].paragraphs;texts=[p.text for p in rows]
    assert texts[:4]==['张三 Python开发','专业：软件工程','本科','项目：人才平台']
    assert 'zhangsan@example.com' in texts and '联系电话：13800000000' in texts
    assert len({p.id for p in rows})==len(rows)
    assert all(p.id.startswith('docx:') for p in rows)

def test_docx_merged_cells_not_duplicated():
    from app.ingestion.parsers import DocxParser
    def populate(doc):
        t=doc.add_table(rows=1,cols=2);t.cell(0,0).merge(t.cell(0,1)).text='Merged Python'
    out=DocxParser().parse(BytesIO(docx_bytes(populate)))
    assert [p.text for p in out.pages[0].paragraphs]==['Merged Python']

def test_empty_docx_not_success():
    from app.ingestion.parsers import DocxParser
    with pytest.raises(DomainError) as error: DocxParser().parse(BytesIO(docx_bytes()))
    assert error.value.code=='DOCUMENT_NO_TEXT'

def test_docx_expansion_limit():
    from app.ingestion.parsers import DocxParser
    from app.ingestion.document_types import ParserLimits
    with pytest.raises(DomainError) as error: DocxParser(ParserLimits(max_docx_expanded_bytes=100)).parse(BytesIO(docx_bytes(lambda d:d.add_paragraph('Python'))))
    assert error.value.code=='FILE_EXPANSION_LIMIT'

def test_docx_textbox_requires_advanced_parser():
    from app.ingestion.parsers import DocxParser
    from docx.oxml import OxmlElement
    def populate(doc):
        doc.add_paragraph('Body')
        box=OxmlElement('w:txbxContent');box.append(OxmlElement('w:p'));doc._element.body.append(box)
    with pytest.raises(DomainError) as error: DocxParser().parse(BytesIO(docx_bytes(populate)))
    assert error.value.code=='DOCUMENT_COMPLEX_LAYOUT'

@pytest.mark.parametrize('kind',['content_control','tracked_insertion','alternate_content'])
def test_docx_wrapped_visible_text_not_silently_lost(kind):
    from app.ingestion.parsers import DocxParser
    from docx.oxml import OxmlElement
    from lxml import etree
    def populate(doc):
        p=doc.add_paragraph('Ordinary visible text')
        run=OxmlElement('w:r');text=OxmlElement('w:t');text.text='hidden-by-library@example.com';run.append(text)
        if kind=='tracked_insertion':
            wrapper=OxmlElement('w:ins');wrapper.append(run);p._p.append(wrapper)
        else:
            paragraph=OxmlElement('w:p');paragraph.append(run)
            if kind=='content_control':
                wrapper=OxmlElement('w:sdt');content=OxmlElement('w:sdtContent');content.append(paragraph);wrapper.append(content)
            else:
                wrapper=etree.Element('{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent');wrapper.append(paragraph)
            doc._element.body.insert(1,wrapper)
    with pytest.raises(DomainError) as error: DocxParser().parse(BytesIO(docx_bytes(populate)))
    assert error.value.code=='DOCUMENT_COMPLEX_LAYOUT'

def test_docx_hyperlink_text_is_preserved():
    from app.ingestion.parsers import DocxParser
    from docx.oxml import OxmlElement
    def populate(doc):
        p=doc.add_paragraph('Email: ')
        link=OxmlElement('w:hyperlink');run=OxmlElement('w:r');text=OxmlElement('w:t');text.text='alice@example.com'
        run.append(text);link.append(run);p._p.append(link)
    result=DocxParser().parse(BytesIO(docx_bytes(populate)))
    assert result.pages[0].paragraphs[0].text=='Email: alice@example.com'

@pytest.mark.parametrize('size_limit',[False,True])
def test_short_read_stream_is_fully_consumed_or_size_limited(size_limit):
    from app.ingestion.parsers import PdfParser
    from app.ingestion.document_types import ParserLimits
    class ShortStream(BytesIO):
        def read(self,size=-1): return super().read(min(size,17))
    stream=ShortStream(pdf_bytes(['Complete text']))
    if size_limit:
        with pytest.raises(DomainError) as error: PdfParser(ParserLimits(max_file_bytes=32)).parse(stream)
        assert error.value.code=='FILE_SIZE_LIMIT'
    else:
        assert PdfParser().parse(stream).pages[0].paragraphs[0].text=='Complete text'
