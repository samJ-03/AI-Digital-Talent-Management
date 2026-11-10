# AI数字化人才平台详细开发Todolist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.
>
> 上述为writing-plans的执行交接约定。本轮只编写计划，不调用实施技能、不安装依赖、不创建代码项目。执行时检查所需技能，缺失再用find-skills定位；不得假称已调用不存在的技能。主任务及步骤全部未勾选，必须实际验证后更新。

**Goal:** 实现单企业外部人才智慧招聘：HR建岗/导入→粗筛→画像匹配→自动邮件邀考→线上笔试/评分复核→HR人工选人及招聘跟踪。

**Architecture:** 前后端分离模块化单体＋Linux异步worker。MySQL保存事实和版本，Milvus保存语义索引，MinIO保存原件，Redis承载队列/会话；模型、OCR、邮件通过适配器隔离。先完成真实纵向闭环，再完善完整界面、知识库、统计、恢复及交付。

**Tech Stack:** Node24、Next.js（沿用既有16系建议，T01实测后锁精确版本）、React、TypeScript、Ant Design、TanStack Query、ECharts；Python3.11、FastAPI、Pydantic2、SQLAlchemy2同步Session、Alembic、PyMySQL；MySQL8、Redis、Celery Linux、Milvus、MinIO；LangGraph固定子图、模型网关、pypdf、python-docx、PaddleOCR、LibreOffice隔离转换、SMTP/Mailpit；pytest、HTTPX、Playwright、Compose、Nginx。

**Spec:** [01需求PRD](./01-需求分析与PRD.md)、[02环境](./02-本机环境与技术选型.md)、[03技术设计](./03-总体架构与技术设计.md)、[04数据库](./04-数据库表与数据一致性设计.md)、[05接口](./05-接口契约设计.md)、[06验收](./06-验收标准与联调验证方案.md)、[07自审记录](./07-需求自审与决策记录.md)。原始参考为D:/AI数字化人才平台-相关文档内PRD、独立HTML、design/test资料。

日期：2026-11-05。用户已明确要求开始todolist，本计划沿用前轮文档包，不重新讨论核心范围。此请求不等于立即开发、上线或向真实候选人发信。

## Global Constraints

- 单企业、外部人才；管理员配置系统，HR招聘，候选人只访问本人考试。
- required/preferred条件分开，粗筛pass/fail/unknown；未知不填0，不当不符。邮箱是进入自动流程的前提。
- 自动邀请默认关闭，HR开启后按门槛执行；重评不重复发卷；跨岗推荐须HR加入。
- 40张表及104条接口见附录A/B，变更必须同步需求、模型、接口和验收。
- BIGINT UNSIGNED的ID对外用字符串；DATETIME(6)存UTC，界面Asia/Shanghai；分数Decimal，匹配分与考试分分列。
- ORM映射，repository不commit，服务层控制事务；锁内不得调用外部模型/邮件/文件服务。
- 发布岗位/试卷不可变；简历画像保留版本；正式score_reports追加；合并用canonical别名及主应聘关系映射，不迁移历史归属。
- 空答案revision=0；服务端计时；submit与超时共用幂等动作；未答题0分，已答主观题人工复核。
- 共享画像/向量只用共享简历事实，私有考试评价授权后动态附加。
- 后台/候选人会话隔离；安全Cookie与CSRF；密钥只写不回显；不在日志保存token/验证码/答案/全文。
- Celery必须Linux；本机现有服务/库/模型不擅自重置；新项目新库新卷。
- 培训仅框架；智能问数、视频面试、自适应千人千卷、通用拖拽、内部员工、多租户延期。
- 单元可替身，最终闭环真实MySQL/Redis/MinIO/Milvus/模型/测试邮件；不以固定答复验收。
- 开发验证建议1万人才、20活跃HR、50并发考试；p95列表≤1s、看板≤3s、保存≤1s，向量目标≤500ms不含模型。2000在线/99.9%年可用未验证。
- P0/P1全部通过；环境/质量未就绪标blocked。一次性跑通通过预检、锁版本、真实闭环、恢复验证提高成功率，不作无证据保证。

## Review Focus

1. MF-01 合并撞上同岗位历史/活动考次：不得部分提交、重复邀考；T16/T19/T22/T39覆盖。
2. MF-02 SMTP接受后响应丢失、发送前暂停：unknown不盲重发，取消映射revoked；T23/T39覆盖。
3. MF-03 断线、双设备、开考有效期已过但未到答题截止：恢复同卷、revision冲突可见、deadline不重置；T24/T25/T29/T39覆盖。
4. MF-04 私有评价经摘要/向量泄露：共享AI输入禁止私有评价；T17/T20/T28/T39覆盖。
5. MF-05 空白主观题及复核/正式化竞争：全题建行、空题0分、旧报告不改；T25/T26/T39覆盖。

## 1. 位置、执行约定与完成定义

输出位置：D:/Obsidian仓库/Obsidian/项目/AI数字化人才平台项目/开发计划-2026-11-05/AI数字化人才平台-详细开发todolist.md。

拟议代码根R：D:/Obsidian仓库/Obsidian/项目/AI数字化人才平台项目/code/ai-talent，当前未创建。以下文件均相对R，命令从R执行，backend容器目录/app/backend。执行前检查目录、Git状态、AGENTS；已有代码必须先映射本计划，不能覆盖用户改动。

任务先定接口/失败场景、最小实现、再实际验证。每项任务的代码片段是待编写测试，当前没有执行。RED必须因为未实现行为而失败，不能以环境故障或缺fixture冒充有效RED。GREEN预期命令退出0、pytest全部passed、构建成功。证据、异常验证、代码审阅和提交均满足后才勾任务。

| 阶段 | 任务 | 退出条件 |
|---|---|---|
| M0环境 | T01—T02 | 版本与Linux引擎可用，核心服务就绪，最小同域应用可访问 |
| M1基础 | T03—T10 | 迁移/权限/任务/私有文件/模型/邮件通过 |
| M2主线 | T11—T29 | 岗位→简历→评估→邀考→考试→评分/招聘及最小页面可操作 |
| G1纵向闭环 | T30 | 真实数据及完整ID链，从导入到正式成绩/HR推进 |
| M3完整功能 | T31—T37 | 完整后台、人才复用、知识库、AI出题、统计、培训框架 |
| M4专项 | T38—T41 | 契约/权限/并发/恢复/质量/性能/AT01—16 |
| G2测试交付 | T42 | 干净环境启动、全回归、备份恢复、运行手册 |
| G3生产交接 | T43 | 获用户批准后正式HTTPS/SMTP/发布，否则保持待批准 |

T30未过不进入扩展；T42是可运行测试版本交付节点，生产资源与正式发布另行批准。

### 通用类型、测试夹具与代码约定

core/types.py定义JsonValue递归JSON、PageQuery(page=1,page_size=20≤100)、Page[T](items,total,page,page_size)、ApiEnvelope[T](code,message,data,request_id)、ResultRef(entity_type,entity_id,response_code)、TaskAccepted(task_id,state,poll_url)、ActorContext、ResourceScope。Server端id:int，wire端id:string。

ActorContext={actor_type,user_id?,candidate_id?,attempt_id?,department_ids,permissions}；ResourceScope={kind,id?,department_id?,shared}。上下文只能认证依赖构造，不能用body角色。DomainError={code,http_status,safe_details}，具体异常如PermissionDenied/MergeConflict/ModelNotVerified均继承该类。

UowFactory=Callable[[],SqlAlchemyUow]，每请求/任务独立Session；Clock UTC可替换FrozenClock。Service通过构造器注入本任务依赖的uow_factory/clock/policy/适配器，禁止隐式全局Session；方法签名中的Command/Result在该领域schemas.py或专用dataclass定义。View字段以05为准，内部领域对象/ORM/公开DTO隔离。

测试clients/actors/uow/时钟和岗位/试卷/考次工厂由T03/T05的conftest/factories定义。每项代表性测试引用的场景fixture在同一任务测试文件建立，并保证名字表达的前置成立；不能返回固定成功数据。Playwright的examScenario/hrScenario在T29 fixtures.ts通过测试factory/真实API初始化，不增加生产后门。模型实时测试与确定性替身测试分开。

Create是首次文件，Modify是扩展前序文件；Python包__init__.py随首次目录建立，T03注册完整metadata。前端组件props在同feature/types.ts显式定义，事件/服务端返回类型引用OpenAPI。T02定义typecheck/build/test:e2e/generate:api脚本，T38作最终全量契约校验；开发中每次API变更已要同步类型，不等到最后。

T02建立最小CI，任务持续扩充测试，T42固化完整流水线。测试用独立数据库/卷/前缀；禁止对现有业务库运行重置。详细提交仅暂存本任务文件，报告/配置秘密不进Git。

## 2. 目录职责（相对R）

~~~text
backend/app/
  main.py                 应用装配与健康检查
  core/                   配置、UoW、时间、权限、幂等与秘密
  identity/ jobs/ files/  账号组织、岗位版本、私有文件
  ingestion/ talents/     导入解析、身份/版本/画像/合并
  evaluation/ recruitment/ 粗筛匹配、应聘关系与招聘阶段
  assessment/             题库试卷、邀请核验、答卷评分
  notifications/          邮件配置/投递/未知状态
  knowledge/ search/      招聘资料问答与语义索引
  reporting/ runtime/     统计待办、任务outbox与恢复
  ai_runtime/ audit/      固定AI流程、配置与审计
backend/alembic/           迁移及循环当前指针外键
backend/tests/             unit/integration/contract/security/e2e/ops
frontend/src/app/(staff)/admin/  管理员配置
frontend/src/app/(staff)/hr/     HR招聘
frontend/src/app/exam/           候选人考试
frontend/src/features/ lib/ generated/  业务组件、HTTP、OpenAPI类型
frontend/tests/e2e/        浏览器主线和异常验证
infra/ scripts/           Compose/Nginx/OCR、预检/启动/备份恢复
 evaluation/ tests/load/   固定质量数据集及性能场景
docs/                     测试交付、运行、发布回退手册
~~~

40个实体类见附录A，104个handler与服务方法见附录B；具体文件在任务内完整列出。

## 3. 主任务清单

| 状态/任务 | 阶段 | 可审阅成果 | 前置 |
|---|---|---|---|
| - [x] T01 | M0 | 环境预检与版本冻结 | 无 |
| - [x] T02 | M0 | 最小应用、Compose与同域入口 | T01 |
| - [x] T03 | M1 | 40表ORM与可重复迁移 | T02 |
| - [x] T04 | M1 | 时间、权限上下文、审计与通用幂等 | T03 |
| - [x] T05 | M1 | 后台登录、会话与组织账号管理 | T04 |
| - [x] T06 | M1 | 持久任务、outbox与租约恢复 | T04 |
| - [x] T07 | M1 | 私有文件、上传校验与下载授权 | T04 |
| - [x] T08 | M1 | 模型配置、提示词与固定流程管理 | T05、T06 |
| - [x] T09 | M1 | 模型网关和结构化输出验证 | T08 |
| - [x] T10 | M1 | 邮件配置测试、激活与安全发送适配器 | T05、T06、T08 |
| - [x] T11 | M2 | 题库与不可变岗位试卷 | T05、T04 |
| - [x] T12 | M2 | 岗位版本与自动邀请配置 | T11、T09、T10 |
| - [ ] T13 | M2 | PDF、Word、扫描件与图片解析适配器 | T07、T09 |
| - [x] T14 | M2 | 批量导入、任务排队和失败重试 | T06、T07、T12 |
| - [ ] T15 | M2 | 人才建档、邮箱门槛与简历修订 | T13、T14 |
| - [ ] T16 | M2 | 重复确认及历史关系合并 | T15 |
| - [ ] T17 | M2 | 共享人才画像与岗位授权视图 | T09、T15 |
| - [ ] T18 | M2 | 岗位硬条件三态规则引擎 | T12、T15 |
| - [ ] T19 | M2 | 应聘关系、评估快照与人工覆盖 | T17、T18、T16 |
| - [ ] T20 | M2 | 真实语义索引与权限过滤检索 | T09、T17、T16 |
| - [ ] T21 | M2 | 岗位匹配评分与证据校验 | T19、T20 |
| - [ ] T22 | M2 | 邀请资格门与唯一考次创建 | T21、T11、T10 |
| - [ ] T23 | M2 | 邮件投递、未知结果与重发 | T22、T10、T06 |
| - [ ] T24 | M2 | 候选人入口、邮箱核验与考次会话 | T23、T05 |
| - [ ] T25 | M2 | 服务端计时、答题保存和统一提交 | T24、T11、T06 |
| - [ ] T26 | M2 | 客观评分、主观建议与正式成绩版本 | T25、T09 |
| - [ ] T27 | M2 | 招聘阶段、面试评价与人工决定 | T19、T26 |
| - [ ] T28 | M2 | 查询服务、筛选分页与完整读接口 | T27、T23、T21、T20 |
| - [ ] T29 | M2 | 最小可操作前端与考试页面 | T05、T12、T14、T17、T22、T25、T26、T27、T28 |
| - [ ] T30 | G1 | 最小纵向闭环与事件串联验收 | T29、T23、T21、T20 |
| - [ ] T31 | M3 | 管理员完整配置界面 | T28、T08、T10、T30 |
| - [ ] T32 | M3 | HR岗位、题库与试卷完整界面 | T28、T11、T12、T30 |
| - [ ] T33 | M3 | HR人才库、去重、画像与招聘完整界面 | T28、T16、T17、T19、T20、T27、T30 |
| - [ ] T34 | M3 | 招聘知识库解析、发布与有来源问答 | T30、T20、T13 |
| - [ ] T35 | M3 | AI辅助出题与岗位资料融合 | T34、T11、T09 |
| - [ ] T36 | M3 | 招聘统计口径、待办与管理员运行视图 | T28、T27、T26、T16、T30 |
| - [ ] T37 | M3 | 知识库、看板与培训框架界面 | T34、T35、T36、T31、T33 |
| - [ ] T38 | M4 | 104接口覆盖、OpenAPI与前端类型同步 | T37 |
| - [ ] T39 | M4 | 安全隔离、竞争条件与断点恢复专项 | T38 |
| - [ ] T40 | M4 | 真实AI质量与解析评测 | T39 |
| - [ ] T41 | M4 | 性能、资源与全链路回归 | T40 |
| - [ ] T42 | G2 | 干净环境启动、备份恢复与测试环境交付 | T41 |
| - [ ] T43 | G3 | 生产准备、发布审批与运行交接 | T42 |

## 4. 逐任务实施与验收

### T01 环境预检与版本冻结

**阶段/前置：** M0；无。**需求：** FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `scripts/preflight.py`
- Create: `infra/versions.lock.json`
- Create: `backend/requirements.in`
- Create: `backend/requirements.lock`
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `tests/ops/test_preflight.py`

**Consumes：** 现有环境信息与评审文档，不依赖已有代码。

**Produces / 类与函数签名：**

~~~text
PreflightChecker.check_runtime(self, executable: str, args: list[str]) -> CheckResult
PreflightChecker.check_service(self, name: str, endpoint: str) -> CheckResult
PreflightChecker.run(self, config: PreflightConfig) -> PreflightReport
~~~

**类型与规则：** CheckResult={name,ok,version?,reason?,evidence_path?}; PreflightConfig={profile,required_services}; PreflightReport={checks,ready,blocked_reasons}。只输出允许信息，不dump环境变量。

- [x] **T01.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_missing_docker_blocks_linux_worker(checker, config_missing_docker):
    report = checker.run(config_missing_docker)
    assert report.ready is False
    assert "DOCKER_UNAVAILABLE" in report.blocked_reasons
~~~

- [x] **T01.1.1** test_missing_docker_blocks_linux_worker：Docker不可执行时ready=false，不退回原生Windows Celery。
- [x] **T01.1.2** test_tcp_open_not_ready：仅TCP开放但SDK读写失败不得ready。
- [x] **T01.1.3** test_secrets_redacted：报告不含环境秘密。

- [x] **T01.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T01.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T01.4 验证GREEN及异常。** 执行：

~~~text
python -m pytest tests/ops/test_preflight.py -q；python scripts/preflight.py --profile dev --report artifacts/preflight.json
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：实际记录Node24/Python3.11/Git/Docker/Compose/WSL2、模型与SDK组合；冻结精确依赖/镜像digest。无法运行则本任务blocked，不勾完成；不改已有服务。

- [x] **T01.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t01-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T01.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'scripts/preflight.py' 'infra/versions.lock.json' 'backend/requirements.in' 'backend/requirements.lock' 'frontend/package.json' 'frontend/package-lock.json' 'tests/ops/test_preflight.py'
git commit -m 'feat: T01 环境预检与版本冻结'
~~~

### T02 最小应用、Compose与同域入口

**阶段/前置：** M0；T01。**需求：** FR-01、FR-15。**负责接口：** API-100、API-101。

**文件：**

- Create: `infra/compose.yaml`
- Create: `infra/nginx.conf`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `backend/app/main.py`
- Create: `backend/app/core/settings.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/core/types.py`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/lib/http.ts`
- Create: `frontend/src/providers/AppProviders.tsx`
- Create: `backend/tests/integration/test_health.py`
- Create: `backend/pytest.ini`
- Create: `backend/tests/conftest.py`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/eslint.config.mjs`
- Create: `frontend/src/lib/api-error.ts`

**Consumes：** 使用T01的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
create_app(settings: Settings) -> FastAPI
Settings.load() -> Settings
health_live() -> HealthView
health_ready(ctx: MonitorContext) -> ReadinessView
apiFetch<T>(path: string, options?: RequestOptions): Promise<ApiEnvelope<T>>
~~~

**类型与规则：** Settings由独立env读取，禁止打印secret；HealthView={alive}; ReadinessView={ready,dependencies}; ApiEnvelope<T>={code,message,data,request_id}。Node服务13000、API18080为宿主默认且启动前探测；容器内部端口独立。

- [x] **T02.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_ready_requires_db_and_redis(monitor_client, unavailable_redis):
    response = monitor_client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["data"]["ready"] is False
~~~

- [x] **T02.1.1** test_health_no_secrets：live不暴露连接串。
- [x] **T02.1.2** test_ready_requires_db_and_redis：依赖未就绪503。
- [x] **T02.1.3** test_error_envelope：422/500有request_id且无raw_error。

- [x] **T02.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T02.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T02.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py config；python scripts/compose.py up -d --wait mysql redis minio milvus mailpit api frontend nginx；python scripts/compose.py exec -T api python -m pytest tests/integration/test_health.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：Linux服务DNS、Cookie/CSRF反代路径可用；使用新库/新卷，API与前端可访问；OCR与模型不就绪单列。；配置pytest/Playwright、package scripts(typecheck/build/generate:api/test:e2e)、包初始化和结构化错误；CI基础检查随本任务建立，完整交付任务再扩展。

- [x] **T02.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t02-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T02.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'infra/compose.yaml' 'infra/nginx.conf' 'backend/Dockerfile' 'frontend/Dockerfile' 'backend/app/main.py' 'backend/app/core/settings.py' 'backend/app/core/errors.py' 'backend/app/core/types.py' 'frontend/src/app/layout.tsx' 'frontend/src/lib/http.ts' 'frontend/src/providers/AppProviders.tsx' 'backend/tests/integration/test_health.py' 'backend/pytest.ini' 'backend/tests/conftest.py' 'frontend/playwright.config.ts' 'frontend/tsconfig.json' 'frontend/eslint.config.mjs' 'frontend/src/lib/api-error.ts'
git commit -m 'feat: T02 最小应用、Compose与同域入口'
~~~

### T03 40表ORM与可重复迁移

