# 开发记录与断点续接

更新：2026-11-08；状态：T01～T12完成；完整测试241通过；T13文本格式解析子任务完成，下一步字段提取与导入，优先交付T30核心招聘闭环。

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
|T07 私有文件与授权下载|完成|完整测试107通过；真实代理二进制下载、MinIO私有桶与清理验证通过|
|T08 模型配置、提示词、固定流程|完成|完整测试126通过；百炼 text-embedding-v3 真实鉴权/1024维通过；真实管理员入口检查通过|
|T09 模型网关与固定流程|完成|代码4641161；最终完整186通过；真实3组合成履历及1024维整批向量通过|
|T10 邮件配置和发送适配器|完成|完整149通过；本地Celery→SMTP→Mailpit真实收件并激活配置1；企业SMTP未接入|
|T11 题库与不可变试卷|完成|完整137通过；开发库两个部门各发布3题型/100分试卷并验证隔离|
|T12 岗位版本与自动邀请配置|完成|19项定向、209项完整回归；本地合成岗位9项检查通过|
|T13～T43|未完成|优先T30核心闭环，扩展功能后补；生产发布需单独授权|

最新完整测试：artifacts/t13-core-final-suite.log，241 passed in175.27s；T13文本格式定向32通过，T12定向19通过。本轮前端未变，未重复构建；之前前端lint/typecheck/build通过。
真实Mailpit：artifacts/t10-live-mailpit.json，config1已验证并active，只有本地测试信。
真实百炼：artifacts/t08-live-dashscope.json，text-embedding-v3/1024维，只有合成文本。
真实队列：artifacts/t06-live-queue.json，queued/pending→succeeded/sent。
不要声称招聘业务已跑通；当前完成的是基础设施、账号和任务框架。
证据报告：artifacts/t01-*～t05-*；执行流水：.execution/progress.md；任务摘录：.execution/T04-brief.md、T05-brief.md、T06-brief.md。
artifacts 和 .execution 被 Git 忽略，但已经保存在本机项目目录。GitHub目标为https://github.com/samJ-03/AI-Digital-Talent-Management，已配置origin；同步状态以实际origin/main与Git记录为准。本地执行证据和秘密不上传，未做生产部署。

## 3. 当前工作与下一步

已完成T01～T12。下一步T13解析，随后依原任务实现导入、画像、筛选、考试及最小页面，先验收T30。核心优先级见docs/CORE_DELIVERY_PRIORITY.md；岗位API细节见docs/JOB_VERSIONS_CONTRACT.md。T12只原子生产invite.scan，T22/T23消费者未完成；不能称为已自动发信。用户已授权代码上传，未授权生产部署。

T09内部契约见docs/MODEL_GATEWAY_CONTRACT.md。AiConfigSnapshot包含config_revision；生成核对发布提示词/schema、证据引用和模型配置；只有校验结果进入AiRun。EmbeddingBatch带model_config_id/revision_no/model_name，云端model_digest=None，本地核验真实digest。T20按配置修订/维度隔离向量，私有考试评价不得进入共享画像/embedding。

用户要求减少token：只读当前任务计划段和相关文件，输出摘要；局部验证后仅任务末完整回归，失败/变化才重跑；不重复已保存的付费真实合成探测，不用未授权子agent。

T08起publisher排除.env；主项目.env持有用户选定模型密钥和Fernet主密钥，不能用旧stage覆盖。Standalone default_session_factory注册全部40ORM；API/Worker重启后读取当前绑定源代码。企业SMTP未接入；本地Mailpit配置1已验证并active。

T07边界：Word渲染100页/完整图像解码和OCR留T13，批量50留T14。文件授权下载基于持久化引用；attach须同一业务UoW。Worker当前仅system.verify、mail.test；其他固定处理器随任务注册。

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
同步脚本：该 staging 下 .execution/publish.py，检查固定目标后 robocopy /E /XF .env（不是 /MIR，不删除目标文件，不覆盖私有环境），并复制计划完成状态。
注意：staging 包含本项目生成的 .env，必须当作秘密；不要输出、提交或分享。广泛同步前先核对目标工作区有无新增修改，避免旧 staging 覆盖新 agent 在目标目录的改动；如直接在目标目录开发，先同步到 staging 或停止使用旧同步流程。
计划状态 staging：D:/AI数字化人才平台-相关文档/.plan-progress-stage。
若新会话对 Obsidian 有正常写权限，可直接编辑目标仓库，不必沿用临时 staging；但必须先检查两边差异。

