# 数据库模型字典

由 scripts/export_schema_docs.py 从当前SQLAlchemy元数据生成。共40张表、478个字段；包含已实现与后续业务预建模型，存在表不代表相应业务接口已完成。

统一约定：无符号自增ID通过API序列化为字符串；DATETIME(6)存UTC；row_version控制乐观锁；历史版本与审计不可随意覆盖；外键默认RESTRICT。

字段中文说明通过0005_schema_comments及后续注释修订写入MySQL COMMENT；原始建表迁移不回写。

## ai_runs — 模型运行证据

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| background_job_id | BIGINT UNSIGNED | 是 | — | 关联持久后台任务ID |
| task_type | VARCHAR(50) | 否 | — | 代码固定的AI流程类型 |
| model_config_id | BIGINT UNSIGNED | 否 | — | 固定模型连接修订ID |
| prompt_version_id | BIGINT UNSIGNED | 否 | — | 冻结的已发布提示词版本ID |
| input_hash | CHAR(64) COLLATE utf8mb4_bin | 否 | — | 规范化模型输入的SHA256；不保存原始输入 |
| source_refs | JSON | 否 | — | 模型生成所用的已授权来源引用 |
| validated_output | JSON | 是 | — | 仅保存通过schema和引用校验的模型结果 |
| state | VARCHAR(24) | 否 | running | 领域对象运行或审核状态；允许值：running,succeeded,invalid,failed |
| duration_ms | INTEGER UNSIGNED | 是 | — | 执行耗时（毫秒） |
| error_code | VARCHAR(64) | 是 | — | 允许记录的稳定错误码 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：background_job_id → background_jobs.id (ON DELETE RESTRICT)；model_config_id → model_configs.id (ON DELETE RESTRICT)；prompt_version_id → prompt_versions.id (ON DELETE RESTRICT)。

约束与索引：CHECK state IN ('running','succeeded','invalid','failed')；INDEX ix_ai_runs_background_job_id(background_job_id)；INDEX ix_ai_runs_model_config_id(model_config_id)；INDEX ix_ai_runs_prompt_version_id(prompt_version_id)；INDEX ix_ai_runs_task_type_created_at(task_type,created_at)。

## applications — 人×岗位招聘关系

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| candidate_id | BIGINT UNSIGNED | 否 | — | 所属人才身份ID |
| job_id | BIGINT UNSIGNED | 否 | — | 所属招聘岗位ID |
| source | VARCHAR(24) | 否 | — | 招聘关系来源；允许值：import,talent_pool |
| stage | VARCHAR(32) | 否 | — | 招聘关系当前阶段；允许值：evaluating,assessment,hr_review,interview_pending,interview_passed,offer_pending,hired,rejected,withdrawn |
| current_evaluation_id | BIGINT UNSIGNED | 是 | — | 当前生效的筛选匹配运行ID |
| current_round | INTEGER UNSIGNED | 否 | 1 | 当前招聘考试轮次 |
| ended_at | DATETIME(6) | 是 | — | 招聘关系结束时间（UTC） |
| relationship_state | VARCHAR(24) | 否 | — | 招聘关系的有效或合并状态；允许值：active,merged |
| canonical_application_id | BIGINT UNSIGNED | 是 | — | 合并后保留的规范招聘关系ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：candidate_id → candidates.id (ON DELETE RESTRICT)；canonical_application_id → applications.id (ON DELETE RESTRICT)；current_evaluation_id → evaluation_runs.id (ON DELETE RESTRICT)；job_id → jobs.id (ON DELETE RESTRICT)。

约束与索引：CHECK relationship_state IN ('active','merged')；CHECK source IN ('import','talent_pool')；CHECK stage IN ('evaluating','assessment','hr_review','interview_pending','interview_passed','offer_pending','hired','rejected','withdrawn')；INDEX ix_applications_candidate_id(candidate_id)；INDEX ix_applications_candidate_id_created_at(candidate_id,created_at)；INDEX ix_applications_canonical_application_id(canonical_application_id)；INDEX ix_applications_current_evaluation_id(current_evaluation_id)；INDEX ix_applications_job_id(job_id)；INDEX ix_applications_job_id_stage(job_id,stage)；UNIQUE(candidate_id,job_id)。

## audit_logs — 操作与权限审计

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| actor_type | VARCHAR(24) | 否 | — | 操作者类型；允许值：admin,hr,candidate,system |
| actor_user_id | BIGINT UNSIGNED | 是 | — | 后台操作者ID |
| actor_candidate_id | BIGINT UNSIGNED | 是 | — | 候选人操作者ID |
| action | VARCHAR(100) | 否 | — | 操作动作 |
| entity_type | VARCHAR(50) | 否 | — | 关联业务实体类型 |
| entity_id | BIGINT UNSIGNED | 是 | — | 关联业务实体ID；结合entity_type解释 |
| request_id | CHAR(36) | 否 | — | 请求链路标识 |
| change_summary | JSON | 否 | — | 审计变更摘要；仅允许脱敏字段 |
| result | VARCHAR(24) | 否 | — | 筛选或操作结果；允许值：success,denied,failed |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：actor_candidate_id → candidates.id (ON DELETE RESTRICT)；actor_user_id → users.id (ON DELETE RESTRICT)。

约束与索引：CHECK actor_type IN ('admin','hr','candidate','system')；CHECK result IN ('success','denied','failed')；INDEX ix_audit_logs_actor_candidate_id(actor_candidate_id)；INDEX ix_audit_logs_actor_user_id(actor_user_id)；INDEX ix_audit_logs_actor_user_id_created_at(actor_user_id,created_at)；INDEX ix_audit_logs_entity_type_entity_id_created_at(entity_type,entity_id,created_at)。

## background_jobs — 持久任务与租约

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| job_type | VARCHAR(50) | 否 | — | 代码白名单中的后台任务类型 |
| entity_type | VARCHAR(50) | 否 | — | 关联业务实体类型 |
| entity_id | BIGINT UNSIGNED | 否 | — | 关联业务实体ID；结合entity_type解释 |
| idempotency_key | VARCHAR(190) COLLATE utf8mb4_bin | 否 | — | 客户端或系统请求幂等键 |
| input_refs | JSON | 否 | — | 任务允许访问的业务输入引用 |
| state | VARCHAR(24) | 否 | queued | 领域对象运行或审核状态；允许值：queued,running,succeeded,retry,failed,cancelled |
| attempt_count | INTEGER UNSIGNED | 否 | 0 | 已尝试执行或发送次数 |
| lease_owner | VARCHAR(100) | 是 | — | 任务租约持有者随机标识 |
| lease_until | DATETIME(6) | 是 | — | 租约到期时间（UTC） |
| next_run_at | DATETIME(6) | 是 | — | 任务下次允许执行时间（UTC） |
| error_code | VARCHAR(64) | 是 | — | 允许记录的稳定错误码 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

