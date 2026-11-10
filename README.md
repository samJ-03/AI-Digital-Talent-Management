# AI 数字化人才平台

面向单企业外部人才招聘的开发中项目。管理员管理账号、权限与模型配置；HR开展招聘；候选人通过独立考试入口参与测评。AI辅助筛选、画像、匹配与评分，最终招聘结果由HR决定。智能培训当前只做框架。

当前完成T01～T12：基础服务与40张表、账号权限、持久任务/Outbox、私有文件、模型与提示词配置、受控模型网关、题库与发布试卷、本地邮件配置、岗位版本与自动邀请配置。完整招聘流程和业务页面尚未完成，T13已增加[文本PDF/DOCX内部解析](docs/CORE_PARSER_SUPPORT.md)，已完成[字段提取](docs/RESUME_EXTRACTION_CONTRACT.md)与[T14批量导入受理](docs/IMPORT_BATCH_CONTRACT.md)，已增加[T15人才建档、邮箱门槛与简历修订](docs/CANDIDATE_MATERIALIZATION_CONTRACT.md)；已增加[T16人工去重与历史合并](docs/DUPLICATE_RESOLUTION_CONTRACT.md)；已增加[T17共享画像与恢复流程](docs/PROFILE_GENERATION_CONTRACT.md)；下一步T18硬规则筛选；OCR和旧DOC转换仍未完成；按[核心交付顺序](docs/CORE_DELIVERY_PRIORITY.md)先推进T30最小闭环。岗位阶段只生产扫描事件，实际邀考由T22/T23承接。上传前完整验证结果见开发记录，不把连接成功当业务验收。

## 技术组成

| 层 | 技术与职责 |
|---|---|
| 前端 | Next.js 16、React 19、TypeScript、Ant Design、TanStack Query |
| 后端 | Python 3.11、FastAPI、Pydantic、SQLAlchemy、Alembic |
| 业务事实 | MySQL 8；当前40张表、478个字段，表和字段均有中文COMMENT |
| 异步任务 | Redis、Celery、事务Outbox与数据库租约 |
| 文件和索引 | 私有MinIO、Milvus；向量索引可从业务事实重建 |
| 模型 | DeepSeek deepseek-flash、百炼text-embedding-v3；可选本地Ollama与后续rerank |

实际依赖版本及镜像摘要以锁文件和infra/versions.lock.json为准。

## 首次启动（Windows CMD）

需要Python 3.11、Docker Desktop Linux引擎；本地前端开发另需Node 24。以下命令在仓库根目录执行。

~~~bat
git clone https://github.com/samJ-03/AI-Digital-Talent-Management.git
cd AI-Digital-Talent-Management
python -m venv .venv
.venv\Scripts\python.exe scripts/init_env.py
docker build -f infra/Dockerfile.runtime -t ai-talent-runtime:dev .
.venv\Scripts\python.exe scripts/compose.py --profile test up -d --build --wait
.venv\Scripts\python.exe scripts/compose.py exec -T api alembic upgrade head
.venv\Scripts\python.exe scripts/bootstrap_local.py
~~~

Linux/macOS将.venv\Scripts\python.exe替换为.venv/bin/python。Compose包装器显式加载本仓库.env，避免直接调用错误的环境配置。

init_env仅创建新.env，不覆盖已有文件，也不显示秘密；两个环境模板.env_example与.env.example内容一致。bootstrap生成管理员及两个部门HR的随机密码，保存在忽略提交的.execution/local-accounts.json，不提供固定默认密码，不重置已有账号。

| 本地入口 | 地址 |
|---|---|
| 开发状态页 | http://localhost:13000 |
| API文档 | http://localhost:18080/docs |
| 本地邮件收件箱 | http://localhost:18025 |

邮件被Mailpit截获，不对外投递。首页当前为开发状态页，具体HR业务页面按后续任务实现。

## 配置与模型

完整变量、用途、单位和默认值写在[.env_example](.env_example)，补充说明见[配置文档](docs/CONFIGURATION.md)。基础服务秘密由脚本生成；可选官方模型Key自行填入私有.env。模型地址、提示词、固定流程和SMTP连接由管理员服务管理，不使用虚构环境变量。

七个AI流程默认关闭；模型能力验证通过也不会自动开启。保留原Fernet主密钥，恢复加密数据库时必须一起恢复。真实模型测试是显式付费操作，只允许合成资料；常规pytest不消耗模型额度。企业SMTP和生产部署尚未接入。

## 验证

完整测试使用隔离talent_test，会迁移和重置测试数据，禁止指向talent_dev或其他已有数据库。

~~~bat
.venv\Scripts\python.exe scripts/compose.py --profile test up -d mysql-test
.venv\Scripts\python.exe scripts/compose.py run --rm -T --no-deps -v "%CD%:/work:ro" -w /work api python -m pytest -q -p no:cacheprovider
~~~

首次运行前完成上面的构建和启动。迁移往返、真实MySQL COMMENT、字段定义保真、权限隔离、幂等和模型错误处理都在测试范围。前端变更另运行npm run lint、npm run typecheck、npm run build。强制中断后先排除旧测试进程与隔离库残留，不要放宽保护逻辑消除失败。

## 代码与文档导航

- backend/app：按身份、岗位、导入、人才、筛选、考试、邮件和任务等领域组织。
- backend/alembic：追加式数据库迁移；0005把中文字段说明写入MySQL。
- frontend/src：页面、公共Provider及同域API客户端。
- infra：本项目Compose、反向代理与镜像锁定。
- scripts、backend/tests、tests：初始化、检查、数据库字典导出与测试。
- [数据库字典](docs/DATABASE.md)：全部40表、478字段、外键、约束与索引。
- [注释及开发规范](docs/CONTRIBUTING.md)、[模型网关契约](docs/MODEL_GATEWAY_CONTRACT.md)、[开发续接记录](docs/DEVELOPMENT_HANDOFF.md)。
- [岗位版本契约](docs/JOB_VERSIONS_CONTRACT.md)、[核心交付顺序](docs/CORE_DELIVERY_PRIORITY.md)。
- docs/specs：需求、架构、接口、验收和详细开发计划；原评审基线保留，最新实施差异以模型/数据库决策补充和开发记录为准。

## 上传内容与排除范围

上传源码、测试、迁移、锁文件、基础设施配置、无秘密环境模板、需求及技术文档和CI工作流。所有代码注释应说明职责与业务边界，数据库模型同时包含类说明、表comment与字段comment。

不上传真实.env、API Key、Fernet主密钥、账号密码文件、日志、artifacts、.execution、简历/答卷、数据库导出、对象存储内容、虚拟环境、node_modules或构建缓存。忽略规则不能替代提交前检查，首次上传还需检查既有Git历史中是否误存秘密。仓库仍处于开发阶段。


## 从哪里看架构

先读[当前代码架构与目录导航](docs/specs/10-当前代码架构与目录导航.md)，再读backend/app/README.md。代码按业务领域分包，每个领域内部通过router/schema/service/model区分职责；目前没有全局controller/service/repository三大目录。文档图使用本地PNG，不再只依赖Mermaid渲染。