**阶段/前置：** M1；T02。**需求：** FR-01、FR-02、FR-03、FR-04、FR-05、FR-06、FR-07、FR-08、FR-09、FR-10、FR-11、FR-12、FR-13、FR-14、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `backend/app/core/db.py`
- Create: `backend/app/core/uow.py`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_entities.py`
- Create: `backend/alembic/versions/0002_current_pointers.py`
- Create: `backend/tests/integration/test_schema_contract.py`
- Create: `backend/app/identity/models.py`
- Create: `backend/app/files/models.py`
- Create: `backend/app/jobs/models.py`
- Create: `backend/app/ingestion/models.py`
- Create: `backend/app/talents/models.py`
- Create: `backend/app/recruitment/models.py`
- Create: `backend/app/evaluation/models.py`
- Create: `backend/app/assessment/models/papers.py`
- Create: `backend/app/assessment/models/exams.py`
- Create: `backend/app/assessment/models/grading.py`
- Create: `backend/app/notifications/models.py`
- Create: `backend/app/knowledge/models.py`
- Create: `backend/app/ai_runtime/models.py`
- Create: `backend/app/runtime/models.py`
- Create: `backend/app/search/models.py`
- Create: `backend/app/audit/models.py`
- Create: `backend/app/core/models.py`
- Create: `backend/tests/factories.py`

**Consumes：** 使用T02的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
SqlAlchemyUow.__enter__(self) -> SqlAlchemyUow
SqlAlchemyUow.commit(self) -> None
SqlAlchemyUow.rollback(self) -> None
make_uow() -> SqlAlchemyUow
metadata_contract() -> SchemaManifest
~~~

**类型与规则：** ORM具体类/路径见附录A；每请求/worker独立Session。SchemaManifest={tables,indexes,foreign_keys}; UowFactory=Callable[[],SqlAlchemyUow]；repositories只flush不commit。

- [x] **T03.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_initial_answer_revision_zero(db_session, empty_answer):
    db_session.add(empty_answer)
    db_session.flush()
    assert empty_answer.answer_revision == 0
~~~

- [x] **T03.1.1** test_all_40_tables_present：表集合等于附录A。
- [x] **T03.1.2** test_initial_answer_revision_zero：默认0。
- [x] **T03.1.3** test_attempt_round_unique：同application/round插入冲突。
- [x] **T03.1.4** test_current_pointers_nullable_then_fk：首迁移可空，次迁移FK存在。
- [x] **T03.1.5** test_migration_roundtrip：独立空测试库upgrade→downgrade→upgrade，版本一致。

- [x] **T03.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T03.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T03.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api alembic upgrade head；python scripts/compose.py exec -T api python -m pytest tests/integration/test_schema_contract.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：真实MySQL迁移及索引约束通过；循环FK后置建立；不得在现有业务库downgrade。；conftest/factories定义独立MySQL/Redis命名空间、UowFactory、FrozenClock、角色/岗位/试卷/考次工厂，单元替身与真实集成fixtures分离；fixture中不回写现有数据库。

- [x] **T03.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t03-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T03.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/core/db.py' 'backend/app/core/uow.py' 'backend/alembic/env.py' 'backend/alembic/versions/0001_entities.py' 'backend/alembic/versions/0002_current_pointers.py' 'backend/tests/integration/test_schema_contract.py' 'backend/app/identity/models.py' 'backend/app/files/models.py' 'backend/app/jobs/models.py' 'backend/app/ingestion/models.py' 'backend/app/talents/models.py' 'backend/app/recruitment/models.py' 'backend/app/evaluation/models.py' 'backend/app/assessment/models/papers.py' 'backend/app/assessment/models/exams.py' 'backend/app/assessment/models/grading.py' 'backend/app/notifications/models.py' 'backend/app/knowledge/models.py' 'backend/app/ai_runtime/models.py' 'backend/app/runtime/models.py' 'backend/app/search/models.py' 'backend/app/audit/models.py' 'backend/app/core/models.py' 'backend/tests/factories.py'
git commit -m 'feat: T03 40表ORM与可重复迁移'
~~~

### T04 时间、权限上下文、审计与通用幂等

**阶段/前置：** M1；T03。**需求：** FR-01、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `backend/app/core/clock.py`
- Create: `backend/app/core/access.py`
- Create: `backend/app/core/idempotency.py`
- Create: `backend/app/audit/service.py`
- Create: `backend/tests/unit/test_access.py`
- Create: `backend/tests/integration/test_idempotency.py`

**Consumes：** 使用T03的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
Clock.now(self) -> datetime
AccessPolicy.require(self, actor: ActorContext, permission: str, resource: ResourceScope) -> None
IdempotencyService.execute(self, actor: ActorContext, operation: str, key: str, payload_hash: str, command: Callable[[SqlAlchemyUow], ResultRef]) -> ResultRef
AuditService.append(self, uow: SqlAlchemyUow, actor: ActorContext, event: AuditEvent) -> None
~~~

**类型与规则：** ActorContext={actor_type,user_id?,candidate_id?,attempt_id?,department_ids,permissions}; ResourceScope={kind,id?,department_id?,shared}; ResultRef={entity_type,entity_id,response_code}; AuditEvent={action,resource,summary,result,request_id}; Clock始终UTC，FrozenClock供测试。

- [x] **T04.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_admin_not_hr(policy, admin_actor, shared_talent_scope):
    with pytest.raises(PermissionDenied):
        policy.require(admin_actor, "talent.read", shared_talent_scope)
~~~

- [x] **T04.1.1** test_admin_not_hr：管理员无talent.read不能读。
- [x] **T04.1.2** test_same_key_different_hash_409：相同key异内容冲突。
- [x] **T04.1.3** test_idempotency_and_business_commit_together：业务回滚幂等不留completed。
- [x] **T04.1.4** test_audit_redacts_secrets：token/答案/密码不入日志。

- [x] **T04.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T04.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T04.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/unit/test_access.py tests/integration/test_idempotency.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：同事务写审计和幂等；读取权限也覆盖详情/文件/检索，后台与候选人不混用上下文。；关键Service自己调用IdempotencyService.execute并将持久化动作作为command(uow)传入，同事务完成；router不在外层再包另一事务，callback不得新建Session或commit。

- [x] **T04.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t04-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T04.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/core/clock.py' 'backend/app/core/access.py' 'backend/app/core/idempotency.py' 'backend/app/audit/service.py' 'backend/tests/unit/test_access.py' 'backend/tests/integration/test_idempotency.py'
git commit -m 'feat: T04 时间、权限上下文、审计与通用幂等'
~~~

### T05 后台登录、会话与组织账号管理

**阶段/前置：** M1；T04。**需求：** FR-01。**负责接口：** API-001、API-002、API-003、API-005、API-006、API-008、API-009、API-011、API-012、API-013。

**文件：**

- Create: `backend/app/identity/auth_service.py`
- Create: `backend/app/identity/admin_service.py`
- Create: `backend/app/identity/session_store.py`
- Create: `backend/app/identity/router.py`
- Create: `backend/app/identity/schemas.py`
- Create: `backend/tests/integration/test_identity.py`

**Consumes：** 使用T04的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
AuthService.login(self, cmd: LoginCommand) -> StaffSessionView
AuthService.me(self, actor: ActorContext) -> UserView
AuthService.logout(self, session_id: str) -> None
IdentityAdminService.create_user(self, actor: ActorContext, cmd: UserCreate) -> UserView
IdentityAdminService.update_user(self, actor: ActorContext, user_id: int, cmd: UserPatch, expected_version: int) -> UserView
IdentityAdminService.set_roles(self, actor: ActorContext, user_id: int, role_ids: list[int], expected_version: int) -> UserView
IdentityAdminService.upsert_department(self, actor: ActorContext, department_id: int | None, cmd: DepartmentWrite) -> DepartmentView
IdentityAdminService.upsert_role(self, actor: ActorContext, role_id: int | None, cmd: RoleWrite) -> RoleView
~~~

**类型与规则：** LoginCommand={login_name,password}; UserCreate={login_name,password,department_id,status}; UserPatch={department_id?,status?,password?}; DepartmentWrite={name,parent_id?,status}; RoleWrite={code,name,permission_codes,data_scope,status}; User/Department/RoleView采用05封套，列表与角色查询走本模块ReadService（附录B）。

- [x] **T05.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_disable_revokes_cookie(admin_client, logged_in_hr, disable_command):
    admin_client.patch(disable_command.path, json=disable_command.body,
                       headers=disable_command.headers)
    assert logged_in_hr.get("/api/v1/auth/me").status_code == 401
~~~

- [x] **T05.1.1** test_argon2_hash_only：库中非明文密码。
- [x] **T05.1.2** test_disable_revokes_cookie：禁用旧会话立即401。
- [x] **T05.1.3** test_role_change_refreshes_permissions：权限缩减立即生效。
- [x] **T05.1.4** test_department_no_cycle：父子循环422。
- [x] **T05.1.5** test_csrf_required_for_write：仅Cookie无CSRF写请求403。

- [x] **T05.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T05.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T05.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_identity.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：API-001～013可调用；准备管理员、两个部门HR测试账号，无公开默认密码。

- [x] **T05.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t05-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T05.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/identity/auth_service.py' 'backend/app/identity/admin_service.py' 'backend/app/identity/session_store.py' 'backend/app/identity/router.py' 'backend/app/identity/schemas.py' 'backend/tests/integration/test_identity.py'
git commit -m 'feat: T05 后台登录、会话与组织账号管理'
~~~

### T06 持久任务、outbox与租约恢复

**阶段/前置：** M1；T04。**需求：** FR-03、FR-09、FR-15。**负责接口：** API-098。

**文件：**

- Create: `backend/app/runtime/job_service.py`
- Create: `backend/app/runtime/outbox.py`
- Create: `backend/app/runtime/worker.py`
- Create: `backend/app/runtime/scheduler.py`
- Create: `backend/app/runtime/router.py`
- Create: `backend/tests/integration/test_outbox.py`
- Create: `backend/app/runtime/queries.py`

**Consumes：** 使用T04的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
BackgroundJobService.enqueue(self, uow: SqlAlchemyUow, spec: JobSpec) -> int
BackgroundJobService.claim(self, job_id: int, worker_id: str) -> JobLease | None
BackgroundJobService.complete(self, lease: JobLease, result: ResultRef) -> None
OutboxDispatcher.dispatch_due(self, limit: int) -> DispatchReport
LeaseRecovery.requeue_expired(self, now: datetime, limit: int) -> int
execute_job(job_id: int) -> None
RuntimeQueries.task(self, actor: ActorContext, task_id: int) -> TaskView
~~~

**类型与规则：** JobSpec={job_type,entity_type,entity_id,idempotency_key,input_refs}; JobLease={job_id,lease_owner,lease_until}; DispatchReport={claimed,sent,failed}; worker注册固定job_type处理器，未知类型拒绝。结果引用存领域表；scheduler只能一个实例。

- [x] **T06.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_redis_down_keeps_outbox(dispatcher, uow, pending_event, redis_down):
    dispatcher.dispatch_due(limit=10)
    event = uow.session.get(OutboxEvent, pending_event.id)
    assert event.state in {"pending", "failed"}
    assert event.private_payload_ciphertext is None or event.expires_at is not None
~~~

- [x] **T06.1.1** test_redis_down_keeps_outbox：DB提交后Redis失败可补投。
- [x] **T06.1.2** test_duplicate_delivery_single_effect：重复消息只完成一次。
- [x] **T06.1.3** test_expired_lease_recovered：崩溃后租约到期重领。
- [x] **T06.1.4** test_outbox_commit_order：未提交事务不得被派发。

- [x] **T06.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T06.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T06.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_outbox.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：202只代表受理；任务明细可按资源授权轮询；进度显示真实阶段，不伪造百分比。

- [x] **T06.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t06-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T06.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/runtime/job_service.py' 'backend/app/runtime/outbox.py' 'backend/app/runtime/worker.py' 'backend/app/runtime/scheduler.py' 'backend/app/runtime/router.py' 'backend/tests/integration/test_outbox.py' 'backend/app/runtime/queries.py'
git commit -m 'feat: T06 持久任务、outbox与租约恢复'
~~~

### T07 私有文件、上传校验与下载授权

**阶段/前置：** M1；T04。**需求：** FR-03。**负责接口：** API-099。

**文件：**

- Create: `backend/app/files/storage.py`
- Create: `backend/app/files/service.py`
- Create: `backend/app/files/router.py`
- Create: `backend/tests/integration/test_files.py`

**Consumes：** 使用T04的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
S3FileStore.put(self, key: str, stream: BinaryIO, content_type: str) -> StoredObject
S3FileStore.get(self, key: str) -> BinaryIO
FileService.stage(self, actor: ActorContext, upload: UploadDescriptor) -> FileView
FileService.authorized_download(self, actor: ActorContext, file_id: int) -> DownloadGrant
FileService.cleanup_orphans(self, before: datetime) -> int
~~~

**类型与规则：** UploadDescriptor={name,content_type,size,stream}; StoredObject={key,etag}; FileView={id,name,mime,size,sha256}; DownloadGrant={url,expires_at}或流代理。大小20MiB/100页/单批50是可配置D默认，超限413。

- [x] **T07.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_private_bucket_no_anonymous_get(private_file_url, anonymous_http):
    response = anonymous_http.get(private_file_url)
    assert response.status_code in {401, 403}
~~~

- [x] **T07.1.1** test_extension_mime_mismatch_rejected：伪装可执行文件拒绝。
- [x] **T07.1.2** test_private_bucket_no_anonymous_get：匿名不能读。
- [x] **T07.1.3** test_cross_department_exam_file_denied：关联资料按领域权限。
- [x] **T07.1.4** test_path_traversal_filename_safe：../仅作原名显示，不作为存储路径。

- [x] **T07.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T07.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T07.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_files.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：真实MinIO读写与授权下载通过；业务桶与Milvus内部桶隔离；孤儿清理仅删无引用过期对象。

- [x] **T07.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t07-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T07.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/files/storage.py' 'backend/app/files/service.py' 'backend/app/files/router.py' 'backend/tests/integration/test_files.py'
git commit -m 'feat: T07 私有文件、上传校验与下载授权'
~~~

### T08 模型配置、提示词与固定流程管理

**阶段/前置：** M1；T05、T06。**需求：** FR-15。**负责接口：** API-088、API-089、API-091、API-092、API-093。

**文件：**

- Create: `backend/app/ai_runtime/config_service.py`
- Create: `backend/app/ai_runtime/prompt_service.py`
- Create: `backend/app/ai_runtime/router.py`
- Create: `backend/app/ai_runtime/schemas.py`
- Create: `backend/app/core/secrets.py`
- Create: `backend/tests/integration/test_ai_config.py`

**Consumes：** 使用T05、T06的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ModelConfigService.create_revision(self, actor: ActorContext, cmd: ModelConfigCreate) -> MaskedModelConfig
ModelConfigService.test(self, actor: ActorContext, config_id: int) -> CapabilityTest
PromptService.create(self, actor: ActorContext, cmd: PromptCreate) -> PromptView
PromptService.publish(self, actor: ActorContext, prompt_id: int, reason: str) -> PromptView
WorkflowConfigService.configure(self, actor: ActorContext, task_type: str, cmd: WorkflowWrite, expected_version: int) -> WorkflowView
SecretCipher.encrypt(self, plaintext: str) -> str
SecretCipher.decrypt(self, ciphertext: str) -> str
~~~

**类型与规则：** ModelConfigCreate/WorkflowWrite/PromptCreate字段按05；task_type白名单extract/profile/match/question_generation/grade/knowledge_ask/embedding。CapabilityTest={verified,capabilities,model_digest,embedding_dimension?,error_code?}；连接测试合成输入，不传真实资料。

- [x] **T08.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_unverified_model_cannot_enable(workflow_service, admin_actor, unverified_workflow):
    with pytest.raises(ModelNotVerified):
        workflow_service.configure(admin_actor, "match", unverified_workflow, expected_version=1)
~~~

- [x] **T08.1.1** test_secret_write_only：响应无明文及ciphertext。
- [x] **T08.1.2** test_url_allowlist_blocks_ssrf：未知目标拒绝测试。
- [x] **T08.1.3** test_unverified_model_cannot_enable：能力未确认不能启用。
- [x] **T08.1.4** test_prompt_published_immutable：已发布内容不可原位改。

- [x] **T08.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T08.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T08.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_ai_config.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：管理员能配置本地模型修订与提示词，不执行任意脚本；实际凭据只在后续用户授权配置时取得。

- [x] **T08.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t08-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T08.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/ai_runtime/config_service.py' 'backend/app/ai_runtime/prompt_service.py' 'backend/app/ai_runtime/router.py' 'backend/app/ai_runtime/schemas.py' 'backend/app/core/secrets.py' 'backend/tests/integration/test_ai_config.py'
git commit -m 'feat: T08 模型配置、提示词与固定流程管理'
~~~

### T09 模型网关和结构化输出验证

**阶段/前置：** M1；T08。**需求：** FR-06、FR-07、FR-08、FR-11、FR-13。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `backend/app/ai_runtime/gateway.py`
- Create: `backend/app/ai_runtime/ollama_adapter.py`
- Create: `backend/app/ai_runtime/graphs.py`
- Create: `backend/tests/unit/test_model_validation.py`
- Create: `backend/tests/integration/test_model_gateway.py`

**Consumes：** 使用T08的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ModelGateway.generate(self, request: GenerationRequest, output_type: type[T]) -> GenerationResult[T]
ModelGateway.embed(self, texts: list[str], model_config_id: int) -> EmbeddingBatch
FixedGraphRunner.run(self, task_type: str, input_data: dict[str, JsonValue], config: AiConfigSnapshot) -> ValidatedAiResult
OllamaAdapter.generate(self, request: GenerationRequest) -> RawModelResponse
~~~

**类型与规则：** GenerationRequest={task_type,model_config_id,prompt_version_id,input_refs,evidence,output_schema}; GenerationResult<T>={value,ai_run_id}; EmbeddingBatch={vectors,dimension,model_digest:Optional[str],model_config_id,revision_no,model_name}; AiConfigSnapshot={model_config_id,prompt_version_id,timeout,max_retries,config_revision}; ValidatedAiResult={output,ai_run_id}; RawModelResponse只在适配器内部。

- [x] **T09.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_embedding_dimension_consistent(gateway, embedding_config_id):
    result = gateway.embed(["Python数据分析", "算法工程经历"], embedding_config_id)
    assert len(result.vectors) == 2
    assert all(len(v) == result.dimension for v in result.vectors)
    assert result.model_config_id == embedding_config_id
    assert result.revision_no >= 1  # cloud digest=None; local actual digest required
~~~

- [x] **T09.1.1** test_invalid_json_not_success：不合schema转invalid。
- [x] **T09.1.2** test_evidence_required：编造来源不得成功。
- [x] **T09.1.3** test_prompt_injection_data_not_instruction：资料诱导不具业务写权限。
- [x] **T09.1.4** test_embedding_dimension_consistent：整批维度一致；本地核验真实digest，云端记录配置修订并保持digest=None。

- [x] **T09.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T09.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T09.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/unit/test_model_validation.py tests/integration/test_model_gateway.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：真实模型能返回结构化数据与向量；固定LangGraph子图无发邮件等副作用；不合格小模型阻塞质量门，不填固定答复。

- [x] **T09.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t09-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T09.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/ai_runtime/gateway.py' 'backend/app/ai_runtime/ollama_adapter.py' 'backend/app/ai_runtime/graphs.py' 'backend/tests/unit/test_model_validation.py' 'backend/tests/integration/test_model_gateway.py'
git commit -m 'feat: T09 模型网关和结构化输出验证'
~~~

**2026-11-06完成：** Docker经用户授权重启后恢复，最终完整186通过（118.16s）；真实模型3组合成履历与3条1024维向量通过。付费门独立CLI python scripts/compose.py exec -T api python -m app.ai_runtime.verify_gateway，普通pytest不调用。代码4641161，证据artifacts/t09-verification.md及t09-clean-final-suite.log。下一步T12。

### T10 邮件配置测试、激活与安全发送适配器

**阶段/前置：** M1；T05、T06、T08。**需求：** FR-09、FR-15。**负责接口：** API-096、API-097、API-103、API-104。

**文件：**

- Create: `backend/app/notifications/config_service.py`
- Create: `backend/app/notifications/smtp_adapter.py`
- Create: `backend/app/notifications/router.py`
- Create: `backend/tests/integration/test_mail_config.py`

**Consumes：** 使用T05、T06、T08的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
MailConfigService.create(self, actor: ActorContext, cmd: MailConfigWrite) -> MaskedMailConfig
MailConfigService.test(self, actor: ActorContext, config_id: int, recipient: str) -> TaskAccepted
MailConfigService.activate(self, actor: ActorContext, config_id: int, expected_version: int, reason: str) -> MaskedMailConfig
MailConfigService.disable(self, actor: ActorContext, config_id: int, expected_version: int, reason: str) -> MaskedMailConfig
SmtpAdapter.send(self, config: MailConnection, message: MailMessage) -> DeliveryResult
~~~

**类型与规则：** MailConfigWrite见05；MailConnection={config_id,host,port,tls_mode,sender,credential_ref}; MailMessage={recipient,subject,body,message_id}; DeliveryResult={status:accepted|failed|unknown,provider_message_id?,error_code?}。TCP已连接后响应超时须unknown。

- [x] **T10.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_only_verified_config_active(mail_service, admin_actor, draft_mail):
    with pytest.raises(MailConfigNotVerified):
        mail_service.activate(admin_actor, draft_mail.id, draft_mail.row_version, "启用")
~~~

- [x] **T10.1.1** test_only_verified_config_active：未验证不能激活。
- [x] **T10.1.2** test_activate_single_active：并发激活最终只有一个active。
- [x] **T10.1.3** test_notification_freezes_config_id：每封信关联发送修订。
- [x] **T10.1.4** test_mailpit_actual_receive：测试收件箱真实收到配置测试信。

- [x] **T10.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T10.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T10.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_mail_config.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：本地Mailpit收到真实SMTP消息；正式TLS和PUBLIC_BASE_URL校验独立，未连接企业SMTP不称外部送达。

- [x] **T10.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t10-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T10.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/notifications/config_service.py' 'backend/app/notifications/smtp_adapter.py' 'backend/app/notifications/router.py' 'backend/tests/integration/test_mail_config.py'
git commit -m 'feat: T10 邮件配置测试、激活与安全发送适配器'
~~~

### T11 题库与不可变岗位试卷

**阶段/前置：** M2；T05、T04。**需求：** FR-08。**负责接口：** API-047、API-048、API-050、API-051、API-054、API-055、API-056、API-058。

**文件：**

- Create: `backend/app/assessment/question_service.py`
- Create: `backend/app/assessment/paper_service.py`
- Create: `backend/app/assessment/paper_router.py`
- Create: `backend/app/assessment/schemas.py`
- Create: `backend/tests/integration/test_paper_versions.py`

**Consumes：** 使用T05、T04的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
QuestionService.create(self, actor: ActorContext, cmd: QuestionDraft) -> QuestionView
QuestionService.revise(self, actor: ActorContext, question_id: int, cmd: QuestionDraft, reason: str) -> QuestionView
QuestionService.approve(self, actor: ActorContext, question_id: int, reason: str) -> QuestionView
PaperService.create(self, actor: ActorContext, cmd: PaperCreate) -> PaperView
PaperService.draft_version(self, actor: ActorContext, paper_id: int, cmd: PaperVersionDraft) -> PaperVersionView
PaperService.edit_draft(self, actor: ActorContext, version_id: int, cmd: PaperVersionDraft, expected_version: int) -> PaperVersionView
PaperService.publish(self, actor: ActorContext, version_id: int, reason: str) -> PaperVersionView
QuestionService.create_bank(self, actor: ActorContext, cmd: QuestionBankCreate) -> QuestionBankView
~~~

**类型与规则：** QuestionDraft/PaperVersionDraft按05；PaperCreate={name,department_id}; QuestionBankCreate={name,department_id}；手工建立试卷用于先跑闭环，不要求先完成AI出题。

- [x] **T11.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_published_paper_frozen(paper_service, hr_actor, published_paper, revised_bank_question):
    frozen = published_paper.items[0]
    assert frozen.stem != revised_bank_question.stem
    assert frozen.answer_key == published_paper.original_answer_key
~~~

- [x] **T11.1.1** test_only_approved_questions_publish：草稿题不能入发布卷。
- [x] **T11.1.2** test_published_paper_frozen：题库改版后旧卷题干/答案/量表不变。
- [x] **T11.1.3** test_total_score_computed：后端求和，多选全对规则冻结。
- [x] **T11.1.4** test_candidate_projection_no_answer：候选DTO不含answer_key/rubric。

- [x] **T11.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T11.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T11.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_paper_versions.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：至少发布岗位A和B不同试卷；所有题型标准完整，满分大于0，时长大于0。

- [x] **T11.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t11-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T11.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/assessment/question_service.py' 'backend/app/assessment/paper_service.py' 'backend/app/assessment/paper_router.py' 'backend/app/assessment/schemas.py' 'backend/tests/integration/test_paper_versions.py'
git commit -m 'feat: T11 题库与不可变岗位试卷'
~~~

### T12 岗位版本与自动邀请配置

**阶段/前置：** M2；T11、T09、T10。**需求：** FR-02。**负责接口：** API-015、API-016、API-018、API-019、API-020、API-021、API-022。

**文件：**

- Create: `backend/app/jobs/service.py`
- Create: `backend/app/jobs/router.py`
- Create: `backend/app/jobs/schemas.py`
- Create: `backend/tests/integration/test_job_versions.py`

**Consumes：** 使用T11、T09、T10的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
JobService.create(self, actor: ActorContext, cmd: JobCreate) -> JobView
JobService.update(self, actor: ActorContext, job_id: int, cmd: JobPatch, expected_version: int) -> JobView
JobService.draft(self, actor: ActorContext, job_id: int, cmd: JobVersionDraft) -> JobVersionView
JobService.edit_draft(self, actor: ActorContext, version_id: int, cmd: JobVersionDraft, expected_version: int) -> JobVersionView
JobService.publish(self, actor: ActorContext, version_id: int, reason: str) -> JobVersionView
JobService.transition(self, actor: ActorContext, job_id: int, action: str, expected_version: int, reason: str) -> JobView
JobService.set_automation(self, actor: ActorContext, job_id: int, enabled: bool, expected_version: int) -> AutomationView
~~~

**类型与规则：** JobCreate={title,department_id,headcount}; JobPatch={title?,headcount?,owner_hr_id?}; JobVersionDraft见05；AutomationView={job,readiness:{ready,blocking_reasons}}。仅open且卷/邮件/AI就绪可开启，默认false。

- [x] **T12.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_default_automation_off(job_service, hr_actor, valid_job_command):
    job = job_service.create(hr_actor, valid_job_command)
    assert job.auto_invite_enabled is False
    assert job.status == "draft"
~~~

- [x] **T12.1.1** test_default_automation_off：建岗不发信。
- [x] **T12.1.2** test_required_before_enable：缺卷/模型/邮件返回409及原因。
- [x] **T12.1.3** test_weights_sum_100：50/35/15合法，和非100拒绝。
- [x] **T12.1.4** test_published_job_version_immutable：修改发布内容必须新版本。
- [x] **T12.1.5** test_current_version_owner_mismatch：其他岗位版本不可设为current。

- [x] **T12.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T12.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T12.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_job_versions.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：岗位版本与试卷版本归属/权限验证正确；暂停/关闭只阻止后续动作，不修改历史。；开关false→true时追加invite.scan事件。T12只验收生产事件；T22/T23负责消费时扫描尚未有考次的首次auto_allowed匹配记录，不复活manual_only、revoked和历史已邀考记录。

- [x] **T12.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t12-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T12.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/jobs/service.py' 'backend/app/jobs/router.py' 'backend/app/jobs/schemas.py' 'backend/tests/integration/test_job_versions.py'
git commit -m 'feat: T12 岗位版本与自动邀请配置'
~~~

### T13 PDF、Word、扫描件与图片解析适配器

**阶段/前置：** M2；T07、T09。**需求：** FR-03。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `backend/app/ingestion/parsers.py`
- Create: `backend/app/ingestion/extraction.py`
- Create: `infra/ocr/Dockerfile`
- Create: `backend/tests/unit/test_parser_selection.py`
- Create: `backend/tests/integration/test_resume_formats.py`

**Consumes：** 使用T07、T09的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ParserRegistry.select(self, descriptor: FileView) -> ResumeParser
ResumeParser.parse(self, source: BinaryIO) -> ParsedDocument
PdfParser.parse(self, source: BinaryIO) -> ParsedDocument
DocxParser.parse(self, source: BinaryIO) -> ParsedDocument
OcrParser.parse(self, source: BinaryIO) -> ParsedDocument
LegacyDocParser.parse(self, source: BinaryIO) -> ParsedDocument
ResumeExtractor.extract(self, document: ParsedDocument, config: AiConfigSnapshot) -> ExtractedResume
~~~

**类型与规则：** ParsedDocument={pages:[{number,paragraphs:[{id,text}]}],parser_revision}; ExtractedResume={identity,contacts,education,employment,projects,skills,certificates,field_sources,ai_run_id}; ResumeParser为Protocol。超页数/加密/损坏返回明确错误，不生成假字段。

- [ ] **T13.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_missing_email_remains_unknown(extractor, document_without_email, extraction_config):
    result = extractor.extract(document_without_email, extraction_config)
    assert result.contacts.email is None
    assert "@" not in str(result.contacts.email or "")
~~~

- [x] **T13.1.1** test_text_pdf_no_ocr_needed：文本PDF保留段落。
- [ ] **T13.1.2** test_scan_routes_to_ocr：扫描件真实OCR。
- [ ] **T13.1.3** test_doc_conversion_timeout：旧DOC转换超时可控终止且临时文件清理。
- [x] **T13.1.4** test_missing_email_remains_unknown：不编造邮箱。
- [ ] **T13.1.5** test_mixed_language_sources：中文英文来源可定位。

- [ ] **T13.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T13.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T13.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/unit/test_parser_selection.py tests/integration/test_resume_formats.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：五类真实样本输出带来源；OCR权重和LibreOffice版本固定。不可解析单份失败，不回滚其他文件。

- [ ] **T13.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t13-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T13.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/ingestion/parsers.py' 'backend/app/ingestion/extraction.py' 'infra/ocr/Dockerfile' 'backend/tests/unit/test_parser_selection.py' 'backend/tests/integration/test_resume_formats.py'
git commit -m 'feat: T13 PDF、Word、扫描件与图片解析适配器'
~~~

### T14 批量导入、任务排队和失败重试

**阶段/前置：** M2；T06、T07、T12。**需求：** FR-03。**负责接口：** API-023、API-024、API-025、API-026。

**文件：**

- Create: `backend/app/ingestion/service.py`
- Create: `backend/app/ingestion/router.py`
- Create: `backend/app/ingestion/schemas.py`
- Create: `backend/tests/integration/test_import_batches.py`

**Consumes：** 使用T06、T07、T12的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ImportService.create(self, actor: ActorContext, files: list[UploadDescriptor], job_id: int | None, request_key: str) -> ImportBatchView
ImportService.retry_item(self, actor: ActorContext, item_id: int, reason: str) -> TaskAccepted
ImportService.get_batch(self, actor: ActorContext, batch_id: int) -> BatchDetail
ImportService.list_batches(self, actor: ActorContext, query: PageQuery) -> Page[ImportBatchView]
~~~

**类型与规则：** ImportBatchView/BatchDetail字段按05；JobSpec input_refs仅file/import_item/job ID。批次独立事务建队列，每文件异常独立可重试，任务类型resume.parse由T15注册处理。

- [x] **T14.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_idempotent_batch(import_service, hr_actor, same_uploads, job_id):
    first = import_service.create(hr_actor, same_uploads(), job_id, "batch-key-1")
    second = import_service.create(hr_actor, same_uploads(), job_id, "batch-key-1")
    assert first.id == second.id
~~~

- [x] **T14.1.1** test_partial_failure_keeps_valid_items：混合批次部分成功。
- [x] **T14.1.2** test_idempotent_batch：重复key返回同批次。
- [x] **T14.1.3** test_no_job_import_no_invite：人才库导入不创建邀考。
- [x] **T14.1.4** test_file_limit_enforced：50份/20MiB/100页可配置且有错误。

- [x] **T14.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T14.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T14.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_import_batches.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：上传→文件存储→任务受理→轮询可查；T15之前实际解析处理尚未完成，不提前标闭环成功。

- [x] **T14.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t14-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T14.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/ingestion/service.py' 'backend/app/ingestion/router.py' 'backend/app/ingestion/schemas.py' 'backend/tests/integration/test_import_batches.py'
git commit -m 'feat: T14 批量导入、任务排队和失败重试'
~~~

### T15 人才建档、邮箱门槛与简历修订

**阶段/前置：** M2；T13、T14。**需求：** FR-03、FR-04。**负责接口：** API-029、API-030、API-035。

**文件：**

- Create: `backend/app/talents/candidate_service.py`
- Create: `backend/app/talents/identity_resolver.py`
- Create: `backend/app/ingestion/worker.py`
- Create: `backend/app/talents/router.py`
- Create: `backend/app/talents/schemas.py`
- Create: `backend/tests/integration/test_candidate_materialization.py`

**Consumes：** 使用T13、T14的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
CandidateService.materialize(self, item_id: int, extracted: ExtractedResume) -> MaterializationResult
CandidateService.update_contacts(self, actor: ActorContext, candidate_id: int, cmd: ContactsPatch, expected_version: int) -> TalentView
CandidateService.correct_resume(self, actor: ActorContext, candidate_id: int, cmd: ResumeCorrection) -> ResumeVersionView
CandidateService.archive(self, actor: ActorContext, candidate_id: int, reason: str, expected_version: int) -> TalentView
CanonicalResolver.resolve(self, uow: SqlAlchemyUow, candidate_id: int, lock: bool = False) -> CanonicalIdentity
handle_resume_parse(job_id: int) -> ResultRef
~~~

**类型与规则：** MaterializationResult={candidate_id,resume_version_id,application_id?,state,next_task?}; ContactsPatch={email?,phone?,reason}; ResumeCorrection={base_resume_version_id,changes,reason}; CanonicalIdentity={root_id,alias_ids}; ResumeVersionView按04字段但敏感内容受HR权限。

- [x] **T15.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_parsed_without_email_stays_pending(candidate_service, import_item, extracted_without_email):
    result = candidate_service.materialize(import_item.id, extracted_without_email)
    assert result.state == "pending_email"
    assert result.next_task is None
~~~

- [x] **T15.1.1** test_parsed_without_email_stays_pending：成功留库但不筛选邀考。
- [x] **T15.1.2** test_email_completion_resumes_pipeline：补齐后只继续一次。
- [x] **T15.1.3** test_same_name_not_merge：同名不自动合并。
- [x] **T15.1.4** test_correction_new_version：原解析结果仍可查。
- [x] **T15.1.5** test_canonical_cycle_rejected：别名环拒绝。

- [x] **T15.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T15.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T15.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_candidate_materialization.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：邮箱验证是格式/联系人完整性门槛，邮箱控制权由候选人核验；未决重复保持duplicate_review；同文件哈希不等于同一个人。

- [x] **T15.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t15-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T15.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/talents/candidate_service.py' 'backend/app/talents/identity_resolver.py' 'backend/app/ingestion/worker.py' 'backend/app/talents/router.py' 'backend/app/talents/schemas.py' 'backend/tests/integration/test_candidate_materialization.py'
git commit -m 'feat: T15 人才建档、邮箱门槛与简历修订'
~~~

### T16 重复确认及历史关系合并

**阶段/前置：** M2；T15。**需求：** FR-04。**负责接口：** API-033、API-034。

**文件：**

- Create: `backend/app/talents/merge_service.py`
- Create: `backend/app/talents/merge_router.py`
- Create: `backend/tests/integration/test_candidate_merge.py`

**Consumes：** 使用T15的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
DuplicateService.list_cases(self, actor: ActorContext, query: DuplicateQuery) -> Page[DuplicateCaseView]
DuplicateService.resolve(self, actor: ActorContext, case_id: int, cmd: MergeDecision, expected_version: int) -> MergeResult
MergePlanner.plan(self, uow: SqlAlchemyUow, cmd: MergeDecision) -> MergePlan
MergePlanner.apply(self, uow: SqlAlchemyUow, plan: MergePlan) -> MergeResult
~~~

**类型与规则：** MergeDecision={decision,target_candidate_id?,application_resolutions:[{job_id,primary_application_id,secondary_application_ids}],reason}; MergePlan={canonical_root,aliases,application_mappings,conflicts}; MergeResult={canonical_candidate_id,application_mappings}; 不将历史表candidate_id搬家。

- [x] **T16.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_active_attempt_conflict_no_partial_commit(duplicate_service, hr_actor, conflict_case, merge_command):
    with pytest.raises(MergeConflict):
        duplicate_service.resolve(hr_actor, conflict_case.id, merge_command, conflict_case.row_version)
    assert conflict_case.reload().status == "pending"
    assert conflict_case.candidate_a.reload().merged_into_id is None
~~~

- [x] **T16.1.1** test_merge_two_historical_applications：双方有同岗位历史考试仍可合并并保留。
- [x] **T16.1.2** test_active_attempt_conflict_no_partial_commit：冲突409，无部分迁移。
- [x] **T16.1.3** test_merge_lock_order：按ID排序锁根，防并发反向死锁。
- [x] **T16.1.4** test_unknown_other_department_denied：不能借合并读无权限评价。

- [x] **T16.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T16.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T16.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_candidate_merge.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：选择主应聘后次关系merged，原考试和版本归属不变；冲突需HR先处置，自动流程只处理主关系。；合并默认保留目标人才当前简历/共享画像指针，来源档案版本只作为历史聚合，HR明确修订才更换；去重结论使资料ready时追加一次pipeline.resume事件。

- [x] **T16.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t16-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T16.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/talents/merge_service.py' 'backend/app/talents/merge_router.py' 'backend/tests/integration/test_candidate_merge.py'
git commit -m 'feat: T16 重复确认及历史关系合并'
~~~

### T17 共享人才画像与岗位授权视图

**阶段/前置：** M2；T09、T15。**需求：** FR-06。**负责接口：** API-043、API-044。

**文件：**

- Create: `backend/app/talents/profile_service.py`
- Create: `backend/app/talents/profile_builder.py`
- Create: `backend/app/talents/profile_router.py`
- Create: `backend/tests/integration/test_profile_sources.py`

**Consumes：** 使用T09、T15的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ProfileBuilder.build(self, resume: ResumeVersionView, config: AiConfigSnapshot) -> ProfileDraft
ProfileService.generate(self, candidate_id: int, resume_version_id: int) -> ProfileView
ProfileService.get(self, actor: ActorContext, candidate_id: int, version_id: int | None = None) -> ProfileView
ProfileService.revise(self, actor: ActorContext, candidate_id: int, cmd: ProfileRevision) -> ProfileView
~~~

**类型与规则：** ProfileDraft={summary,skills,experiences,evidence}; ProfileRevision={base_profile_id,changes,reason}; ProfileView=共享字段＋authorized_application_views，后者从授权岗位动态查询，不传入共享AI摘要和向量。

- [x] **T17.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_no_private_interview_in_shared_summary(profile_service, hr_a, shared_candidate_with_private_note):
    profile = profile_service.get(hr_a, shared_candidate_with_private_note.id)
    assert "PRIVATE_EVALUATION_SENTINEL" not in profile.summary
    assert all(v.department_id in hr_a.department_ids for v in profile.authorized_application_views)
~~~

- [x] **T17.1.1** test_no_private_interview_in_shared_summary：私有评价不进摘要/向量。
- [x] **T17.1.2** test_all_claims_have_sources：claim来源须存在且归属本人才。
- [x] **T17.1.3** test_no_exam_no_radar：无正式测评不画虚构能力雷达。
- [x] **T17.1.4** test_manual_revision_preserves_ai_version：手工改动新版本。

- [x] **T17.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T17.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T17.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_profile_sources.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：画像是可核查经历与评价视图，不生成性格、忠诚度或稳定性预测；版本记录完整。

- [x] **T17.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t17-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T17.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/talents/profile_service.py' 'backend/app/talents/profile_builder.py' 'backend/app/talents/profile_router.py' 'backend/tests/integration/test_profile_sources.py'
git commit -m 'feat: T17 共享人才画像与岗位授权视图'
~~~

### T18 岗位硬条件三态规则引擎

**阶段/前置：** M2；T12、T15。**需求：** FR-05。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `backend/app/evaluation/rules.py`
- Create: `backend/app/evaluation/normalization.py`
- Create: `backend/app/evaluation/schemas.py`
- Create: `backend/tests/unit/test_screening_rules.py`

**Consumes：** 使用T12、T15的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ScreeningEngine.evaluate(self, facts: ResumeFacts, conditions: list[ScreeningCondition]) -> ScreeningReport
EducationNormalizer.normalize(self, value: str | None) -> EducationValue | None
MajorNormalizer.resolve(self, value: str | None, dictionary_revision: str) -> MajorResolution
ExperienceCalculator.relevant_years(self, employment: list[Employment], as_of: date) -> Decimal | None
~~~

**类型与规则：** ScreeningReport={result:pass|fail|unknown,details:[{condition_key,required,expected,actual,result,evidence}]}; ResumeFacts来自结构化简历；MajorResolution={canonical?,confidence,needs_review}; 重叠经历按区间并集，未知不是0。

- [x] **T18.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_preferred_missing_not_fail(engine, complete_required_facts, rules_with_missing_preferred):
    report = engine.evaluate(complete_required_facts, rules_with_missing_preferred)
    assert report.result == "pass"
~~~

- [x] **T18.1.1** test_required_truth_table：任一required unmet→fail；否则有unknown→unknown；全met→pass。
- [x] **T18.1.2** test_preferred_missing_not_fail：加分条件缺失不硬拒。
- [x] **T18.1.3** test_overlapping_employment_no_double_count：重叠日期按并集。
- [x] **T18.1.4** test_age_manual_only：年龄不参与默认自动评分。
- [x] **T18.1.5** test_unknown_major_requires_review：模糊专业不能硬通过。

- [x] **T18.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T18.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T18.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/unit/test_screening_rules.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：纯函数规则不调用模型/数据库；测试覆盖学历、专业、年限、技能、证书和缺失/冲突信息。

- [x] **T18.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t18-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T18.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/evaluation/rules.py' 'backend/app/evaluation/normalization.py' 'backend/app/evaluation/schemas.py' 'backend/tests/unit/test_screening_rules.py'
git commit -m 'feat: T18 岗位硬条件三态规则引擎'
~~~

### T19 应聘关系、评估快照与人工覆盖

**阶段/前置：** M2；T17、T18、T16。**需求：** FR-04、FR-05。**负责接口：** API-037、API-040、API-041、API-042。

**文件：**

- Create: `backend/app/recruitment/application_service.py`
- Create: `backend/app/evaluation/service.py`
- Create: `backend/app/evaluation/router.py`
- Create: `backend/tests/integration/test_evaluation_runs.py`
- Modify: `backend/app/talents/router.py`（首次创建于T15）

**Consumes：** 使用T17、T18、T16的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ApplicationService.add_candidates(self, actor: ActorContext, job_id: int, candidate_ids: list[int], source: str) -> list[ApplicationView]
EvaluationService.start(self, actor: ActorContext, application_id: int, cmd: EvaluationRequest) -> TaskAccepted
EvaluationService.screen(self, run_id: int) -> EvaluationView
EvaluationService.override(self, actor: ActorContext, run_id: int, reason: str) -> EvaluationView
EvaluationService.get(self, actor: ActorContext, run_id: int) -> EvaluationDetail
~~~

**类型与规则：** EvaluationRequest={resume_version_id?,reason}; EvaluationView/Detail见05；首次自动run.invitation_mode=auto_allowed，显式重评manual_only。覆盖写recruitment_events，不改已完成粗筛结果。

- [x] **T19.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_reevaluate_manual_only(evaluation_service, hr_actor, existing_application, reevaluation_cmd):
    accepted = evaluation_service.start(hr_actor, existing_application.id, reevaluation_cmd)
    assert accepted.state == "queued"
    assert existing_application.latest_run().invitation_mode == "manual_only"
~~~

- [x] **T19.1.1** test_one_canonical_application_per_job：锁canonical根复用同岗位关系。
- [x] **T19.1.2** test_missing_email_no_start：待邮箱/重复不进入自动评估。
- [x] **T19.1.3** test_override_keeps_original_result：覆盖有reason且不发卷。
- [x] **T19.1.4** test_stale_run_not_current：迟到旧任务不能覆盖新current指针。
- [x] **T19.1.5** test_reevaluate_manual_only：重评不自动重复邀请。

- [x] **T19.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [x] **T19.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [x] **T19.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_evaluation_runs.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：原始粗筛输出、岗位/简历/画像版本都冻结，人工推进是独立决定。

- [x] **T19.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t19-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [x] **T19.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/recruitment/application_service.py' 'backend/app/evaluation/service.py' 'backend/app/evaluation/router.py' 'backend/tests/integration/test_evaluation_runs.py' 'backend/app/talents/router.py'
git commit -m 'feat: T19 应聘关系、评估快照与人工覆盖'
~~~

### T20 真实语义索引与权限过滤检索

**阶段/前置：** M2；T09、T17、T16。**需求：** FR-04、FR-07、FR-13。**负责接口：** API-032、API-036。

**文件：**

- Create: `backend/app/search/milvus_store.py`
- Create: `backend/app/search/index_service.py`
- Create: `backend/app/search/talent_search.py`
- Create: `backend/tests/integration/test_semantic_search.py`
- Modify: `backend/app/talents/router.py`（首次创建于T15）

**Consumes：** 使用T09、T17、T16的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
MilvusStore.upsert(self, collection: str, records: list[VectorRecord]) -> None
MilvusStore.search(self, collection: str, vector: list[float], filters: SearchScope, top_k: int) -> list[VectorHit]
IndexService.sync(self, entity: IndexEntityRef, model_config_id: int) -> IndexSyncResult
TalentSearchService.search(self, actor: ActorContext, cmd: TalentSearchQuery) -> SemanticSearchResult
TalentSearchService.recommend(self, actor: ActorContext, job_id: int, query: TalentFilter) -> list[Recommendation]
~~~

**类型与规则：** VectorRecord={key,entity_id,entity_type,scope,department_id?,content_hash,vector}; VectorHit={entity_id,relevance}; IndexEntityRef={type,id}; IndexSyncResult={state,record_id}; TalentFilter与TalentSearchQuery见05；候选共享profile向量与知识chunk按类型/权限隔离。

- [ ] **T20.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_index_down_503_not_empty(hr_client, milvus_down, csrf_headers):
    response = hr_client.post("/api/v1/talents/search",
        json={"query": "有金融项目经验的Python工程师", "page_size": 20}, headers=csrf_headers)
    assert response.status_code == 503
    assert response.json()["code"] == "SEMANTIC_INDEX_UNAVAILABLE"
~~~

- [ ] **T20.1.1** test_milvus_real_roundtrip：真实SDK写入召回。
- [ ] **T20.1.2** test_stale_vector_filtered：归档/merged/旧版本召回后MySQL过滤。
- [ ] **T20.1.3** test_index_down_503_not_empty：索引故障明确不可用。
- [ ] **T20.1.4** test_private_evidence_not_indexed：共享向量无私有评价。
- [ ] **T20.1.5** test_new_embedding_dimension_new_collection：换模型维度不混写。

- [ ] **T20.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T20.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T20.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_semantic_search.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：自然语言找人真实可用；top_k/阈值可配置；相关度不当岗位分；索引失败可重建。

- [ ] **T20.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t20-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T20.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/search/milvus_store.py' 'backend/app/search/index_service.py' 'backend/app/search/talent_search.py' 'backend/tests/integration/test_semantic_search.py' 'backend/app/talents/router.py'
git commit -m 'feat: T20 真实语义索引与权限过滤检索'
~~~

### T21 岗位匹配评分与证据校验

**阶段/前置：** M2；T19、T20。**需求：** FR-07。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `backend/app/evaluation/match_service.py`
- Create: `backend/app/evaluation/match_scoring.py`
- Create: `backend/tests/unit/test_match_scoring.py`
- Create: `backend/tests/integration/test_match_pipeline.py`

**Consumes：** 使用T19、T20的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
MatchService.match(self, run_id: int) -> MatchView
MatchScorer.aggregate(self, dimensions: list[DimensionScore], weights: MatchWeights) -> Decimal
MatchEvidenceValidator.validate(self, draft: MatchDraft, evidence: list[EvidenceRef]) -> MatchValidation
~~~

**类型与规则：** MatchWeights={skills,experience,responsibilities}和100；DimensionScore={name,score?,evidence}; MatchDraft={dimensions,strengths,gaps,evidence}; MatchValidation={valid,unknown_dimensions,reasons}; MatchView见05。模型提出分项，服务端Decimal加权，禁止余弦×100。

- [ ] **T21.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_weighted_50_35_15(scorer, dimension_scores_80_60_100, default_weights):
    result = scorer.aggregate(dimension_scores_80_60_100, default_weights)
    assert result == Decimal("76.00")
~~~

- [ ] **T21.1.1** test_weighted_50_35_15：分项80/60/100结果76.00。
- [ ] **T21.1.2** test_unknown_dimension_blocks_invite：无证据维度unknown，不补0/100。
- [ ] **T21.1.3** test_match_bound_to_versions：结果引用本run输入版本。
- [ ] **T21.1.4** test_ai_failure_needs_review：模型失败不视作不合格。

- [ ] **T21.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T21.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T21.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/unit/test_match_scoring.py tests/integration/test_match_pipeline.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：硬筛未通过不触发自动匹配邀考；手动覆盖可以请求匹配，但邀请仍须显式动作。

- [ ] **T21.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t21-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T21.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/evaluation/match_service.py' 'backend/app/evaluation/match_scoring.py' 'backend/tests/unit/test_match_scoring.py' 'backend/tests/integration/test_match_pipeline.py'
git commit -m 'feat: T21 岗位匹配评分与证据校验'
~~~

### T22 邀请资格门与唯一考次创建

**阶段/前置：** M2；T21、T11、T10。**需求：** FR-09。**负责接口：** API-059、API-062、API-063。

**文件：**

- Create: `backend/app/assessment/invitation_service.py`
- Create: `backend/app/assessment/eligibility.py`
- Create: `backend/app/assessment/invitation_router.py`
- Create: `backend/tests/integration/test_invitation_eligibility.py`

**Consumes：** 使用T21、T11、T10的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
InvitationEligibility.check(self, snapshot: InvitationSnapshot, mode: str) -> EligibilityResult
InvitationService.issue(self, actor: ActorContext, application_id: int, cmd: InvitationRequest) -> AttemptView
InvitationService.issue_automatic(self, run_id: int) -> AttemptView | None
InvitationService.new_round(self, actor: ActorContext, application_id: int, cmd: NewRoundRequest) -> AttemptView
InvitationService.revoke(self, actor: ActorContext, attempt_id: int, reason: str, expected_version: int) -> AttemptView
InvitationService.scan_pending(self, job_id: int, limit: int) -> int
~~~

**类型与规则：** InvitationSnapshot={job_state,automation,email_valid,duplicate_clear,screening,match,paper_state,application_stage,invitation_mode,existing_attempt}; EligibilityResult={allowed,reasons}; InvitationRequest={evaluation_run_id,reason,manual_override?}; NewRoundRequest={paper_version_id,evaluation_run_id,reason}。同一canonical主应聘锁＋application/round唯一。

- [ ] **T22.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_all_gates_required(eligibility, snapshot_missing_email):
    result = eligibility.check(snapshot_missing_email, mode="automatic")
    assert result.allowed is False
    assert "EMAIL_REQUIRED" in result.reasons
~~~

- [ ] **T22.1.1** test_all_gates_required：任一前提失败不创建考次/外发事件。
- [ ] **T22.1.2** test_two_workers_one_attempt：并发自动触发只一考次。
- [ ] **T22.1.3** test_reassessment_manual_only：manual_only不得自动issue。
- [ ] **T22.1.4** test_manual_override_requires_reason：只覆盖业务筛选，不绕邮箱/卷/岗位。
- [ ] **T22.1.5** test_new_round_no_active_attempt：活动考次不能再开一轮。
- [ ] **T22.1.6** test_enable_later_scans_only_never_invited：关开切换只处理未邀考首次评估，不复活撤销或重评。

- [ ] **T22.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T22.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T22.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_invitation_eligibility.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：attempt冻结评估/试卷/邮箱/有效期；写考次、通知和outbox同事务；默认开关关闭不发送。

- [ ] **T22.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t22-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T22.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/assessment/invitation_service.py' 'backend/app/assessment/eligibility.py' 'backend/app/assessment/invitation_router.py' 'backend/tests/integration/test_invitation_eligibility.py'
git commit -m 'feat: T22 邀请资格门与唯一考次创建'
~~~

### T23 邮件投递、未知结果与重发

**阶段/前置：** M2；T22、T10、T06。**需求：** FR-09。**负责接口：** API-061。

**文件：**

- Create: `backend/app/notifications/delivery_service.py`
- Create: `backend/app/notifications/worker.py`
- Create: `backend/app/assessment/resend_service.py`
- Create: `backend/tests/integration/test_invitation_delivery.py`
- Modify: `backend/app/assessment/invitation_router.py`（首次创建于T22）

**Consumes：** 使用T22、T10、T06的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
NotificationDelivery.send(self, notification_id: int) -> DeliveryResult
InvitationResendService.resend(self, actor: ActorContext, attempt_id: int, reason: str) -> NotificationView
InvitationTokenService.rotate(self, uow: SqlAlchemyUow, attempt_id: int) -> EncryptedTokenPayload
handle_notification_send(job_id: int) -> ResultRef
~~~

**类型与规则：** NotificationView={id,attempt_id,purpose,status,mail_config_id,attempt_count,error_code?}; EncryptedTokenPayload={token_hash,ciphertext,expires_at}，仅敏感outbox短存；首次冻结active邮件修订，停用转待办，显式resend取新active修订并记新通知。

- [ ] **T23.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_timeout_after_accept_unknown(delivery_service, queued_notification, smtp_accept_then_timeout):
    result = delivery_service.send(queued_notification.id)
    assert result.status == "unknown"
    assert queued_notification.reload().status == "unknown"
~~~

- [ ] **T23.1.1** test_pause_before_send_revokes：发前暂停→notification.cancelled＋invite.revoked。
- [ ] **T23.1.2** test_timeout_after_accept_unknown：接受后超时unknown不盲重发。
- [ ] **T23.1.3** test_resend_same_attempt_rotates_token：未开考换token但考次不变。
- [ ] **T23.1.4** test_no_token_in_logs：token/验证码不入日志。
- [ ] **T23.1.5** test_mailpit_invitation_contents：岗位、时限、专属链接正确。

- [ ] **T23.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T23.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T23.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_invitation_delivery.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：测试收件箱真实收到岗位邀请，发送接受不标候选人已读；撤销入口不能再核验；已开考不允许resend。

- [ ] **T23.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t23-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T23.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/notifications/delivery_service.py' 'backend/app/notifications/worker.py' 'backend/app/assessment/resend_service.py' 'backend/tests/integration/test_invitation_delivery.py' 'backend/app/assessment/invitation_router.py'
git commit -m 'feat: T23 邮件投递、未知结果与重发'
~~~

### T24 候选人入口、邮箱核验与考次会话

**阶段/前置：** M2；T23、T05。**需求：** FR-10。**负责接口：** API-064、API-065、API-066。

**文件：**

- Create: `backend/app/assessment/access_service.py`
- Create: `backend/app/assessment/candidate_access_router.py`
- Create: `backend/app/assessment/code_store.py`
- Create: `backend/tests/integration/test_candidate_access.py`

**Consumes：** 使用T23、T05的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
CandidateAccessService.exchange(self, invitation_token: str) -> VerificationContext
CandidateAccessService.send_code(self, context_id: str) -> None
CandidateAccessService.verify(self, context_id: str, code: str) -> ExamSessionView
CodeStore.verify_once(self, challenge_id: str, code: str) -> bool
CandidateSessionStore.require(self, session_id: str) -> ActorContext
~~~

**类型与规则：** VerificationContext={id,masked_email,expires_at}; ExamSessionView={attempt_id,state}，会话token只写安全Cookie；验证码哈希/TTL/错误次数原子操作。参数中禁止接收可改写的收件邮箱。

- [ ] **T24.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_code_single_use_and_rate_limit(code_store, challenge_with_known_code):
    challenge_id, code = challenge_with_known_code
    assert code_store.verify_once(challenge_id, code) is True
    assert code_store.verify_once(challenge_id, code) is False
~~~

- [ ] **T24.1.1** test_unverified_no_questions：未验证响应无试题。
- [ ] **T24.1.2** test_code_single_use_and_rate_limit：用过/过期不能验证，限频429。
- [ ] **T24.1.3** test_revoked_link_fails：旧轮换/撤销token拒绝。
- [ ] **T24.1.4** test_session_bound_to_attempt：不能换ID读另一考次。
- [ ] **T24.1.5** test_invalid_token_no_email_leak：无效token不泄露完整邮箱。
- [ ] **T24.1.6** test_started_exam_reverify_before_deadline：已开考且deadline未到时可重新核验，即使开考有效期已过。

- [ ] **T24.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T24.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T24.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_candidate_access.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：只证明邮箱控制权，不宣传防替考；邀请过期410；后台与考次Cookie/CSRF隔离。；not_started检查valid_until，in_progress恢复只看deadline/撤销/本人状态；会话过期不延长考试截止。

- [ ] **T24.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t24-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T24.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/assessment/access_service.py' 'backend/app/assessment/candidate_access_router.py' 'backend/app/assessment/code_store.py' 'backend/tests/integration/test_candidate_access.py'
git commit -m 'feat: T24 候选人入口、邮箱核验与考次会话'
~~~

### T25 服务端计时、答题保存和统一提交

**阶段/前置：** M2；T24、T11、T06。**需求：** FR-10。**负责接口：** API-067、API-068、API-069、API-070、API-071。

**文件：**

- Create: `backend/app/assessment/exam_service.py`
- Create: `backend/app/assessment/answer_service.py`
- Create: `backend/app/assessment/candidate_exam_router.py`
- Create: `backend/app/assessment/deadline_service.py`
- Create: `backend/tests/integration/test_exam_lifecycle.py`
- Create: `backend/app/assessment/submission.py`

**Consumes：** 使用T24、T11、T06的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ExamService.get(self, actor: ActorContext) -> CandidateExamView
ExamService.start(self, actor: ActorContext, acknowledged: bool) -> CandidatePaperView
AnswerService.save(self, actor: ActorContext, item_id: int, cmd: AnswerSave) -> AnswerReceipt
ExamService.submit(self, actor: ActorContext, reason: str = "manual") -> SubmissionReceipt
DeadlineService.submit_due(self, now: datetime, limit: int) -> int
ExamService.receipt(self, actor: ActorContext) -> SubmissionReceipt
~~~

**类型与规则：** AnswerSave={answer,expected_revision}; CandidatePaperView/AnswerReceipt见05；start锁attempt并全题建空行revision=0；保存CAS，服务端deadline判断；统一submit_once内部函数供submit与DeadlineService共用，只有首次投评分事件。

- [ ] **T25.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_first_save_revision_zero(exam_service, answer_service, candidate_actor, first_answer_command):
    paper = exam_service.start(candidate_actor, acknowledged=True)
    assert paper.saved_answers[0].revision == 0
    receipt = answer_service.save(candidate_actor, paper.items[0].id, first_answer_command)
    assert receipt.revision == 1
~~~

- [ ] **T25.1.1** test_start_twice_same_deadline：重复开始不重置时间。
- [ ] **T25.1.2** test_first_save_revision_zero：expected_revision=0首次成功。
- [ ] **T25.1.3** test_save_conflict_409：双设备旧版本保存拒绝。
- [ ] **T25.1.4** test_deadline_submit_without_browser：浏览器关闭照样超时交卷。
- [ ] **T25.1.5** test_submit_vs_timeout_one_event：并发提交只冻结一次。
- [ ] **T25.1.6** test_candidates_never_get_answer_key：响应无标准答案。

- [ ] **T25.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T25.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T25.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_exam_lifecycle.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：邀请valid_until限制开考，deadline限制答题；暂停/关闭禁止新开考，已开考允许完成；GET只读有效状态，不偷偷写提交。

- [ ] **T25.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t25-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T25.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/assessment/exam_service.py' 'backend/app/assessment/answer_service.py' 'backend/app/assessment/candidate_exam_router.py' 'backend/app/assessment/deadline_service.py' 'backend/tests/integration/test_exam_lifecycle.py' 'backend/app/assessment/submission.py'
git commit -m 'feat: T25 服务端计时、答题保存和统一提交'
~~~

### T26 客观评分、主观建议与正式成绩版本

**阶段/前置：** M2；T25、T09。**需求：** FR-11。**负责接口：** API-073、API-074、API-075。

**文件：**

- Create: `backend/app/assessment/objective_scorer.py`
- Create: `backend/app/assessment/grading_service.py`
- Create: `backend/app/assessment/review_service.py`
- Create: `backend/app/assessment/grading_router.py`
- Create: `backend/tests/unit/test_objective_scoring.py`
- Create: `backend/tests/integration/test_score_reports.py`

**Consumes：** 使用T25、T09的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ObjectiveScorer.score(self, item: FrozenPaperItem, answer: AnswerValue | None) -> Decimal
GradingService.grade(self, attempt_id: int) -> GradingView
ScoreReviewService.review(self, actor: ActorContext, answer_id: int, cmd: ReviewCommand) -> ReviewView
ScoreReviewService.finalize(self, actor: ActorContext, attempt_id: int, expected_version: int, reason: str) -> FormalScoreView
ScoreReviewService.reopen(self, actor: ActorContext, attempt_id: int, expected_version: int, reason: str) -> GradingView
~~~

**类型与规则：** ReviewCommand={score,reason,expected_revision}; FrozenPaperItem={type,max_score,answer_key,rubric}; AnswerValue为选择keys或text；主观AI建议不写final_score，空题全部确定性0。正式score_reports包含全题快照；全客观卷用system actor自动finalize。

- [ ] **T26.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_multiple_choice_all_or_nothing(scorer, multi_item_ab):
    assert scorer.score(multi_item_ab, {"selected_keys": ["A", "B"]}) == Decimal("5.00")
    assert scorer.score(multi_item_ab, {"selected_keys": ["A"]}) == Decimal("0.00")
    assert scorer.score(multi_item_ab, None) == Decimal("0.00")
~~~

- [ ] **T26.1.1** test_multiple_choice_all_or_nothing：全对满分，漏/多选0。
- [ ] **T26.1.2** test_blank_subjective_zero_no_review_needed：未答简答0且不阻塞。
- [ ] **T26.1.3** test_ai_failure_manual_review：AI失败仍可HR评分。
- [ ] **T26.1.4** test_review_finalize_same_lock：并发题分和总分一致。
- [ ] **T26.1.5** test_finalized_cannot_direct_review：须reopen再生成新报告。
- [ ] **T26.1.6** test_score_reports_immutable：旧正式版本不能改。

- [ ] **T26.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T26.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T26.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/unit/test_objective_scoring.py tests/integration/test_score_reports.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：按paper_items全集核对，已答主观题全部复核才正式化；改分留reason与版本；候选人无成绩接口。

- [ ] **T26.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t26-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T26.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/assessment/objective_scorer.py' 'backend/app/assessment/grading_service.py' 'backend/app/assessment/review_service.py' 'backend/app/assessment/grading_router.py' 'backend/tests/unit/test_objective_scoring.py' 'backend/tests/integration/test_score_reports.py'
git commit -m 'feat: T26 客观评分、主观建议与正式成绩版本'
~~~

### T27 招聘阶段、面试评价与人工决定

**阶段/前置：** M2；T19、T26。**需求：** FR-12。**负责接口：** API-076、API-077、API-078。

**文件：**

- Create: `backend/app/recruitment/service.py`
- Create: `backend/app/recruitment/transitions.py`
- Create: `backend/app/recruitment/router.py`
- Create: `backend/tests/integration/test_recruitment_transitions.py`

**Consumes：** 使用T19、T26的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
RecruitmentService.transition(self, actor: ActorContext, application_id: int, cmd: StageTransition) -> ApplicationView
RecruitmentService.reopen(self, actor: ActorContext, application_id: int, expected_version: int, reason: str) -> ApplicationView
RecruitmentService.add_interview_note(self, actor: ActorContext, application_id: int, cmd: InterviewNote) -> RecruitmentEventView
TransitionPolicy.validate(self, current: str, target: str, has_active_exam: bool) -> None
~~~

**类型与规则：** StageTransition={to_stage,reason,expected_version}; InterviewNote={evaluation,interviewed_at}; 阶段字面值原样使用04；人工可带reason跳过非终态阶段，不抹去活动考试。

- [ ] **T27.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_no_ai_hire_action(recruitment_service, system_actor, application, hire_command):
    with pytest.raises(PermissionDenied):
        recruitment_service.transition(system_actor, application.id, hire_command)
~~~

- [ ] **T27.1.1** test_no_ai_hire_action：system/候选人不能调用HR录用。
- [ ] **T27.1.2** test_rejection_job_specific：岗位A拒绝不影响B。
- [ ] **T27.1.3** test_terminal_late_worker_no_invite：终态迟到任务不推进。
- [ ] **T27.1.4** test_reopen_explicit_event：复开留reason和事件。
- [ ] **T27.1.5** test_private_note_not_shared：面试备注只在岗位权限内。

- [ ] **T27.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T27.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T27.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_recruitment_transitions.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：面试安排/Offer/入职自动化未引入；所有人工阶段变化有事件和乐观锁。

- [ ] **T27.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t27-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T27.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/recruitment/service.py' 'backend/app/recruitment/transitions.py' 'backend/app/recruitment/router.py' 'backend/tests/integration/test_recruitment_transitions.py'
git commit -m 'feat: T27 招聘阶段、面试评价与人工决定'
~~~

### T28 查询服务、筛选分页与完整读接口

**阶段/前置：** M2；T27、T23、T21、T20。**需求：** FR-01、FR-02、FR-03、FR-04、FR-05、FR-06、FR-07、FR-08、FR-09、FR-11、FR-15。**负责接口：** API-004、API-007、API-010、API-014、API-017、API-027、API-028、API-031、API-038、API-039、API-045、API-046、API-049、API-053、API-057、API-060、API-072、API-087、API-090、API-102。

**文件：**

- Create: `backend/app/identity/queries.py`
- Create: `backend/app/jobs/queries.py`
- Create: `backend/app/talents/queries.py`
- Create: `backend/app/recruitment/queries.py`
- Create: `backend/app/assessment/queries.py`
- Modify: `backend/app/runtime/queries.py`（首次创建于T06）
- Create: `backend/tests/integration/test_read_permissions.py`
- Modify: `backend/app/identity/router.py`（首次创建于T05）
- Modify: `backend/app/jobs/router.py`（首次创建于T12）
- Modify: `backend/app/talents/router.py`（首次创建于T15）
- Modify: `backend/app/evaluation/router.py`（首次创建于T19）
- Modify: `backend/app/assessment/paper_router.py`（首次创建于T11）
- Modify: `backend/app/assessment/invitation_router.py`（首次创建于T22）
- Modify: `backend/app/assessment/grading_router.py`（首次创建于T26）
- Modify: `backend/app/ai_runtime/router.py`（首次创建于T08）
- Modify: `backend/app/notifications/router.py`（首次创建于T10）
- Create: `backend/app/runtime/admin_queries.py`

**Consumes：** 使用T27、T23、T21、T20的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
IdentityQueries.users(self, actor: ActorContext, query: PageQuery) -> Page[UserView]
JobQueries.jobs(self, actor: ActorContext, query: JobQuery) -> Page[JobView]
TalentQueries.talents(self, actor: ActorContext, query: TalentFilter) -> Page[TalentView]
TalentQueries.detail(self, actor: ActorContext, candidate_id: int) -> TalentDetail
ApplicationQueries.list(self, actor: ActorContext, query: ApplicationQuery) -> Page[ApplicationView]
ApplicationQueries.detail(self, actor: ActorContext, application_id: int) -> ApplicationDetail
AssessmentQueries.attempts(self, actor: ActorContext, query: AttemptQuery) -> Page[AttemptView]
IdentityQueries.departments(self, actor: ActorContext) -> list[DepartmentView]
IdentityQueries.roles(self, actor: ActorContext) -> list[RoleView]
JobQueries.detail(self, actor: ActorContext, job_id: int) -> JobDetail
TalentQueries.resumes(self, actor: ActorContext, candidate_id: int) -> list[ResumeVersionView]
AssessmentQueries.matches(self, actor: ActorContext, query: MatchQuery) -> Page[MatchView]
AssessmentQueries.banks(self, actor: ActorContext, query: PageQuery) -> Page[QuestionBankView]
AssessmentQueries.questions(self, actor: ActorContext, query: QuestionQuery) -> Page[QuestionView]
AssessmentQueries.papers(self, actor: ActorContext, query: PageQuery) -> Page[PaperView]
AssessmentQueries.paper_version(self, actor: ActorContext, version_id: int) -> PaperVersionView
AssessmentQueries.grading(self, actor: ActorContext, attempt_id: int) -> GradingView
RuntimeQueries.models(self, actor: ActorContext) -> list[MaskedModelConfig]
RuntimeQueries.workflows(self, actor: ActorContext) -> list[WorkflowView]
RuntimeQueries.mail_configs(self, actor: ActorContext) -> list[MaskedMailConfig]
~~~

**类型与规则：** 分页/过滤DTO以05为准；额外读方法、router与归属见附录B。detail包含已授权历史，不能因为人才共享就返回他部门答卷/备注。名单稳定排序，page_size上限100。

- [ ] **T28.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_admin_direct_talent_denied(admin_client, shared_candidate):
    response = admin_client.get(f"/api/v1/talents/{shared_candidate.id}")
    assert response.status_code in {403, 404}
~~~

- [ ] **T28.1.1** test_admin_direct_talent_denied：管理员知道ID也不能读。
- [ ] **T28.1.2** test_other_department_details_redacted：历史存在提示而非正文。
- [ ] **T28.1.3** test_stable_page_no_duplicates：固定排序无重复翻页。
- [ ] **T28.1.4** test_archived_talent_filter_explicit：归档不混进默认活跃推荐。
- [ ] **T28.1.5** test_task_follows_resource_permission：任务ID不能绕权限。

- [ ] **T28.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T28.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T28.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_read_permissions.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：附录B全部GET与搜索请求有明确handler及字段投影；不把ORM整对象自动序列化到前端。

- [ ] **T28.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t28-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T28.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/identity/queries.py' 'backend/app/jobs/queries.py' 'backend/app/talents/queries.py' 'backend/app/recruitment/queries.py' 'backend/app/assessment/queries.py' 'backend/app/runtime/queries.py' 'backend/tests/integration/test_read_permissions.py' 'backend/app/identity/router.py' 'backend/app/jobs/router.py' 'backend/app/talents/router.py' 'backend/app/evaluation/router.py' 'backend/app/assessment/paper_router.py' 'backend/app/assessment/invitation_router.py' 'backend/app/assessment/grading_router.py' 'backend/app/ai_runtime/router.py' 'backend/app/notifications/router.py' 'backend/app/runtime/admin_queries.py'
git commit -m 'feat: T28 查询服务、筛选分页与完整读接口'
~~~

### T29 最小可操作前端与考试页面

**阶段/前置：** M2；T05、T12、T14、T17、T22、T25、T26、T27、T28。**需求：** FR-01、FR-02、FR-03、FR-06、FR-09、FR-10、FR-11、FR-12。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/app/(staff)/layout.tsx`
- Create: `frontend/src/app/(staff)/hr/jobs/page.tsx`
- Create: `frontend/src/app/(staff)/hr/imports/page.tsx`
- Create: `frontend/src/app/(staff)/hr/applications/[id]/page.tsx`
- Create: `frontend/src/app/(staff)/hr/grading/[id]/page.tsx`
- Create: `frontend/src/app/exam/page.tsx`
- Create: `frontend/src/features/exam/ExamShell.tsx`
- Create: `frontend/src/features/exam/useExamAutosave.ts`
- Create: `frontend/tests/e2e/recruitment-smoke.spec.ts`
- Create: `frontend/tests/e2e/fixtures.ts`