约束与索引：CHECK state IN ('queued','running','succeeded','retry','failed','cancelled')；INDEX ix_background_jobs_state_next_run_at(state,next_run_at)；UNIQUE(idempotency_key)。

## candidate_profiles — 通用人才画像版本

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| candidate_id | BIGINT UNSIGNED | 否 | — | 所属人才身份ID |
| resume_version_id | BIGINT UNSIGNED | 否 | — | 冻结的简历修订ID |
| version_no | INTEGER UNSIGNED | 否 | — | 同一主对象下的业务版本序号 |
| summary | TEXT | 否 | — | 通用画像摘要或审计摘要；按所属表授权 |
| skills | JSON | 否 | — | 来自简历的技能事实 |
| experiences | JSON | 否 | — | 来自简历的经历事实 |
| evidence | JSON | 否 | — | 可追溯的事实证据与来源定位 |
| source_record_refs | JSON | 否 | — | 共享画像只允许简历来源引用；禁止部门私有考试和面试评价 |
| ai_run_id | BIGINT UNSIGNED | 是 | — | 关联的模型生成运行记录ID |
| confirmed_by | BIGINT UNSIGNED | 是 | — | 人工确认者账号ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：ai_run_id → ai_runs.id (ON DELETE RESTRICT)；candidate_id → candidates.id (ON DELETE RESTRICT)；confirmed_by → users.id (ON DELETE RESTRICT)；resume_version_id → resume_versions.id (ON DELETE RESTRICT)。

约束与索引：INDEX ix_candidate_profiles_ai_run_id(ai_run_id)；INDEX ix_candidate_profiles_candidate_id(candidate_id)；INDEX ix_candidate_profiles_confirmed_by(confirmed_by)；INDEX ix_candidate_profiles_resume_version_id(resume_version_id)；UNIQUE(candidate_id,version_no)。

## candidates — 人才身份

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| display_name | VARCHAR(120) | 否 | — | 人才显示姓名 |
| email | VARCHAR(254) | 是 | — | 人才原始邮箱；未补齐时可空 |
| email_normalized | VARCHAR(254) COLLATE utf8mb4_bin | 是 | — | 规范化邮箱；不擅自删除本地部分点号或加号 |
| email_valid | BOOL | 否 | 0 | 邮箱格式已校验标记；不等于验证收件人身份 |
| phone | VARCHAR(64) | 是 | — | 原始联系电话 |
| phone_normalized | VARCHAR(64) COLLATE utf8mb4_bin | 是 | — | 规范化联系电话；不作为唯一身份约束 |
| status | VARCHAR(32) | 否 | pending_email | 业务生命周期状态；允许值：pending_email,duplicate_review,ready,archived,merged |
| current_resume_version_id | BIGINT UNSIGNED | 是 | — | 当前简历修订ID |
| current_profile_id | BIGINT UNSIGNED | 是 | — | 当前通用人才画像版本ID |
| merged_into_id | BIGINT UNSIGNED | 是 | — | 合并后保留的人才ID；不得形成环 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：current_profile_id → candidate_profiles.id (ON DELETE RESTRICT)；current_resume_version_id → resume_versions.id (ON DELETE RESTRICT)；merged_into_id → candidates.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('pending_email','duplicate_review','ready','archived','merged')；INDEX ix_candidates_current_profile_id(current_profile_id)；INDEX ix_candidates_current_resume_version_id(current_resume_version_id)；INDEX ix_candidates_merged_into_id(merged_into_id)。

## departments — 部门

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| name | VARCHAR(100) | 否 | — | 业务对象名称 |
| parent_id | BIGINT UNSIGNED | 是 | — | 上级部门ID |
| status | VARCHAR(24) | 否 | active | 业务生命周期状态；允许值：active,disabled |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：parent_id → departments.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('active','disabled')；INDEX ix_departments_parent_id(parent_id)。

## duplicate_cases — 疑似重复与合并审计

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| candidate_a_id | BIGINT UNSIGNED | 否 | — | 疑似重复人才A的ID；小于B |
| candidate_b_id | BIGINT UNSIGNED | 否 | — | 疑似重复人才B的ID；大于A |
| evidence | JSON | 否 | — | 可追溯的事实证据与来源定位 |
| status | VARCHAR(24) | 否 | pending | 业务生命周期状态；允许值：pending,same_person,different_person |
| resolved_by | BIGINT UNSIGNED | 是 | — | 重复身份判定者账号ID |
| resolution_reason | TEXT | 是 | — | 疑似重复身份的人工判定理由 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：candidate_a_id → candidates.id (ON DELETE RESTRICT)；candidate_b_id → candidates.id (ON DELETE RESTRICT)；resolved_by → users.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('pending','same_person','different_person')；INDEX ix_duplicate_cases_candidate_a_id(candidate_a_id)；INDEX ix_duplicate_cases_candidate_b_id(candidate_b_id)；INDEX ix_duplicate_cases_resolved_by(resolved_by)；UNIQUE(candidate_a_id,candidate_b_id)。

## evaluation_runs — 一次粗筛匹配快照

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| application_id | BIGINT UNSIGNED | 否 | — | 人才与岗位招聘关系ID |
| resume_version_id | BIGINT UNSIGNED | 否 | — | 冻结的简历修订ID |
| profile_id | BIGINT UNSIGNED | 否 | — | 评估时冻结的通用人才画像ID |
| job_version_id | BIGINT UNSIGNED | 否 | — | 评估时冻结的岗位发布版本ID |
| state | VARCHAR(32) | 否 | pending | 领域对象运行或审核状态；允许值：pending,screening,needs_review,screened_out,matching,matched,evaluation_failed |
| screening_result | VARCHAR(16) | 是 | — | 硬条件筛选结论：通过、不通过或未知；允许值：pass,fail,unknown |
| override_by | BIGINT UNSIGNED | 是 | — | 人工覆盖筛选结果的HR账号ID |
| override_reason | TEXT | 是 | — | 人工覆盖原因；必留审计 |
| invitation_mode | VARCHAR(24) | 否 | — | 首次允许自动邀考或仅人工邀请；允许值：auto_allowed,manual_only |
| error_code | VARCHAR(64) | 是 | — | 允许记录的稳定错误码 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：application_id → applications.id (ON DELETE RESTRICT)；job_version_id → job_versions.id (ON DELETE RESTRICT)；override_by → users.id (ON DELETE RESTRICT)；profile_id → candidate_profiles.id (ON DELETE RESTRICT)；resume_version_id → resume_versions.id (ON DELETE RESTRICT)。

