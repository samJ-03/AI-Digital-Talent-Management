# AI数字化人才平台 · 一期核心开发Todolist

> 执行方式：沿用Superpowers executing-plans，逐项RED→GREEN，阶段末独立审查。本文依据用户2026-11-10“按审查修正、一期仅核心、其余二期”的授权修订；不再按历史完整计划顺序机械实施。

**Goal：** HR准备岗位与试卷→导入外部简历→三态硬筛/共享画像/岗位匹配→唯一邀考→候选人答题→评分复核→HR人工决定，最小页面可以操作全链路。
**Architecture：** 现有模块化单体；router/schema→service→ORM或适配器，纯计算单独rules/scorer。MySQL事实与任务、MinIO原件、Redis会话/交付；不补机械Repository、QuerySpec或新流程平台。
**Spec：** [01范围](01-需求分析与PRD.md)、[03架构](03-总体架构与技术设计.md)、[04数据语义](04-数据库表与数据一致性设计.md)、[05接口](05-接口契约设计.md)、[06验收](06-验收标准与联调验证方案.md)。历史T01～T43全文见[归档](../plans/archive/2026-11-10-original-full-plan.md)，不能据旧Create清单覆盖现有代码。

## 1. 本期边界与统一完成标准

- 单企业、外部候选人；管理员配置，HR招聘，候选人只访问本人考次。部门私有考试/评价不能进入共享画像或向量。
- 缺邮箱可入库，不能自动筛选/邀考；重复待核不自动推进。unknown不填0、不伪装通过；人工例外有理由且不绕邮箱、开放岗位、发布试卷等技术门。
- 自动邀请默认关闭；重评与人工继续manual_only。当前run在受理事务切换；新run未就绪时不能沿用旧分数邀请。
- 岗位/简历/画像/试卷/评估/正式成绩保留版本。合并按canonical别名/主应聘聚合，不移动历史归属。
- 公开ID用string，数据库UTC；HTTP候选人DTO独立，不能泄露答案/评分量表/内部评价。
- 每个命令一个UoW提交业务、审计、幂等和任务/outbox；回调不得commit或另开Session。模型/SMTP/文件网络I/O在锁外，最终发布复验来源/权限/配置/租约。
- 破坏性数据库验证只允许talent_test。不能reset开发库、删数据卷、提交秘密/原始简历/运行证据。
- 常规回归模型/邮件用受控传输；G1必须真实选定供应商和Mailpit合成闭环，真实模型质量另有样本门，不能用单元数量替代质量。
- 每任务只保留特有失败场景和验证命令；共用步骤为失败测试→观察有效RED→最小实现→定向GREEN→审查/相应回归→证据/提交。环境失败不计RED。

状态：已验证 / 部分完成 / 待做 / 二期延期；“已验证”只覆盖所列能力，真实模型质量、业务页面与G1另列，不暗示已经跑通招聘。最新代码/验证入口只有[handoff](../DEVELOPMENT_HANDOFF.md)，此处不维护会不断过时的测试总数。

## 2. 已完成能力（无需重新搭建）

|任务|状态|一期采用范围/证据|
|---|---|---|
|T01～T07|已验证|环境、最小应用、40表、权限审计幂等、持久任务、私有文件；见handoff与现有测试|
|T08～T10|已验证|受控模型/提示词配置、网关、SMTP测试配置；不自动开启模型或企业邮件|
|T11～T12|已验证|题库/发布试卷、岗位版本/自动邀请配置；配置开关不等于实际发信|
|T13a|已验证|文本PDF/DOCX解析、受控字段提取；[支持边界](../CORE_PARSER_SUPPORT.md)、[提取契约](../RESUME_EXTRACTION_CONTRACT.md)|
|T13b|二期延期|OCR/MinerU、扫描图片、旧DOC、Word物理分页与全格式性能验收|
|T14|已验证|[批量受理/轮询/单份重试](../IMPORT_BATCH_CONTRACT.md)|
|T15|已验证|[建档/邮箱门/不可变修订](../CANDIDATE_MATERIALIZATION_CONTRACT.md)，前置是T13a+T14，不是整个OCR任务|
|T16|已验证|[人工去重与历史合并](../DUPLICATE_RESOLUTION_CONTRACT.md)|
|T17|已验证|[共享事实画像/授权岗位视图/恢复](../PROFILE_GENERATION_CONTRACT.md)|
|T18|已验证|[确定性三态规则](../SCREENING_RULES_CONTRACT.md)|
|T19|已验证|[应聘复用/冻结评估/人工继续](../EVALUATION_SNAPSHOTS_CONTRACT.md)|
|T20|已验证，保留可选|[真实Milvus语义检索后端](../SEMANTIC_SEARCH_AND_MATCH_CONTRACT.md)；高级界面/rerank不阻塞一期，Milvus非核心匹配依赖|
|T21|已验证|[证据匹配/服务端加权/租约提交](../SEMANTIC_SEARCH_AND_MATCH_CONTRACT.md)；直接消费冻结履历与岗位，不依赖语义找人|