**Consumes：** 使用T05、T12、T14、T17、T22、T25、T26、T27、T28的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
StaffLayout({children}: StaffLayoutProps): ReactNode
ExamShell({initial}: ExamShellProps): ReactNode
useExamAutosave(attemptId: string): ExamAutosaveController
useStaffSession(): UseQueryResult<UserView>
submitSavedExam(): Promise<SubmissionReceipt>
~~~

**类型与规则：** ExamAutosaveController={save(itemId,answer,revision),flush(),pending,conflict,lastSavedAt}; props类型定义在同feature/types.ts；前端ID为string，服务端UTC→上海显示。点击提交先flush保存，失败明确提示，截止到达仅已保存答案生效。

- [ ] **T29.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~typescript
test('autosave failure is visible', async ({ page, examScenario }) => {
  await examScenario.open(page);
  await page.route('**/api/v1/candidate/exam/answers/*', route => route.abort());
  await page.getByRole('textbox', { name: '简答题答案' }).fill('我的答案');
  await expect(page.getByText('保存失败')).toBeVisible();
});
~~~

- [ ] **T29.1.1** test_hr_import_to_review_browser：HR可操作一条主线。
- [ ] **T29.1.2** test_candidate_token_fragment_removed：入口token用后移除，不进日志/Referer。
- [ ] **T29.1.3** test_autosave_failure_visible：失败不能显示已保存。
- [ ] **T29.1.4** test_two_tab_conflict_visible：409提示刷新，不静默覆盖。
- [ ] **T29.1.5** test_candidate_no_answer_in_network：抓包检查不泄露答案。

