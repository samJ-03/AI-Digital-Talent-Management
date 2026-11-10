# Why
落实既有计划T16（FR-04、API033/034），使HR人工确认重复并保留历史。用户已授权继续开发；不新增业务需求。

# What Changes
增加去重读取、CAS裁决、主招聘关系选择、原子合并和pipeline.resume事件。

# Capabilities
## New Capabilities
- duplicate-resolution: 人工去重与历史关系合并。

# Impact
沿用40表与T15接口；不迁移历史candidate_id、不接入模型或外发邮件。