约束与索引：CHECK invitation_mode IN ('auto_allowed','manual_only')；CHECK screening_result IN ('pass','fail','unknown')；CHECK state IN ('pending','screening','needs_review','screened_out','matching','matched','evaluation_failed')；INDEX ix_evaluation_runs_application_id(application_id)；INDEX ix_evaluation_runs_application_id_created_at(application_id,created_at)；INDEX ix_evaluation_runs_job_version_id(job_version_id)；INDEX ix_evaluation_runs_override_by(override_by)；INDEX ix_evaluation_runs_profile_id(profile_id)；INDEX ix_evaluation_runs_resume_version_id(resume_version_id)。

## exam_answers — 个人答案与评分

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| attempt_id | BIGINT UNSIGNED | 否 | — | 关联考试轮次ID |
| paper_item_id | BIGINT UNSIGNED | 否 | — | 冻结试卷题目ID |
| answer | JSON | 是 | — | 候选人作答内容 |
| answer_revision | INTEGER UNSIGNED | 否 | 0 | 答案保存修订号；初始为0，拒绝旧版本覆盖 |
| saved_at | DATETIME(6) | 否 | — | 最近一次答卷保存时间（UTC） |
| objective_score | NUMERIC(6, 2) | 是 | — | 客观题得分小计 |
| ai_suggested_score | NUMERIC(6, 2) | 是 | — | AI建议分；不作为人工确认成绩 |
| ai_reason | JSON | 是 | — | AI评分建议理由；仅内部可见 |
| review_state | VARCHAR(24) | 否 | not_required | 答案复核状态；允许值：not_required,pending,reviewed |
| final_score | NUMERIC(6, 2) | 是 | — | 本题最终有效得分；由评分与复核流程确认 |
| ai_run_id | BIGINT UNSIGNED | 是 | — | 关联的模型生成运行记录ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：ai_run_id → ai_runs.id (ON DELETE RESTRICT)；attempt_id → exam_attempts.id (ON DELETE RESTRICT)；paper_item_id → paper_items.id (ON DELETE RESTRICT)。

约束与索引：CHECK review_state IN ('not_required','pending','reviewed')；INDEX ix_exam_answers_ai_run_id(ai_run_id)；INDEX ix_exam_answers_attempt_id(attempt_id)；INDEX ix_exam_answers_paper_item_id(paper_item_id)；UNIQUE(attempt_id,paper_item_id)。

## exam_attempts — 邀请与个人考次

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| application_id | BIGINT UNSIGNED | 否 | — | 人才与岗位招聘关系ID |
| evaluation_run_id | BIGINT UNSIGNED | 否 | — | 所属粗筛匹配运行ID |
| paper_version_id | BIGINT UNSIGNED | 否 | — | 固定发布试卷版本ID |
| round_no | INTEGER UNSIGNED | 否 | — | 同一招聘关系下的考试轮次 |
| email_snapshot | VARCHAR(254) | 否 | — | 本考次冻结的邮箱快照 |
| invitation_token_hash | CHAR(64) COLLATE utf8mb4_bin | 是 | — | 邀请令牌哈希；不存明文令牌 |
| invite_status | VARCHAR(24) | 否 | pending | 邀考状态；允许值：pending,sent,delivery_failed,delivery_unknown,revoked,expired |
| valid_until | DATETIME(6) | 否 | — | 邀请或验证码有效截止时间（UTC） |
| state | VARCHAR(24) | 否 | not_started | 领域对象运行或审核状态；允许值：not_started,in_progress,submitted,grading,pending_review,finalized,no_show |
| started_at | DATETIME(6) | 是 | — | 服务端实际开始时间（UTC） |
| deadline_at | DATETIME(6) | 是 | — | 服务端考试截止时间（UTC） |
| submitted_at | DATETIME(6) | 是 | — | 服务端收卷时间（UTC） |
| submission_reason | VARCHAR(24) | 是 | — | 正常提交或服务端超时收卷原因；允许值：manual,timeout |
| objective_score | NUMERIC(6, 2) | 是 | — | 客观题得分小计 |
| final_score | NUMERIC(6, 2) | 是 | — | 本考次最终有效总分；正式结果以冻结成绩报告为准 |
| finalized_at | DATETIME(6) | 是 | — | 正式成绩确认时间（UTC） |
| finalized_by | BIGINT UNSIGNED | 是 | — | 正式成绩确认者账号ID |
| current_score_report_id | BIGINT UNSIGNED | 是 | — | 当前正式成绩报告ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：application_id → applications.id (ON DELETE RESTRICT)；current_score_report_id → score_reports.id (ON DELETE RESTRICT)；evaluation_run_id → evaluation_runs.id (ON DELETE RESTRICT)；finalized_by → users.id (ON DELETE RESTRICT)；paper_version_id → paper_versions.id (ON DELETE RESTRICT)。

约束与索引：CHECK invite_status IN ('pending','sent','delivery_failed','delivery_unknown','revoked','expired')；CHECK state IN ('not_started','in_progress','submitted','grading','pending_review','finalized','no_show')；CHECK submission_reason IN ('manual','timeout')；INDEX ix_exam_attempts_application_id(application_id)；INDEX ix_exam_attempts_current_score_report_id(current_score_report_id)；INDEX ix_exam_attempts_evaluation_run_id(evaluation_run_id)；INDEX ix_exam_attempts_finalized_by(finalized_by)；INDEX ix_exam_attempts_invite_status_valid_until(invite_status,valid_until)；INDEX ix_exam_attempts_paper_version_id(paper_version_id)；INDEX ix_exam_attempts_state_deadline_at(state,deadline_at)；UNIQUE(application_id,round_no)；UNIQUE(invitation_token_hash)。

