# Proposal

## Why
继续已确认T14：已有文件存储、岗位与任务框架，尚无批量导入API。

## What Changes
实现API023～026及ImportService；逐文件校验/存储、同事务建批次/条目/任务/outbox，查询和失败重试。补充0007迁移：import_items.file_id仅failed条目可空，使无有效存储文件的前置失败也可记录。

## Capabilities
### New Capabilities
- import-batches：HR批量导入受理、轮询和重试。
### Modified Capabilities
无。

## Impact
新增ingestion服务/契约/路由/测试，main注册；已有ImportItem空值约束调整，无新增表/字段/依赖。T15处理器和人才建档留后续；不宣称解析闭环已完成。
