# T13字段提取验收（2026-11-09）

- 定向18项通过，完整259项通过（173.46秒），独立审阅无阻塞发现。
- RED证据：5项真实失败表明原类型校验会放过编造姓名/邮箱、缺失或多余字段来源、空事实；补充逐字段原文校验后通过。
- 真实隔离MySQL + 固定LangGraph + ModelGateway + MockTransport验证：缺邮箱保持null，合法字段保留来源；无效字段/来源的AiRun为invalid且validated_output为空，不保存为成功。
- Docker原先未启动，本机venv缺jsonschema，最初环境失败不计RED；启动Docker并恢复本项目已有服务后，在锁定依赖容器内验证通过。不对宿主补装依赖、不重置数据库。
- 原T13仍未完成：OCR、旧DOC转换、全格式及真实AI提取质量待验收。T14导入授权/任务与T15建档尚未实现，无新公开API、表或依赖。
- 未调用真实付费模型或外部邮件；管理员现有工作流与提示词未自动修改。调用前需已发布的extract schema与ResumeFacts.model_json_schema()匹配。
- 本地证据：artifacts/t13-extract-red.log、t13-extract-expanded-green.log、t13-extract-final-suite.log。原PDF/DOCX提交902cdbf已成功补传GitHub。

复验：通过scripts/compose.py run容器，在仓库只读挂载/work、工作目录/work，运行python -m pytest -q -p no:cacheprovider。定向文件为backend/tests/unit/test_resume_extraction.py及backend/tests/integration/test_resume_extraction_gateway.py。破坏性DB检查只允许talent_test。
