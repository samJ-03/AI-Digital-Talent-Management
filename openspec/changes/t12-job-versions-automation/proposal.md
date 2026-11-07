# Proposal

## Why

T01～T11已具备身份、试卷、模型和邮件基础，但尚无岗位版本与自动邀请开关的领域服务。用户已授权按原详细计划继续实施T12，本变更承接既有FR-02、API-015/016/018～022，不重新发起业务选型。

## What Changes

- 实现HR岗位草稿、元数据编辑、版本草稿/发布、状态转换和自动邀请就绪门。
- 复用现有40表，不增加迁移；发布版本不可原位改写，当前版本指针必须属于本岗位。
- false→true在同一事务追加带岗位/版本引用的invite.scan事件；T22/T23承接消费过滤及实际邀考，T12不发送邮件。
- 关键POST幂等、可变更新CAS、权限复验及审计同事务落地。
- 最近讨论的负责人登录、协作确认、破格规则细化与MinerU评测另作增量，不混入本任务。

## Capabilities

### New Capabilities
- job-versions-automation：岗位发布版本、生命周期及自动邀请配置和事件生产。

### Modified Capabilities
无；已有project-workflow仅约束开发过程，业务基线继续引用docs/specs/01、04、05、06及09的T12。

## Impact

新增backend/app/jobs/{schemas,views,readiness,service,router}.py及tests/integration/test_job_versions.py；main.py注册路由。无新包、无真实SMTP/模型调用、无生产部署。更新T12计划和验收记录，保留现有OpenSpec未提交配置。