## 6. 凭据、模型与授权状态

本项目生成的数据库/对象存储/后台账号凭据仅在ignored .env与.execution/local-accounts.json，不打印、不提交。DeepSeek官方Key已按用户授权从D:/wolin_learn-master/.env选择DEEPSEEK_API_KEY，主项目TALENT_DEEPSEEK_API_KEY，官方config3真实JSON及T09合成样本通过。百炼按授权rag_examples代码选取ALIYUN_API_KEY（DASHSCOPE_API_KEY是占位项），主项目TALENT_DASHSCOPE_API_KEY，config2真实1024维通过。加密主密钥也仅在主项目.env。publisher排除.env，禁止用stage覆盖。源文件未改动；第三方代理未使用，不再重复询问Key/渠道/地域。

保留MySQL+Milvus；未认证/修改用户PostgreSQL。企业SMTP、生产服务、部署仍待对应阶段确认。仅合成输入发往已授权官方模型，未发送真实候选人资料或企业招聘邮件。

## 7. 已确认且不能擅自改的核心业务

单企业、外部候选人；管理员管账号/模型，HR 招聘。共享基础履历人才库；岗位、考试、面试评价按部门授权，私有评价不能进入共享画像/向量。HR 导入，邮箱必须补齐才能自动邀考。硬规则筛选 pass/fail/unknown，画像匹配加岗位卷分数辅助人工选人；有理由人工覆盖不能绕过邮箱/岗位/试卷等技术前提。岗位自动邀请默认关闭。服务端计时/保存/提交，候选人不看答案/评分/私密评价。招聘结果由 HR 决定。智能培训只做框架。


### T10续接注意

Worker现在支持受控handler.prepare(lease)→原子finalize；邮件测试在SMTP前持久化processing标记，崩溃/超时后unknown终态，不自动重发。TerminalJobFailure可与领域状态同事务提交。服务端停用/切换SMTP只处理尚未发送pending通知为failed，mail_config_id不改。SMTP延迟connect要设置经过验证的_host用于Python3.11 SNI，证书检查始终启用。0004仅放宽数据库允许none，服务策略只准本地Mailpit。API094最小脱敏任务报告已提前提供，T28再补完整读取层。


### 2026-11-06 T09验收与Docker恢复

用户明确允许重启Docker Desktop，已用官方desktop restart完成；本项目全部基础服务健康，API live200，7个固定流程仍关闭，真实合成AiRun1/2/3保持succeeded。证据artifacts/t09-recovery-check.json。重启会影响所有项目，本轮授权已执行，不将它当作以后无限重启授权。

T09有效RED：畸形协议JSON2失败3通过，修复错误归类。此前定向45通过。最终版本（含新增重试边界2项、task/来源键限制）完整186 passed in118.16s，artifacts/t09-clean-final-suite.log。第一次恢复回归185通过1失败：最后管理员保护受中断残留测试账号影响，后段schema迁移往返清空隔离库后单项1通过；再完整186全绿。没有放宽保护，也未修改开发库。

真实门artifacts/t09-live-gateway.json ready=true：官方DeepSeek config3三个合成样本（Python3年、Java8年、夹带注入行政履历unknown）与引用通过；百炼config2三条整批1024维通过；云端未提供权重摘要保留None。合成调用后流程已恢复。付费CLI python scripts/compose.py exec -T api python -m app.ai_runtime.verify_gateway，故意不放入普通pytest。恢复期间未重复调用模型。

验收详情artifacts/t09-verification.md，内部契约docs/MODEL_GATEWAY_CONTRACT.md，详细计划T09已全部勾选。仅T09基础能力完成，招聘业务及业务页面仍待后续任务，不称整套系统跑通。下一步T12。

