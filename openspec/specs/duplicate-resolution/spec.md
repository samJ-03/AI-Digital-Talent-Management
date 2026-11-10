# duplicate-resolution Specification

## Purpose
落实已确认T16人工去重与历史关系合并：保留原始归属，显式选择主应聘，遇冲突整体拒绝，并按邮箱及未决线索门槛产生恢复事件。

## Requirements

### Requirement: 人工去重 SHALL 保留历史
系统 MUST 通过身份别名合并，不改写简历、画像、应聘或考次的原始candidate/application归属。

#### Scenario: 同岗历史合并
- **WHEN** HR指定同岗位主应聘且无活动考试冲突
- **THEN** 次关系标记merged，原考试保留，目标当前简历画像保持

### Requirement: 冲突 SHALL 原子拒绝
系统 MUST 在越权、过期版本或活动考试冲突时拒绝全部变更。

#### Scenario: 无权限部门
- **WHEN** 重叠岗位属于无权限部门
- **THEN** 返回通用拒绝，不返回私有评价、考次或冲突ID

### Requirement: 裁决 SHALL 受状态门槛约束
系统 MUST 在无未决重复且邮箱有效时变ready，并追加一次pipeline.resume。

#### Scenario: 不同身份
- **WHEN** HR确认不是同一人且无其他待审重复
- **THEN** 保留两人并按邮箱门槛恢复，重复请求不得重复事件
