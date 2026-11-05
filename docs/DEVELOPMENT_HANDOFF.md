# 开发记录与断点续接

更新：2026-11-05；状态：T11已验证，下一项T10邮件配置；T09真实LLM缺凭据。

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
|T09、T10|未完成|T09真实LLM缺凭据；下一项先推进T10邮件配置|
|T11 题库与不可变试卷|完成|完整137通过；开发库两个部门各发布3题型/100分试卷并验证隔离|
|T12～T43|未完成|按依赖推进，生产发布需单独授权|

最新完整测试：artifacts/t11-final-suite.log，137 passed。
真实百炼：artifacts/t08-live-dashscope.json，text-embedding-v3/1024维，只有合成文本。
真实队列：artifacts/t06-live-queue.json，queued/pending→succeeded/sent。
不要声称招聘业务已跑通；当前完成的是基础设施、账号和任务框架。
证据报告：artifacts/t01-*～t05-*；执行流水：.execution/progress.md；任务摘录：.execution/T04-brief.md、T05-brief.md、T06-brief.md。
artifacts 和 .execution 被 Git 忽略，但已经保存在本机项目目录。未推送远端；本机磁盘损坏不在这些本地记录的保障范围内。

## 3. 当前工作与下一步

T06 已提交42794f3，T07 已提交fa55a2f。T08已完成验收，见artifacts/t08-verification.md；先检查git实际日志/未提交修改，不覆盖新工作。

T11 已完成验收，见 artifacts/t11-verification.md；本地两份合成试卷ID与版本ID分别1/1、2/2。下一步先T10邮件配置（T05/T06/T08已满足）；T12依赖T09/T10，不能跳过自动邀请就绪门直接标完成。T09真实DeepSeek缺官方Key或明确代理授权，不能伪造验收。

用户要求减少token：只读当前任务摘录和相关文件，输出摘要；保留有意义RED/GREEN和任务末完整回归，避免无变化重复检查；不用未授权的子agent。原审批曾因额度失败，用户现已明确继续，正常审批已恢复；不要绕过审批。

T08实现约定：provider_type仍是ollama/compatible_http，官方 URL+model allowlist 决定实际适配；不自动允许 api.openai-proxy.org。七个固定流程由0003_fixed_workflows迁移创建且默认关闭。提示词发布自身调用IdempotencyService，幂等键由服务构造参数从HTTP传入。模型测试只用合成输入；cloud model_digest=None，不能把model ID当作权重摘要。加密主密钥保留主项目.env，恢复加密数据库时必须一并保留。

凭据事实：旧DASHSCOPE_API_KEY是占位项；已根据旧TextEmbedding代码的明确引用，复用授权文件ALIYUN_API_KEY到主项目.env的TALENT_DASHSCOPE_API_KEY。真实embedding鉴权1024维成功。不要再盲选占位项或重复询问百炼地域。DeepSeek官方Key仍缺。

从T08起 .execution/publish.py 排除.env；不要用旧缓存覆盖主项目私有环境。临时staging已去掉用户模型Key与加密主密钥，仅主项目.env持有配置；源文件从未改动。Standalone default_session_factory初始化时加载全部40ORM表，回归测试使用新进程且显式设置backend PYTHONPATH。

后续边界：Word渲染后100页/完整图像解码与OCR留T13，单批50留T14。API099为鉴权附件流，FileService.attach须在领域调用方同一UoW保存关联。任务Worker固定处理器，当前仅system.verify技术诊断；外部副作用必须有领域幂等/租约隔离，不能把技术诊断当招聘验收。

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

本地 MySQL/Redis/MinIO/.env 凭据由本项目随机生成；没有使用用户已有数据库或企业服务密码。后台管理员与两名部门 HR 的密码也是随机生成，保存在 .execution/local-accounts.json。该文件和 .env 均在 Git 忽略范围内；不要读取后显示、写进文档或 Git；bootstrap 不重置现有账号。

最新授权：用户指定 DeepSeek deepseek-flash，百炼 text-embedding-v3（原文 test-embedding-v3）与可选 qwen3-rerank，并授权从 D:/Wolin_Project/Yue-Education/.env 选择所需凭据。只读核对发现百炼 Key 存在；无独立 DeepSeek 官方 Key，旧 OPENAI_API_KEY 配套第三方 api.openai-proxy.org。已询问官方直连还是该代理，等待答复。已补查 D:/wolin_learn-master/rag_examples：发现百炼北京旧共享域名 https://dashscope.aliyuncs.com/compatible-mode/v1，地区/endpoint 不再需用户补充，但实际认证/模型调用尚未验证；该目录也无 DeepSeek 官方 Key。后续 T08 已按代码用途选择 ALIYUN_API_KEY（DASHSCOPE_API_KEY 实为占位项）复制到主项目私有环境并通过合成文本 embedding 真实检查；未调用 DeepSeek、未发送真实招聘邮件。详见 docs/MODEL_AND_DATABASE_DECISION.md。数据库按用户“改动大则保持原栈”决定保留 MySQL+Milvus；PostgreSQL 端口与协议已确认响应，但未认证或修改。

到 T08/T09 接入前，先取得待答复的 DeepSeek 官方凭据或明确代理渠道选择；百炼按已查到的北京共享域名进行合成输入连通检查，不再重复询问地域。云端路线与拟用模型已经由用户指定，不要重复询问同一选择；合成数据做最小连通验证，费用/额度问题出现时如实反馈。若选 OpenAI，先使用 openai-platform-api-key 技能的凭据流程，再配置用户明确指定的本地目的地；不得扫描并复用现有 Key。其他供应商也只使用用户明确指定的项目凭据。不要让用户将密码/完整 API Key 发到普通聊天；用本地 .env/秘密文件或受支持的安全配置流程。企业 SMTP、生产数据库/对象存储、部署机器与 HTTPS 域名配置在实际接入时单独确认。

## 7. 已确认且不能擅自改的核心业务

单企业、外部候选人；管理员管账号/模型，HR 招聘。共享基础履历人才库；岗位、考试、面试评价按部门授权，私有评价不能进入共享画像/向量。HR 导入，邮箱必须补齐才能自动邀考。硬规则筛选 pass/fail/unknown，画像匹配加岗位卷分数辅助人工选人；有理由人工覆盖不能绕过邮箱/岗位/试卷等技术前提。岗位自动邀请默认关闭。服务端计时/保存/提交，候选人不看答案/评分/私密评价。招聘结果由 HR 决定。智能培训只做框架。
