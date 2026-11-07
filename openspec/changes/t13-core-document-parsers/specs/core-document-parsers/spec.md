## ADDED Requirements

### Requirement: Traceable core format parsing
系统 SHALL 对受支持文本PDF和DOCX输出pages、paragraph id/text及parser_revision；PDF标为物理页，DOCX以逻辑文档定位，不冒充渲染页码。正文和表格保持顺序，DOCX页眉页脚文本纳入来源。

#### Scenario: Text and table document
- **WHEN** HR导入合法文本PDF或带中文正文/表格的DOCX
- **THEN** 输出可重复定位的原文片段，不编造结构化人才字段

### Requirement: Explicit unsupported content
系统 MUST 对扫描/混合PDF、图片、DOC和未支持的嵌入布局给出可判别失败；不静默漏掉需OCR的页，不返回假空简历成功。

#### Scenario: Image page in PDF
- **WHEN** 任一PDF页没有可提取文本
- **THEN** 返回DOCUMENT_NEEDS_OCR，不返回已解析的其他页作为完整结果

### Requirement: Bounded isolated parsing
系统 SHALL 限制输入大小、PDF页数、文档文本/段落数量和DOCX展开大小；在独立进程执行并设置超时。Linux工作进程设置地址空间与CPU上限，凭据环境不得传入子进程；超限/损坏/加密失败均不包含原始内容。

#### Scenario: Parser timeout
- **WHEN** 子进程超过配置期限
- **THEN** 子进程被终止并返回DOCUMENT_PARSE_TIMEOUT，无临时文件残留

### Requirement: Honest partial T13 progress
系统 MUST 保持原T13未完成，直到OCR、旧DOC转换、受控AI字段提取和全格式证据按原验收完成。本增量不改变原T13全格式的完成定义。

#### Scenario: Subtask delivered
- **WHEN** 文本PDF与DOCX子任务通过测试
- **THEN** 只关闭本增量清单，并在续接记录明确剩余原T13工作
