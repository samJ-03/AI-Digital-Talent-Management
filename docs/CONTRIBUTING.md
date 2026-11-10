# 代码与注释约定

Python模块说明职责；公开类和函数使用PEP257文档字符串；重要参数说明权限、事务、单位和版本语义。TypeScript公开客户端、组件和异常使用JSDoc。注释解释业务限制、失败条件与副作用，不逐行复述语法。

所有ORM模型须有类说明、表级comment和每个mapped_column的comment。新增或调整数据库说明须追加Alembic迁移，不修改已应用的历史迁移。字段类型、默认值、可空性、自增及外键不能因补注释而丢失；MySQL列修改需保留完整原定义，见[Alembic官方说明](https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.alter_column)。数据库字典由当前ORM导出，不能手填不存在的字段。

领域服务负责权限复验和持久化对象归属。多表变更、审计和幂等结果在同一UoW提交；模型/SMTP等外部调用不在长事务内等待。模型输入引用必须先由业务服务授权，模型没有发邮件或决定录用的工具。

新功能先写真实失败场景，再实现和验证；纯注释改动使用AST对比确认可执行语句不变。数据库验证仅允许独立talent_test。中断测试后先排除旧测试进程和残留数据，不能放宽业务约束来消除失败。

不得提交.env、真实密钥、账号文件、简历、答卷、数据库导出、对象存储数据、日志和本地执行证据。Git提交应说明实际变更及验证；当前开发分支feat/recruitment-v1，首轮上传提供main快照。

## 一期精简实施边界（2026-11-10）

不要为目录外观创建机械Repository/QuerySpec/BaseService；router/schema→service→ORM/薄适配器足够。复杂读投影归领域queries，纯规则/scorer独立。跨领域只使用已公开方法，不能继续串私有_method。后台处理器必须沿用有效租约prepare/finalize协议，不新增中央业务流水线。

当前范围以09为准，知识/出题/看板/培训/OCR/高级语义界面二期；已完成可选后端保留。API修改必须导出OpenAPI、检查reviewed manifest并生成前端类型；不能在CI自动刷新manifest掩盖漂移。文档维护分清最新状态与历史归档，保存旧计划但不再追加多份“当前进度”。
