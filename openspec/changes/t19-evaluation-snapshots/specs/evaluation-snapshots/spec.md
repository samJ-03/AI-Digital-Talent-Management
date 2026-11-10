## ADDED Requirements

### Requirement: 应聘关系 SHALL 按canonical根复用
系统 MUST 锁根后查全部别名，复用同岗位主关系，重复选择不得新建评估。

#### Scenario: 历史别名再次加入
- **WHEN** 同一人才根已存在该岗位主关系
- **THEN** 返回原关系与原归属，不创建第二条

### Requirement: 评估 SHALL 冻结可重放上下文
系统 MUST 固定岗位/简历/画像、日期及规则修订，并阻止不满足技术门槛的评估。

#### Scenario: 缺邮箱
- **WHEN** 人才待邮箱或重复审核
- **THEN** 不正式创建/执行自动评估，不通过人工覆盖绕过

### Requirement: 人工覆盖 SHALL 保留原始输出
系统 MUST 追加有理由的人工决定并使用manual_only，迟到任务不覆盖当前结果。

#### Scenario: 重评后旧任务到达
- **WHEN** 新评估已成为当前
- **THEN** 旧任务只保留历史，不改当前指针或自动发卷
