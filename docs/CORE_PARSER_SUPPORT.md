# T13核心文档解析支持范围

日期：2026-11-08。此为原T13的文本格式子任务，不代表全T13完成，也不代表简历导入/AI字段提取或招聘流程已可用。

## 当前接口

- ParserRegistry.select(FileView) → ResumeParser；按扩展名与已验证MIME双重检查。
- PdfParser.parse(BinaryIO) / DocxParser.parse(BinaryIO) → ParsedDocument。
- ParsedDocument包含pages、paragraph id/text、parser_revision和pagination；不包含猜测的姓名/邮箱/学历。
- 默认20MiB原文件、100页PDF、120000字符、2000段、单段20000字符、100MiB DOCX展开上限和30秒解析超时。超限不截断为部分成功。

## 已支持与明确拒绝

| 内容 | 当前行为 |
|---|---|
| 文本PDF | 保留物理页与行定位，例如pdf:p2:l1 |
| 无文本或混合扫描PDF页 | 整份返回DOCUMENT_NEEDS_OCR，不静默漏页 |
| 普通文字DOCX | 保留正文段落、表格及嵌套表格、合并单元格去重、页眉页脚及超链接显示文字 |
| DOCX分页 | 一个logical容器，以逻辑块路径定位，不声称真实Word页数；物理分页上限待渲染适配器 |
| 图片/文本框/含可见文字的内容控件或修订包装/其他未支持的Word文字包装 | DOCUMENT_COMPLEX_LAYOUT；包括含头像图片的Word文档，暂不尝试判断图片是否有简历信息 |
| 图片、旧DOC | 注册表返回DOCUMENT_FORMAT_UNAVAILABLE；OCR/转换后续实现 |
| 损坏、加密、展开过大、超时 | 安全的固定错误消息，不返回原始文档或库堆栈 |

PDF的无文本页检测不等于OCR准确性判断；同页嵌入图像中的文字尚未识别。不得把当前文本解析当成全部视觉内容的完整还原。

## 执行边界

原文件授权由调用方完成，解析器本身没有业务API。实际字节流循环读取，支持短read并核对总大小。父进程仅将固定格式、服务端资源预算和文件字节交给固定子进程；数据库URL、模型Key等应用环境不传入。子进程无网络调用代码、不加载应用配置，Linux设置512MiB地址空间和CPU上限，父进程超时终止回收；全程无临时文件。

该子进程提供可用性保护，不是独立容器或完整恶意文件安全沙箱。将来T14仍需任务恢复/失败隔离。原T13的OCR权重、LibreOffice版本和转换超时验收尚未完成。

## 验证及剩余工作

32项定向测试通过（23.03秒）：真实PDF内容流和DOCX包，覆盖加密/损坏/扫描页、来源稳定、中文表格/页眉、超链接、合并单元格、包装文字明确失败、短read/大小限制、超时和子进程凭据环境。独立审阅发现并已修复的内容控件/修订文字漏读问题有真实OOXML回归。

下一步：按现有受控模型网关实现ResumeExtractor及字段证据校验，缺失邮箱保持unknown；随后T14导入任务、T15建档。OCR、旧DOC和全格式真实样本验收完成前，原T13保持未完成。没有企业邮件或付费模型调用。

依赖沿用锁文件pypdf6.21.4、python-docx1.2.0，无新包。实现依据：[pypdf文本提取说明](https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md)、[python-docx文档与顺序遍历](https://python-docx.readthedocs.io/en/latest/_modules/docx/document.html)。本地详细证据位于ignored artifacts/t13-core-*。

完整回归：241 passed in175.27s（2026-11-08），日志artifacts/t13-core-final-suite.log；严格规格验证通过。前端未修改，不重复构建；解析测试使用真实合成文件，生产导入任务仍未接入。