- [ ] **T29.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T29.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T29.4 验证GREEN及异常。** 执行：

~~~text
npm --prefix frontend run typecheck；npm --prefix frontend run build；npm --prefix frontend run test:e2e -- recruitment-smoke.spec.ts
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：最小真实页面可操作，无mock业务数据；角色路由正确；UI沿用原型布局基调，不保留静态成功率。

- [ ] **T29.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t29-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T29.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'frontend/src/app/login/page.tsx' 'frontend/src/app/(staff)/layout.tsx' 'frontend/src/app/(staff)/hr/jobs/page.tsx' 'frontend/src/app/(staff)/hr/imports/page.tsx' 'frontend/src/app/(staff)/hr/applications/[id]/page.tsx' 'frontend/src/app/(staff)/hr/grading/[id]/page.tsx' 'frontend/src/app/exam/page.tsx' 'frontend/src/features/exam/ExamShell.tsx' 'frontend/src/features/exam/useExamAutosave.ts' 'frontend/tests/e2e/recruitment-smoke.spec.ts' 'frontend/tests/e2e/fixtures.ts'
git commit -m 'feat: T29 最小可操作前端与考试页面'
~~~

### T30 最小纵向闭环与事件串联验收

**阶段/前置：** G1；T29、T23、T21、T20。**需求：** FR-01、FR-02、FR-03、FR-04、FR-05、FR-06、FR-07、FR-08、FR-09、FR-10、FR-11、FR-12、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `backend/app/runtime/handlers.py`
- Create: `backend/tests/e2e/test_recruitment_vertical_slice.py`
- Create: `scripts/seed_demo.py`
- Create: `scripts/run_acceptance.py`

