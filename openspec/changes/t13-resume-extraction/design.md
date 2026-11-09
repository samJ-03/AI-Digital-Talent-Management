# Design

## Context
引用原T13和MODEL_GATEWAY_CONTRACT。用户已授权按核心优先继续。

## Decisions
extraction_types.py定义严格白名单事实和来源，未知用null/空列表；日期和学历保留原文，不在提取阶段推算年龄/年限或规范化为评分。field_sources按叶路径引用完整Evidence；所有字段引用必须在根citations中，且非空值是原文子串，随后网关核验citations来自输入。该业务校验发生在AiRun成功持久化之前。

ResumeExtractor构造时接收网关及调用方已授权的stored_file ID，extract(document,AiConfigSnapshot)为原接口；输入来源固定stored_file，locator用真实paragraph.id。每段作为独立证据，超100段或256KiB拒绝，不静默截断。使用FixedGraphRunner注册extract输出类型；已发布提示词schema必须与类型schema一致，由已有网关复验，不自动改用户模型配置/提示词。

## Boundaries
仅内部能力；不宣称T14授权导入贯通或真实模型质量验收。无需真实模型调用、外部邮件、依赖或表变更。保留已有未提交文档/配置改动。
