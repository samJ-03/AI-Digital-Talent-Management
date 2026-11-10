# 人才建档与人工修订（T15）

对应已确认计划T15及API029/030/035。实现是后端能力；人才列表、去重审核、画像生成和招聘页面仍由后续任务完成。

## 业务行为

- HR导入的文本PDF/DOCX经过原文件哈希、完整解析、固定extract流程和证据校验后建档。成功AiRun必须属于同一stored_file，客户端不能提交模型结果或自报AiRun来建档。
- 没有邮箱仍创建人才及简历，状态pending_email，不安排画像、筛选或邀考。无姓名显示“待补充姓名”，结构化事实中的姓名仍为null。
- 邮箱只是本地格式验证，不查询DNS、不发送验证邮件，不代表控制权核验。规范化保留邮箱本地部分大小写、点号和加号。
- 邮箱、规范化电话、原文件哈希相同只产生疑似重复线索。两侧有效人才进入duplicate_review；已归档记录保持归档。不同姓名不影响该规则，同名本身不构成线索，绝不自动合并。
- ready且有当前简历时原子追加profile.build，键为`profile.build:{candidate_id}:{resume_version_id}`。重复补齐同一简历不会追加第二份任务。T17画像处理器尚未实现，任务被受理不表示画像已生成。
- 归档保留原简历和关系历史，禁止用补齐联系人或简历修订恢复自动处理。未来画像/评估处理器领取后必须复验人才状态和当前简历，不能依赖排队时的ready状态。

## HTTP

所有入口要求当前有效HR会话、CSRF、talent.write和talent.read；响应`Cache-Control: private, no-store`，版本通过ETag提供。

|接口|请求|并发与幂等|响应|
|---|---|---|---|
|PATCH /api/v1/talents/{id}/contacts|email?、phone?、reason|If-Match必填；省略保持，null清空|200 TalentView，邮箱遮罩|
|POST /api/v1/talents/{id}/resume-corrections|base_resume_version_id、changes、reason|Idempotency-Key必填；基准必须是当前简历|202 ResumeVersionView|
|POST /api/v1/talents/{id}/archive|reason|If-Match必填|200 TalentView|

修订示例：

```json
{"base_resume_version_id":12,"changes":{"identity.name":"张三","skills":["Python","SQL"]},"reason":"HR已核实"}
```

允许的changes键：identity.name、identity.birth_date、contacts.email、contacts.phone，以及整个education/employment/projects/skills/certificates列表。列表元素沿用ResumeFacts类型；不能写field_sources、citations、ai_run_id、状态或当前版本指针。

修改产生新ResumeVersion，parent_version_id指向原版本，复制原始文本及解析器修订，保留原版本数据。手工事实使用manual_correction来源、真实HR ID及字段路径，不能冒充原文模型证据。当前画像指针清空，ready时请求重建。当前联系人只有在修订明确包含对应contacts路径时才替换。

## 代码分层与事务

- `talents/router.py`：HTTP、会话、CSRF、ETag及禁缓存。
- `talents/schemas.py`：输入白名单、视图和内部建档结果。
- `talents/candidate_service.py`：授权复验、状态门槛、去重线索、简历修订及事务编排。
- `talents/identity_resolver.py`：主身份链及历史别名解析，损坏引用或环明确失败。
- `ingestion/worker.py`：下载/解析/提取prepare，最终数据库写入finalize。
- 现有SQLAlchemy models负责表映射，继续使用既有40表，无新增迁移。

建档和人工身份写入持有数据库隔离的MySQL命名锁，单独连接并在所有退出路径显式释放；锁内只做短数据库操作。Worker的可选`finalization_context()`包围整个run_atomic及commit，不能在回调返回时提前释放。任务锁序为BackgroundJob→batch→item；其他调用不反向等待该解析任务。

Worker执行文件/模型I/O期间不持有业务行锁，准备和最终提交都复验持久化导入归属、当前HR权限、文件状态和来源。失效租约拒绝所有写入。条目、人才、简历、招聘关系、后继任务及审计同事务，回调不得commit。

永久解析/配置错误使用固定安全说明，写入ImportItem并结束任务；网络/供应商限流由已有任务最大3次重试处理。导入详情优先展示已知条目原因，不暴露异常消息、对象路径、原文或模型响应。暂不自动缓存重用AiRun，数据库完成前发生失败重试可能再次调用模型。

## 明确边界

图片、扫描件、旧DOC及复杂布局仍提示需要后续适配器或人工处理；未接入MinerU/OCR。未自动发布提示词、修改模型或发送招聘邮件。真实模型质量与招聘核心闭环验收不能由受控HTTP集成测试代替。