## idempotency_records — 关键命令幂等记录

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| actor_scope | VARCHAR(100) COLLATE utf8mb4_bin | 否 | — | 幂等主体范围（角色与账号或候选人标识） |
| operation | VARCHAR(100) COLLATE utf8mb4_bin | 否 | — | 幂等业务操作标识 |
| request_key | VARCHAR(100) COLLATE utf8mb4_bin | 否 | — | 请求幂等键；结合操作者范围与操作标识唯一 |
| request_hash | CHAR(64) COLLATE utf8mb4_bin | 否 | — | 规范化幂等请求内容SHA256 |
| state | VARCHAR(24) | 否 | processing | 领域对象运行或审核状态；允许值：processing,completed,failed |
| result_refs | JSON | 是 | — | 已完成任务或幂等操作的结果引用 |
| expires_at | DATETIME(6) | 否 | — | 记录或私有载荷过期时间（UTC） |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

约束与索引：CHECK state IN ('processing','completed','failed')；UNIQUE(actor_scope,operation,request_key)。

## import_batches — 导入批次

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| job_id | BIGINT UNSIGNED | 是 | — | 所属招聘岗位ID |
| created_by | BIGINT UNSIGNED | 否 | — | 创建者后台账号ID |
| status | VARCHAR(24) | 否 | queued | 业务生命周期状态；允许值：queued,processing,completed,partial_failed |
| request_key | VARCHAR(100) COLLATE utf8mb4_bin | 否 | — | 批量导入请求幂等键 |
| file_count | INTEGER UNSIGNED | 否 | — | 本批导入文件数量 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：created_by → users.id (ON DELETE RESTRICT)；job_id → jobs.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('queued','processing','completed','partial_failed')；INDEX ix_import_batches_created_by(created_by)；INDEX ix_import_batches_job_id(job_id)；UNIQUE(created_by,request_key)。

## import_items — 每份文件的导入处理

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| batch_id | BIGINT UNSIGNED | 否 | — | 所属简历导入批次ID |
| file_id | BIGINT UNSIGNED | 是 | — | 私有原始文件ID；仅上传前置失败时可空且状态必须failed |
| resume_version_id | BIGINT UNSIGNED | 是 | — | 冻结的简历修订ID |
| status | VARCHAR(32) | 否 | uploaded | 业务生命周期状态；允许值：uploaded,queued,parsing,parsed,failed |
| error_code | VARCHAR(64) | 是 | — | 允许记录的稳定错误码 |
| error_detail_safe | TEXT | 是 | — | 可展示的脱敏错误说明；禁止原始异常或秘密 |
| source_order | INTEGER UNSIGNED | 否 | — | 导入文件在批次中的顺序 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：batch_id → import_batches.id (ON DELETE RESTRICT)；file_id → stored_files.id (ON DELETE RESTRICT)；resume_version_id → resume_versions.id (ON DELETE RESTRICT)。

约束与索引：CHECK file_id IS NOT NULL OR status = 'failed'；CHECK status IN ('uploaded','queued','parsing','parsed','failed')；INDEX ix_import_items_batch_id(batch_id)；INDEX ix_import_items_batch_id_status(batch_id,status)；INDEX ix_import_items_file_id(file_id)；INDEX ix_import_items_resume_version_id(resume_version_id)；UNIQUE(batch_id,source_order)。

## index_records — 关系数据与向量索引映射

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| entity_type | VARCHAR(32) | 否 | — | 关联业务实体类型；允许值：profile,knowledge_chunk,job_version |
| entity_id | BIGINT UNSIGNED | 否 | — | 关联业务实体ID；结合entity_type解释 |
| model_config_id | BIGINT UNSIGNED | 否 | — | 固定模型连接修订ID |
| collection_name | VARCHAR(120) | 否 | — | Milvus集合名；按模型配置与维度隔离 |
| vector_key | VARCHAR(190) COLLATE utf8mb4_bin | 否 | — | Milvus向量记录的稳定键 |
| content_hash | CHAR(64) COLLATE utf8mb4_bin | 否 | — | 内容指纹；用于变更和索引一致性检查 |
| state | VARCHAR(24) | 否 | pending | 领域对象运行或审核状态；允许值：pending,ready,failed,stale,deleted |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：model_config_id → model_configs.id (ON DELETE RESTRICT)。

约束与索引：CHECK entity_type IN ('profile','knowledge_chunk','job_version')；CHECK state IN ('pending','ready','failed','stale','deleted')；INDEX ix_index_records_model_config_id(model_config_id)；UNIQUE(collection_name,vector_key)；UNIQUE(entity_type,entity_id,model_config_id)。

## job_versions — 岗位发布版本

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| job_id | BIGINT UNSIGNED | 否 | — | 所属招聘岗位ID |
| version_no | INTEGER UNSIGNED | 否 | — | 同一主对象下的业务版本序号 |
| description | TEXT | 否 | — | 业务说明正文 |
| conditions | JSON | 否 | — | 必选或优选的结构化岗位条件 |
| match_weights | JSON | 否 | — | 匹配维度权重；总和必须为100 |
| invite_threshold | NUMERIC(5, 2) | 否 | — | 自动邀考匹配分参考阈值（0至100） |
| paper_version_id | BIGINT UNSIGNED | 是 | — | 固定发布试卷版本ID |
| invite_valid_hours | INTEGER UNSIGNED | 否 | — | 邀请有效时长（小时） |
| mail_template | JSON | 否 | — | 岗位邀考模板结构 |
| status | VARCHAR(24) | 否 | draft | 业务生命周期状态；允许值：draft,published |
| published_by | BIGINT UNSIGNED | 是 | — | 发布者后台账号ID |
| published_at | DATETIME(6) | 是 | — | 版本发布时间（UTC） |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：job_id → jobs.id (ON DELETE RESTRICT)；paper_version_id → paper_versions.id (ON DELETE RESTRICT)；published_by → users.id (ON DELETE RESTRICT)。

约束与索引：CHECK invite_threshold >= 0 AND invite_threshold <= 100；CHECK invite_valid_hours > 0；CHECK status IN ('draft','published')；INDEX ix_job_versions_job_id(job_id)；INDEX ix_job_versions_paper_version_id(paper_version_id)；INDEX ix_job_versions_published_by(published_by)；UNIQUE(job_id,version_no)。

