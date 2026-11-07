# Spec Delta

## Purpose

承接已确认T12与FR-02，使授权HR能建立部门岗位、发布不可变招聘条件版本，并在具备试卷、邮件和AI基础条件时显式开启自动邀考，为后续邀考消费者提供可追踪事件，避免越权、重复扫描或历史快照被覆盖。

## ADDED Requirements

### Requirement: Department scoped job administration
系统 SHALL 只允许具备岗位读写权限及对应部门范围的HR创建和修改岗位，初始状态为draft且自动邀请关闭；后台管理员不能借系统身份管理招聘数据。

#### Scenario: Create does not trigger invitations
- **WHEN** 授权HR创建合法岗位
- **THEN** 返回draft岗位、自动邀请false，且不写入邀请扫描或发送事件

#### Scenario: Cross department mutation denied
- **WHEN** 部门HR请求另一部门岗位，或管理员请求招聘写接口
- **THEN** 拒绝操作且没有业务写入

### Requirement: Immutable published job versions
系统 MUST 为条件变更创建新版本，只允许编辑draft；当前版本指针必须指向本岗位的published版本，试卷引用必须可访问且属于同一部门。

#### Scenario: Published content cannot be overwritten
- **WHEN** HR编辑published版本或通过元数据接口提交current_version_id
- **THEN** 拒绝修改并保留历史版本

#### Scenario: Invalid owner pointer cannot open a job
- **WHEN** 当前版本指向其他岗位版本
- **THEN** 开放岗位或启用自动邀请被拒绝

### Requirement: Validated conditions and weights
系统 SHALL 校验条件字段/运算符/值类型及唯一键；skills、experience、responsibilities权重必须非负且精确合计100。未选择的规则不得通过任意字符串执行。

#### Scenario: Invalid weight total rejected
- **WHEN** 权重合计不是100，或条件键重复、值类型不匹配
- **THEN** 返回422且不创建或编辑版本

### Requirement: Controlled lifecycle and explicit automation
系统 SHALL 在开放前要求本岗位发布版本，暂停或关闭时关闭自动邀请；重新开放不自动恢复开关，新版本发布也要求重新确认开关。状态变化不得改写历史版本、考试或已发送记录。

#### Scenario: Pause and reopen keep automation off
- **WHEN** 已开启自动邀请的岗位暂停后重新开放
- **THEN** 自动邀请仍为false，历史快照保持原样

### Requirement: Automation readiness gate
系统 MUST 在启用时验证岗位open、有效当前发布版本、同部门published试卷、唯一active且合规邮件配置，以及extract/profile/match/embedding流程与验证模型；含主观题时还需要grade流程。失败返回409和安全的blocking_reasons，不开启或写事件。

#### Scenario: Missing dependencies are reviewable
- **WHEN** HR启用但卷、邮件或模型流程未就绪
- **THEN** 返回明确原因代码，开关不变且无扫描事件

### Requirement: Atomic and recoverable scan event production
系统 SHALL 仅在false到true时，随开关/审计同事务追加唯一invite.scan事件，冻结岗位与当前版本引用。关键POST幂等，修改CAS；重复开启或幂等重放不得重复写事件。

#### Scenario: Enabling twice creates one event
- **WHEN** 同一开启动作重试或对已开启岗位重复设置true
- **THEN** 仅初次状态变化产生事件

#### Scenario: Downstream consumer boundary
- **WHEN** T22/T23后续消费扫描事件
- **THEN** 仅考虑当前合格且无考次的首次auto_allowed评估，不复活manual_only、revoked或历史已邀考记录；本T12事件生产接口不直接发信