已完成内容的本轮修正：单次生成使用薄执行器而非构建单节点图；公开最少跨领域接口；wire字段按05统一；真实状态/文件归属与代码核对。结果见本轮验收记录，不能据此把T22以后勾选。

## 3. 剩余核心顺序与最小操作入口

立即下一业务任务是T22。T28/T29按a/b/c跟随交付，不等待所有后端后一次补界面：

|任务|状态|真实依赖|交付|
|---|---|---|---|
|T38a|本轮建立基础|现行已实现API|OpenAPI导出与manifest检查，未实现/二期明确标识|
|T28a/T29a|待做|T05/T11/T12/T14～T19|基本账号/岗位/人才查询、登录、岗位/试卷准备、导入/评估页面|
|T22|待做|T19/T21/T11/T10|资格门、唯一考次、冻结邀请与通知/Outbox|
|T23|待做|T22/T10/T06|真实Mailpit投递、unknown与显式重发|
|T24/T25|待做|T23/T11/T06|候选人核验、服务端计时/保存/统一交卷|
|T28b/T29b|待做|对应T22～T25产物|考次读取、邀请操作、候选人考试页面|
|T26/T27|待做|T25/T09、T19|客观分/人工复核/正式报告、HR招聘决定|
|T28c/T29c|待做|T26/T27|评分与招聘读取、复核/推进页面|
|T39a/T40a/T41a/T42a|待做，跟随模块|对应核心产物|安全竞争/真实AI质量/资源/干净启动与恢复最小门|
|T30|待做|上述核心功能及质量门|G1合成纵向验收，不能靠开发者直接改数据库完成业务动作|

G1初次部署允许受控CLI创建管理员、合成示范资料和发布模型提示词/schema；必须在手册明确操作者/命令/输出引用。HR应能从页面选择现有发布卷并建岗、导入、处理待办、查看评估、邀考、复核和推进。最小试卷编辑/发布表单纳入T29a；完整管理员管理台/复杂题库交互留二期。禁止用只有seed_demo成功冒充HR可操作。

## 4. 当前可复用接口与任务协议

- EvaluationService.resource_scope(uow,application_id)->ResourceScope；is_current(uow,run)->bool。只在调用方UoW内复验，不自行提交；T22据此核对当前来源，再读取冻结评估/匹配。
- CandidateService.resume_view(row)->ResumeVersionView供内部已授权事实投影；权限由调用业务服务负责，不能作为公开HTTP绕过授权。
- ProfileService.current(uow,candidate_id,resume_version_id)仅返回当前可核查画像；MatchScorer/ScreeningEngine/ObjectiveScorer均为纯计算，不注入DB。
- BackgroundJobService.enqueue(uow,JobSpec)->int在同业务事务写任务/交付事件。短处理器handler(uow,job)->ResultRef或TerminalJobFailure；外部I/O处理器prepare(lease)->finalize(uow,job)，可提供finalization_context()，由JobRunner复验有效租约并原子提交。不能改回Callable[[int],ResultRef]。
- Query服务归所属领域：匹配归evaluation，试卷/考次归assessment，模型配置归ai_runtime，SMTP配置归notifications；runtime仅任务/技术视图。复用已存在IdentityQueries与RuntimeAdminQueries，不再Create同名文件。

### 事件与恢复唯一责任

|事件/任务|生产者|消费者|去重/事务|
|---|---|---|---|
|job.dispatch|BackgroundJobService/租约恢复|OutboxDispatcher→Celery→JobRunner|dispatch:job_id:attempt_count；业务任务先持久化|
|resume.parse|ImportService|ResumeParseHandler|沿现行导入契约，不接收自由脚本|
|pipeline.resume|人才补邮箱/去重处理|PipelineResume|只恢复画像前提，不创建另一套中央状态机|
|application.evaluate.requested|新关系/初次恢复|InitialEvaluation|application-initial:id；仅从未评估的关系|
|application.evaluate|EvaluationService|EvaluationHandler|evaluation:run_id；旧结果不推进当前|
|evaluation.match.requested|粗筛通过/人工继续|MatchDispatch→MatchHandler|application-match:run_id；按实际模型与来源复验|
|profile.index（可选）|IndexRecovery|ProfileIndexHandler|模型代际+profile/hash；不阻塞一期匹配|
|invite.scan（T22待接）|岗位开关false→true|T22邀请消费者|只扫描从未邀考首次auto_allowed；不能复活revoked|
|invitation.evaluate.requested（T22待加）|T21有效当前匹配finalize同事务|T22邀请消费者|每run唯一；T22需Modify match_service.py生产此事件|
|notification.send（T22/T23待接）|邀考/验证码命令|通知处理器|同事务enqueue固定引用；SMTP未知不自动盲发|
|exam.grade（T25/T26待接）|统一submit_once|评分处理器|attempt+submission_revision；只首次交卷排队|

