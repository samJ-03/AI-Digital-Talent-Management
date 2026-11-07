# Proposal

## Why
用户已确认优先T30核心招聘闭环。T12已验收上传，T13尚无解析实现。先交付文本PDF与DOCX解析适配器，后续字段提取和全格式支持仍按T13继续，避免引入未评测的OCR服务拖住文本简历链路。

## What Changes
- 实现ParsedDocument、ParserRegistry和PDF/DOCX适配器，保留稳定来源定位。
- 解析在有超时/资源限制的独立进程中执行，失败不给半份假成功结果。
- 扫描/混合PDF、图片、DOC和不支持的复杂DOCX明确拒绝并提示后续解析/人工补录。
- 不实施AI字段提取、导入API、OCR/MinerU、旧DOC转换或前端；原T13保持未完成，只有本子任务可关闭。

## Capabilities
### New Capabilities
- core-document-parsers：核心简历格式的受限解析与来源定位。
### Modified Capabilities
无；引用原docs/specs/09的T13、T07文件校验和docs/CORE_DELIVERY_PRIORITY.md。

## Impact
新增ingestion文档类型、parsers/parse_worker及真实格式测试。只用已锁定pypdf/python-docx，无表变更、新依赖或模型调用。