**Consumes：** 使用T29、T23、T21、T20的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
register_handlers(registry: JobHandlerRegistry) -> None
seed_demo(settings: Settings, actor_passwords: SecretInputs) -> DemoFixtureRefs
run_acceptance(profile: str, scenario: str) -> AcceptanceReport
resume_pipeline(entity_type: str, entity_id: int) -> ResultRef
~~~

**类型与规则：** JobHandlerRegistry={job_type→Callable[[int],ResultRef]}; SecretInputs只从交互/env安全读取；DemoFixtureRefs={users,jobs,papers,candidates}；AcceptanceReport={passed,steps,entity_refs,errors,artifact_paths}。绑定parse→profile→screen→match→invite→mail→submit→grade，任务只传ID。

- [ ] **T30.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_complete_real_recruitment_chain():
    report = run_acceptance("test", "vertical-slice")
    assert report.passed is True
    assert report.entity_refs["score_report_id"]
    assert report.entity_refs["recruitment_event_id"]
~~~

- [ ] **T30.1.1** test_complete_real_recruitment_chain：PDF导入→真实模型画像/匹配→Mailpit邀考/验证码→答题→HR复核→面试待办。
- [ ] **T30.1.2** test_second_job_different_paper：A/B岗位收到不同发布卷。
- [ ] **T30.1.3** test_import_and_worker_retry_no_duplicate_invite：重试不多发。
- [ ] **T30.1.4** test_no_placeholder_model_output：真实网关调用和证据refs存在。

- [ ] **T30.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T30.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T30.4 验证GREEN及异常。** 执行：

~~~text
python scripts/seed_demo.py --profile test；python scripts/run_acceptance.py --profile test --scenario vertical-slice
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：保存完整ID链与测试证据；真实MySQL/Redis/MinIO/Milvus/模型/测试邮箱；有一步blocked就不进入扩展阶段，无固定答复凑成功。

- [ ] **T30.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t30-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T30.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/runtime/handlers.py' 'backend/tests/e2e/test_recruitment_vertical_slice.py' 'scripts/seed_demo.py' 'scripts/run_acceptance.py'
git commit -m 'feat: T30 最小纵向闭环与事件串联验收'
~~~

### T31 管理员完整配置界面

**阶段/前置：** M3；T28、T08、T10、T30。**需求：** FR-01、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `frontend/src/app/(staff)/admin/users/page.tsx`
- Create: `frontend/src/app/(staff)/admin/departments/page.tsx`
- Create: `frontend/src/app/(staff)/admin/roles/page.tsx`
- Create: `frontend/src/app/(staff)/admin/models/page.tsx`
- Create: `frontend/src/app/(staff)/admin/prompts/page.tsx`
- Create: `frontend/src/app/(staff)/admin/workflows/page.tsx`
- Create: `frontend/src/app/(staff)/admin/mail/page.tsx`
- Create: `frontend/src/app/(staff)/admin/runtime/page.tsx`
- Create: `frontend/src/features/admin/SecretField.tsx`
- Create: `frontend/tests/e2e/admin-config.spec.ts`

**Consumes：** 使用T28、T08、T10、T30的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
AdminUsersPage(): ReactNode
ModelConfigForm({initial,onSaved}: ModelConfigFormProps): ReactNode
MailRevisionPanel({revision}: MailRevisionPanelProps): ReactNode
SecretField({configured,onChange}: SecretFieldProps): ReactNode
WorkflowConfigPanel({taskType}: WorkflowConfigPanelProps): ReactNode
~~~

**类型与规则：** 所有表单类型由OpenAPI生成类型引用；SecretField值不使用服务端掩码回填，空值代表保持或未设置，明确区分替换；邮件draft→test→verified→activate可见，停用有原因提示。

- [ ] **T31.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~typescript
test('admin has no recruitment entry', async ({ page, adminScenario }) => {
  await adminScenario.login(page);
  await expect(page.getByRole('link', { name: '账号管理' })).toBeVisible();
  await expect(page.getByRole('link', { name: '简历筛选' })).toHaveCount(0);
});
~~~

- [ ] **T31.1.1** test_admin_can_config_not_recruit：能配置但无招聘菜单/API权限。
- [ ] **T31.1.2** test_secret_not_in_dom_or_response：密钥不出现在DOM/查询返回。
- [ ] **T31.1.3** test_mail_revision_activation_flow：测试完成后可启用新修订。
- [ ] **T31.1.4** test_invalid_model_disable_workflow：未验证模型不能开启流程。

- [ ] **T31.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T31.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T31.4 验证GREEN及异常。** 执行：

~~~text
npm --prefix frontend run typecheck；npm --prefix frontend run test:e2e -- admin-config.spec.ts
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：管理员页面覆盖账号/部门/角色/模型/提示词/固定流程/邮件/运行，不做通用拖拽画布。

- [ ] **T31.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t31-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T31.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'frontend/src/app/(staff)/admin/users/page.tsx' 'frontend/src/app/(staff)/admin/departments/page.tsx' 'frontend/src/app/(staff)/admin/roles/page.tsx' 'frontend/src/app/(staff)/admin/models/page.tsx' 'frontend/src/app/(staff)/admin/prompts/page.tsx' 'frontend/src/app/(staff)/admin/workflows/page.tsx' 'frontend/src/app/(staff)/admin/mail/page.tsx' 'frontend/src/app/(staff)/admin/runtime/page.tsx' 'frontend/src/features/admin/SecretField.tsx' 'frontend/tests/e2e/admin-config.spec.ts'
git commit -m 'feat: T31 管理员完整配置界面'
~~~

### T32 HR岗位、题库与试卷完整界面

**阶段/前置：** M3；T28、T11、T12、T30。**需求：** FR-02、FR-08、FR-09。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `frontend/src/app/(staff)/hr/jobs/[id]/page.tsx`
- Create: `frontend/src/app/(staff)/hr/question-banks/page.tsx`
- Create: `frontend/src/app/(staff)/hr/papers/page.tsx`
- Create: `frontend/src/features/jobs/ConditionEditor.tsx`
- Create: `frontend/src/features/jobs/AutomationPanel.tsx`
- Create: `frontend/src/features/papers/PaperEditor.tsx`
- Create: `frontend/tests/e2e/job-paper-admin.spec.ts`

**Consumes：** 使用T28、T11、T12、T30的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ConditionEditor({value,onChange}: ConditionEditorProps): ReactNode
AutomationPanel({job}: AutomationPanelProps): ReactNode
PaperEditor({draft}: PaperEditorProps): ReactNode
usePublishPaper(): UseMutationResult<PaperVersionView,ApiError,PublishPaperCommand>
~~~

**类型与规则：** ConditionEditor区分必需/优先、unknown说明；PaperEditor提供单选/多选/简答与量表，发布后只读并可另建版本；AutomationPanel显示readiness阻塞项，关闭默认值false。

- [ ] **T32.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~typescript
test('automation lists blocking reasons', async ({ page, jobWithoutPaper }) => {
  await jobWithoutPaper.open(page);
  await page.getByRole('button', { name: '开启自动邀请' }).click();
  await expect(page.getByText('岗位尚未绑定已发布试卷')).toBeVisible();
});
~~~

- [ ] **T32.1.1** test_required_preferred_distinct：优先项缺失不显示淘汰。
- [ ] **T32.1.2** test_publish_readonly_and_new_version：发布后另建草稿。
- [ ] **T32.1.3** test_enable_automation_shows_blockers：缺配置可定位。
- [ ] **T32.1.4** test_score_total_from_server：不以客户端合计替代服务端正式总分。

- [ ] **T32.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T32.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T32.4 验证GREEN及异常。** 执行：

~~~text
npm --prefix frontend run typecheck；npm --prefix frontend run test:e2e -- job-paper-admin.spec.ts
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：HR可独立完成岗位与试卷准备、发布及自动邀请配置，不依赖修改数据库。

- [ ] **T32.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t32-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T32.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'frontend/src/app/(staff)/hr/jobs/[id]/page.tsx' 'frontend/src/app/(staff)/hr/question-banks/page.tsx' 'frontend/src/app/(staff)/hr/papers/page.tsx' 'frontend/src/features/jobs/ConditionEditor.tsx' 'frontend/src/features/jobs/AutomationPanel.tsx' 'frontend/src/features/papers/PaperEditor.tsx' 'frontend/tests/e2e/job-paper-admin.spec.ts'
git commit -m 'feat: T32 HR岗位、题库与试卷完整界面'
~~~

### T33 HR人才库、去重、画像与招聘完整界面

**阶段/前置：** M3；T28、T16、T17、T19、T20、T27、T30。**需求：** FR-03、FR-04、FR-05、FR-06、FR-07、FR-09、FR-11、FR-12。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `frontend/src/app/(staff)/hr/talents/page.tsx`
- Create: `frontend/src/app/(staff)/hr/talents/[id]/page.tsx`
- Create: `frontend/src/app/(staff)/hr/duplicates/page.tsx`
- Create: `frontend/src/app/(staff)/hr/matches/page.tsx`
- Create: `frontend/src/app/(staff)/hr/attempts/page.tsx`
- Create: `frontend/src/features/talents/MergeDialog.tsx`
- Create: `frontend/src/features/talents/EvidencePanel.tsx`
- Create: `frontend/src/features/grading/ScoreReviewPanel.tsx`
- Create: `frontend/tests/e2e/talent-recruitment.spec.ts`

**Consumes：** 使用T28、T16、T17、T19、T20、T27、T30的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
MergeDialog({caseData,onResolved}: MergeDialogProps): ReactNode
EvidencePanel({evidence}: EvidencePanelProps): ReactNode
ScoreReviewPanel({attempt}: ScoreReviewPanelProps): ReactNode
TalentPoolSearch({jobId}: TalentPoolSearchProps): ReactNode
RecruitmentTimeline({events}: RecruitmentTimelineProps): ReactNode
~~~

**类型与规则：** TalentPoolSearch可结构化/自然语言查人并显式加入选定岗位；MergeDialog逐岗位选主关系并显示活动考次冲突；分列粗筛/匹配分/考试分，不合总排名；版本及来源可以切换。

- [ ] **T33.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~typescript
test('failed screening remains in pool', async ({ page, screenedOutCandidate }) => {
  await page.goto('/hr/talents');
  await page.getByRole('searchbox', { name: '搜索人才' }).fill(screenedOutCandidate.name);
  await expect(page.getByText(screenedOutCandidate.name)).toBeVisible();
});
~~~

- [ ] **T33.1.1** test_failed_screen_still_in_pool：当前岗位不符仍在人才库。
- [ ] **T33.1.2** test_merge_history_visible：合并后原始考试/简历版本可查。
- [ ] **T33.1.3** test_unknown_needs_review_not_zero：缺字段显示待核实。
- [ ] **T33.1.4** test_reevaluate_no_auto_reinvite：重评提示不重复发卷。
- [ ] **T33.1.5** test_final_score_revision_visible：改分后可查旧报告。

- [ ] **T33.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T33.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T33.4 验证GREEN及异常。** 执行：

~~~text
npm --prefix frontend run typecheck；npm --prefix frontend run test:e2e -- talent-recruitment.spec.ts
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：从HR界面完成补邮箱、去重确认、画像修正、人工覆盖、手动邀请、重发/新轮次、复核及招聘推进。