恢复扫描只做本领域前提恢复；runtime负责交付/租约，不作招聘判断。T30不新增resume_pipeline万能入口。

## 5. 各核心任务的增量施工说明

### T22 邀请资格门与唯一考次创建

**阶段/真实前置：** M2；T21、T11、T10。**需求：** FR-09。**负责接口：** API-059、API-062、API-063。

**文件：**

- Create: `backend/app/assessment/invitation_service.py`
- Create: `backend/app/assessment/eligibility.py`
- Create: `backend/app/assessment/invitation_router.py`
- Create: `backend/tests/integration/test_invitation_eligibility.py`


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


**本轮补齐的实施边界：** 新增invitation_tokens.py：InvitationTokenService.issue(uow,attempt_id)->EncryptedTokenPayload，token仅hash/短期密文持久化；rotate在T23扩展。Modify evaluation/match_service.py，在有效当前匹配结果同事务生产invitation.evaluate.requested；接入现有runtime/scheduler.py消费该事件与invite.scan。不能只接开关事件而遗漏后续新匹配。技术门对手动/自动均成立；manual_override只允许有理由越过业务筛选/邀请线，不篡改原结果；unknown维度只阻止自动邀请，人工例外必须显式记录。新增run pending而旧run高分不得邀请测试。

**必须通过的失败/竞争场景：**

- [ ] test_all_gates_required：任一前提失败不创建考次/外发事件。
- [ ] test_two_workers_one_attempt：并发自动触发只一考次。
- [ ] test_reassessment_manual_only：manual_only不得自动issue。
- [ ] test_manual_override_requires_reason：只覆盖业务筛选，不绕邮箱/卷/岗位。
- [ ] test_new_round_no_active_attempt：活动考次不能再开一轮。
- [ ] test_enable_later_scans_only_never_invited：关开切换只处理未邀考首次评估，不复活撤销或重评。

**验证：** `python scripts/compose.py exec -T api python -m pytest tests/integration/test_invitation_eligibility.py -q`；再按本节实际变更运行必要回归，证据保存在artifacts/t22-verification.md。

### T23 邮件投递、未知结果与重发

**阶段/真实前置：** M2；T22、T10、T06。**需求：** FR-09。**负责接口：** API-061。

**文件：**

- Create: `backend/app/notifications/delivery_service.py`
- Create: `backend/app/notifications/worker.py`
- Create: `backend/app/assessment/resend_service.py`
- Create: `backend/tests/integration/test_invitation_delivery.py`
- Modify: `backend/app/assessment/invitation_router.py`（首次创建于T22）


**Produces / 类与函数签名：**

~~~text
NotificationDelivery.send(self, notification_id: int) -> DeliveryResult
InvitationResendService.resend(self, actor: ActorContext, attempt_id: int, reason: str) -> NotificationView
InvitationTokenService.rotate(self, uow: SqlAlchemyUow, attempt_id: int) -> EncryptedTokenPayload
NotificationSendHandler.prepare(self, lease: JobLease) -> Callable[[SqlAlchemyUow, BackgroundJob], ResultRef | TerminalJobFailure]
NotificationSendHandler.finalization_context(self) -> ContextManager
~~~

**类型与规则：** NotificationView={id,attempt_id,purpose,status,mail_config_id,attempt_count,error_code?}; EncryptedTokenPayload={token_hash,ciphertext,expires_at}，仅敏感outbox短存；首次冻结active邮件修订，停用转待办，显式resend取新active修订并记新通知。


**本轮补齐的实施边界：** 复用T22创建的InvitationTokenService；首次邀请和重发共用冻结通知产物，不另开通用邮件平台。NotificationDelivery.prepare在锁外SMTP，最终状态在有效租约提交；先持久processing使崩溃变unknown。Modify runtime/worker.py注册notification.send。

