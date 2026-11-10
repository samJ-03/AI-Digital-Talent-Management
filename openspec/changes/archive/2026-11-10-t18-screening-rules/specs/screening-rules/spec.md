## ADDED Requirements

### Requirement: 硬筛 SHALL 使用三态
系统 MUST 在任一必需条件unmet时fail，否则有unknown时unknown，其余pass；preferred不硬拒。

#### Scenario: 条件缺失
- **WHEN** 必需信息不足或冲突
- **THEN** 输出unknown及证据原因，不伪造0或自动通过

### Requirement: 规则 SHALL 可追溯且确定
系统 MUST 固定评估日期和规范化修订，保留原文证据，经历按并集不重复计算。

#### Scenario: 月份精度不足
- **WHEN** 工龄范围跨过岗位门槛
- **THEN** 标记待核实而非用四舍五入通过

### Requirement: 自动硬筛 SHALL 不推断敏感属性
系统 MUST 仅处理学历、专业、年限、技能、证书白名单，年龄人工复核。

#### Scenario: 提交年龄规则
- **WHEN** 条件使用age或未知字段
- **THEN** 输入校验拒绝，不默认自动计算
