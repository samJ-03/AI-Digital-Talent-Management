# Design

## Context

动机见proposal.md。T12来自已确认docs/specs/09及05，用户已明确继续开发。复用Job/JobVersion、HrServiceBase、IdempotencyService、PaperVersion、ModelConfig/WorkflowConfig/PromptVersion、MailConfig及OutboxEvent。无数据库迁移、新依赖或外部模型/SMTP调用。

## Goals / Non-Goals

**Goals:** 实现七项API、内部get/get_version与readiness；所有POST幂等、PATCH/状态/开关CAS；响应读权限在写前复验；持久事件生产。

**Non-Goals:** T22过滤/建考次与T23发送处理器、部门负责人/面试双确认、破格策略JSON扩展、OCR或前端。不把仅生产事件称已完成自动邀考链路。

## Decisions

1. schemas.py定义JobCreate/Patch、JobVersionDraft/View、JobView、AutomationView。views.py构造允许字段；readiness.py聚合只读依赖检查；service.py控制领域事务；router.py注册七项契约，main.py装配。不把管理模型服务当HR服务调用，避免HR获得管理员权限。
2. 条件当前白名单education/major/relevant_years/skill/certificate；教育采用high_school/secondary/associate/bachelor/master/doctor，支持eq/gte/in；专业eq/in；年限gte/lte/between（0～100），技能/证书contains_any/contains_all；唯一key、非空字符串列表。年龄未启用自动条件，原契约的人工核实方向留T18。权重以Decimal校验总和100，序列化为JSON数值。
3. 必填模板subject/body仅普通文本；允许candidate_name/job_title/exam_url/valid_until占位，不允许属性/索引、转换、格式指令或脚本模板。draft可无paper，发布时已引用的paper须published；自动开关则必须有paper。
4. 新草稿序号锁Job串行分配，使用锁定的最新版本号当前读，不能使用授权快照下的普通MAX读取；发布锁当前Job与版本。新发布切换current并关闭自动邀请；已发布旧版本不能再次切回current。所有current读取校验job_id，PATCH不接受current_version_id。
5. 启用与发布采用workflow→mail→model→prompt→job→paper锁顺序，固定配置检查期间不做网络I/O。LockedDependencies持有锁定实体的强引用，populate_existing刷新缓存，邮件激活状态在锁定行中筛选，避免REPEATABLE READ授权快照与ORM弱引用回收造成停用配置误通过。就绪检查四项流水线任务，主观卷加grade；排除不必要的question_generation/knowledge_ask。云端检查有效密文和本地加密配置，Ollama要求真实digest；邮件按MailPolicy验证当前active修订。返回安全原因代码，不展示密钥/内部地址。
6. false→true只追加Outbox invite.scan，event_key包含岗位ID与本次CAS修订，payload仅job_id/job_version_id/automation_revision。现有dispatcher只消费job.dispatch，T12不把扫描事件误投成未知任务；T22必须以事件引用及当前状态二次校验，执行完整过滤后建考次。
7. API021接受契约reopen_reason并兼容reason；归一化后交给transition(reason)。再次请求相同状态为无副作用结果；真实状态转换及新版本发布均关闭自动邀请，不恢复旧记录。

## Risks / Trade-offs

- 配置并发停用 → 在启用事务锁定依赖；后续发送仍必须二次校验，T12不作永久就绪承诺。
- 只有写权限但响应需读 → HrServiceBase response_permission在写前和事务内复验。
- 事件消费者未到阶段 → 事件持久化可恢复，验收明确本阶段不发信；T22/T23才称链路完成。
- 既有OpenSpec未提交内容 → 限定文件同步和提交；不使用旧大范围stage覆盖。

## Migration Plan

无表变化。新路由依赖已应用0001～0006；本地仅talent_test运行破坏性验证。部署仅本地重载服务，未获生产发布授权。回滚代码不删除已发布岗位和Outbox记录；自动邀请默认关闭。