**必须通过的失败/竞争场景：**

- [ ] test_pause_before_send_revokes：发前暂停→notification.cancelled＋invite.revoked。
- [ ] test_timeout_after_accept_unknown：接受后超时unknown不盲重发。
- [ ] test_resend_same_attempt_rotates_token：未开考换token但考次不变。
- [ ] test_no_token_in_logs：token/验证码不入日志。
- [ ] test_mailpit_invitation_contents：岗位、时限、专属链接正确。

**验证：** `python scripts/compose.py exec -T api python -m pytest tests/integration/test_invitation_delivery.py -q`；再按本节实际变更运行必要回归，证据保存在artifacts/t23-verification.md。

### T24 候选人入口、邮箱核验与考次会话

**阶段/真实前置：** M2；T23、T05。**需求：** FR-10。**负责接口：** API-064、API-065、API-066。

**文件：**

- Create: `backend/app/assessment/access_service.py`
- Create: `backend/app/assessment/candidate_access_router.py`
- Create: `backend/app/assessment/code_store.py`
- Create: `backend/tests/integration/test_candidate_access.py`


**Produces / 类与函数签名：**

~~~text
CandidateAccessService.exchange(self, invitation_token: str) -> VerificationContext
CandidateAccessService.send_code(self, context_id: str) -> None
CandidateAccessService.verify(self, context_id: str, code: str) -> ExamSessionView
CodeStore.verify_once(self, challenge_id: str, code: str) -> bool
CandidateSessionStore.require(self, session_id: str) -> ActorContext
~~~

**类型与规则：** VerificationContext={id,masked_email,expires_at}; ExamSessionView={attempt_id,state}，会话token只写安全Cookie；验证码哈希/TTL/错误次数原子操作。参数中禁止接收可改写的收件邮箱。


**本轮补齐的实施边界：** 新增assessment/candidate_sessions.py承接CandidateSessionStore；不得复用后台Cookie。验证码收件人来自冻结考次，发码复用通知任务；限制过期、频率、错误次数和单次消费。

**必须通过的失败/竞争场景：**

- [ ] test_unverified_no_questions：未验证响应无试题。
- [ ] test_code_single_use_and_rate_limit：用过/过期不能验证，限频429。
- [ ] test_revoked_link_fails：旧轮换/撤销token拒绝。
- [ ] test_session_bound_to_attempt：不能换ID读另一考次。
- [ ] test_invalid_token_no_email_leak：无效token不泄露完整邮箱。
- [ ] test_started_exam_reverify_before_deadline：已开考且deadline未到时可重新核验，即使开考有效期已过。

**验证：** `python scripts/compose.py exec -T api python -m pytest tests/integration/test_candidate_access.py -q`；再按本节实际变更运行必要回归，证据保存在artifacts/t24-verification.md。

### T25 服务端计时、答题保存和统一提交

**阶段/真实前置：** M2；T24、T11、T06。**需求：** FR-10。**负责接口：** API-067、API-068、API-069、API-070、API-071。

**文件：**

- Create: `backend/app/assessment/exam_service.py`
- Create: `backend/app/assessment/answer_service.py`
- Create: `backend/app/assessment/candidate_exam_router.py`
- Create: `backend/app/assessment/deadline_service.py`
- Create: `backend/tests/integration/test_exam_lifecycle.py`
- Create: `backend/app/assessment/submission.py`


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


**本轮补齐的实施边界：** submission.py拥有submit_once(uow,attempt,now,reason)->SubmissionReceipt，manual/timeout共用同一幂等提交；仅首次enqueue exam.grade。Modify runtime/scheduler.py接DeadlineService，不能靠GET或浏览器计时推进。

**必须通过的失败/竞争场景：**

- [ ] test_start_twice_same_deadline：重复开始不重置时间。
- [ ] test_first_save_revision_zero：expected_revision=0首次成功。
- [ ] test_save_conflict_409：双设备旧版本保存拒绝。
- [ ] test_deadline_submit_without_browser：浏览器关闭照样超时交卷。
- [ ] test_submit_vs_timeout_one_event：并发提交只冻结一次。
- [ ] test_candidates_never_get_answer_key：响应无标准答案。

**验证：** `python scripts/compose.py exec -T api python -m pytest tests/integration/test_exam_lifecycle.py -q`；再按本节实际变更运行必要回归，证据保存在artifacts/t25-verification.md。

### T26 客观评分、主观建议与正式成绩版本

**阶段/真实前置：** M2；T25、T09。**需求：** FR-11。**负责接口：** API-073、API-074、API-075。