## jobs — 岗位主对象

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| department_id | BIGINT UNSIGNED | 否 | — | 归属部门ID；用于部门数据权限 |
| owner_hr_id | BIGINT UNSIGNED | 否 | — | 岗位负责HR账号ID |
| title | VARCHAR(200) | 否 | — | 岗位或知识标题 |
| headcount | INTEGER UNSIGNED | 否 | — | 计划招聘人数；必须大于0 |
| status | VARCHAR(24) | 否 | draft | 业务生命周期状态；允许值：draft,open,paused,closed |
| current_version_id | BIGINT UNSIGNED | 是 | — | 当前发布版本ID；服务层校验属于本主对象 |
| auto_invite_enabled | BOOL | 否 | 0 | 自动邀考开关；新岗位默认关闭 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：current_version_id → job_versions.id (ON DELETE RESTRICT)；department_id → departments.id (ON DELETE RESTRICT)；owner_hr_id → users.id (ON DELETE RESTRICT)。

约束与索引：CHECK headcount > 0；CHECK status IN ('draft','open','paused','closed')；INDEX ix_jobs_current_version_id(current_version_id)；INDEX ix_jobs_department_id(department_id)；INDEX ix_jobs_department_id_status(department_id,status)；INDEX ix_jobs_owner_hr_id(owner_hr_id)。

## knowledge_chunks — 带来源切片

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| document_id | BIGINT UNSIGNED | 否 | — | 所属知识文档ID |
| chunk_no | INTEGER UNSIGNED | 否 | — | 文档片段序号 |
| content | TEXT | 否 | — | 领域结构化内容或文本；按所属表解释 |
| source_locator | JSON | 否 | — | 知识片段页码或段落定位 |
| content_hash | CHAR(64) COLLATE utf8mb4_bin | 否 | — | 内容指纹；用于变更和索引一致性检查 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：document_id → knowledge_documents.id (ON DELETE RESTRICT)。

约束与索引：INDEX ix_knowledge_chunks_document_id(document_id)；UNIQUE(document_id,chunk_no)。

## knowledge_documents — 招聘资料版本

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| logical_key | CHAR(36) COLLATE utf8mb4_bin | 否 | — | 跨修订保持稳定的逻辑标识 |
| version_no | INTEGER UNSIGNED | 否 | — | 同一主对象下的业务版本序号 |
| file_id | BIGINT UNSIGNED | 否 | — | 私有原始文件ID |
| title | VARCHAR(255) | 否 | — | 岗位或知识标题 |
| category | VARCHAR(50) | 否 | — | 知识分类；允许值：job,technical,rubric,reference |
| scope | VARCHAR(24) | 否 | — | 知识可见范围；允许值：company,department |
| department_id | BIGINT UNSIGNED | 是 | — | 归属部门ID；用于部门数据权限 |
| state | VARCHAR(24) | 否 | draft | 领域对象运行或审核状态；允许值：draft,processing,published,failed,archived |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：department_id → departments.id (ON DELETE RESTRICT)；file_id → stored_files.id (ON DELETE RESTRICT)。

约束与索引：CHECK category IN ('job','technical','rubric','reference')；CHECK scope IN ('company','department')；CHECK state IN ('draft','processing','published','failed','archived')；INDEX ix_knowledge_documents_department_id(department_id)；INDEX ix_knowledge_documents_file_id(file_id)；INDEX ix_knowledge_documents_scope_department_id_state(scope,department_id,state)；UNIQUE(logical_key,version_no)。

## mail_configs — 邮件连接修订

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| revision_no | INTEGER UNSIGNED | 否 | — | 不可变配置或题目修订序号 |
| smtp_host | VARCHAR(255) | 否 | — | 通过白名单校验的SMTP主机 |
| smtp_port | INTEGER UNSIGNED | 否 | — | SMTP服务端口 |
| tls_mode | VARCHAR(24) | 否 | — | SMTP传输加密模式；生产须TLS；允许值：starttls,tls,none |
| sender_address | VARCHAR(254) | 否 | — | 发送方邮箱地址 |
| username | VARCHAR(255) | 是 | — | SMTP认证用户名 |
| secret_ciphertext | TEXT | 是 | — | Fernet加密凭据；只写不回显 |
| public_base_url | VARCHAR(500) | 否 | — | 邮件中的候选人公共入口基础地址 |
| state | VARCHAR(24) | 否 | draft | 领域对象运行或审核状态；允许值：draft,verified,active,disabled |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

约束与索引：CHECK state IN ('draft','verified','active','disabled')；CHECK tls_mode IN ('starttls','tls','none')；UNIQUE(revision_no)。

## match_results — 岗位匹配结果

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| evaluation_run_id | BIGINT UNSIGNED | 否 | — | 所属粗筛匹配运行ID |
| ai_run_id | BIGINT UNSIGNED | 是 | — | 关联的模型生成运行记录ID |
| total_score | NUMERIC(5, 2) | 是 | — | 岗位匹配加权总分（0至100）；不等于考试成绩 |
| dimension_scores | JSON | 否 | — | 各匹配维度的分数及依据 |
| strengths | JSON | 否 | — | 岗位优势及证据 |
| gaps | JSON | 否 | — | 岗位能力差距及证据 |
| evidence | JSON | 否 | — | 可追溯的事实证据与来源定位 |
| state | VARCHAR(24) | 否 | valid | 领域对象运行或审核状态；允许值：valid,needs_review,failed |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：ai_run_id → ai_runs.id (ON DELETE RESTRICT)；evaluation_run_id → evaluation_runs.id (ON DELETE RESTRICT)。

约束与索引：CHECK state IN ('valid','needs_review','failed')；CHECK total_score >= 0 AND total_score <= 100；INDEX ix_match_results_ai_run_id(ai_run_id)；INDEX ix_match_results_evaluation_run_id(evaluation_run_id)；INDEX ix_match_results_state_total_score(state,total_score)；UNIQUE(evaluation_run_id)。

## model_configs — 模型连接及修订

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| logical_key | VARCHAR(100) COLLATE utf8mb4_bin | 否 | — | 跨修订保持稳定的逻辑标识 |
| revision_no | INTEGER UNSIGNED | 否 | — | 不可变配置或题目修订序号 |
| provider_type | VARCHAR(32) | 否 | — | 受支持的模型协议类型；允许值：ollama,compatible_http |
| base_url | VARCHAR(500) | 否 | — | 经供应商白名单校验的服务地址 |
| model_name | VARCHAR(150) | 否 | — | 供应商模型名称 |
| model_digest | VARCHAR(255) | 是 | — | 本地真实权重摘要；云端未提供时为NULL |
| capabilities | JSON | 否 | — | 已实测模型能力与verified标记 |
| embedding_dimension | INTEGER UNSIGNED | 是 | — | 实测向量维度；整批必须一致 |
| secret_ciphertext | TEXT | 是 | — | Fernet加密凭据；只写不回显 |
| enabled | BOOL | 否 | 0 | 配置启用状态 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

