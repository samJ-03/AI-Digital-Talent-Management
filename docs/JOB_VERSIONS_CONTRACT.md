# T12 岗位版本与自动邀请配置契约

实施日期：2026-11-07。承接docs/specs/05的API015、016、018～022。复用现有Job/JobVersion/Outbox表，无迁移、无新依赖；操作主体是HR，管理员无招聘写权限。

## API与并发约定

| 方法及路径（均以/api/v1开头） | 输入 | 额外请求头 |
|---|---|---|
| POST /jobs | title、department_id、headcount | Idempotency-Key |
| PATCH /jobs/{id} | title?、headcount?、owner_hr_id?，至少一个非null字段 | If-Match |
| POST /jobs/{id}/versions | 完整JobVersionDraft | Idempotency-Key |
| PATCH /job-versions/{id} | 完整JobVersionDraft，仅draft可改 | If-Match |
| POST /job-versions/{id}/publish | reason | Idempotency-Key |
| POST /jobs/{id}/state | action=open/pause/close、reopen_reason；兼容reason别名，两者不同时提交 | If-Match、Idempotency-Key |
| PUT /jobs/{id}/automation | enabled，严格布尔 | If-Match |

响应沿用ApiEnvelope；ID是字符串。响应ETag对应Job或JobVersion的row_version，AutomationView对应其中job.version。If-Match接受现有认证层的版本格式。写前与事务中复验job.write及job.read；当前账户、岗位部门范围均由服务端解析，跨部门资源隐藏为404。开启额外需要exam.invite与paper.read；绑定试卷还检查真实试卷范围及同部门，不因企业可读而允许跨部门绑定。

## 草稿与发布

JobVersionDraft包含description、conditions、match_weights、invite_threshold、paper_version_id?、invite_valid_hours、mail_template。权重skills/experience/responsibilities精确合计100。阈值0～100，响应为两位小数字符串；有效小时为1～8760整数。元数据修改不能注入status、department_id、current_version_id或auto_invite_enabled。

条件键唯一；education使用high_school/secondary/associate/bachelor/master/doctor，支持eq/gte/in；major支持eq/in；relevant_years支持gte/lte/between（0～100，拒绝布尔）；skill/certificate支持contains_any/contains_all。未开放的字段和运算符拒绝422；年龄自动规则未实现，留T18人工核实。后续“非豁免/可豁免/偏好”细化须单独增量设计，不能将当前required布尔冒充完整破格策略。

邮件仅普通文本subject/body，允许candidate_name/job_title/exam_url/valid_until占位；拒绝对象属性、索引、格式/转换和subject换行。草稿可不绑定试卷；若绑定，发布时须有效且published。自动邀请必须有有效试卷。

发布版不可编辑；发布新版本切换本岗位current并关闭自动邀请。已发布旧版本不能重新切回current。开放前校验current属于本岗位且published；暂停、关闭、重开均不会恢复开关或修改历史考试。相同状态请求是无副作用结果。

## 开启资格与原子性

必须满足：岗位open、当前版本属于本岗位且published、同部门active试卷的published版本、非空题项及总分一致、唯一active且符合MailPolicy的邮件配置，以及有效的extract/profile/match/embedding流程；包含short_answer时还需要grade。模型须启用、已验证能力、合规地址、可解密凭据或本地模型digest，提示词需已发布且任务一致。检查不发起网络探测。

失败409 AUTOMATION_NOT_READY，data.blocking_reasons只返回JOB_NOT_OPEN、JOB_VERSION_NOT_PUBLISHED、CURRENT_VERSION_MISMATCH、PAPER_NOT_PUBLISHED、MODEL_UNAVAILABLE、MAIL_NOT_VERIFIED等安全代码，不返回密钥或连接信息。

开启事务按workflow→mail→model→prompt→job→paper锁定。LockedDependencies持有当前读实体，避免ORM弱引用回收和MySQL REPEATABLE READ旧快照导致失效配置误通过。岗位锁保护版本分配，最新版本号也使用当前锁定读。

只有false→true追加invite.scan，开关、事件和审计同事务。event_key包含job_id和automation_revision；payload_refs只有job_id、job_version_id、automation_revision。CAS冲突不能生成第二个事件；中途审计失败则全部回滚。关闭不要求模型/邮件保持就绪。

## 下游边界

本阶段生产扫描事件，不建立考次、不调用SMTP。现有OutboxDispatcher只消费job.dispatch，因此invite.scan保持pending供T22承接。T22/T23须复验当前资格，仅处理尚未有考次的首次auto_allowed评估，不复活manual_only、revoked或历史已邀考记录；暂停或配置停用不能靠旧事件继续发信。此部分是后续义务，不是T12已完成能力。

内部get/get_version用于写后视图；公开列表和读取接口按T28补齐。业务前端尚未完成。
