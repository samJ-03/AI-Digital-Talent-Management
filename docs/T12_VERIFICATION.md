# T12验收记录（2026-11-07）

- 范围：七项岗位写API、草稿与发布版本、状态机、自动邀请就绪门、原子invite.scan事件；无表结构或依赖变更。
- 有效RED：t12-red.log记录路由未实现导致404而预期201；t12-concurrency-red.log记录邮件/模型并发停用被误放行及并发草稿序号冲突，3项真实失败。
- 定向GREEN：t12-expanded-green.log，19 passed in28.58s。涵盖部门/身份隔离、权重与模板校验、发布不可变、CAS/幂等、当前版本归属、配置并发失效、并发版本分配、事件防重及审计失败整体回滚。另一次跨部门测试失败源于测试客户端切换账号后未恢复匹配的Cookie/CSRF，修正fixture会话后通过，不将其算作有效领域RED。
- 完整回归：t12-final-suite.log，209 passed in142.30s。独立talent_test，容器只读挂载当前源代码运行pytest -q -p no:cacheprovider。前端未修改，本轮未重复前端构建。
- 本地开发库合成验收：t12-live-local.json，ready=true，9/9。job_id=1、job_version_id=1；draft/off→published→open→缺卷拒绝开启→pause→reopen/off→closed/off，扫描事件数0。没有读取账号密码，没有模型/SMTP请求。此为领域服务验收，HTTP契约由集成测试覆盖，未冒充真实浏览器端到端验收。
- 独立只读审阅：T12授权、快照、锁序、事务、接口/测试未发现剩余阻塞问题。已修复强引用依赖快照、刷新ORM实体以及锁定最新版本号读取。
- 仍未完成：T22扫描消费者/唯一考次、T23实际邀考投递、T13解析和招聘页面；企业SMTP、生产部署未接入。普通就绪预览是时点提示，发送时必须复验。

执行命令（代码根目录）：

~~~text
.venv\Scripts\python.exe scripts/compose.py run --rm -T --no-deps -v "%CD%:/work:ro" -w /work api python -m pytest -q -p no:cacheprovider backend/tests/integration/test_job_versions.py
.venv\Scripts\python.exe scripts/compose.py run --rm -T --no-deps -v "%CD%:/work:ro" -w /work api python -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe scripts/compose.py exec -T api python /app/scripts/verify_jobs_local.py --allow-dev-write
~~~

详细日志保存在原开发机ignored artifacts；新克隆可按上面命令复验，先完成README的构建与本地账号初始化。