约束与索引：CHECK provider_type IN ('ollama','compatible_http')；UNIQUE(logical_key,revision_no)。

## notifications — 邮件发送记录

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| attempt_id | BIGINT UNSIGNED | 是 | — | 关联考试轮次ID |
| event_key | VARCHAR(190) COLLATE utf8mb4_bin | 否 | — | 业务事件唯一幂等键 |
| purpose | VARCHAR(32) | 否 | — | 邮件用途；允许值：exam_invite,verify_code |
| recipient_snapshot | VARCHAR(254) | 否 | — | 本次发送冻结的收件人邮箱 |
| status | VARCHAR(24) | 否 | pending | 业务生命周期状态；允许值：pending,sending,accepted,failed,unknown,cancelled |
| provider_message_id | VARCHAR(255) | 是 | — | 邮件供应商返回的消息标识 |
| attempt_count | INTEGER UNSIGNED | 否 | 0 | 已尝试执行或发送次数 |
| last_error_code | VARCHAR(64) | 是 | — | 最近一次执行或发送的脱敏错误码 |
| sent_at | DATETIME(6) | 是 | — | 邮件交付时间（UTC） |
| mail_config_id | BIGINT UNSIGNED | 否 | — | 发送时冻结的邮件连接修订ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：attempt_id → exam_attempts.id (ON DELETE RESTRICT)；mail_config_id → mail_configs.id (ON DELETE RESTRICT)。

约束与索引：CHECK purpose IN ('exam_invite','verify_code')；CHECK status IN ('pending','sending','accepted','failed','unknown','cancelled')；INDEX ix_notifications_attempt_id(attempt_id)；INDEX ix_notifications_mail_config_id(mail_config_id)；INDEX ix_notifications_status_created_at(status,created_at)；UNIQUE(event_key)。

## outbox_events — 事务外发事件

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| event_type | VARCHAR(50) | 否 | — | 业务事件类型 |
| aggregate_type | VARCHAR(50) | 否 | — | 业务聚合类型 |
| aggregate_id | BIGINT UNSIGNED | 否 | — | 业务聚合ID |
| event_key | VARCHAR(190) COLLATE utf8mb4_bin | 否 | — | 业务事件唯一幂等键 |
| payload_refs | JSON | 否 | — | Outbox业务引用；禁止写入原始敏感正文 |
| private_payload_ciphertext | TEXT | 是 | — | 短期私有载荷密文；不得进入队列或日志 |
| state | VARCHAR(24) | 否 | pending | 领域对象运行或审核状态；允许值：pending,processing,sent,failed,unknown,cancelled |
| lease_until | DATETIME(6) | 是 | — | 租约到期时间（UTC） |
| next_attempt_at | DATETIME(6) | 是 | — | 下一次Outbox事件投递尝试时间（UTC） |
| expires_at | DATETIME(6) | 是 | — | 记录或私有载荷过期时间（UTC） |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

约束与索引：CHECK state IN ('pending','processing','sent','failed','unknown','cancelled')；INDEX ix_outbox_events_state_next_attempt_at(state,next_attempt_at)；UNIQUE(event_key)。

## paper_items — 冻结试题与评分标准

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| paper_version_id | BIGINT UNSIGNED | 否 | — | 固定发布试卷版本ID |
| source_question_id | BIGINT UNSIGNED | 是 | — | 发布试卷所引用的已批准题目修订ID |
| position_no | INTEGER UNSIGNED | 否 | — | 试题显示顺序 |
| question_type | VARCHAR(24) | 否 | — | 题型 |
| stem | TEXT | 否 | — | 题干正文 |
| options | JSON | 是 | — | 题目选项结构 |
| max_score | NUMERIC(6, 2) | 否 | — | 本题冻结满分 |
| answer_key | JSON | 是 | — | 标准答案；仅授权HR和评分流程可见 |
| rubric | JSON | 否 | — | 冻结的评分量表；候选人不可见 |
| reference_sources | JSON | 否 | — | 题目引用的知识或资料来源 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：paper_version_id → paper_versions.id (ON DELETE RESTRICT)；source_question_id → questions.id (ON DELETE RESTRICT)。

约束与索引：CHECK max_score >= 0；INDEX ix_paper_items_paper_version_id(paper_version_id)；INDEX ix_paper_items_source_question_id(source_question_id)；UNIQUE(paper_version_id,position_no)。

## paper_versions — 试卷版本

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| paper_id | BIGINT UNSIGNED | 否 | — | 所属试卷主对象ID |
| version_no | INTEGER UNSIGNED | 否 | — | 同一主对象下的业务版本序号 |
| duration_minutes | INTEGER UNSIGNED | 否 | — | 考试时长（分钟） |
| total_score | NUMERIC(6, 2) | 否 | — | 本版试卷满分；等于冻结题目满分之和 |
| reference_pass_score | NUMERIC(6, 2) | 是 | — | 试卷参考通过线；不自动决定淘汰 |
| status | VARCHAR(24) | 否 | draft | 业务生命周期状态；允许值：draft,published |
| published_by | BIGINT UNSIGNED | 是 | — | 发布者后台账号ID |
| published_at | DATETIME(6) | 是 | — | 版本发布时间（UTC） |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：paper_id → papers.id (ON DELETE RESTRICT)；published_by → users.id (ON DELETE RESTRICT)。

约束与索引：CHECK duration_minutes > 0；CHECK status IN ('draft','published')；CHECK total_score > 0；INDEX ix_paper_versions_paper_id(paper_id)；INDEX ix_paper_versions_published_by(published_by)；UNIQUE(paper_id,version_no)。

## papers — 试卷主对象

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| department_id | BIGINT UNSIGNED | 否 | — | 归属部门ID；用于部门数据权限 |
| name | VARCHAR(200) | 否 | — | 业务对象名称 |
| created_by | BIGINT UNSIGNED | 否 | — | 创建者后台账号ID |
| status | VARCHAR(24) | 否 | active | 业务生命周期状态；允许值：active,archived |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：created_by → users.id (ON DELETE RESTRICT)；department_id → departments.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('active','archived')；INDEX ix_papers_created_by(created_by)；INDEX ix_papers_department_id(department_id)；INDEX ix_papers_department_id_status(department_id,status)。

