# Design

## Context
复用T07的FileView/真实类型校验与已锁定pypdf/python-docx。按已确认核心优先级先做T13内部能力，不重开技术栈或付费模型选型。

## Decisions
- document_types.py定义不可变Pydantic类型Paragraph、DocumentPage、ParsedDocument与ParserLimits；parsers.py定义ResumeParser Protocol、ParserRegistry、PdfParser、DocxParser及隔离执行边界；parse_worker.py仅执行本模块固定格式。
- ParserRegistry.select(FileView)->ResumeParser按受支持扩展名和已验证MIME双重匹配，拒绝不支持类型，描述符大小超限提前拒绝。parse(BinaryIO)->ParsedDocument再次限制实际输入，防止描述符失真。
- 父进程仅传入格式、非秘密限制参数和原始字节，不传递API Key/数据库URL等环境。子进程Linux设置RLIMIT_AS/CPU；父进程timeout终止。无临时文件、无网络或模型能力。
- PDF用pypdf读取物理页；拒绝加密、损坏、超页数和任一无文本页；文本按非空行形成稳定pN:lM定位。混合扫描不能当部分成功。
- DOCX在解压大小检查后使用Document.iter_inner_content递归遍历段落/表格，合并单元格去重。页眉页脚同样遍历，并去重共享part。DOCX输出一个明确logical页，locator为docx:body或header/footer的段落路径，不伪造实际Word分页。检测文本框/嵌入对象/脚注等未支持内容时明确失败，后续高级适配器处理。
- 文本仅规范化换行及去除首尾空白，不做AI改写；控制空文档、总字符、单段长度和段数，避免截断丢失信息。parser_revision包括实现修订及库版本，来源可重现。

## Alternatives
在API进程直接解析较省代码但难以终止失控PDF；独立进程更适合已有后台任务架构。引入MinerU/OCR现在需要模型/资源验收，按用户确认后补，不宣称已有。

## Boundaries
本阶段无公开API、AI字段提取、OCR及DOC转换；T14调用前须完成原文件授权。Linux资源上限用于可用性保护，不将普通子进程宣称为完整恶意文件安全沙箱。DOCX物理页数上限仍待后续渲染适配器，全T13继续未完成。
