# T13 Resume Extraction Implementation Plan

**Goal:** 将ParsedDocument转为有原文证据的ExtractedResume。
**Architecture:** 严格类型、字段证据、固定图与已有网关；无新依赖/表/API。
**Tech Stack:** 当前Python/Pydantic/LangGraph/pytest。
**Spec:** 本变更spec及原09的T13。

## Global Constraints
合成资料，不调用真实付费模型，不改已有秘密配置；全T13仍待OCR/DOC等。

## Review Focus
伪造字段/引用、缺失邮箱、越界字段、超段数、错误来源和网关校验前后持久化边界。

## Tasks
- [x] 1. 建立未知邮箱及伪造事实等真实失败测试。
- [x] 2. 实现extraction_types.py和extraction.py，定向验证。
- [x] 3. 审阅、完整回归，更新续接与证据。
- [ ] 4. 独立提交上传并核对结果，不混入架构文档或配置改动。