## prompt_versions — 提示词版本

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| task_type | VARCHAR(50) | 否 | — | 代码固定的AI流程类型 |
| revision_no | INTEGER UNSIGNED | 否 | — | 不可变配置或题目修订序号 |
| content | TEXT | 否 | — | 领域结构化内容或文本；按所属表解释 |
| output_schema | JSON | 否 | — | 发布时冻结的离线JSON Schema |
| status | VARCHAR(24) | 否 | draft | 业务生命周期状态；允许值：draft,published |
| published_by | BIGINT UNSIGNED | 是 | — | 发布者后台账号ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：published_by → users.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('draft','published')；INDEX ix_prompt_versions_published_by(published_by)；UNIQUE(task_type,revision_no)。

## question_banks — 题库

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| department_id | BIGINT UNSIGNED | 否 | — | 归属部门ID；用于部门数据权限 |
| name | VARCHAR(200) | 否 | — | 业务对象名称 |
| status | VARCHAR(24) | 否 | active | 业务生命周期状态；允许值：active,archived |
| created_by | BIGINT UNSIGNED | 否 | — | 创建者后台账号ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：created_by → users.id (ON DELETE RESTRICT)；department_id → departments.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('active','archived')；INDEX ix_question_banks_created_by(created_by)；INDEX ix_question_banks_department_id(department_id)；INDEX ix_question_banks_department_id_status(department_id,status)。

## questions — 题库题目修订

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| bank_id | BIGINT UNSIGNED | 否 | — | 所属题库ID |
| logical_key | CHAR(36) COLLATE utf8mb4_bin | 否 | — | 跨修订保持稳定的逻辑标识 |
| revision_no | INTEGER UNSIGNED | 否 | — | 不可变配置或题目修订序号 |
| question_type | VARCHAR(24) | 否 | — | 题型；允许值：single_choice,multiple_choice,short_answer |
| stem | TEXT | 否 | — | 题干正文 |
| options | JSON | 是 | — | 题目选项结构 |
| answer_key | JSON | 是 | — | 标准答案；仅授权HR和评分流程可见 |
| rubric | JSON | 否 | — | 冻结的评分量表；候选人不可见 |
| reference_sources | JSON | 否 | — | 题目引用的知识或资料来源 |
| state | VARCHAR(24) | 否 | draft | 领域对象运行或审核状态；允许值：draft,approved,archived |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：bank_id → question_banks.id (ON DELETE RESTRICT)。

约束与索引：CHECK question_type IN ('single_choice','multiple_choice','short_answer')；CHECK state IN ('draft','approved','archived')；INDEX ix_questions_bank_id(bank_id)；INDEX ix_questions_bank_id_state(bank_id,state)；UNIQUE(logical_key,revision_no)。

## recruitment_events — 阶段与面试评价历史

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| application_id | BIGINT UNSIGNED | 否 | — | 人才与岗位招聘关系ID |
| event_type | VARCHAR(50) | 否 | — | 业务事件类型 |
| from_stage | VARCHAR(32) | 是 | — | 事件发生前招聘阶段 |
| to_stage | VARCHAR(32) | 是 | — | 事件发生后招聘阶段 |
| content | JSON | 否 | — | 领域结构化内容或文本；按所属表解释 |
| actor_id | BIGINT UNSIGNED | 否 | — | 执行操作的后台账号ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：actor_id → users.id (ON DELETE RESTRICT)；application_id → applications.id (ON DELETE RESTRICT)。

约束与索引：INDEX ix_recruitment_events_actor_id(actor_id)；INDEX ix_recruitment_events_application_id(application_id)；INDEX ix_recruitment_events_application_id_created_at(application_id,created_at)。

## resume_versions — 简历与校正版本

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| candidate_id | BIGINT UNSIGNED | 否 | — | 所属人才身份ID |
| file_id | BIGINT UNSIGNED | 否 | — | 私有原始文件ID |
| version_no | INTEGER UNSIGNED | 否 | — | 同一主对象下的业务版本序号 |
| parent_version_id | BIGINT UNSIGNED | 是 | — | 来源简历修订ID |
| raw_text | LONGTEXT | 是 | — | 解析得到的简历原文；按敏感数据授权访问 |
| structured_data | JSON | 否 | — | 经过类型校验的结构化简历事实 |
| field_sources | JSON | 否 | — | 结构化简历各字段的页码或段落证据 |
| parser_revision | VARCHAR(100) | 否 | — | 解析器或解析流程修订 |
| state | VARCHAR(24) | 否 | extracted | 领域对象运行或审核状态；允许值：extracted,confirmed,superseded |
| change_reason | TEXT | 是 | — | 创建修订的变更原因 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：candidate_id → candidates.id (ON DELETE RESTRICT)；file_id → stored_files.id (ON DELETE RESTRICT)；parent_version_id → resume_versions.id (ON DELETE RESTRICT)。

约束与索引：CHECK state IN ('extracted','confirmed','superseded')；INDEX ix_resume_versions_candidate_id(candidate_id)；INDEX ix_resume_versions_candidate_id_created_at(candidate_id,created_at)；INDEX ix_resume_versions_file_id(file_id)；INDEX ix_resume_versions_parent_version_id(parent_version_id)；UNIQUE(candidate_id,version_no)。

## roles — 角色

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| code | VARCHAR(50) | 否 | — | 稳定业务编码 |
| name | VARCHAR(100) | 否 | — | 业务对象名称 |
| permission_codes | JSON | 否 | — | 明确授予的权限码列表 |
| data_scope | VARCHAR(24) | 否 | — | 数据授权范围：部门或全企业；允许值：department,company |
| status | VARCHAR(24) | 否 | active | 业务生命周期状态；允许值：active,disabled |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

约束与索引：CHECK data_scope IN ('department','company')；CHECK status IN ('active','disabled')；UNIQUE(code)。

