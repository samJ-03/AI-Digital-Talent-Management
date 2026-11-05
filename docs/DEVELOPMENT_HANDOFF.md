# 开发记录与断点续接

更新：2026-11-05；状态：继续开发；T06 已验证，下一任务 T07。

## 1. 从这里继续

项目目录：D:/Obsidian仓库/Obsidian/项目/AI数字化人才平台项目
代码仓库：上述目录/code/ai-talent
分支：feat/recruitment-v1
详细计划：开发计划-2026-11-05/AI数字化人才平台-详细开发todolist.md
已确认规格：评审稿-2026-11-04/00～07 共八份文档。
原始资料与 HTML：D:/AI数字化人才平台-相关文档；历史快照，只作对照，不直接当成最终需求。

接手者先读代码根目录 AGENTS.md，再读本文件、详细计划、.execution/progress.md。以实际文件、Git 和测试结果为准，不从聊天记忆猜测完成度。检查未提交 diff 后再修改，不能重置或覆盖未提交工作。

## 2. 当前进度与证据

|任务|状态|本地提交/证据|
|---|---|---|
|T01 环境与依赖冻结|完成|8d035b0；运行时、锁文件、Windows/Linux 预检|
|T02 最小应用与独立服务|完成|b30fd4f；前端 lint/typecheck/build，5项基础设施实测|
|T03 40表与迁移|完成|1df51c0；478列、迁移往返、乐观锁、开发库无漂移|
|T04 权限/审计/幂等|完成|0ca1833；当时完整测试55通过|
|T05 后台账号管理|完成|f8aee3a；当前最近完整测试74通过|
|T06 持久任务与恢复|完成|完整测试93通过；真实 DB/Redis/Celery 交付与单调度器租约验证通过|
|T07～T43|未完成|按详细计划和依赖推进；生产发布需单独授权|

最新完整测试：artifacts/t06-final-suite.log，93 passed。
真实队列：artifacts/t06-live-queue.json，queued/pending→succeeded/sent。
不要声称招聘业务已跑通；当前完成的是基础设施、账号和任务框架。
证据报告：artifacts/t01-*～t05-*；执行流水：.execution/progress.md；任务摘录：.execution/T04-brief.md、T05-brief.md、T06-brief.md。
artifacts 和 .execution 被 Git 忽略，但已经保存在本机项目目录。未推送远端；本机磁盘损坏不在这些本地记录的保障范围内。

## 3. 当前工作与下一步

T06 已完成，详细变更与结果见 artifacts/t06-verification.md。先检查实际 git status/log，保护任何新出现的未提交修改。

继续 T07：私有文件、上传格式/大小/页数校验、MinIO 真实读写、按领域关联授权下载、过期孤儿清理。先读详细计划 T07 与数据库/接口文档；写失败测试，再实现并验证。之后依赖顺序推进 T08 等；DeepSeek 官方 Key 或明确代理渠道仍待用户提供，不重复询问已找到的百炼北京地址。模型缺项只阻塞对应实际接入，不阻塞基础模块。

T06 约定：worker只有固定 handler 注册表，当前业务 handler 尚未实现；system.verify 仅技术诊断。外部慢 I/O 不能凭任务租约假定可任意提交业务结果，应在落库时验证任务租约/版本与领域幂等。API098 HR-only；管理员另用后续脱敏runtime，不能借task接口读私有业务结果。

## 4. 运行环境和命令

Windows；CMD 可用，PowerShell 曾因 CET 启动失败。工具调用用 CMD、login=false。
宿主 Python：C:/Users/Windows/anaconda3/envs/wolin/python.exe (3.11.17)。项目隔离 venv：代码目录/.venv。
Node24、Docker Desktop Linux 引擎。所有容器命名空间 ai-talent-dev，不动其他项目容器。
Compose 必须用 python scripts/compose.py（显式 --env-file），不要直接 docker compose -f infra/compose.yaml，后者曾漏载根 .env。

在代码根目录运行：
- .venv\Scripts\python.exe scripts\compose.py ps
- .venv\Scripts\python.exe scripts\compose.py exec -T api python -m pytest -q（仅后端测试）
- .venv\Scripts\python.exe scripts\compose.py run --rm -T --no-deps -v D:\Obsidian仓库\Obsidian\项目\AI数字化人才平台项目\code\ai-talent:/work:ro -w /work api python -m pytest -q -p no:cacheprovider（当前完整测试）
- .venv\Scripts\python.exe scripts\verify_identity_http.py（本地真实代理认证检查，不输出密码）

