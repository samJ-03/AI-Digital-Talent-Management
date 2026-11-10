# Why
落实既有T19/FR04/05/API037、040、041、042，用户已授权继续。

# What Changes
canonical人才岗位关系复用，冻结评估版本与规则上下文，三态结果持久化，人工有理由覆盖与旧任务保护。

# Capabilities
## New Capabilities
- evaluation-snapshots: 应聘关系和可重放评估。

# Impact
新增0008迁移及evaluation_runs.screening_context JSON；40表479字段。不调用匹配模型、不发邀请，不自动启用真实模型/业务开关。