# T14批量导入验收（2026-11-09）

范围：API023～026与ImportService，私有文件暂存/关联、持久任务/Outbox、权限查询及重试。0007只放宽failed条目的file_id并增加CHECK；40表/478字段不变。

- RED：artifacts/t14-red.log，10项代表性请求因路由未实现返回404而预期202；artifacts/t14-scope-red.log，真实范围撤回后列表仍包含无权详情的批次，已统一为持久部门范围过滤。
- 定向：21 passed in25.14s，artifacts/t14-expanded-green.log；真实隔离MySQL+私有MinIO。覆盖部分失败、实际内容幂等、数量/字节限制、身份与部门、权限撤回、并发创建/重试、无反向等待任务锁、审计整体回滚、原始错误不回显、SQL CHECK3819、保护性降级及迁移往返FK/unsigned/comment保真。
- 独立只读审阅：发现并修复列表与详情权限不一致；复核无剩余代码阻塞，规格已澄清创建者也受当前岗位部门范围约束。
- 首次完整279通过/1失败：历史注释测试假定head到0004全部为注释，0007结构变更使其旧假设不成立。已把注释保真比较限定0004～0006，并在finally恢复head。原字段定义/数据断言保留，0007由新增往返/降级保护专项覆盖。两项注释测试单独通过。
- 最终完整：280 passed in194.15s，artifacts/t14-final-suite.log。破坏性验证只在talent_test；前端无变更，不重复构建。
- 本地开发环境：0007已应用talent_dev，API已重载，真实OpenAPI包含4项导入操作。本地合成batch_id=1，7项检查通过，混合有效PNG/损坏PDF；有效文件/任务存在、坏文件失败、相同请求返回同批次、仅引用任务且无岗位。artifacts/t14-live-local.json。仅领域服务+真实依赖验收；HTTP契约由TestClient覆盖，不称已完成浏览器招聘页面。
- 没有调用真实模型或外部邮件。T15处理器尚未注册，现有worker可能显示HANDLER_NOT_REGISTERED，接口如实呈现任务失败，不冒充已解析或已建档。人才建档、邮箱门槛和后续流程仍待T15等。
- 严格规格验证通过；数据库字典由当前ORM重新导出，原有架构文档/配置改动保留。

复验（代码根目录）：

~~~text
.venv\Scripts\python.exe scripts/compose.py run --rm -T --no-deps -v "%CD%:/work:ro" -w /work api python -m pytest -q -p no:cacheprovider backend/tests/integration/test_import_batches.py
.venv\Scripts\python.exe scripts/compose.py run --rm -T --no-deps -v "%CD%:/work:ro" -w /work api python -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe scripts/compose.py exec -T api python /app/scripts/verify_imports_local.py --allow-dev-write
~~~
