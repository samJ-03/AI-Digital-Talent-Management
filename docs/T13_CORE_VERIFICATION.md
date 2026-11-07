# T13核心文本格式子任务验收（2026-11-08）

范围：ParserRegistry、ResumeParser Protocol、PdfParser、DocxParser、ParsedDocument、受限parse_worker。无新依赖、数据库变更、公开业务API、模型/SMTP调用。全T13未完成。

- 真实RED：artifacts/t13-core-red.log的test_text_pdf_retains_pages_and_stable_sources使用真实PDF内容流，尚未实现的入口抛DOCUMENT_FORMAT_UNAVAILABLE而未能返回原文。初轮其他场景还包含未建立类型/注册表引起的ImportError，不将这些导入缺失描述为已测到解析算法故障。
- 定向：32 passed in23.03s，artifacts/t13-core-expanded-green.log。涵盖PDF物理页/稳定定位、混合扫描拒绝、加密/损坏、文件/页数/文本/展开限制、中文DOCX正文/表格/页眉/页脚、合并单元格、超链接、未支持文字包装拒绝、短read完整消费、超时、进程失败及凭据环境不传入。
- 独立审阅：发现DOCX内容控件/修订包装可能被python-docx跳过；已增加全部可见w:t节点的支持祖先路径检查，真实OOXML回归覆盖sdt/ins/AlternateContent。复核无剩余阻塞问题。
- 完整回归：241 passed in175.27s，artifacts/t13-core-final-suite.log；仅talent_test做数据库破坏性测试，解析用合成内存文件；前端未改，不重复前端构建。
- 规格严格验证通过。依赖沿用pypdf6.21.4/python-docx1.2.0，parser_revision保留实际运行版本。
- 尚未验收：生产导入/私有文件贯通、ResumeExtractor与字段证据校验、OCR/旧DOC转换、Word物理分页/全格式验收。当前支持范围见docs/CORE_PARSER_SUPPORT.md。不能宣称完整简历导入或招聘闭环已跑通。

命令（代码根目录）：

~~~text
.venv\Scripts\python.exe scripts/compose.py run --rm -T --no-deps -v "%CD%:/work:ro" -w /work api python -m pytest -q -p no:cacheprovider backend/tests/integration/test_core_document_parsers.py backend/tests/unit/test_core_parser_selection.py
.venv\Scripts\python.exe scripts/compose.py run --rm -T --no-deps -v "%CD%:/work:ro" -w /work api python -m pytest -q -p no:cacheprovider
openspec validate t13-core-document-parsers --strict --json --no-interactive
~~~