- [ ] **T33.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t33-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T33.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'frontend/src/app/(staff)/hr/talents/page.tsx' 'frontend/src/app/(staff)/hr/talents/[id]/page.tsx' 'frontend/src/app/(staff)/hr/duplicates/page.tsx' 'frontend/src/app/(staff)/hr/matches/page.tsx' 'frontend/src/app/(staff)/hr/attempts/page.tsx' 'frontend/src/features/talents/MergeDialog.tsx' 'frontend/src/features/talents/EvidencePanel.tsx' 'frontend/src/features/grading/ScoreReviewPanel.tsx' 'frontend/tests/e2e/talent-recruitment.spec.ts'
git commit -m 'feat: T33 HR人才库、去重、画像与招聘完整界面'
~~~

### T34 招聘知识库解析、发布与有来源问答

**阶段/前置：** M3；T30、T20、T13。**需求：** FR-13。**负责接口：** API-079、API-080、API-081、API-082、API-083、API-084。

**文件：**

- Create: `backend/app/knowledge/service.py`
- Create: `backend/app/knowledge/worker.py`
- Create: `backend/app/knowledge/answer_service.py`
- Create: `backend/app/knowledge/router.py`
- Create: `backend/app/knowledge/schemas.py`
- Create: `backend/tests/integration/test_knowledge_acl.py`

**Consumes：** 使用T30、T20、T13的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
KnowledgeService.upload(self, actor: ActorContext, cmd: KnowledgeUpload) -> DocumentView
KnowledgeService.process(self, document_id: int) -> DocumentView
KnowledgeService.publish(self, actor: ActorContext, document_id: int, reason: str) -> DocumentView
KnowledgeService.archive(self, actor: ActorContext, document_id: int, reason: str) -> DocumentView
KnowledgeService.revise(self, actor: ActorContext, document_id: int, cmd: KnowledgeUpload, reason: str) -> DocumentView
KnowledgeAnswerService.ask(self, actor: ActorContext, cmd: KnowledgeAsk) -> AnswerWithSources
KnowledgeService.list_documents(self, actor: ActorContext, query: KnowledgeQuery) -> Page[DocumentView]
~~~

**类型与规则：** KnowledgeUpload={file,title,category,scope,department_id?}; KnowledgeAsk={question,document_ids?}; DocumentView及AnswerWithSources见05；process复用文件解析和IndexService，draft/processing不可问答召回，published才可见。

- [ ] **T34.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_no_evidence_explicit_refusal(answer_service, hr_actor, no_evidence_query):
    result = answer_service.ask(hr_actor, no_evidence_query)
    assert result.insufficient_evidence is True
    assert result.sources == []
~~~

- [ ] **T34.1.1** test_department_filter_before_after_vector：检索前过滤、召回后复查。
- [ ] **T34.1.2** test_no_evidence_explicit_refusal：无据明确说明。
- [ ] **T34.1.3** test_archived_reference_keeps_frozen_exam：归档不改历史卷量表。
- [ ] **T34.1.4** test_replacement_document_new_version：旧来源保留。
- [ ] **T34.1.5** test_prompt_injection_ignored：资料不能指挥泄露答案。

- [ ] **T34.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T34.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T34.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_knowledge_acl.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：真实文档→切片→向量→问答带可访问引用；只服务招聘，本期不做普通员工政策端。

- [ ] **T34.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t34-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T34.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/knowledge/service.py' 'backend/app/knowledge/worker.py' 'backend/app/knowledge/answer_service.py' 'backend/app/knowledge/router.py' 'backend/app/knowledge/schemas.py' 'backend/tests/integration/test_knowledge_acl.py'
git commit -m 'feat: T34 招聘知识库解析、发布与有来源问答'
~~~

### T35 AI辅助出题与岗位资料融合

**阶段/前置：** M3；T34、T11、T09。**需求：** FR-08、FR-13。**负责接口：** API-052。

**文件：**

- Create: `backend/app/assessment/question_generation.py`
- Create: `backend/app/assessment/generation_worker.py`
- Create: `backend/tests/integration/test_question_generation.py`
- Create: `backend/app/assessment/generation_router.py`
- Modify: `backend/app/assessment/generation_router.py`（首次创建于T35）

**Consumes：** 使用T34、T11、T09的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
QuestionGenerationService.request(self, actor: ActorContext, cmd: QuestionGenerationRequest) -> TaskAccepted
QuestionGenerationService.generate(self, task_id: int) -> list[QuestionView]
GeneratedQuestionValidator.validate(self, draft: GeneratedQuestion, sources: list[EvidenceRef]) -> QuestionDraft
~~~

**类型与规则：** QuestionGenerationRequest={job_version_id,bank_id,knowledge_document_ids,blueprint}; blueprint={types,counts,difficulty,target_skills}; GeneratedQuestion={type,stem,options?,answer_key?,rubric,reference_sources}; 有权限的发布资料作为来源，产物始终draft待HR审核。

- [ ] **T35.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_generated_questions_draft_only(generator, generated_task):
    questions = generator.generate(generated_task.id)
    assert questions
    assert all(q.state == "draft" for q in questions)
~~~

- [ ] **T35.1.1** test_generated_questions_draft_only：AI不能自行发布。
- [ ] **T35.1.2** test_reference_scope_same_department：无权资料不能入题。
- [ ] **T35.1.3** test_choice_answer_in_options：正确项必须存在。
- [ ] **T35.1.4** test_short_answer_rubric_complete：量表维度和满分明确。
- [ ] **T35.1.5** test_no_source_unsupported_claim：不足资料提示，不编造引用。

- [ ] **T35.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T35.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T35.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_question_generation.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：在HR界面生成题目→审核→发布卷→绑定岗位可闭环；AI出题失败不影响已有正式试卷使用。

- [ ] **T35.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t35-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T35.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/assessment/question_generation.py' 'backend/app/assessment/generation_worker.py' 'backend/tests/integration/test_question_generation.py' 'backend/app/assessment/generation_router.py' 'backend/app/assessment/generation_router.py'
git commit -m 'feat: T35 AI辅助出题与岗位资料融合'
~~~

### T36 招聘统计口径、待办与管理员运行视图

**阶段/前置：** M3；T28、T27、T26、T16、T30。**需求：** FR-14、FR-15。**负责接口：** API-085、API-086、API-094、API-095。

**文件：**

- Create: `backend/app/reporting/service.py`
- Create: `backend/app/reporting/todo_service.py`
- Create: `backend/app/reporting/router.py`
- Modify: `backend/app/runtime/admin_queries.py`（首次创建于T28）
- Create: `backend/tests/integration/test_reporting_counts.py`
- Modify: `backend/app/ai_runtime/router.py`（首次创建于T08）

**Consumes：** 使用T28、T27、T26、T16、T30的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
RecruitmentReportService.get(self, actor: ActorContext, query: ReportQuery) -> RecruitmentReport
TodoService.list(self, actor: ActorContext, query: TodoQuery) -> Page[TodoView]
AdminRuntimeQueries.overview(self, actor: ActorContext) -> SanitizedRuntimeReport
AdminRuntimeQueries.audit(self, actor: ActorContext, query: AuditQuery) -> Page[AuditView]
~~~

**类型与规则：** ReportQuery={from,to,department_id?,job_id?}; RecruitmentReport={inventory,period_flow,funnel,exam_summary,vacancies,generated_at}; TodoQuery={type,page,page_size}; 待办由真实pending_email/duplicate_review/任务失败/待复核派生，不另存重复事实。

- [ ] **T36.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_vacancy_from_hired_not_matched(report_service, hr_actor, report_query, seeded_26_9_3):
    report = report_service.get(hr_actor, report_query)
    assert report.vacancies[0].headcount == 26
    assert report.vacancies[0].hired == 3
    assert report.vacancies[0].gap == 23
~~~

- [ ] **T36.1.1** test_canonical_count_once：合并人才计1人。
- [ ] **T36.1.2** test_vacancy_from_hired_not_matched：缺口=需求-已录用。
- [ ] **T36.1.3** test_funnel_from_events_not_current_stage：漏斗按事件进入去重。
- [ ] **T36.1.4** test_latest_finalized_round_only：各主应聘取最新正式考次，复核中不计均分。
- [ ] **T36.1.5** test_empty_denominator_none：无数据为null/—，不是0%成功率。

- [ ] **T36.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T36.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T36.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_reporting_counts.py -q
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：HR统计按岗位授权；管理员运行视图只技术元信息，没有候选人正文。

- [ ] **T36.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t36-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T36.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/app/reporting/service.py' 'backend/app/reporting/todo_service.py' 'backend/app/reporting/router.py' 'backend/app/runtime/admin_queries.py' 'backend/tests/integration/test_reporting_counts.py' 'backend/app/ai_runtime/router.py'
git commit -m 'feat: T36 招聘统计口径、待办与管理员运行视图'
~~~

### T37 知识库、看板与培训框架界面

**阶段/前置：** M3；T34、T35、T36、T31、T33。**需求：** FR-08、FR-13、FR-14、FR-15、FR-16。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `frontend/src/app/(staff)/hr/knowledge/page.tsx`
- Create: `frontend/src/app/(staff)/hr/dashboard/page.tsx`
- Create: `frontend/src/app/(staff)/hr/training/page.tsx`
- Create: `frontend/src/features/knowledge/CitationAnswer.tsx`
- Create: `frontend/src/features/dashboard/RecruitmentCharts.tsx`
- Create: `frontend/src/features/papers/GenerateQuestionsDialog.tsx`
- Create: `frontend/tests/e2e/knowledge-dashboard.spec.ts`

**Consumes：** 使用T34、T35、T36、T31、T33的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
CitationAnswer({answer}: CitationAnswerProps): ReactNode
RecruitmentCharts({report}: RecruitmentChartsProps): ReactNode
GenerateQuestionsDialog({jobVersionId}: GenerateQuestionsDialogProps): ReactNode
TrainingFrameworkPage(): ReactNode
~~~

**类型与规则：** 图表直接使用服务端统计，空值显示—，区分期间和当前库存。培训仅规划说明和静态结构占位，示例显式标注“规划/演示”，无后端训练接口/培训执行表。

- [ ] **T37.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~typescript
test('training is visibly planned', async ({ page, hrScenario }) => {
  await hrScenario.login(page);
  await page.goto('/hr/training');
  await expect(page.getByText('规划中', { exact: true })).toBeVisible();
  await expect(page.getByText('防挂机已开启')).toHaveCount(0);
});
~~~

- [ ] **T37.1.1** test_citation_click_authorized：出处只打开有权资料。
- [ ] **T37.1.2** test_generation_result_draft_review：生成后进入题库审核。
- [ ] **T37.1.3** test_report_empty_state_not_fake：空数据不显示示意成功率。
- [ ] **T37.1.4** test_training_no_execution_claim：无防挂机已开启等假状态。

- [ ] **T37.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T37.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T37.4 验证GREEN及异常。** 执行：

~~~text
npm --prefix frontend run typecheck；npm --prefix frontend run test:e2e -- knowledge-dashboard.spec.ts
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：去掉原型NL2SQL已执行、培训在学人数等未交付宣传；保留整体视觉体系，不扩展延期业务。

- [ ] **T37.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t37-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T37.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'frontend/src/app/(staff)/hr/knowledge/page.tsx' 'frontend/src/app/(staff)/hr/dashboard/page.tsx' 'frontend/src/app/(staff)/hr/training/page.tsx' 'frontend/src/features/knowledge/CitationAnswer.tsx' 'frontend/src/features/dashboard/RecruitmentCharts.tsx' 'frontend/src/features/papers/GenerateQuestionsDialog.tsx' 'frontend/tests/e2e/knowledge-dashboard.spec.ts'
git commit -m 'feat: T37 知识库、看板与培训框架界面'
~~~

### T38 104接口覆盖、OpenAPI与前端类型同步

**阶段/前置：** M4；T37。**需求：** FR-01、FR-02、FR-03、FR-04、FR-05、FR-06、FR-07、FR-08、FR-09、FR-10、FR-11、FR-12、FR-13、FR-14、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `scripts/export_openapi.py`
- Create: `scripts/check_contract_coverage.py`
- Create: `frontend/src/generated/api-types.ts`
- Create: `backend/tests/contract/test_openapi_manifest.py`
- Create: `backend/tests/contract/test_response_projections.py`
- Create: `docs/api-manifest.json`

**Consumes：** 使用T37的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
export_openapi(app: FastAPI, output_path: Path) -> None
check_contract_coverage(spec: ApiManifest, openapi: dict[str, JsonValue]) -> CoverageReport
~~~

**类型与规则：** ApiManifest来自附录B：API ID/method/path/owner/role；CoverageReport={missing,unexpected,duplicates,schema_mismatches}。前端类型从真实OpenAPI生成，只允许在生成层修改流程，不能手写另一套API结构。

- [ ] **T38.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_104_operations_exact(contract_report):
    assert contract_report.missing == []
    assert contract_report.duplicates == []
    assert contract_report.schema_mismatches == []
    assert contract_report.checked_business_operations == 104
~~~

- [ ] **T38.1.1** test_104_operations_exact：规范104操作全部注册，无漏/重。
- [ ] **T38.1.2** test_candidate_dto_excludes_secrets：所有候选响应递归无答案/量表/内部分数。
- [ ] **T38.1.3** test_ids_serialized_as_strings：大整数ID字符串。
- [ ] **T38.1.4** test_error_status_matches_code：409/410/429不包200。
- [ ] **T38.1.5** test_if_match_required：关键可变资源拒绝无版本修改。

- [ ] **T38.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T38.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T38.4 验证GREEN及异常。** 执行：

~~~text
python scripts/export_openapi.py --output artifacts/openapi.json；python scripts/check_contract_coverage.py --manifest docs/api-manifest.json --openapi artifacts/openapi.json；npm --prefix frontend run generate:api；npm --prefix frontend run typecheck
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：104接口方法路径与评审稿一一对应；上传multipart/Cookie/CSRF/ETag/幂等错误实际可调用。；只比较/api/v1下104业务/健康操作，框架/docs和/openapi.json单独允许，不算新增业务接口。

- [ ] **T38.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t38-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T38.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'scripts/export_openapi.py' 'scripts/check_contract_coverage.py' 'frontend/src/generated/api-types.ts' 'backend/tests/contract/test_openapi_manifest.py' 'backend/tests/contract/test_response_projections.py' 'docs/api-manifest.json'
git commit -m 'feat: T38 104接口覆盖、OpenAPI与前端类型同步'
~~~

### T39 安全隔离、竞争条件与断点恢复专项

**阶段/前置：** M4；T38。**需求：** FR-01、FR-04、FR-09、FR-10、FR-11、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `backend/tests/integration/test_failure_recovery.py`
- Create: `backend/tests/integration/test_concurrent_commands.py`
- Create: `backend/tests/security/test_resource_isolation.py`
- Create: `frontend/tests/e2e/exam-recovery.spec.ts`
- Create: `backend/tests/helpers/failure_injection.py`
- Create: `backend/tests/helpers/concurrency_probe.py`

**Consumes：** 使用T38的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
FailureInjection.run(self, scenario: str, fixture: ScenarioFixture) -> RecoveryEvidence
ConcurrencyProbe.run(self, operation: str, actors: list[ActorContext], workers: int) -> ConcurrencyEvidence
~~~

**类型与规则：** 测试工具仅profile=test启用，不能对生产暴露故障注入接口。ScenarioFixture={entity_refs,dependency_targets}; Evidence包含前后状态/事件数量/请求ID，不含secret。 ConcurrencyEvidence={operation,grading_event_count,submitted_attempt_count,duplicate_application_count,score_consistent,artifact_paths}；RecoveryEvidence={scenario,before_state,after_state,passed,artifact_paths}。

- [ ] **T39.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_submit_timeout_race(concurrency_probe, submission_race_fixture):
    evidence = concurrency_probe.run("submit_vs_timeout", submission_race_fixture.actors, workers=2)
    assert evidence.grading_event_count == 1
    assert evidence.submitted_attempt_count == 1
~~~

- [ ] **T39.1.1** test_worker_crash_after_commit：提交后崩溃重放无重复邀请。
- [ ] **T39.1.2** test_submit_timeout_race：同时提交与超时只一评分事件。
- [ ] **T39.1.3** test_merge_vs_add_application：合并与加岗并发无双主关系。
- [ ] **T39.1.4** test_review_vs_finalize：总分一致且旧报告不改。
- [ ] **T39.1.5** test_redis_restart_saved_answers_survive：会话重核验后已保存答案仍在。
- [ ] **T39.1.6** test_private_vector_inference_blocked：共享检索不能间接泄露私有评价。

- [ ] **T39.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T39.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T39.4 验证GREEN及异常。** 执行：

~~~text
python scripts/compose.py exec -T api python -m pytest tests/integration/test_failure_recovery.py tests/integration/test_concurrent_commands.py tests/security/test_resource_isolation.py -q；npm --prefix frontend run test:e2e -- exam-recovery.spec.ts
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：MySQL真实锁/事务验证，不用SQLite冒充；SMTP unknown、停用邮件配置、暂停岗位都验证恢复路径。

- [ ] **T39.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t39-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T39.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'backend/tests/integration/test_failure_recovery.py' 'backend/tests/integration/test_concurrent_commands.py' 'backend/tests/security/test_resource_isolation.py' 'frontend/tests/e2e/exam-recovery.spec.ts' 'backend/tests/helpers/failure_injection.py' 'backend/tests/helpers/concurrency_probe.py'
git commit -m 'feat: T39 安全隔离、竞争条件与断点恢复专项'
~~~

### T40 真实AI质量与解析评测

**阶段/前置：** M4；T39。**需求：** FR-03、FR-05、FR-06、FR-07、FR-08、FR-11、FR-13。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `evaluation/datasets/manifest.json`
- Create: `evaluation/run_parse_eval.py`
- Create: `evaluation/run_match_eval.py`
- Create: `evaluation/run_rag_eval.py`
- Create: `evaluation/run_grading_eval.py`
- Create: `backend/tests/unit/test_eval_metrics.py`
- Create: `evaluation/models.py`

**Consumes：** 使用T39的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
field_metrics(predictions: list[FieldFact], labels: list[FieldFact]) -> FieldMetrics
match_metrics(predictions: list[InvitePrediction], labels: list[InviteLabel]) -> MatchMetrics
rag_metrics(cases: list[RagJudgement]) -> RagMetrics
grading_metrics(cases: list[GradingJudgement]) -> GradingMetrics
~~~

**类型与规则：** FieldMetrics={precision,recall,f1,critical_exact_match}; MatchMetrics={agreement,false_invite,false_miss,confusion}; RagMetrics={recall_at_k,supported_answer_rate,refusal_rate}; 数据集有来源/标注版本/留出集，不上传真实个人隐私到未知服务。

- [ ] **T40.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_f1_not_recall(predicted_two_with_one_correct, labels_one):
    result = field_metrics(predicted_two_with_one_correct, labels_one)
    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(1.0)
    assert result.f1 == pytest.approx(2 / 3)
~~~

- [ ] **T40.1.1** test_f1_not_recall：P=.5,R=1时F1约.6667，不等于1。
- [ ] **T40.1.2** test_missing_predictions_count：漏项纳入分母。
- [ ] **T40.1.3** test_no_answer_keyword_shortcut：RAG要来源支持和人工正确性判断。
- [ ] **T40.1.4** test_model_revision_recorded：每次报告含digest/prompt/rule版本。

- [ ] **T40.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T40.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T40.4 验证GREEN及异常。** 执行：

~~~text
python -m pytest backend/tests/unit/test_eval_metrics.py -q；python -m evaluation.run_parse_eval --profile test；python -m evaluation.run_match_eval --profile test；python -m evaluation.run_rag_eval --profile test；python -m evaluation.run_grading_eval --profile test
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：先至少20份简历/30对匹配/30问冒烟，正式按06建议各≥100固定样本；99/90/95质量目标分别报告，未达标不改期望凑通过。

- [ ] **T40.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t40-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T40.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'evaluation/datasets/manifest.json' 'evaluation/run_parse_eval.py' 'evaluation/run_match_eval.py' 'evaluation/run_rag_eval.py' 'evaluation/run_grading_eval.py' 'backend/tests/unit/test_eval_metrics.py' 'evaluation/models.py'
git commit -m 'feat: T40 真实AI质量与解析评测'
~~~

### T41 性能、资源与全链路回归

**阶段/前置：** M4；T40。**需求：** FR-03、FR-04、FR-07、FR-09、FR-10、FR-14、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `tests/load/recruitment_load.py`
- Create: `scripts/collect_metrics.py`
- Create: `backend/tests/e2e/test_full_acceptance.py`
- Create: `frontend/tests/e2e/full-acceptance.spec.ts`
- Create: `tests/load/models.py`

**Consumes：** 使用T40的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
LoadRunner.run(self, config: LoadConfig) -> PerformanceReport
AcceptanceCollector.collect(self, scenario_id: str) -> AcceptanceReport
~~~

**类型与规则：** LoadConfig={talent_count:10000,active_hr:20,concurrent_exams:50,duration_seconds,profile}; PerformanceReport={hardware,dataset,requests,error_rate,p50,p95,p99,queue_latency,peak_memory}；性能采样包含服务端计时，AI异步另报。 config保存实际LoadConfig；claims={production_2000_verified:false,annual_999_verified:false}，除非有独立证据和另行批准不更改。

- [ ] **T41.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_50_not_claim_2000(performance_report):
    assert performance_report.config.concurrent_exams == 50
    assert performance_report.claims.production_2000_verified is False
    assert performance_report.claims.annual_999_verified is False
