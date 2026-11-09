# Proposal

## Why
继续已确认T13及核心招聘闭环：解析文档已有，尚缺带字段证据的受控AI提取。

## What Changes
实现ResumeExtractor.extract(document,config)、固定事实契约及字段来源校验；复用模型网关和固定图，无新表、依赖或公开API。邮箱未知保持null。调用方必须先授权持久文件来源。

## Capabilities
### New Capabilities
- resume-extraction：带可验证原文来源的简历事实提取。
### Modified Capabilities
无。

## Impact
新增ingestion/extraction.py及类型、定向测试。OCR、旧DOC、T14批量导入与T15建档不在本增量，原T13不整体勾选。
