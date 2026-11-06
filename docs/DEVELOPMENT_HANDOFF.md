# 开发记录与断点续接

更新：2026-11-06；状态：T09网关已实现，定向45通过及真实合成门通过；Docker引擎500阻塞最终完整回归。

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
|T09|未完成（最终回归待恢复）|网关/固定图实现；定向45通过；真实3组合成履历及1024维整批向量通过；Docker引擎500阻塞完整回归|
|T10 邮件配置和发送适配器|完成|完整149通过；本地Celery→SMTP→Mailpit真实收件并激活配置1；企业SMTP未接入|
|T11 题库与不可变试卷|完成|完整137通过；开发库两个部门各发布3题型/100分试卷并验证隔离|
|T12～T43|未完成|按依赖推进，生产发布需单独授权|

最新完整测试：artifacts/t10-final-suite.log，149 passed。
真实Mailpit：artifacts/t10-live-mailpit.json，config1已验证并active，只有本地测试信。
真实百炼：artifacts/t08-live-dashscope.json，text-embedding-v3/1024维，只有合成文本。
真实队列：artifacts/t06-live-queue.json，queued/pending→succeeded/sent。
不要声称招聘业务已跑通；当前完成的是基础设施、账号和任务框架。
证据报告：artifacts/t01-*～t05-*；执行流水：.execution/progress.md；任务摘录：.execution/T04-brief.md、T05-brief.md、T06-brief.md。
artifacts 和 .execution 被 Git 忽略，但已经保存在本机项目目录。未推送远端；本机磁盘损坏不在这些本地记录的保障范围内。

## 3. 当前工作与下一步

T06 已提交42794f3，T07 已提交fa55a2f。T08已完成验收，见artifacts/t08-verification.md；先检查git实际日志/未提交修改，不覆盖新工作。

T11 已完成验收，见 artifacts/t11-verification.md；本地两份合成试卷ID与版本ID分别1/1、2/2。T10现已完成：完整149通过，本地Mailpit测试接入已激活；下一步T09网关实现；官方deepseek-flash已通过最小JSON检查，不再缺凭据。T12依赖T09/T10，不能跳过自动邀请就绪门直接标完成。T09网关与业务质量验收仍未完成，不能用官方连接成功替代。

用户要求减少token：只读当前任务摘录和相关文件，输出摘要；保留有意义RED/GREEN和任务末完整回归，避免无变化重复检查；不用未授权的子agent。原审批曾因额度失败，用户现已明确继续，正常审批已恢复；不要绕过审批。

T08实现约定：provider_type仍是ollama/compatible_http，官方 URL+model allowlist 决定实际适配；不自动允许 api.openai-proxy.org。七个固定流程由0003_fixed_workflows迁移创建且默认关闭。提示词发布自身调用IdempotencyService，幂等键由服务构造参数从HTTP传入。模型测试只用合成输入；cloud model_digest=None，不能把model ID当作权重摘要。加密主密钥保留主项目.env，恢复加密数据库时必须一并保留。

凭据事实：旧DASHSCOPE_API_KEY是占位项；已根据旧TextEmbedding代码的明确引用，复用授权文件ALIYUN_API_KEY到主项目.env的TALENT_DASHSCOPE_API_KEY。真实embedding鉴权1024维成功。不要再盲选占位项或重复询问百炼地域。DeepSeek官方Key现已从新增授权根.env配置并通过合成JSON检查。

从T08起 .execution/publish.py 排除.env；不要用旧缓存覆盖主项目私有环境。临时staging已去掉用户模型Key与加密主密钥，仅主项目.env持有配置；源文件从未改动。Standalone default_session_factory初始化时加载全部40ORM表，回归测试使用新进程且显式设置backend PYTHONPATH。

后续边界：Word渲染后100页/完整图像解码与OCR留T13，单批50留T14。API099为鉴权附件流，FileService.attach须在领域调用方同一UoW保存关联。任务Worker固定处理器，当前已有system.verify及mail.test，其他业务处理器待逐任务注册；外部副作用必须有领域幂等/租约隔离，不能把技术诊断当招聘验收。

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


### 最新官方模型续接

DEEPSEEK_API_KEY来源D:/wolin_learn-master/.env已明确授权且成功；主项目.env变量TALENT_DEEPSEEK_API_KEY。官方config3（logical_key deepseek-flash）能力verified，JSON成功；不要再询问/扫描其他Key，不用第三方代理。只做了最小协议检查，T09仍未完成。测试证据deepseek-official-capability.json、deepseek-config-regression.log（10通过），最近完整主线测试仍为149通过。下一步按 .execution/T09-brief.md（暂在staging，已复制到主仓库）实现gateway、graphs、校验和真实业务样本。

### 2026-11-06 T09最新断点（优先读）

实现gateway、严格结构化/证据/整批向量校验、代码注册LangGraph、受控DeepSeek/Ollama适配器及AiRuntime入口。内部契约见docs/MODEL_GATEWAY_CONTRACT.md。云端digest可空，EmbeddingBatch带model_config_id/revision_no/model_name；AiConfigSnapshot新增config_revision。生成写AiRun；embedding无虚构prompt，以返回来源配置供T20记录。

有效RED：协议畸形JSON测试2失败3通过，修复为MODEL_OUTPUT_INVALID；首次缺模块RED与夹具identity缺导入另有记录，夹具错误不算业务RED。修复后定向45通过（artifacts/t09-targeted-final.log）。之后新增2项重试边界测试、限定生成task类型及来源引用键、整理校验异常和CLI恢复；这几项最终版本仅语法22文件检查通过，尚未在容器执行。

显式真实调用artifacts/t09-live-gateway.json ready=true：模型config3、AiRun1/2/3，Python3年/Java8年/夹带注入的行政履历unknown均正确；config2三条embedding全部1024维。调用后恢复match/embedding原配置与关闭状态。没有把真实验收CLI加入常规pytest，避免每次回归付费；计划相应命令已同步。

完整测试启动artifacts/t09-final-suite.log，创建本项目一次性容器ai-talent-dev-api-run-526232beca41，到前15项后停滞；docker ps返回LinuxEngine API500、18080健康端点超时。宿主TCP仍可连接但不代表服务健康。没有重启Docker或其他项目容器。已异步询问用户是否允许重启整个Docker（影响所有项目），尚未收到许可；不要把等待当授权。

恢复时先读最终日志与实际docker状态，先判断这次回归是否仍在跑，不能启动重复full suite。若需清理仅处理上述本项目一次性测试容器，勿重启/删除其他项目服务。恢复后跑最终版本定向与完整回归，再检查工作流恢复与模型契约，满足后才能标T09完成并进入T12。最近已完成完整基线仍为149 passed。当前T09未完成，不用局部成功冒充完整业务通过。