~~~

- [ ] **T41.1.1** test_at01_to_at16_all_pass：16验收场景无漏。
- [ ] **T41.1.2** test_no_duplicate_or_lost_answers_under_load：负载后答案/邀请/报告唯一。
- [ ] **T41.1.3** test_p95_targets：列表≤1s、看板≤3s、保存≤1s，向量目标≤500ms不含模型。
- [ ] **T41.1.4** test_50_not_claim_2000：报告明确本期规模，不冒充2000在线或99.9%年可用。

- [ ] **T41.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T41.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T41.4 验证GREEN及异常。** 执行：

~~~text
python tests/load/recruitment_load.py --profile test --talents 10000 --hr 20 --exams 50；python scripts/run_acceptance.py --profile test --scenario full；npm --prefix frontend run test:e2e -- full-acceptance.spec.ts
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：P0/P1全部通过，P2已记录且不破坏主线；记录性能未达标项及修复，不默默放宽指标。

- [ ] **T41.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t41-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T41.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'tests/load/recruitment_load.py' 'scripts/collect_metrics.py' 'backend/tests/e2e/test_full_acceptance.py' 'frontend/tests/e2e/full-acceptance.spec.ts' 'tests/load/models.py'
git commit -m 'feat: T41 性能、资源与全链路回归'
~~~

### T42 干净环境启动、备份恢复与测试环境交付

**阶段/前置：** G2；T41。**需求：** FR-01、FR-03、FR-04、FR-09、FR-10、FR-11、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `scripts/bootstrap.py`
- Create: `scripts/backup.py`
- Create: `scripts/restore_check.py`
- Create: `.github/workflows/ci.yml`
- Create: `docs/runbook.md`
- Create: `docs/test-environment-handoff.md`
- Create: `backend/tests/ops/test_bootstrap_restore.py`
- Create: `backend/app/talents/retention_service.py`

**Consumes：** 使用T41的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
Bootstrap.run(self, profile: str, non_interactive: bool = False) -> BootstrapReport
BackupService.backup(self, profile: str, destination: Path) -> BackupManifest
RestoreVerifier.verify(self, manifest: BackupManifest, isolated_target: str) -> RestoreReport
RetentionService.preview(self, actor: ActorContext, policy: RetentionPolicy) -> PurgePlan
RetentionService.execute(self, actor: ActorContext, plan: PurgePlan, approval_ref: str) -> PurgeResult
~~~

**类型与规则：** BootstrapReport={versions,readiness,migrations,seed_refs,blocked}; BackupManifest={db_snapshot,file_manifest,index_metadata,key_recovery_ref,checksums}; RestoreReport={counts,checksums,readable_samples,passed}。密钥恢复引用不是把主密钥明文装包。 RetentionPolicy={cutoff,scope,legal_hold_exclusions}; PurgePlan={entity_refs,object_keys,vector_keys,counts,hash}; PurgeResult={deleted,retained,retry_jobs}。仅隔离测试资料验证清除与重试；真实清除需指定范围与批准，审计保留无隐私的ID/结果。 RestoreReport同时返回counts_match/checksums_match布尔断言，二者都真才能passed。

- [ ] **T42.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_restore_in_isolation(restore_report):
    assert restore_report.passed is True
    assert restore_report.counts_match is True
    assert restore_report.checksums_match is True
~~~

- [ ] **T42.1.1** test_clean_bootstrap_idempotent：新测试卷首次启动和重复启动成功。
- [ ] **T42.1.2** test_no_existing_database_touch：只用项目独立库/卷。
- [ ] **T42.1.3** test_restore_in_isolation：隔离恢复后文件/档案/正式报告可查。
- [ ] **T42.1.4** test_ci_core_checks_required：迁移、契约、单元/集成/E2E失败不发布。
- [ ] **T42.1.5** test_retention_preview_no_side_effect：preview只读，清除失败可重试且不误删仍有引用文件。

- [ ] **T42.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T42.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T42.4 验证GREEN及异常。** 执行：

~~~text
python scripts/bootstrap.py --profile test；python scripts/run_acceptance.py --profile test --scenario full；python scripts/backup.py --profile test --output artifacts/backup-manifest.json；python scripts/restore_check.py --manifest artifacts/backup-manifest.json --target isolated-restore
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：形成可复现测试环境包：锁文件、镜像摘要、迁移、配置样例、启动入口、演示数据、验收证据；不含真实secret/候选人原件。；资料保留策略可配置，清除覆盖文件/向量/AI产物并尊重保留例外，默认不开启真实批量清除。

- [ ] **T42.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t42-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T42.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'scripts/bootstrap.py' 'scripts/backup.py' 'scripts/restore_check.py' '.github/workflows/ci.yml' 'docs/runbook.md' 'docs/test-environment-handoff.md' 'backend/tests/ops/test_bootstrap_restore.py' 'backend/app/talents/retention_service.py'
git commit -m 'feat: T42 干净环境启动、备份恢复与测试环境交付'
~~~

### T43 生产准备、发布审批与运行交接

**阶段/前置：** G3；T42。**需求：** FR-01、FR-09、FR-10、FR-15。**负责接口：** 内部能力或界面，不新增公开业务API。

**文件：**

- Create: `infra/compose.production.yaml`
- Create: `infra/nginx.production.conf`
- Create: `docs/production-readiness.md`
- Create: `docs/release-checklist.md`
- Create: `docs/rollback-runbook.md`
- Create: `docs/operations-handoff.md`
- Create: `scripts/production_readiness.py`
- Create: `scripts/release_smoke.py`
- Create: `backend/tests/ops/test_production_readiness.py`

**Consumes：** 使用T42的Interfaces，调用已定义的原签名。

**Produces / 类与函数签名：**

~~~text
ProductionReadiness.check(self, config: ProductionConfig) -> ProductionReadinessReport
ReleaseVerifier.smoke(self, base_url: str, fixture_refs: DemoFixtureRefs) -> SmokeReport
~~~

**类型与规则：** ProductionConfig含正式HTTPS域名/证书引用/SMTP授权/数据保留策略/备份与告警接收方；只写配置引用。生产发布与真实候选人邮件在用户明确批准后执行，本轮计划不实际操作。

- [ ] **T43.1 建立失败场景与测试数据。** 在测试文件写入代表性断言，并补齐下面各场景；fixture不能返回固定成功结论。

~~~python
def test_readiness_blocks_missing_retention_backup(production_checker, incomplete_production_config):
    report = production_checker.check(incomplete_production_config)
    assert report.ready is False
    assert "RETENTION_POLICY_REQUIRED" in report.blocked_reasons
    assert "BACKUP_RESTORE_UNVERIFIED" in report.blocked_reasons
~~~

- [ ] **T43.1.1** test_public_https_candidate_access：受控测试账号从企业外网络验证。
- [ ] **T43.1.2** test_smtp_real_recipient_controlled：明确授权测试收件人真实收到且链接正确。
- [ ] **T43.1.3** test_readiness_blocks_missing_retention_backup：缺数据保留/备份/证书不得标可上线。
- [ ] **T43.1.4** test_rollback_keeps_submitted_answers：回滚应用不删除已交答卷/正式成绩。

- [ ] **T43.2 验证RED。** 运行下列相关测试，确认未实现行为引起预期断言失败并记录原因；环境/fixture错误先修复，不算有效RED。运维任务使用故障fixture验证阻塞，不给纯文档写镜像测试。
- [ ] **T43.3 最小实现。** 按上述签名逐函数实现及注册；只落实本任务规则，模型以04、HTTP以05为准。跨任务修改同步Interfaces、测试与附录B。
- [ ] **T43.4 验证GREEN及异常。** 执行：

~~~text
python scripts/preflight.py --profile production --report artifacts/production-preflight.json；经发布批准后python scripts/run_acceptance.py --profile production --scenario smoke
~~~

预期：测试全部PASS、构建成功、退出0。完成条件：交付发布/回退/监控/恢复记录；禁止对生产执行reset、down -v或数据库downgrade。没有生产授权时保持待批准，不影响G2测试交付完成。

- [ ] **T43.5 保存证据并审阅。** 记录实际版本、命令、结果、资源引用和未解决项至`artifacts/t43-verification.md`。秘密和真实候选人资料不入报告；环境/质量未满足标blocked。
- [ ] **T43.6 提交改动。** 在R已初始化Git且确认未混入用户改动后，仅暂存本任务文件；本地报告和secret默认不入Git。

~~~text
git add -- 'infra/compose.production.yaml' 'infra/nginx.production.conf' 'docs/production-readiness.md' 'docs/release-checklist.md' 'docs/rollback-runbook.md' 'docs/operations-handoff.md' 'scripts/production_readiness.py' 'scripts/release_smoke.py' 'backend/tests/ops/test_production_readiness.py'
git commit -m 'feat: T43 生产准备、发布审批与运行交接'
~~~

## 5. 类协作、事务边界与补充实施裁定

### 5.1 主要类协作

| 边界 | 输入 | 输出/下游 | 事务及副作用 |
|---|---|---|---|
| ImportService→解析worker→CandidateService | HR上传/岗位ID、文件ID | 简历版本、人才档案、岗位关系或待办 | 对象上传与DB分开；结果与后续outbox同事务 |
| ProfileService→ScreeningEngine→EvaluationService | 简历版本/共享事实/岗位版本 | 画像、三态条件结果、当前评估引用 | 先AI/规则计算后短事务；迟到旧结果不得覆盖当前 |
| MatchService→InvitationEligibility→InvitationService | 完成的评估版本及匹配分 | 唯一考次、冻结试卷/邮箱、外发事件 | 根身份/应聘锁＋唯一约束；SMTP在提交后 |
| NotificationDelivery→SmtpAdapter | 通知ID、冻结邮件修订 | accepted/failed/unknown | 接受不等于已读，unknown不自动盲重发 |
| CandidateAccessService→ExamService→AnswerService | 邀请token/邮箱核验、本人会话 | 开始时间、全题空答案、CAS保存与冻结提交 | 服务端UTC；不返回答案；已保存写MySQL |
| GradingService→ScoreReviewService | 冻结卷/答案、量表与来源 | AI建议/人工题分、不可变正式报告 | review/finalize先锁同考次；总分由服务端求和 |
| RecruitmentService→ReportService | HR人工决定、阶段事件 | 岗位招聘历史与统计 | 不做AI自动录用/淘汰，统计按授权和去重口径 |

构造器采用显式依赖注入：纯ScreeningEngine/MatchScorer/ObjectiveScorer不依赖DB；业务Service注入UowFactory、Clock、AccessPolicy及其实际使用的Gateway/Store/Dispatcher。Router只作认证、DTO/ETag/幂等key提取与服务调用，不包含打分/SQL或SMTP逻辑。Query类独立可读Session；repository.get(id,for_update=False)、add(entity)、find(QuerySpec)不commit，QuerySpec只允许白名单条件，禁止接收SQL字符串。

关键Service在同一个UoW内调用IdempotencyService.execute的command(uow)完成领域写入；callback不得再开Session。外部I/O已在锁外完成，入事务时复查状态/版本。响应封套可在事务后构造，但幂等记录必须与业务引用同事务提交。

### 5.2 本计划补全的非范围变更

| 情况 | 固定实施规则 | 负责 |
|---|---|---|
| 开启自动邀请前已有匹配结果 | false→true发invite.scan，仅扫未邀考、首次auto_allowed、当前合格记录；不扫manual_only或复活revoked | T12/T22/T30 |
| 缺邮箱/重复确认解决后恢复 | 状态ready时追加幂等pipeline.resume；不从头重复导入，不重复建岗位关系 | T15/T16/T30 |
| 合并后当前版本选择 | 目标人才保留当前简历/画像，源版本聚合为历史；HR明确修订才改变 | T16/T17 |
| 正在答题时开考有效期已过 | in_progress可在deadline前重新邮箱核验并恢复；not_started仍按valid_until拒绝；任何恢复不延时 | T24/T25 |
| 暂停与正在发送邮件竞争 | 发送前检查可取消尚未开始网络发送的信；已提交SMTP的信无法收回，界面不得声称已撤回 | T23/T39 |
| 正式成绩重开复核 | 当前attempt标pending_review，旧score_report仍可查；再finalize追加新版本，复核中不纳入正式均分 | T26/T36 |
| 资料保留与清除 | preview只读；隔离测试验证级联清理和重试；真实清除需范围/批准，默认关闭 | T42/T43 |

这些是既定流程的恢复/一致性细化，未引入新业务模块；若后续改变规则，应同步04/05/06和任务测试，不能只改页面。

### 5.3 首次联调的最小测试资料

管理员1名、部门A/B各1名HR；岗位A/B与不同已发布试卷；单选/多选/简答各至少1题；有效邮箱候选人、缺邮箱、硬条件不符、待核实、疑似重复、同岗位双历史档案各至少1组；无权部门资料和带明显私有评价sentinel；正常/失败/unknown三种SMTP结果；正文PDF/DOCX/图片/扫描PDF/旧DOC及损坏/加密样本。

全部用虚构/脱敏资料，邮箱使用受控测试收件箱。pytest固定时间，模型确定性单元替身与真实模型集成分开；真实质量数据集另建，不复用固定答复。

## 附录A：40张表→实体类→文件→任务

字段、FK、UK、索引和状态以04为唯一详细定义；本表固定实现文件，不重复抄写字段造成分歧。所有实体继承Base及id/created_at/updated_at/row_version约定。

| 数据表 | ORM类 | 文件（相对R） | 创建任务 |
|---|---|---|---|
| departments | Department | backend/app/identity/models.py | T03 |
| users | User | backend/app/identity/models.py | T03 |
| roles | Role | backend/app/identity/models.py | T03 |
| user_roles | UserRole | backend/app/identity/models.py | T03 |
| stored_files | StoredFile | backend/app/files/models.py | T03 |
| jobs | Job | backend/app/jobs/models.py | T03 |
| job_versions | JobVersion | backend/app/jobs/models.py | T03 |
| import_batches | ImportBatch | backend/app/ingestion/models.py | T03 |
| import_items | ImportItem | backend/app/ingestion/models.py | T03 |
| candidates | Candidate | backend/app/talents/models.py | T03 |
| resume_versions | ResumeVersion | backend/app/talents/models.py | T03 |
| candidate_profiles | CandidateProfile | backend/app/talents/models.py | T03 |
| duplicate_cases | DuplicateCase | backend/app/talents/models.py | T03 |
| applications | Application | backend/app/recruitment/models.py | T03 |
| evaluation_runs | EvaluationRun | backend/app/evaluation/models.py | T03 |
| screening_details | ScreeningDetail | backend/app/evaluation/models.py | T03 |
| match_results | MatchResult | backend/app/evaluation/models.py | T03 |
| recruitment_events | RecruitmentEvent | backend/app/recruitment/models.py | T03 |
| question_banks | QuestionBank | backend/app/assessment/models/papers.py | T03 |
| questions | Question | backend/app/assessment/models/papers.py | T03 |
| papers | Paper | backend/app/assessment/models/papers.py | T03 |
| paper_versions | PaperVersion | backend/app/assessment/models/papers.py | T03 |
| paper_items | PaperItem | backend/app/assessment/models/papers.py | T03 |
| exam_attempts | ExamAttempt | backend/app/assessment/models/exams.py | T03 |
| exam_answers | ExamAnswer | backend/app/assessment/models/exams.py | T03 |
| score_reviews | ScoreReview | backend/app/assessment/models/grading.py | T03 |
| notifications | Notification | backend/app/notifications/models.py | T03 |
| knowledge_documents | KnowledgeDocument | backend/app/knowledge/models.py | T03 |
| knowledge_chunks | KnowledgeChunk | backend/app/knowledge/models.py | T03 |
| model_configs | ModelConfig | backend/app/ai_runtime/models.py | T03 |
| prompt_versions | PromptVersion | backend/app/ai_runtime/models.py | T03 |
| workflow_configs | WorkflowConfig | backend/app/ai_runtime/models.py | T03 |
| background_jobs | BackgroundJob | backend/app/runtime/models.py | T03 |
| outbox_events | OutboxEvent | backend/app/runtime/models.py | T03 |
| ai_runs | AiRun | backend/app/ai_runtime/models.py | T03 |
| index_records | IndexRecord | backend/app/search/models.py | T03 |
| audit_logs | AuditLog | backend/app/audit/models.py | T03 |
| score_reports | ScoreReport | backend/app/assessment/models/grading.py | T03 |
| idempotency_records | IdempotencyRecord | backend/app/core/models.py | T03 |
| mail_configs | MailConfig | backend/app/notifications/models.py | T03 |

## 附录B：104条API→服务方法→handler与文件

路径省略/api/v1。handler函数使用下表给出的唯一名称；参数拆分path/query/body，actor由认证注入，ETag/Idempotency-Key由依赖读取；服务签名在所属任务的Interfaces。所有query类型字段在05列明，缺省PageQuery不引入新过滤字段。

此表要求显式注册路由；不是建议以运行时反射自动暴露Service所有方法。公开候选人DTO独立，管理员不能因函数存在而访问HR服务。

