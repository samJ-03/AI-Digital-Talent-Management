# T13核心格式解析子任务 Implementation Plan

> For agentic workers: native implementation of the approved T13/core-first scope; final independent review follows verification. Does not complete all of T13.

**Goal:** 支持带来源的文本PDF/DOCX解析并显式失败，不消费模型额度。
**Architecture:** 固定注册表、不可变文档类型、有限资源子进程；无新依赖/表/API。
**Tech Stack:** 现有Python3.11、pypdf、python-docx、Pydantic、pytest。
**Spec:** 本变更specs/core-document-parsers/spec.md，原09的T13、docs/CORE_DELIVERY_PRIORITY.md。

## Global Constraints
只使用合成资料；不读取秘密；不将OCR或全T13勾选完成。

## Review Focus
混合PDF漏页、DOCX表格/页眉漏文本、zip展开上限、输入描述符与真实大小不符、子进程凭据环境/超时回收。

## Tasks
- [x] 1. 建立真实PDF/DOCX和失败场景测试，记录功能未实现的有效RED。
- [x] 2. 实现document_types.py、parsers.py、parse_worker.py，定向验证全部通过。
- [x] 3. 独立审阅并修复，运行完整回归，保存实际证据。
- [x] 4. 更新原计划中的部分进度/续接和支持范围，保留全T13未完成；提交并上传，核对远端版本。