本地入口 http://localhost:13000；当前只有基础页面，招聘页面未实现。API http://localhost:18080/docs（开发态）。MySQL 开发库 talent_dev，隔离测试库 talent_test。测试仅允许 talent_test；不得对已有个人/企业库运行 downgrade、清库或灌种子。

## 5. 文件写入限制与安全同步

当前工具工作区可写 D:/AI数字化人才平台-相关文档；Obsidian 目录需要沙箱提权写入。已获用户明确授权的目标路径不需要再次询问。
临时 staging：D:/AI数字化人才平台-相关文档/.implementation-stage。
同步脚本：该 staging 下 .execution/publish.py，检查固定目标后 robocopy /E（不是 /MIR，不删除目标文件），并复制计划完成状态。
注意：staging 包含本项目生成的 .env，必须当作秘密；不要输出、提交或分享。广泛同步前先核对目标工作区有无新增修改，避免旧 staging 覆盖新 agent 在目标目录的改动；如直接在目标目录开发，先同步到 staging 或停止使用旧同步流程。
计划状态 staging：D:/AI数字化人才平台-相关文档/.plan-progress-stage。
若新会话对 Obsidian 有正常写权限，可直接编辑目标仓库，不必沿用临时 staging；但必须先检查两边差异。

## 6. 凭据、模型与授权状态

本地 MySQL/Redis/MinIO/.env 凭据由本项目随机生成；没有使用用户已有数据库或企业服务密码。后台管理员与两名部门 HR 的密码也是随机生成，保存在 .execution/local-accounts.json。该文件和 .env 均在 Git 忽略范围内；不要读取后显示、写进文档或 Git；bootstrap 不重置现有账号。

最新授权：用户指定 DeepSeek deepseek-flash，百炼 text-embedding-v3（原文 test-embedding-v3）与可选 qwen3-rerank，并授权从 D:/Wolin_Project/Yue-Education/.env 选择所需凭据。只读核对发现百炼 Key 存在；无独立 DeepSeek 官方 Key，旧 OPENAI_API_KEY 配套第三方 api.openai-proxy.org。已询问官方直连还是该代理，等待答复。已补查 D:/wolin_learn-master/rag_examples：发现百炼北京旧共享域名 https://dashscope.aliyuncs.com/compatible-mode/v1，地区/endpoint 不再需用户补充，但实际认证/模型调用尚未验证；该目录也无 DeepSeek 官方 Key。未复制模型 Key、未调用云模型、未发送真实招聘邮件。详见 docs/MODEL_AND_DATABASE_DECISION.md。数据库按用户“改动大则保持原栈”决定保留 MySQL+Milvus；PostgreSQL 端口与协议已确认响应，但未认证或修改。

到 T08/T09 接入前，先取得待答复的 DeepSeek 官方凭据或明确代理渠道选择；百炼按已查到的北京共享域名进行合成输入连通检查，不再重复询问地域。云端路线与拟用模型已经由用户指定，不要重复询问同一选择；合成数据做最小连通验证，费用/额度问题出现时如实反馈。若选 OpenAI，先使用 openai-platform-api-key 技能的凭据流程，再配置用户明确指定的本地目的地；不得扫描并复用现有 Key。其他供应商也只使用用户明确指定的项目凭据。不要让用户将密码/完整 API Key 发到普通聊天；用本地 .env/秘密文件或受支持的安全配置流程。企业 SMTP、生产数据库/对象存储、部署机器与 HTTPS 域名配置在实际接入时单独确认。

## 7. 已确认且不能擅自改的核心业务

单企业、外部候选人；管理员管账号/模型，HR 招聘。共享基础履历人才库；岗位、考试、面试评价按部门授权，私有评价不能进入共享画像/向量。HR 导入，邮箱必须补齐才能自动邀考。硬规则筛选 pass/fail/unknown，画像匹配加岗位卷分数辅助人工选人；有理由人工覆盖不能绕过邮箱/岗位/试卷等技术前提。岗位自动邀请默认关闭。服务端计时/保存/提交，候选人不看答案/评分/私密评价。招聘结果由 HR 决定。智能培训只做框架。