| API | 方法/路径 | 任务 | 服务方法 | Router文件 :: handler |
|---|---|---|---|---|
| API-001 | POST /auth/login | T05 | AuthService.login | backend/app/identity/router.py :: post_auth_login |
| API-002 | GET /auth/me | T05 | AuthService.me | backend/app/identity/router.py :: get_auth_me |
| API-003 | POST /auth/logout | T05 | AuthService.logout | backend/app/identity/router.py :: post_auth_logout |
| API-004 | GET /admin/users | T28 | IdentityQueries.users | backend/app/identity/router.py :: get_admin_users |
| API-005 | POST /admin/users | T05 | IdentityAdminService.create_user | backend/app/identity/router.py :: post_admin_users |
| API-006 | PATCH /admin/users/{id} | T05 | IdentityAdminService.update_user | backend/app/identity/router.py :: patch_admin_users_by_id |
| API-007 | GET /admin/departments | T28 | IdentityQueries.departments | backend/app/identity/router.py :: get_admin_departments |
| API-008 | POST /admin/departments | T05 | IdentityAdminService.upsert_department | backend/app/identity/router.py :: post_admin_departments |
| API-009 | PATCH /admin/departments/{id} | T05 | IdentityAdminService.upsert_department | backend/app/identity/router.py :: patch_admin_departments_by_id |
| API-010 | GET /admin/roles | T28 | IdentityQueries.roles | backend/app/identity/router.py :: get_admin_roles |
| API-011 | POST /admin/roles | T05 | IdentityAdminService.upsert_role | backend/app/identity/router.py :: post_admin_roles |
| API-012 | PATCH /admin/roles/{id} | T05 | IdentityAdminService.upsert_role | backend/app/identity/router.py :: patch_admin_roles_by_id |
| API-013 | PUT /admin/users/{id}/roles | T05 | IdentityAdminService.set_roles | backend/app/identity/router.py :: put_admin_users_by_id_roles |
| API-014 | GET /jobs | T28 | JobQueries.jobs | backend/app/jobs/router.py :: get_jobs |
| API-015 | POST /jobs | T12 | JobService.create | backend/app/jobs/router.py :: post_jobs |
| API-016 | PATCH /jobs/{id} | T12 | JobService.update | backend/app/jobs/router.py :: patch_jobs_by_id |
| API-017 | GET /jobs/{id} | T28 | JobQueries.detail | backend/app/jobs/router.py :: get_jobs_by_id |
| API-018 | POST /jobs/{id}/versions | T12 | JobService.draft | backend/app/jobs/router.py :: post_jobs_by_id_versions |
| API-019 | PATCH /job-versions/{id} | T12 | JobService.edit_draft | backend/app/jobs/router.py :: patch_job_versions_by_id |
| API-020 | POST /job-versions/{id}/publish | T12 | JobService.publish | backend/app/jobs/router.py :: post_job_versions_by_id_publish |
| API-021 | POST /jobs/{id}/state | T12 | JobService.transition | backend/app/jobs/router.py :: post_jobs_by_id_state |
| API-022 | PUT /jobs/{id}/automation | T12 | JobService.set_automation | backend/app/jobs/router.py :: put_jobs_by_id_automation |
| API-023 | POST /imports | T14 | ImportService.create | backend/app/ingestion/router.py :: post_imports |
| API-024 | GET /imports | T14 | ImportService.list_batches | backend/app/ingestion/router.py :: get_imports |
| API-025 | GET /imports/{id} | T14 | ImportService.get_batch | backend/app/ingestion/router.py :: get_imports_by_id |
| API-026 | POST /import-items/{id}/retry | T14 | ImportService.retry_item | backend/app/ingestion/router.py :: post_import_items_by_id_retry |
| API-027 | GET /talents | T28 | TalentQueries.talents | backend/app/talents/router.py :: get_talents |
| API-028 | GET /talents/{id} | T28 | TalentQueries.detail | backend/app/talents/router.py :: get_talents_by_id |
| API-029 | PATCH /talents/{id}/contacts | T15 | CandidateService.update_contacts | backend/app/talents/router.py :: patch_talents_by_id_contacts |
| API-030 | POST /talents/{id}/resume-corrections | T15 | CandidateService.correct_resume | backend/app/talents/router.py :: post_talents_by_id_resume_corrections |
| API-031 | GET /talents/{id}/resumes | T28 | TalentQueries.resumes | backend/app/talents/router.py :: get_talents_by_id_resumes |
| API-032 | POST /talents/search | T20 | TalentSearchService.search | backend/app/talents/router.py :: post_talents_search |
| API-033 | GET /duplicates | T16 | DuplicateService.list_cases | backend/app/talents/merge_router.py :: get_duplicates |
| API-034 | POST /duplicates/{id}/resolve | T16 | DuplicateService.resolve | backend/app/talents/merge_router.py :: post_duplicates_by_id_resolve |
| API-035 | POST /talents/{id}/archive | T15 | CandidateService.archive | backend/app/talents/router.py :: post_talents_by_id_archive |
| API-036 | GET /jobs/{id}/recommendations | T20 | TalentSearchService.recommend | backend/app/talents/router.py :: get_jobs_by_id_recommendations |
| API-037 | POST /jobs/{id}/applications | T19 | ApplicationService.add_candidates | backend/app/talents/router.py :: post_jobs_by_id_applications |
| API-038 | GET /applications | T28 | ApplicationQueries.list | backend/app/evaluation/router.py :: get_applications |
| API-039 | GET /applications/{id} | T28 | ApplicationQueries.detail | backend/app/evaluation/router.py :: get_applications_by_id |
| API-040 | POST /applications/{id}/evaluations | T19 | EvaluationService.start | backend/app/evaluation/router.py :: post_applications_by_id_evaluations |
| API-041 | GET /evaluations/{id} | T19 | EvaluationService.get | backend/app/evaluation/router.py :: get_evaluations_by_id |
| API-042 | POST /evaluations/{id}/override | T19 | EvaluationService.override | backend/app/evaluation/router.py :: post_evaluations_by_id_override |
| API-043 | GET /talents/{id}/profile | T17 | ProfileService.get | backend/app/talents/profile_router.py :: get_talents_by_id_profile |
| API-044 | POST /talents/{id}/profile-revisions | T17 | ProfileService.revise | backend/app/talents/profile_router.py :: post_talents_by_id_profile_revisions |
| API-045 | GET /jobs/{id}/matches | T28 | AssessmentQueries.matches | backend/app/evaluation/router.py :: get_jobs_by_id_matches |
| API-046 | GET /question-banks | T28 | AssessmentQueries.banks | backend/app/assessment/paper_router.py :: get_question_banks |
| API-047 | POST /question-banks | T11 | QuestionService.create_bank | backend/app/assessment/paper_router.py :: post_question_banks |
| API-048 | POST /questions | T11 | QuestionService.create | backend/app/assessment/paper_router.py :: post_questions |
| API-049 | GET /questions | T28 | AssessmentQueries.questions | backend/app/assessment/paper_router.py :: get_questions |
| API-050 | POST /questions/{id}/revisions | T11 | QuestionService.revise | backend/app/assessment/paper_router.py :: post_questions_by_id_revisions |
| API-051 | POST /questions/{id}/approve | T11 | QuestionService.approve | backend/app/assessment/paper_router.py :: post_questions_by_id_approve |
| API-052 | POST /question-generations | T35 | QuestionGenerationService.request | backend/app/assessment/generation_router.py :: post_question_generations |
| API-053 | GET /papers | T28 | AssessmentQueries.papers | backend/app/assessment/paper_router.py :: get_papers |
| API-054 | POST /papers | T11 | PaperService.create | backend/app/assessment/paper_router.py :: post_papers |
| API-055 | POST /papers/{id}/versions | T11 | PaperService.draft_version | backend/app/assessment/paper_router.py :: post_papers_by_id_versions |
| API-056 | PATCH /paper-versions/{id} | T11 | PaperService.edit_draft | backend/app/assessment/paper_router.py :: patch_paper_versions_by_id |
| API-057 | GET /paper-versions/{id} | T28 | AssessmentQueries.paper_version | backend/app/assessment/paper_router.py :: get_paper_versions_by_id |
| API-058 | POST /paper-versions/{id}/publish | T11 | PaperService.publish | backend/app/assessment/paper_router.py :: post_paper_versions_by_id_publish |
| API-059 | POST /applications/{id}/invitations | T22 | InvitationService.issue | backend/app/assessment/invitation_router.py :: post_applications_by_id_invitations |
| API-060 | GET /exam-attempts | T28 | AssessmentQueries.attempts | backend/app/assessment/invitation_router.py :: get_exam_attempts |
| API-061 | POST /exam-attempts/{id}/resend | T23 | InvitationResendService.resend | backend/app/assessment/invitation_router.py :: post_exam_attempts_by_id_resend |
| API-062 | POST /exam-attempts/{id}/revoke | T22 | InvitationService.revoke | backend/app/assessment/invitation_router.py :: post_exam_attempts_by_id_revoke |
| API-063 | POST /applications/{id}/exam-rounds | T22 | InvitationService.new_round | backend/app/assessment/invitation_router.py :: post_applications_by_id_exam_rounds |
| API-064 | POST /candidate/access/exchange | T24 | CandidateAccessService.exchange | backend/app/assessment/candidate_access_router.py :: post_candidate_access_exchange |
| API-065 | POST /candidate/access/send-code | T24 | CandidateAccessService.send_code | backend/app/assessment/candidate_access_router.py :: post_candidate_access_send_code |
| API-066 | POST /candidate/access/verify | T24 | CandidateAccessService.verify | backend/app/assessment/candidate_access_router.py :: post_candidate_access_verify |
| API-067 | GET /candidate/exam | T25 | ExamService.get | backend/app/assessment/candidate_exam_router.py :: get_candidate_exam |
| API-068 | POST /candidate/exam/start | T25 | ExamService.start | backend/app/assessment/candidate_exam_router.py :: post_candidate_exam_start |
| API-069 | PUT /candidate/exam/answers/{paper_item_id} | T25 | AnswerService.save | backend/app/assessment/candidate_exam_router.py :: put_candidate_exam_answers_by_paper_item_id |
| API-070 | POST /candidate/exam/submit | T25 | ExamService.submit | backend/app/assessment/candidate_exam_router.py :: post_candidate_exam_submit |
| API-071 | GET /candidate/exam/receipt | T25 | ExamService.receipt | backend/app/assessment/candidate_exam_router.py :: get_candidate_exam_receipt |
| API-072 | GET /exam-attempts/{id}/grading | T28 | AssessmentQueries.grading | backend/app/assessment/grading_router.py :: get_exam_attempts_by_id_grading |
| API-073 | PUT /exam-answers/{id}/review | T26 | ScoreReviewService.review | backend/app/assessment/grading_router.py :: put_exam_answers_by_id_review |
| API-074 | POST /exam-attempts/{id}/finalize | T26 | ScoreReviewService.finalize | backend/app/assessment/grading_router.py :: post_exam_attempts_by_id_finalize |
| API-075 | POST /exam-attempts/{id}/reopen-review | T26 | ScoreReviewService.reopen | backend/app/assessment/grading_router.py :: post_exam_attempts_by_id_reopen_review |
| API-076 | POST /applications/{id}/stage-transitions | T27 | RecruitmentService.transition | backend/app/recruitment/router.py :: post_applications_by_id_stage_transitions |
| API-077 | POST /applications/{id}/reopen | T27 | RecruitmentService.reopen | backend/app/recruitment/router.py :: post_applications_by_id_reopen |
| API-078 | POST /applications/{id}/interview-notes | T27 | RecruitmentService.add_interview_note | backend/app/recruitment/router.py :: post_applications_by_id_interview_notes |
| API-079 | POST /knowledge/documents | T34 | KnowledgeService.upload | backend/app/knowledge/router.py :: post_knowledge_documents |
| API-080 | GET /knowledge/documents | T34 | KnowledgeService.list_documents | backend/app/knowledge/router.py :: get_knowledge_documents |
| API-081 | POST /knowledge/documents/{id}/publish | T34 | KnowledgeService.publish | backend/app/knowledge/router.py :: post_knowledge_documents_by_id_publish |
| API-082 | POST /knowledge/documents/{id}/archive | T34 | KnowledgeService.archive | backend/app/knowledge/router.py :: post_knowledge_documents_by_id_archive |
| API-083 | POST /knowledge/documents/{id}/revisions | T34 | KnowledgeService.revise | backend/app/knowledge/router.py :: post_knowledge_documents_by_id_revisions |
| API-084 | POST /knowledge/ask | T34 | KnowledgeAnswerService.ask | backend/app/knowledge/router.py :: post_knowledge_ask |
| API-085 | GET /reports/recruitment | T36 | RecruitmentReportService.get | backend/app/reporting/router.py :: get_reports_recruitment |
| API-086 | GET /workbench/todos | T36 | TodoService.list | backend/app/reporting/router.py :: get_workbench_todos |
| API-087 | GET /admin/model-configs | T28 | RuntimeQueries.models | backend/app/ai_runtime/router.py :: get_admin_model_configs |
| API-088 | POST /admin/model-configs | T08 | ModelConfigService.create_revision | backend/app/ai_runtime/router.py :: post_admin_model_configs |
| API-089 | POST /admin/model-configs/{id}/test | T08 | ModelConfigService.test | backend/app/ai_runtime/router.py :: post_admin_model_configs_by_id_test |
| API-090 | GET /admin/workflows | T28 | RuntimeQueries.workflows | backend/app/ai_runtime/router.py :: get_admin_workflows |
| API-091 | PUT /admin/workflows/{task_type} | T08 | WorkflowConfigService.configure | backend/app/ai_runtime/router.py :: put_admin_workflows_by_task_type |
| API-092 | POST /admin/prompts | T08 | PromptService.create | backend/app/ai_runtime/router.py :: post_admin_prompts |
| API-093 | POST /admin/prompts/{id}/publish | T08 | PromptService.publish | backend/app/ai_runtime/router.py :: post_admin_prompts_by_id_publish |
| API-094 | GET /admin/runtime | T36 | AdminRuntimeQueries.overview | backend/app/ai_runtime/router.py :: get_admin_runtime |
| API-095 | GET /admin/audit-logs | T36 | AdminRuntimeQueries.audit | backend/app/ai_runtime/router.py :: get_admin_audit_logs |
| API-096 | POST /admin/mail-configs | T10 | MailConfigService.create | backend/app/notifications/router.py :: post_admin_mail_configs |
| API-097 | POST /admin/mail-configs/{id}/test | T10 | MailConfigService.test | backend/app/notifications/router.py :: post_admin_mail_configs_by_id_test |
| API-098 | GET /tasks/{id} | T06 | RuntimeQueries.task | backend/app/runtime/router.py :: get_tasks_by_id |
| API-099 | GET /files/{id}/download | T07 | FileService.authorized_download | backend/app/files/router.py :: get_files_by_id_download |
| API-100 | GET /health/live | T02 | health_live | backend/app/main.py :: get_health_live |
| API-101 | GET /health/ready | T02 | health_ready | backend/app/main.py :: get_health_ready |
| API-102 | GET /admin/mail-configs | T28 | RuntimeQueries.mail_configs | backend/app/notifications/router.py :: get_admin_mail_configs |
| API-103 | POST /admin/mail-configs/{id}/activate | T10 | MailConfigService.activate | backend/app/notifications/router.py :: post_admin_mail_configs_by_id_activate |
| API-104 | POST /admin/mail-configs/{id}/disable | T10 | MailConfigService.disable | backend/app/notifications/router.py :: post_admin_mail_configs_by_id_disable |

## 附录C：需求→开发任务→验收

| 需求 | 任务覆盖 | 验收 |
|---|---|---|
| FR-01 | T02、T03、T04、T05、T28、T29、T30、T31、T38、T39、T42、T43 | AT-01 |
| FR-02 | T03、T12、T28、T29、T30、T32、T38 | AT-02 |
| FR-03 | T03、T06、T07、T13、T14、T15、T28、T29、T30、T33、T38、T40、T41、T42 | AT-03 |
| FR-04 | T03、T15、T16、T19、T20、T28、T30、T33、T38、T39、T41、T42 | AT-04 |
| FR-05 | T03、T18、T19、T28、T30、T33、T38、T40 | AT-05 |
| FR-06 | T03、T09、T17、T28、T29、T30、T33、T38、T40 | AT-06 |
| FR-07 | T03、T09、T20、T21、T28、T30、T33、T38、T40、T41 | AT-07 |
| FR-08 | T03、T09、T11、T28、T30、T32、T35、T37、T38、T40 | AT-08 |
| FR-09 | T03、T06、T10、T22、T23、T28、T29、T30、T32、T33、T38、T39、T41、T42、T43 | AT-09 |
| FR-10 | T03、T24、T25、T29、T30、T38、T39、T41、T42、T43 | AT-10 |
| FR-11 | T03、T09、T26、T28、T29、T30、T33、T38、T39、T40、T42 | AT-11 |
| FR-12 | T03、T27、T29、T30、T33、T38 | AT-12 |
| FR-13 | T03、T09、T20、T34、T35、T37、T38、T40 | AT-13 |
| FR-14 | T03、T36、T37、T38、T41 | AT-14 |
| FR-15 | T01、T02、T03、T04、T06、T08、T10、T28、T30、T31、T36、T37、T38、T39、T41、T42、T43 | AT-15 |
| FR-16 | T37 | AT-16 |

## 附录D：验证命令、运行证据与恢复定位

所有命令都是将来执行的计划，当前未运行。T01先验证运行环境与锁版本；T02确认Compose项目名/端口/卷隔离。不要为了让命令运行而绕过权限或证书保护。文档里的分号只表示分步顺序；实际一条一条执行，某步失败停止相关后续步骤，不拼接成无条件批处理。

| 故障 | 应查证据 | 允许恢复 | 禁止做法 |
|---|---|---|---|
| Docker/WSL不可用 | preflight.json、引擎类型/健康 | 修复或使用已授权Linux测试机 | 原生Windows Celery冒充Linux通过 |
| 解析/OCR失败 | import_item/error_code、parser_revision、原文件 | 单份重试/补文件/人工修正 | 填固定姓名邮箱或跳过格式支持 |
| 模型质量不足 | 模型digest/提示词/来源/评测报告 | 调模型/规则后重跑独立评测 | 改标准答案或把失败记0分淘汰 |
| 向量索引失败 | index_records/job及collection/dimension | 从事实库重建，查询明确不可用 | 用结构化空结果伪装语义成功 |
| 邮件unknown | notification/mail_config_id/provider_message_id | 核对后显式重发，记录新通知 | 自动无限重发或宣称恰好一次 |
| 答题断线/冲突 | saved_at/revision/deadline/request_id | 本人重新核验恢复，冲突提示 | 客户端改时间、静默覆盖、Redis清空丢答卷 |
| 分数不一致 | score_reviews/score_reports/锁竞争证据 | 重开复核并发新报告 | 原位改旧正式成绩 |
| 人才合并冲突 | canonical根/application_mappings/活动考次 | HR先解决冲突再原子合并 | 先迁移一半或删除历史考试 |

### 阶段交付证据

- M0：精确版本清单、预检报告、核心健康检查。
- M1：空库迁移/重复迁移证据、角色隔离、真实模型与Mailpit/MinIO/Milvus读写。
- G1：batch/item→file/resume→candidate/canonical→application/job_version→profile/evaluation/match→attempt/paper→notification→answers→score_report→recruitment_event完整ID链。
- M3：各角色页面走查、人才复用、引用问答、统计及规划培训的截图/请求证据。
- M4：104契约报告、AT-01～16、质量分项/置信边界、性能p50/p95/p99、故障恢复结果。
- G2：锁文件、镜像digest、Compose、配置样例、启动脚本、迁移、演示资料、运行/恢复手册；不得带真实secret。
- G3：正式域名/证书/SMTP/数据保留政策/备份/告警及批准记录；未获批准可停留G2，不伪称已上线。

### 继续开发时的最短交接

执行者先读01、03、04、05、06和本计划，检查R及AGENTS，选当前首个未完成且依赖已满足的任务；只实现该任务并记录测试，完成才勾选。新任务开始前不得跳过前项blocked状态。已完成事实来自测试报告和提交，不来自聊天口头“差不多”。

若用户选择逐任务独立实现/复核，按已安装的subagent-driven-development执行；若用户选择同一会话原生实现，则按executing-plans逐项执行并在阶段门审阅。本轮不选择或启动开发执行模式，也不自动创建新聊天。

## 6. 计划自审记录（文档层面）

1. 已逐一映射FR-01～FR-16、40表、104接口；未引入延期模块的业务表/执行接口。
2. 已检查任务依赖为有向无环且顺序满足，查询服务提前于最小界面，完整扩展在G1之后。
3. 每个API绑定的方法在所属任务Interfaces存在；新增读方法、邮件修订启停、合并映射、空答案初始版本已补齐。
4. 五项Review Focus均有明确任务和测试；新增开关补扫、去重恢复、已开考重新核验等补充规则已写到任务。
5. 计划只包含待执行步骤与测试断言，没有实现产品代码/DDL/部署、没有把开发项预勾完成。
6. 评审文档保留原样，本计划细化实现责任；将来正式契约调整必须同步原设计文档，不以本计划隐藏替换需求。

本轮静态校验只证明文档的引用、覆盖和依赖一致，不证明环境、迁移、AI质量、浏览器或业务测试通过。

### 本轮计划静态检查结果

- 43项主任务均有前置、文件、Interfaces、测试场景、验证命令与完成条件；依赖无环且前置均排在前面。
- 40张表均有ORM类及文件归属，104条API均有所属任务、已定义服务方法及router路径。
- FR-01～FR-16全部有任务和验收映射；7个设计文档链接有效。
- 共218条显式类/函数签名、198个具名验证场景；所有开发步骤保持未勾选。
- 未执行任何实现、迁移、构建、模型或浏览器测试。本结果是文档检查，不是软件通过验收。


## 模型与数据库实施补充（2026-11-05）

用户指定云端 deepseek-flash、text-embedding-v3（原文 test-embedding-v3）和可选 qwen3-rerank，并授权择需复用 D:/Wolin_Project/Yue-Education/.env 的凭据。详见项目根目录《模型接入与数据库决策补充-2026-11-05.md》和代码 docs/MODEL_AND_DATABASE_DECISION.md。T08/T09 以确认后的 DeepSeek/DashScope 适配器为主；Ollama 路径改为可选，T09/T40 的实际质量证据必须来自本轮选择的模型。T20 加入权限过滤后的可选 rerank。LLM 官方凭据或代理渠道尚待确认；追加指定目录已查得百炼北京共享 endpoint，接入时据此验证，无需重复询问地域。尚无云端连通成功证据；不得勾选相关任务完成。数据库迁移影响较大，依用户指示保留 MySQL+Milvus。


T08 实际验证补充：已按旧SDK用途选取授权文件的 ALIYUN_API_KEY（DASHSCOPE_API_KEY为占位项），主项目私有环境配置后 text-embedding-v3 两条合成文本返回1024维；完整当前测试126通过。DeepSeek官方Key/明确代理渠道仍缺，T09/T20不因此视为完成。


2026-11-05更新：新增授权根目录.env已提供DeepSeek官方Key，deepseek-flash最小JSON验证通过，配置ID3；T09尚待网关/固定图与实际业务质量验证，保持未勾选。

2026-11-06接口补充：T09的AiConfigSnapshot必须包含config_revision并在调用前校验；云端EmbeddingBatch不再要求虚构权重digest，以model_config_id/revision_no/model_name和实际dimension供T20隔离索引。T09已通过真实官方合成门，Docker经授权重启恢复后完整186通过，任务完成；下一步T12。


## 仓库与实施规范补充（2026-11-06）

用户要求上传GitHub：samJ-03/AI-Digital-Talent-Management。代码补齐模块/公开类函数说明、前端JSDoc及40表478字段SQL COMMENT，追加0005/0006注释迁移，不能修改已应用历史迁移。新增无秘密.env_example（兼容.env.example）及安全init_env脚本、README、配置与数据库字典、docs/specs仓库内规格副本。最终完整190通过，前端lint/typecheck/build通过；不重复付费模型调用。后续新代码遵循docs/CONTRIBUTING.md，字段变更同步数据库字典；.env和本地执行证据不上传。功能进度仍T01～T11完成，下一步T12。


## 核心交付优先级调整（2026-11-07）

用户已确认先以T30最小纵向招聘闭环为可用交付目标。T12已通过19项定向及209项完整测试，本地合成岗位9项验证通过；实际邀考消费者仍留T22/T23。优先T13～T30并穿插最小页面，T31～T37扩展后补；高级语义检索和复杂扫描件优化后补时，相关原任务不得提前勾选，质量门及依赖接口仍须保留。详情见[核心交付顺序](../CORE_DELIVERY_PRIORITY.md)。本轮无生产部署。


### T13核心格式子任务进度（2026-11-08）

文本PDF与普通文字DOCX内部解析已实现，32项定向测试通过；真实段落/表格/页眉来源和进程资源保护已验证。支持范围见[解析说明](../CORE_PARSER_SUPPORT.md)。原T13整体仍未完成：ResumeExtractor、OCR、旧DOC转换、物理Word分页及五格式整体验收继续待做。这里只勾选已验证的T13.1.1，其他步骤不因子任务交付提前勾选。

2026-11-09：ResumeExtractor子任务18项定向/259项完整测试通过；缺失邮箱保持未知已验证，T13整体仍未完成。下一步T14/T15核心导入建档。


### T14实施核验（2026-11-09）

21项定向、280项完整测试与本地合成批次7项受理检查通过；0007允许仅failed条目缺少文件引用并保护无损降级。当前只到受理/轮询/重试，T15处理器与人才建档未完成，不声称缺邮箱已形成可用人才档案。下一步T15，原T13全格式仍待后补。