**文件：**

- Create: `backend/app/assessment/objective_scorer.py`
- Create: `backend/app/assessment/grading_service.py`
- Create: `backend/app/assessment/review_service.py`
- Create: `backend/app/assessment/grading_router.py`
- Create: `backend/tests/unit/test_objective_scoring.py`
- Create: `backend/tests/integration/test_score_reports.py`


**Produces / 类与函数签名：**

~~~text
ObjectiveScorer.score(self, item: FrozenPaperItem, answer: AnswerValue | None) -> Decimal
GradingService.grade(self, attempt_id: int) -> GradingView
ScoreReviewService.review(self, actor: ActorContext, answer_id: int, cmd: ReviewCommand) -> ReviewView
ScoreReviewService.finalize(self, actor: ActorContext, attempt_id: int, expected_version: int, reason: str) -> FormalScoreView
ScoreReviewService.reopen(self, actor: ActorContext, attempt_id: int, expected_version: int, reason: str) -> GradingView
~~~

**类型与规则：** ReviewCommand={score,reason,expected_revision}; FrozenPaperItem={type,max_score,answer_key,rubric}; AnswerValue为选择keys或text；主观AI建议不写final_score，空题全部确定性0。正式score_reports包含全题快照；全客观卷用system actor自动finalize。


**本轮补齐的实施边界：** 纯ObjectiveScorer不依赖DB。外部AI建议在prepare生成，锁考次finalize落建议，不冒充正式成绩。全客观自动正式化使用明确内部system路径；HR review/finalize/reopen保持独立权限、同一考次锁和旧报告不可变。Modify runtime/worker.py注册exam.grade。

**必须通过的失败/竞争场景：**

- [ ] test_multiple_choice_all_or_nothing：全对满分，漏/多选0。
- [ ] test_blank_subjective_zero_no_review_needed：未答简答0且不阻塞。
- [ ] test_ai_failure_manual_review：AI失败仍可HR评分。
- [ ] test_review_finalize_same_lock：并发题分和总分一致。
- [ ] test_finalized_cannot_direct_review：须reopen再生成新报告。
- [ ] test_score_reports_immutable：旧正式版本不能改。

**验证：** `python scripts/compose.py exec -T api python -m pytest tests/unit/test_objective_scoring.py tests/integration/test_score_reports.py -q`；再按本节实际变更运行必要回归，证据保存在artifacts/t26-verification.md。

### T27 招聘阶段、面试评价与人工决定

**阶段/真实前置：** M2；T19、T26。**需求：** FR-12。**负责接口：** API-076、API-077、API-078。

**文件：**

- Create: `backend/app/recruitment/service.py`
- Create: `backend/app/recruitment/transitions.py`
- Modify: `backend/app/recruitment/router.py`（保留已存在API037）
- Create: `backend/tests/integration/test_recruitment_transitions.py`


**Produces / 类与函数签名：**

~~~text
RecruitmentService.transition(self, actor: ActorContext, application_id: int, cmd: StageTransition) -> ApplicationView
RecruitmentService.reopen(self, actor: ActorContext, application_id: int, expected_version: int, reason: str) -> ApplicationView
RecruitmentService.add_interview_note(self, actor: ActorContext, application_id: int, cmd: InterviewNote) -> RecruitmentEventView
TransitionPolicy.validate(self, current: str, target: str, has_active_exam: bool) -> None
~~~

**类型与规则：** StageTransition={to_stage,reason,expected_version}; InterviewNote={evaluation,interviewed_at}; 阶段字面值原样使用04；人工可带reason跳过非终态阶段，不抹去活动考试。


**本轮补齐的实施边界：** 复用现有recruitment/router.py和application_service.py；RecruitmentService仅人工阶段/面试记录，不重新实现应聘创建、匹配、邀考或评分。候选人、模型与system不得作录用决定。

**必须通过的失败/竞争场景：**

- [ ] test_no_ai_hire_action：system/候选人不能调用HR录用。
- [ ] test_rejection_job_specific：岗位A拒绝不影响B。
- [ ] test_terminal_late_worker_no_invite：终态迟到任务不推进。
- [ ] test_reopen_explicit_event：复开留reason和事件。
- [ ] test_private_note_not_shared：面试备注只在岗位权限内。

**验证：** `python scripts/compose.py exec -T api python -m pytest tests/integration/test_recruitment_transitions.py -q`；再按本节实际变更运行必要回归，证据保存在artifacts/t27-verification.md。

### T28a/b/c 分领域读接口（跟随交付，不再集中重建）