若之后强制中断pytest，先确认旧测试容器不再运行，再检查隔离talent_test残留；测试中断可使管理员数量等全局断言受污染。迁移/清理只准严格验证后的talent_test，禁止动talent_dev或用户已有库；不能通过删除业务保护来使测试通过。

### GitHub首次上传整理（2026-11-06）

目标仓库samJ-03/AI-Digital-Talent-Management为用户创建的公开仓库，上传已明确授权。本地开发分支继续feat/recruitment-v1，首次上传到main并保留既有提交历史；远程同步状态应核对实际Git分支，不凭聊天推断。

新增.env_example并与.env.example保持一致，包含全部实际读取的配置、用途、单位、必填/可选说明；scripts/init_env.py仅创建新文件、生成随机独立凭据，不覆盖已有.env或打印秘密。README提供克隆、运行时镜像构建、Compose、迁移、账号初始化和隔离测试的完整命令。

源码文档覆盖148个Python模块、176个类、208个公开函数/方法，前端边界有JSDoc；原135个修改的Python文件以AST比较确认可执行语句不变（排除docstring和mapped_column.comment）。40表478字段都具备中文SQL COMMENT和模型类说明。追加0005_schema_comments及0006_comment_semantics，不改原迁移；字段定义和数据保真测试通过，开发库迁移已应用，alembic check无漂移。docs/DATABASE.md为ORM导出字典，docs/specs包含8份评审基线及计划仓库副本，跨机器续接见AGENTS.md。

验证：github-comments-red.log明确字段comment缺失失败；真实MySQL注释/迁移保真2通过；github-upload-final-suite.log为最终190通过，前端lint/typecheck/build通过。上传前检查工作文件与全部可达Git历史，未发现配置的真实秘密或私有文件路径入历史；.env、.execution、artifacts均忽略，不上传简历/答卷/账号/密钥/数据库导出。没有重复付费模型探测，没有对外招聘邮件。


### T12检查点与核心优先（2026-11-07）

七项岗位写API已实施，岗位版本发布不可变、状态变更关闭开关，自动邀请须具备同部门发布卷、有效模型流程与邮件配置。修复MySQL REPEATABLE READ下配置停用旧快照误通过以及并发草稿编号冲突；锁定依赖强引用保留至事务结束。19项定向及209项完整测试通过，独立只读审阅无阻塞发现。artifacts/t12-live-local.json为合成岗位1/版本1的9项领域服务检查，最终closed/off，无扫描事件、外部邮件或付费模型调用。公开摘要docs/T12_VERIFICATION.md；详细本地证据artifacts/t12-verification.md。

保留原计划，T31～T37扩展后补。企业SMTP和复杂扫描件支持按实际验收说明，人工补录不能替代原T13全格式完成。工作区原有OpenSpec配置/技能改动保留，不混入T12提交。新T12变更目录独立跟踪本任务。提交/远端状态查看Git及最新交付收据，不从文档猜测SHA。


### T13文本格式子任务（2026-11-08）

文本PDF与普通文字DOCX适配器已实现，源码backend/app/ingestion/{document_types,parsers,parse_worker}.py。32项定向和241项完整测试通过；无网络/付费模型调用。独立审阅发现并修复Word内容控件、修订等包装文字静默丢失；不支持的可见文字包装明确失败。子进程环境不传递应用凭据，父进程超时回收，Linux限制地址空间/CPU。

支持说明docs/CORE_PARSER_SUPPORT.md，验收docs/T13_CORE_VERIFICATION.md，本地日志artifacts/t13-core-*。原T13保持未完成，仅T13.1.1已验证勾选。下一步ResumeExtractor通过已有网关实现结构化字段与证据，缺失邮箱保持unknown，再接T14/T15；OCR、旧DOC、复杂Word、Word物理分页仍待后续。当前没有公开导入API/招聘页面，不得把解析测试说成业务闭环验收。T12上传收据仍保留；本子任务提交与上传查看最新Git和artifacts/t13-core-upload-receipt.json。
