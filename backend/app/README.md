# 后端目录阅读入口

本目录按业务领域组织，每个领域内部再分HTTP入口、契约、服务和持久化。

先看[完整架构与目录导航](../../docs/specs/10-当前代码架构与目录导航.md)。

- main.py：装配入口。
- core/：公共事务、权限、幂等、错误与配置。
- identity/jobs/ingestion/assessment等：业务模块。
- runtime/：后台任务、Outbox与调度。
- models.py：ORM注册入口，不是单一业务Model。

以jobs为例：router.py → service.py → models.py；schemas.py定义输入输出，readiness.py检查规则，views.py构造DTO。未统一提取Repository目录，SQLAlchemy查询目前仍在服务/queries中。