**Files：** Modify identity/queries.py、runtime/admin_queries.py及所属router，保留现有用户/部门/角色/技术运行接口；Create jobs/queries.py、talents/queries.py、recruitment/queries.py、evaluation/queries.py、assessment/queries.py、backend/tests/integration/test_read_permissions.py。模型/流程/邮件配置读取在原领域补全，不塞入RuntimeQueries；T28a还需Modify ai_runtime/config_service.py与notifications/config_service.py及各自router。

**T28a前置：** 当前T05/T12/T15/T17；提供JobQueries.jobs(actor,JobQuery)->Page[JobView]、detail(actor,job_id)->JobDetail；TalentQueries.talents(actor,TalentListQuery)->Page[TalentView]、detail(actor,candidate_id)->TalentDetail、resumes(actor,candidate_id)->list[ResumeVersionView]。
**T28a必要准备读取：** AssessmentQueries.banks(actor,PageQuery)->Page[QuestionBankView]、questions(actor,QuestionQuery)->Page[QuestionView]、papers(actor,PageQuery)->Page[PaperView]、paper_version(actor,version_id)->PaperVersionView；ModelConfigService.list(actor)->list[MaskedModelConfig]与MailConfigService.list(actor)->list[MaskedMailConfig]在原配置领域新增，默认只返回脱敏连接状态、不返回密钥。已有WorkflowConfigService.list继续复用。
**T28b前置：** T19/T22/T25；ApplicationQueries.list(actor,ApplicationQuery)->Page[ApplicationView]、detail(actor,application_id)->ApplicationDetail；AssessmentQueries.attempts(actor,AttemptQuery)->Page[AttemptView]；EvaluationQueries.matches(actor,MatchQuery)->Page[MatchView]。
**T28c前置：** T26/T27；AssessmentQueries.grading(actor,attempt_id)->GradingView及已授权招聘历史。题库/试卷查询复用PaperService/QuestionService或在assessment/queries增加只读投影，不重新实现写规则。

**查询DTO：** 共用page≥1/page_size默认20≤100；JobQuery={status?,department_id?,page,page_size}；TalentListQuery={q?,status?,skills[],education?,major?,page,page_size}，与不分页的语义过滤TalentFilter分开；ApplicationQuery={job_id?,stage?,screening_result?,page,page_size}；AttemptQuery={job_id?,state?,invite_status?,page,page_size}；MatchQuery={job_id,min_score?,state?,page,page_size}（job_id由path可信构造）；QuestionQuery={bank_id?,type?,state?,page,page_size}。缺省过滤排除归档人才，状态过滤显式可选；排序created_at DESC,id DESC。只允许白名单参数。

**权限：** HR共享事实可见，私有应聘/答卷/面试按岗位部门逐条复验；其他部门只显示有历史记录，不给详情正文。管理员不能读取HR资料。DTO不自动序列化整个ORM；模型密钥/原始token不进入任何查询。

- [ ] T28a基本列表/详情可操作；已有identity/runtime GET不重复注册。
- [ ] T28b匹配/考次/关系查询归正确领域，主关系按canonical聚合且保留原始历史。
- [ ] T28c评分与HR历史只投影授权内容；稳定分页、归档筛选、越权拒绝测试通过。

验证：test_read_permissions.py以及相关已有领域读接口回归。新增/调整API同时导出OpenAPI并执行T38a检查。

### T29a/b/c 最小可操作界面

