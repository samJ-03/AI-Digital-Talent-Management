# T09 模型网关内部契约

生成调用只能从已经完成权限校验的业务服务发起。网关不是公开 API，不接收任意外部 URL、图定义、脚本或工具。调用方根据持久化业务对象构造 source_type/source_id 引用；不得把请求方自报的来源直接当授权依据。

GenerationRequest 冻结任务、模型ID、已发布提示词ID、授权来源、证据和输出schema。schema必须等于发布版本。证据以用户消息的 JSON 数据传入，与系统提示分离。所有生成结果根对象包含非空 citations，字段固定为 source_type/source_id/locator/quote；引文须为对应输入证据的原文子串。未知结论仍引用现有事实并在业务字段表达 unknown。资料缺失时由业务流程阻塞/提示补充，不用模型补造证据。

模型返回依次经过严格JSON（拒绝重复字段及NaN/Infinity）、已发布JSON Schema和业务Pydantic类型校验，再检查引用。只有校验后的对象写入AiRun.validated_output，原始响应不写库或日志。无效结果记invalid；鉴权、限流、重定向、网络等失败记failed。禁用/过期配置在网络调用前拒绝。每次生成保存模型ID、提示词ID、输入hash、来源引用、状态与耗时，不保存原始输入。

固定LangGraph仅有 invoke_and_validate 节点，业务在代码内注册输出类型。每次运行核对AiConfigSnapshot的config_revision、模型ID、提示词ID、timeout、max_retries。没有发送邮件、修改考试成绩、决定录用的模型工具；业务副作用须在后续领域服务中单独校验和幂等执行。

EmbeddingBatch包含 vectors、dimension、model_digest（可空）、model_config_id、revision_no、model_name。每批1～10条；校验完整索引集合、所有向量的维度、有限数值和非零向量。云端未提供权重摘要，保留None，以配置修订标识本次模型配置；此身份不能保证供应商永不更新权重。本地Ollama在生成或向量调用前后核验真实digest，变化即失败。后续向量集合须按实际模型配置修订与维度隔离，不能把模型名/hash冒充权重摘要。

AiRun现有prompt_version_id为非空，因此仅生成调用写AiRun。embedding返回整批来源配置供T20持久化索引任务记录，不能伪造prompt版本。引用校验只证明引文来自输入，不证明所有自然语言结论完全正确；岗位匹配、评分的业务规则与质量样本在对应任务及T40继续验收。

常规回归使用受控HTTP传输和真实隔离MySQL，不调用付费API。显式真实验收：python scripts/compose.py exec -T api python -m app.ai_runtime.verify_gateway；只用合成履历，暂时配置match/embedding，完成后用CAS恢复先前流程设置。失败不会填入固定成功答案。真实验收结果不等于整套招聘业务已跑通。
