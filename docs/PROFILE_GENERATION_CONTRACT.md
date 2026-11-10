# T17 共享人才画像与部门授权视图

基线：FR-06、API043/044与开发计划T17。画像不是性格、忠诚度或稳定性预测。

## 来源与模型

ProfileBuilder只接收ResumeVersionView，输入为经T13/T15验证的结构化叶子事实；排除邮箱、电话和出生日期，不查询岗位、考试或面试。每条claim必须等于授权简历字段的完整原文事实，引用类型resume_version、ID和字段定位均须匹配；不接受截断否定、虚构新结论或跨人才来源。约束在网关校验阶段执行，错误结果AiRun为invalid而不是succeeded。摘要合计UTF-8字节最多65535（既有MySQL TEXT容量），AI及人工修订共用同一前置校验，超限不进入成功AiRun或插入重试。摘要是完整事实的确定性拼接，技能/经历也逐条留来源。

模型profile工作流输出schema为profile_schemas.ProfileOutput.model_json_schema()，管理员须发布匹配schema并显式启用；本轮没有自动发布/开启真实工作流或重复付费探测。最多100项事实/250KiB，超预算明确拒绝，不伪装全文成功。

## 服务及版本

ProfileService.generate是内部入口，不附加HR私有视图；相同当前简历已有可核查画像时直接复用。prepare在短事务外调用模型，finalize复验canonical根、ready/有效邮箱/全部别名待审线索、当前简历与画像指针、事实快照和配置修订。迟到结果不覆盖新资料；任务租约失效不落库。所有画像只追加版本，当前指针与审计同事务更新。

人工ProfileRevision：{base_profile_id,changes,reason}，changes只允许summary_claims、skills、experiences这三个字符串列表，内容必须等于当前简历完整事实；例如{"summary_claims":["Python"]}。新增或自由改写事实须先通过T15简历修订，避免把面试意见填进共享画像。新版本保留confirmed_by，AI原版/AiRun不覆盖；理由与previous_version记录到审计。

## API与权限

- GET /api/v1/talents/{id}/profile?version_id=画像ID：当前或历史版本；profile.read和talent.read；跨身份版本404。
- POST /api/v1/talents/{id}/profile-revisions：profile.write/read及talent.read、CSRF、Idempotency-Key；base不是当前版本409。
- 响应no-store。共享持久化字段与authorized_application_views分离。后者按canonical根/别名聚合后逐岗位复验当前权限；面试需recruitment.read，正式成绩需exam.read，元数据至少有evaluation.read/exam.read/recruitment.read之一。
- 成绩只取finalized考次当前ScoreReport且report归属一致，返回总分与报告ID/版本；不返回题目答案或逐题私有快照。当前没有正式能力维度模型，radar始终null，不把总分伪造成能力雷达。
- 任何部门私有附加视图均不得进入共享摘要/证据/后续向量。T20只能使用共享字段，不可序列化整个HR响应。

## 后台与恢复

注册profile.build固定处理器，模型I/O和最终租约事务分离。scheduler消费pipeline.resume；所有生产者通过共享active_profile_job按人才+简历引用复用活动任务，不依赖不同来源的幂等键。事件、同一当前简历的任务复用及sent状态同事务，待审/配置关闭延后30秒，不阻塞队列后续人选。归档/无简历/非法引用事件终止。旧HANDLER_NOT_REGISTERED或PROFILE_CONFIG_UNAVAILABLE任务按新profile配置修订恢复一次；新任务写profile_revision，相同配置失败不循环复活。真实模型输出失败不自动无限重试。

T15联系信息操作遇旧失败任务时追加去敏恢复事件，保留旧任务历史。消费者不调用模型、不发送邮件。首批调用/瞬时错误仍遵循既有三次任务重试预算。并发内部直接generate若都在结果落库前开始，可能各自完成一次模型调用，但只允许当前快照结果发布；产品入口通过单一活动任务和租约避免这种重复。

## 未完成边界

T18硬规则、T19岗位评估、T20真实向量索引和业务页面仍未完成；正式维度雷达未设计，不伪造。常规测试仅MockTransport+隔离数据库与合成资料，没有真实模型/外部邮件/生产部署。无新增表、字段、依赖或秘密变量。