**Files：** Create frontend/src/app/login/page.tsx、(staff)/layout.tsx、(staff)/hr/jobs/page.tsx、hr/imports/page.tsx、hr/talents/page.tsx、hr/applications/[id]/page.tsx、hr/grading/[id]/page.tsx、exam/page.tsx；Create features/exam/ExamShell.tsx、useExamAutosave.ts、features/jobs/JobEditor.tsx、features/papers/PaperEditor.tsx、相应features/*/types.ts和frontend/tests/e2e/fixtures.ts、recruitment-smoke.spec.ts。已有文件则Modify，不机械覆盖。

**T29a前置：** T28a；登录/角色路由、岗位条件/现有卷选择与发布、最小试卷编辑发布、导入批次、邮箱/去重处理、人才事实与评估详情。管理员最小模型/邮件设置可用现有API和受控CLI初始化，流程写入手册；一期不要求完整管理仪表盘。
**T29b前置：** T28b/T23/T24/T25；HR显式邀请/重发，候选人链接核验/说明/开始/答题/交卷/回执。地址fragment token核验后移除，不进入Referer/日志。
**T29c前置：** T28c/T26/T27；HR主观复核、正式成绩、招聘阶段和面试备注。

**Interfaces：** StaffLayout({children}:StaffLayoutProps)->ReactNode；JobEditor({initial,onSaved}:JobEditorProps)->ReactNode；PaperEditor({draft,onPublished}:PaperEditorProps)->ReactNode；ExamShell({initial}:ExamShellProps)->ReactNode；useExamAutosave(attemptId:string)->ExamAutosaveController。业务DTO从generated/api-types.ts引用，不手写一套近似schema。ExamAutosaveController={save(itemId,answer,revision),flush(),pending,conflict,lastSavedAt}；submitSavedExam()->Promise[SubmissionReceipt]在提交前flush，失败明确显示；服务器截止后只认已保存数据。

- [ ] T29a HR不改数据库即可准备岗位/试卷、导入并查看/处理评估；不强制语义搜索、看板或知识入口。
- [ ] T29b 重复开始不延时，自动保存失败与409可见，断线恢复同卷；候选人网络响应无答案/量表/内部评分。
- [ ] T29c 正式成绩变更可追溯，HR手动选人，未知分不显示0。

验证：frontend lint/typecheck/build及recruitment-smoke.spec.ts；沿用原型布局基调，不实现二期菜单、不填示例成功率。

### T38a 当前契约导出与轻量检查（本轮前置）

**Files：** scripts/export_openapi.py、scripts/check_contract_coverage.py、docs/api-manifest.json、backend/tests/unit/test_contract_coverage.py；frontend/src/generated/api-types.ts由真实OpenAPI生成。
**Interfaces：** export_openapi(output_path:Path|None)->dict；check_contract_coverage(manifest,openapi,require_complete=False)->CoverageReport。manifest按API ID/方法/标准化路径记录现有实现、一期待做、二期延期；owner属于领域，不强制旧handler函数名，不以固定104数量冒充通过。

- [x] 已实现接口缺失、重复、关键响应键/typed嵌套键漂移报错；一期待做独立报告，不伪称通过。字段类型变化同时通过生成类型差异门检查；不是全DTO语义验收。
- [x] --require-complete检查能力已建立；G1才要求全部一期核心接口具备，当前覆盖尚未完成。二期条目不阻塞，额外API必须归属清楚。
- [x] 当前导出/生成/CI差异检查已建立；新API继续沿用。T38b全量语义覆盖二期，不把工具建立留到二期末。

验证前先按README构建API镜像并生成本项目.env；宿主只需要Python基础工具，不要求另装后端依赖。创建artifacts目录（已存在则跳过），Windows CMD从代码根执行：

~~~bat
python scripts/compose.py run --rm -T --no-deps -v "%CD%:/work:ro" -w /work api python scripts/export_openapi.py --output - > artifacts/openapi.json
python scripts/check_contract_coverage.py --manifest docs/api-manifest.json --openapi artifacts/openapi.json
npm --prefix frontend run generate:api
~~~

Linux把%CD%改为$PWD。容器源码只读、schema经stdout由宿主保存，不给容器用户写源码权限；不在CI自动刷新manifest。G1另加--require-complete，目前应明确报告一期接口仍待做。

### T39a/T40a/T41a/T42a 一期不可后移的质量与交付门

- [ ] T39a安全/竞争：部门越权、私有摘要污染、双worker邀考、交卷/超时竞争、失效租约、SMTP unknown、重启恢复不重复动作。已有测试复用，不为同一句规则另造重复用例。
- [ ] T40a真实质量：按06既有字段P/R/F1、关键字段exact-match、岗位匹配误邀/漏邀、主观分与人工量表差异报告。保留模型/提示词/规则/样本版本与边界样本；样本少只能报局限，不能宣称99%/90%达标。G1前完成当前支持格式和核心提取/画像/匹配/评分，RAG/OCR评测留二期。
- [ ] T41a资源与负载：记录本机实际数据量、并发、错误率、保存p95与队列等待，确保不丢答卷/重复邀请；沿用既定目标，未验证2000在线/99.9%不能宣传。看板和可选Milvus性能不阻塞一期。
- [ ] T42a干净启动/恢复：核心Compose一键准备、重复启动、talent_test隔离恢复、DB与原件可查；备份恢复凭据只记录安全引用。自动真实资料清除、完整保留策略执行器与生产环境留二期T42b/T43，不能一期后台偷偷删数据。

相关Files：复用scripts/compose.py、init_env.py、bootstrap_local.py、现有CI；按需要Create scripts/bootstrap.py、backup.py、restore_check.py、run_acceptance.py、docs/runbook.md与相应tests/ops。不是要求新建四套通用框架。每一子门必须有真实执行证据，文档检查不能算已完成。

### T30 G1核心纵向验收

**Files：** Create backend/tests/e2e/test_recruitment_vertical_slice.py、scripts/seed_demo.py、scripts/run_acceptance.py；Modify runtime/worker.py与scheduler.py只补注册缺口。无需创建新的中央resume_pipeline或Callable[[int],ResultRef]注册协议。
**Interfaces：** seed_demo(settings,secret_inputs)->DemoFixtureRefs；run_acceptance(profile,scenario)->AcceptanceReport。DemoFixtureRefs={users,jobs,papers,candidates}；AcceptanceReport={passed,steps,entity_refs,errors,artifact_paths}，不得包含原始token/验证码/密码。

- [ ] 受控准备管理员/模型/SMTP与两份岗位卷；HR由最小页面建岗、导入文本PDF/DOCX、处理缺邮箱/重复、查看三态与证据匹配。
- [ ] 真实选定供应商+MySQL/Redis/MinIO+Mailpit走邀考/邮箱核验/答题/评分复核/HR面试决定，保存完整ID链；可选语义检索不阻塞主线。
- [ ] 岗位A/B发各自冻结卷；重试/合并/断线恢复不重复邀请、不丢答卷；未知和例外处理可操作。
- [ ] T38a --require-complete、T39a～T42a必要门与浏览器主线通过，缺任一核心前提明确未通过。

验证：受控CLI运行seed_demo与run_acceptance --profile test --scenario vertical-slice；Playwright核心场景。Mailpit不等于企业外收件，生产SMTP/HTTPS属于T43，未经批准不发布。

## 6. 二期延期表（保留需求，不提前实施）

|原任务|延期范围|明确实施边界|
|---|---|---|
|T13b|OCR/MinerU/扫描/旧DOC、物理Word分页|独立格式评测后再选型，不能一期宣称已支持|
|T20b|高级语义检索/推荐界面、rerank、重建运维界面|T20现有后端/数据保留可选；不再为一期增加成本|
|T31|完整管理员账号/组织/模型/流程/邮件/运行管理台|最小初始化/必要配置入口属于一期，扩展交互不阻塞|
|T32|复杂岗位/题库/试卷编辑与管理增强|一期最小试卷/岗位表单已有T29a所有权，二期只Modify|
|T33|完整人才画像/历史/批量招聘界面增强|一期基本资料/去重/评估/复核不能延后；二期不重新开发这些服务|
|T34|知识上传/切片/发布/引用问答|新建知识专用索引/scope，不放宽人才profile/shared限制；复用底层SDK而非人才授权规则|
|T35|AI辅助出题/岗位资料融合|generation_router首次Create仅一次，不同时Create/Modify；草稿必须HR审核|
|T36|漏斗/统计看板/高级待办与审计检索|核心页面展示自身失败/待核，不依赖统计平台；配置归所属领域|
|T37|知识/看板/培训框架与展示页|一期不呈现假培训业务或无效入口|
|部门负责人协作|部门负责人账号、HR沟通/联合选人|独立增量需求与部门权限，不混入当前管理员/HR|
|T38b/T39b/T40b/T41b/T42b|全量接口、知识质量、大规模性能、保留清除执行器|一期必要质量门不跟着延期|
|T43|生产HTTPS/企业SMTP/正式发布与运营交接|仍需具体资源和正式发布授权，不能从本轮修正推定许可|

二期接口保留在05的“后续接口”映射和manifest中，不要求一期凑够104个操作；既有数据库预建表不删除、不据其存在宣称业务完成。原完整需求与签名只供历史追溯，实施二期前按当前代码再次对齐。

## 7. 续接与文档唯一职责

1. 读AGENTS→当前handoff→本计划当前任务→对应实施契约与实际代码；检查Git未提交修改。仅被采用的原型业务进入一期。
2. 01管业务与期次，03管模块/事务/事件，04管数据语义，05管wire契约与manifest，06管准入准出；10管真实目录。DATABASE由ORM生成，OpenAPI由实际应用导出，不手工复制三份字段字典。
3. 计划源在用户指定Obsidian开发计划目录，仓库09为同步副本（仅相对链接不同）；不再独立追加另一套进度。外层续接和阅读入口只链接当前仓库文档。旧计划和旧检查点归档，不删历史证据。
4. 当前实施阶段尚未完成T22及以后，不能把“文档已经修正”算招聘闭环通过。每次交付更新实际证据/状态与已授权GitHub提交，避免重新询问已确认密钥/地域。
