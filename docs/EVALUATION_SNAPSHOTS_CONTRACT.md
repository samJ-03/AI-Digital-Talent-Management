# T19 应聘评估快照契约

范围：API037人才库加入岗位、API040人工重评、API041评估明细、API042人工继续；不包含T21模型匹配、T22/T23邀请或T28页面。

## 业务与分层

HTTP入口在recruitment/router.py及evaluation/router.py；ApplicationService协调规范应聘关系，EvaluationService拥有评估事务，T18 ScreeningEngine仅作纯规则计算。ORM不执行业务提交，worker在持久任务租约事务内筛选，scheduler恢复等待条件的首次关系。

每岗位按人才根及全部合并别名查找有效主关系。重复选择只返回原关系；不移动历史简历、画像、考试或招聘事件。新关系先保留为evaluating；邮箱、去重、来源画像或岗位未就绪时不生成评估。

新关系首次评估为auto_allowed（只是后续自动邀请资格，不能据此立即发信）；显式重评始终manual_only，不重置阶段、考试或轮次。初次等待恢复使用岗位负责人当前权限委托，系统审计不冒充HR操作。

## 冻结与当前性

EvaluationRun冻结resume_version_id、profile_id、job_version_id及screening_context。上下文包含上海业务日期、规则修订screening-core-v1、专业词典core-major-v1、来源内容摘要、发起人及发起方式。只有服务端产生这些字段。旧记录上下文为空时仍可查看，不能用今天口径重新解释。

相关工作经历尚无已确认岗位相关性输入，relevant_employment_indices为空，相关年限保持unknown，不擅自把所有经历当作相关经历。逐条件reason_code保存到冻结上下文condition_reasons。

迟到旧运行可以保存旧版本筛选历史，但is_current必须同时满足当前关系指针、当前简历/画像/岗位版本和摘要一致。旧结果不改变当前指针，也不产生evaluation.match.requested事件。内容被原地篡改、规则不可核实或发起人权限失效时失败关闭。

粗筛pass进入matching并生成引用型Outbox，fail为screened_out，unknown为needs_review。matching表示等待T21，不代表模型匹配已完成。

## 人工继续

仅当前且来源仍有效的fail/unknown可人工继续；reason必填，decision只能continue。保留screening_result与ScreeningDetail，追加evaluation.override事件及审计，设为manual_only。不能绕过邮箱、未决重复、画像、岗位开放等前提，也不会生成考试或邮件。

## API、安全与兼容

所有写接口需要CSRF及Idempotency-Key；读取与重放均复验HR权限/部门范围。请求拒绝额外字段。详情只包含该运行的条件、匹配白名单和覆盖事件，不含部门面试或考试答卷。

API037返回ApplicationView数组及当前评估任务ID；API040返回EvaluationAccepted（继承TaskAccepted，增加evaluation_id）；GET明细包含is_current、冻结上下文及override_events。历史简历指定重评暂不支持：resume_version_id如提供，必须等于当前简历且画像同源，避免混用版本。

## 数据迁移

0008_evaluation_context增加一个非空JSON字段，旧行默认空对象，不回写历史。总表数40，字段479。降级遇到非空上下文先拒绝，避免历史丢失。迁移破坏性检查只允许talent_test，开发库只做加法升级。