## score_reports — 正式成绩不可变版本

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| attempt_id | BIGINT UNSIGNED | 否 | — | 关联考试轮次ID |
| version_no | INTEGER UNSIGNED | 否 | — | 同一主对象下的业务版本序号 |
| objective_score | NUMERIC(6, 2) | 否 | — | 客观题得分小计 |
| subjective_score | NUMERIC(6, 2) | 否 | — | 主观题正式得分小计 |
| total_score | NUMERIC(6, 2) | 否 | — | 本次确认的考试正式总分 |
| item_score_snapshot | JSON | 否 | — | 正式成绩冻结的逐题评分快照 |
| confirmed_by | BIGINT UNSIGNED | 是 | — | 人工确认者账号ID |
| reason | TEXT | 否 | — | 人工操作或复核理由 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：attempt_id → exam_attempts.id (ON DELETE RESTRICT)；confirmed_by → users.id (ON DELETE RESTRICT)。

约束与索引：INDEX ix_score_reports_attempt_id(attempt_id)；INDEX ix_score_reports_confirmed_by(confirmed_by)；UNIQUE(attempt_id,version_no)。

## score_reviews — 人工主观评分修订

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| answer_id | BIGINT UNSIGNED | 否 | — | 关联答卷答案ID |
| reviewer_id | BIGINT UNSIGNED | 否 | — | 评分复核者账号ID |
| revision_no | INTEGER UNSIGNED | 否 | — | 不可变配置或题目修订序号 |
| score | NUMERIC(6, 2) | 否 | — | 本次评分或复核分数 |
| reason | TEXT | 否 | — | 人工操作或复核理由 |
| previous_score | NUMERIC(6, 2) | 是 | — | 本次复核前的单题分数 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：answer_id → exam_answers.id (ON DELETE RESTRICT)；reviewer_id → users.id (ON DELETE RESTRICT)。

约束与索引：CHECK score >= 0；INDEX ix_score_reviews_answer_id(answer_id)；INDEX ix_score_reviews_reviewer_id(reviewer_id)；UNIQUE(answer_id,revision_no)。

## screening_details — 粗筛逐条件证据

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| evaluation_run_id | BIGINT UNSIGNED | 否 | — | 所属粗筛匹配运行ID |
| condition_key | VARCHAR(100) | 否 | — | 岗位条件的稳定键 |
| required | BOOL | 否 | — | 是否硬性条件；未知不得冒充不满足 |
| expected | JSON | 否 | — | 岗位规则期望值 |
| actual | JSON | 是 | — | 实际观测值；未知为NULL |
| result | VARCHAR(16) | 否 | — | 筛选或操作结果；允许值：met,unmet,unknown |
| evidence | JSON | 否 | — | 可追溯的事实证据与来源定位 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：evaluation_run_id → evaluation_runs.id (ON DELETE RESTRICT)。

约束与索引：CHECK result IN ('met','unmet','unknown')；INDEX ix_screening_details_evaluation_run_id(evaluation_run_id)；UNIQUE(evaluation_run_id,condition_key)。

## stored_files — 私有文件

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| bucket | VARCHAR(100) | 否 | — | 私有对象存储桶名 |
| object_key | VARCHAR(500) COLLATE utf8mb4_bin | 否 | — | 私有对象存储内部键；不直接返回外部 |
| sha256 | CHAR(64) COLLATE utf8mb4_bin | 否 | — | 文件内容SHA256；不等于人员身份 |
| original_name | VARCHAR(255) | 否 | — | 原始文件名；不作为对象存储路径 |
| mime_type | VARCHAR(120) | 否 | — | 校验后的文件MIME类型 |
| size_bytes | BIGINT UNSIGNED | 否 | — | 文件实际大小（字节） |
| uploader_id | BIGINT UNSIGNED | 是 | — | 上传者后台账号ID |
| status | VARCHAR(24) | 否 | staged | 业务生命周期状态；允许值：staged,ready,quarantined,deleted |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：uploader_id → users.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('staged','ready','quarantined','deleted')；INDEX ix_stored_files_sha256(sha256)；INDEX ix_stored_files_uploader_id(uploader_id)；UNIQUE(bucket,object_key)。

## user_roles — 账号角色

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| user_id | BIGINT UNSIGNED | 否 | — | 关联后台账号ID |
| role_id | BIGINT UNSIGNED | 否 | — | 关联角色ID |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：role_id → roles.id (ON DELETE RESTRICT)；user_id → users.id (ON DELETE RESTRICT)。

约束与索引：INDEX ix_user_roles_role_id(role_id)；INDEX ix_user_roles_user_id(user_id)；UNIQUE(user_id,role_id)。

## users — 后台账号

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| department_id | BIGINT UNSIGNED | 是 | — | 归属部门ID；用于部门数据权限 |
| login_name | VARCHAR(100) | 否 | — | 后台登录名 |
| password_hash | VARCHAR(255) | 否 | — | Argon2密码哈希；禁止明文或可逆密码 |
| status | VARCHAR(24) | 否 | active | 业务生命周期状态；允许值：active,disabled |
| auth_version | INTEGER UNSIGNED | 否 | 1 | 认证版本；变更后旧会话失效 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：department_id → departments.id (ON DELETE RESTRICT)。

约束与索引：CHECK status IN ('active','disabled')；INDEX ix_users_department_id(department_id)；UNIQUE(login_name)。

## workflow_configs — 固定流程配置

| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |
|---|---|---|---|---|
| task_type | VARCHAR(50) | 否 | — | 代码固定的AI流程类型 |
| model_config_id | BIGINT UNSIGNED | 是 | — | 固定模型连接修订ID |
| prompt_version_id | BIGINT UNSIGNED | 是 | — | 冻结的已发布提示词版本ID |
| enabled | BOOL | 否 | 0 | 配置启用状态 |
| timeout_seconds | INTEGER UNSIGNED | 否 | — | 模型请求超时配置（秒） |
| max_retries | INTEGER UNSIGNED | 否 | — | 允许的额外重试次数 |
| config_revision | INTEGER UNSIGNED | 否 | — | 固定流程配置修订；运行前校验快照 |
| id | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | 无符号自增主键；API序列化为字符串 |
| created_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 创建时间（UTC，微秒精度） |
| updated_at | DATETIME(6) | 否 | CURRENT_TIMESTAMP(6) | 最后业务更新时间（UTC，微秒精度） |
| row_version | INTEGER UNSIGNED | 否 | 1 | 乐观锁版本；修改须匹配If-Match |

外键：model_config_id → model_configs.id (ON DELETE RESTRICT)；prompt_version_id → prompt_versions.id (ON DELETE RESTRICT)。

约束与索引：INDEX ix_workflow_configs_model_config_id(model_config_id)；INDEX ix_workflow_configs_prompt_version_id(prompt_version_id)；UNIQUE(task_type)。
