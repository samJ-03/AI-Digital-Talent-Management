# 当前开发记录与断点续接

2026-11-10一期核心精简修订。唯一当前施工计划：[09](specs/09-详细开发todolist.md)；历史检查点见[归档](plans/archive/2026-11-10-handoff-history.md)。不从聊天记忆或旧“下一步T12/T15”重建进度。

## 当前状态

- 已验证T01～T12、T13a文本PDF/DOCX与字段提取、T14～T19、T21；T20语义后端已验证但一期保留可选。T13b OCR/旧DOC未完成，二期再做。
- 下一业务任务T22邀请资格，随后T23投递、T24/T25核验考试、T26/T27复核/HR决定。查询/最小页面按T28a/b/c与T29a/b/c跟随，不等待全部后端后才接页面。
- 本轮修正已完成代码中的单节点图包装、公开跨模块边界和API041 dimensions字段；一期任务/文档、OpenAPI/manifest与类型生成前置。最终验证与提交：完整448项通过（400.43秒），独立审查3项实际执行问题已修复；业务提交d49c37b，见artifacts/phase1-core-simplification-verification.md。
- 当前数据库40表479字段，迁移0008；本轮不改库、不删表/数据。现行实际注册61个历史基线接口，manifest区分一期待做与二期延期；注册不等于完整业务验收。
- 邀请/考试/复核主线和最小业务页面尚未完成，G1未通过。模型workflow仍由管理员明确开启；不因能力已验证就自动付费调用。

## 一期/二期边界

一期：岗位/发布卷→文本简历导入/建档/去重→三态硬筛/共享画像/证据匹配→唯一邀考→核验/答题/交卷→正式评分复核→HR决定，包含必要权限、恢复与质量门。

二期：知识、AI出题、看板、高级待办、培训框架、部门负责人协作、复杂OCR/旧DOC、高级语义界面/rerank、完整管理增强与生产部署。已实现后端与预建表不删除，也不据其存在伪称二期业务完成。

## 接手必读与实际路径

代码根：D:/Obsidian仓库/Obsidian/项目/AI数字化人才平台项目/code/ai-talent。
项目文档：上两级AI数字化人才平台项目；当前任务源在开发计划-2026-11-05，仓库docs/specs/09同步副本仅链接前缀不同。

先读AGENTS→本文件→09当前任务→对应领域实施契约/测试与实际代码。检查git status，保留用户未提交修改；Create只能用于不存在文件，已有recruitment/router、IdentityQueries、RuntimeAdminQueries、CI必须Modify/Reuse。

后台协议：短handler(uow,job)；长任务prepare(lease)在锁外I/O→JobRunner有效租约内finalize。模型/SMTP不能持业务锁；callback不得commit或另开Session。事件owner与唯一键见09，不在T30另建resume_pipeline。

跨领域公开方法：EvaluationService.resource_scope/is_current、CandidateService.resume_view；它们不自行给调用者授权。权限/来源/模型实际验证状态都必须在最终事务复验。current评估在受理时切换，新run pending不得借旧分数邀请。

## 本机验证与运行

宿主CMD可用，PowerShell曾受CET影响。Compose始终用python scripts/compose.py（显式加载本项目.env），不直接调用漏环境的-f命令。宿主Python C:/Users/Windows/anaconda3/envs/wolin/python.exe；项目工具.venv/Scripts/python.exe。Celery Linux容器，不测试原生Windows Worker。

- 核心启动：Compose默认不启动Milvus/etcd；保留原有项目服务和数据，不重置宿主或其他项目。
- 完整后端回归含保留T20：先显式--profile test --profile semantic up -d --wait mysql-test milvus；仅talent_test允许破坏性迁移。
- OpenAPI导出→manifest检查→frontend generate:api；G1另用--require-complete，当前一期待做接口必须如实列出。中文路径使用generate_api_types.mjs从JSON内容生成，不能改回有路径编码问题的CLI输入方式。
- 前端改动运行相应lint/typecheck/build；文档用链接/状态/文件增量/接口一致性校验，不给纯说明写镜像单测。
- 依赖/模型请求太久无响应要检查进程与日志并报告；不用无限等待或重复付费探测。测试输出写本地artifacts/.execution，不提交真实资料。

## 凭据、授权与证据

现有.env和.execution/local-accounts.json仅本机私有；不打印、提交或用旧stage覆盖。用户已确认DeepSeek官方与百炼北京连接及凭据来源，见MODEL_AND_DATABASE_DECISION，不再询问已解决Key/endpoint。保留原Fernet主密钥；不扫描其他项目env。

用户授权开发、隔离验证、代码提交上传既有GitHub samJ-03/AI-Digital-Talent-Management；没有授权生产部署或真实候选人邮件。普通回归使用受控合成模型/SMTP，不重复付费真实性探针。真实G1须另留实际模型/测试邮箱证据；Mailpit不代表企业外送达。

以当前Git及实际验证为准。本地执行流水.execution/progress.md与本轮验收报告保存断点；历史438通过属于T20/T21当时证据，不作为本轮重新验证结论。
