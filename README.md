# AI数字化人才平台

单企业外部人才智慧招聘。管理员管理系统，HR操作招聘，候选人使用独立考试入口。

当前状态：基础环境与最小应用骨架已建立，招聘业务尚未开放。开发入口 http://localhost:13000 。任务和技术基线位于本项目上级Obsidian目录。

## 已有工具

- scripts/preflight.py：失败关闭的bootstrap/dev/test/production预检。只记允许的版本/错误码，不导出环境变量、凭据或原始错误。TCP开放不等于服务就绪。
- scripts/lock_python.py：在固定Python3.11 Linux镜像解析backend/requirements.lock。
- scripts/verify_dependencies.py：验证锁定依赖在Linux可安装、可导入。
- infra/versions.lock.json：实际运行时版本及镜像内容摘要；尚未验证的能力单独列明。

## 运行本阶段验证（Windows命令提示符）

    .venv\Scripts\python.exe -m pytest -q
    .venv\Scripts\python.exe scripts/preflight.py --profile bootstrap --report artifacts/preflight-bootstrap.json

bootstrap只证明运行时和Linux引擎可用，不等于数据库、语义索引、邮件或模型已就绪。完整服务和业务验证按开发计划后续任务执行。

## 开发约束

使用项目独立库/卷。不要清空已有MySQL或其他项目容器；不要提交.env、令牌、候选人原件和artifacts。运行日志与任务简报分别位于artifacts/、.execution/。未通过验证的任务不得勾选完成。

## 启动与检查独立服务

    .venv\Scripts\python.exe scripts/compose.py up -d --wait
    .venv\Scripts\python.exe scripts/compose.py exec -T api python /app/scripts/verify_services.py
    .venv\Scripts\python.exe scripts/verify_http.py

Compose入口显式加载本项目.env。仅操作ai-talent-dev命名空间，不改动其他项目。服务协议验证与模型/OCR/业务质量验收分开。
