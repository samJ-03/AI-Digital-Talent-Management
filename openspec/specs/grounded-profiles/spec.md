# grounded-profiles Specification

## Purpose
落实已确认T17：共享画像逐条绑定简历事实，部门私有信息动态授权隔离，保留人工/AI历史并通过受控任务与恢复事件处理。

## Requirements

### Requirement: 共享画像 SHALL 仅包含有来源简历事实
系统 MUST 逐条绑定本人才简历版本及字段事实，不生成性格或忠诚度预测。

#### Scenario: 模型加入私有评价或截断否定
- **WHEN** 内容不等于允许的完整字段事实
- **THEN** 拒绝模型结果，不持久化成功画像

### Requirement: 私有视图 SHALL 动态按当前权限返回
系统 MUST 将部门考试和面试与共享画像隔离。

#### Scenario: 无正式测评
- **WHEN** 没有有效正式成绩或维度依据
- **THEN** 不返回虚构成绩或雷达

### Requirement: 版本和恢复 SHALL 保持原子与幂等
系统 MUST 保留AI与人工历史，失效来源/租约不更新当前画像，恢复事件不得重复生成。

#### Scenario: 生成途中HR新增修订
- **WHEN** 当前简历或画像指针发生变化
- **THEN** 拒绝旧结果，保留新修订
