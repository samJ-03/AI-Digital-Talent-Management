# T12 岗位版本与自动邀请配置 Implementation Plan

> For agentic workers: execute the existing approved T12 task natively; use executing-plans conventions and one final independent review. 本文件仅跟踪原详细计划T12，不替换或重复制定业务计划。

**Goal:** 实现已确认FR-02岗位版本与显式自动邀请配置。
**Architecture:** 复用HrServiceBase/UoW、现有模型和Outbox；无新依赖或迁移。
**Tech Stack:** FastAPI/Pydantic/SQLAlchemy/MySQL、pytest；沿用当前锁文件。
**Spec:** specs/job-versions-automation/spec.md；原docs/specs/09的T12与05契约。

## Global Constraints

仅HR及正确部门范围；发布快照不可变；默认自动邀请false；POST幂等/修改CAS/审计同事务；秘密不回显；测试仅talent_test；不直接发真实邮件或重复付费模型探测。

## Review Focus

写后读权限失败不能留下已提交变更；跨岗位current指针不可绕过；配置停用不能绕过就绪门；并发发布/开启不得重复事件；暂停重开或新版本不恢复旧邀请。

## 1. Tests and implementation（对应T12.1～T12.3）

- [x] 1.1 建立岗位集成失败场景：默认draft/off、隔离、权重与条件、发布不可变、current归属、就绪缺项、CAS/幂等；记录RED命令与真实失败原因。
- [x] 1.2 实现schemas/views/service/readiness/router并注册七项API；运行test_job_versions，确认上述场景和事件唯一性GREEN；说明invite.scan生产/消费边界。

## 2. Integration and review（对应T12.4～T12.5）

- [x] 2.1 补并发/配置失效/回滚等实质回归，独立审阅T12改动并处理发现；定向测试通过。
- [x] 2.2 完整pytest通过，实际本地合成岗位状态与自动开关失败门验证；没有企业邮件或付费模型请求，保存artifacts/t12-verification.md。

## 3. Recovery and delivery（对应T12.5～T12.6）

- [x] 3.1 同步T12勾选、接口细化、README与续接记录，OpenSpec validate --strict通过；不混入原OpenSpec工具配置的未提交内容。
- [x] 3.2 仅提交T12及相应文档，上传GitHub并核对远端SHA；当前未完成消费者/后续T13等如实记录。

## Workflow follow-up

- 验收后可将本变更规格同步并归档；不把归档当作生产发布授权。
