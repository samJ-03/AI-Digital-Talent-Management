# 模型接入与数据库决策补充

2026-11-05；根据用户最新指示更新。本文只记录安全元数据，不包含密钥或连接密码。

当前状态：百炼 text-embedding-v3 已用授权来源中的 ALIYUN_API_KEY 通过真实鉴权并返回1024维；DASHSCOPE_API_KEY 是占位项。DeepSeek 官方 Key 仍未找到。文末最新验证结果取代较早“尚未调用/Key待验证/地域待确认”的历史记录。

## 用户选择与核对结果

- 授权读取并择需复用的来源：D:/Wolin_Project/Yue-Education/.env。只读，未修改源文件；不得整份复制旧项目环境。
- LLM：用户指定 DeepSeek 的 deepseek-flash。官方模型 ID 已核对存在。调用渠道尚待用户答复。
- Embedding：用户原文 test-embedding-v3，按官方模型命名纠正为 text-embedding-v3；用于人才共享事实/招聘知识的语义检索。初拟1024维，必须通过实际输出维度检查后冻结索引版本；不能把不同模型/维度混入现有 collection。
- Rerank：用户指定 qwen3-rerank，作为语义召回后的可配置排序增强。它的相关性分数不等于岗位胜任分，不作为自动录用/淘汰依据。只重排当前账号可见的候选文本；结果仍从 MySQL 复核当前权限和有效版本。
- 百炼 DASHSCOPE_API_KEY 已配置。旧文件中的 ALIYUN_API_KEY 是另一个值；不能据变量名猜测用途，更不能替换成云账号 AccessKey 使用。
- 没有 DEEPSEEK_API_KEY。旧 OPENAI_API_KEY 的 OPENAI_BASE_URL 指向第三方 api.openai-proxy.org，而不是 DeepSeek 官方接口。已向用户询问直连官方还是使用该代理；未向任一云模型发送请求，未将代理 Key 发往官方地址。
- 百炼 endpoint/region/workspace 未在该 .env 中配置，实际连通验证前还需核对，不能只凭 Key 存在宣布可用。
- 无需 OpenAI 平台账号；使用 OpenAI-compatible 协议不表示使用 OpenAI 供应商。将通过 provider 独立适配器处理。

## 数据库结论：保留 MySQL + Milvus

用户允许在迁移量大时保留原技术栈，本轮据此决定继续 MySQL8/InnoDB 保存业务事实、Milvus 保存向量索引。

127.0.0.1:5432 TCP 与 PostgreSQL SSLRequest 协议探测均有响应；未认证、未读取库或用户、未获知实际版本，未修改 PostgreSQL 服务。

PostgreSQL 的 JSONB/索引等能力适合此类系统，但本项目没有必须依赖它的新需求。当前40张表、478列、两个显式 Alembic 修订及事务测试已落地。静态检查发现21个后端文件含 MySQL 具体类型/排序规则/迁移/锁或专用断言（629处文本匹配，仅为影响面线索，不代表629项独立改动）。迁移需要重新验证无符号ID语义、utf8mb4排序/唯一性、时间/JSON、迁移往返、约束错误码、单调度器锁、驱动锁文件、Compose和CI，代价已超出简单替换连接串。

因此不为了现有 PostgreSQL 已启动而切换，不接管或改写该实例；新建其他项目时可以重新评估。也不在当前迭代替换已运行的 Milvus 为 pgvector。

## 对开发计划的影响

- T06/T07 与模型渠道无关，可继续开发；当前 T06 仍未完成。
- T08 配置 provider 增加 deepseek、dashscope 及可选经过显式确认的代理类型；凭据只写本项目忽略文件/加密配置，响应只返回 configured 标记。
- T09 主验收由本地 Ollama 改为用户选择的云端适配器；原 OllamaAdapter 保留为可选接口，不将其当作已启用路径。LLM 结构化 schema、来源校验、超时和重试边界保持不变。若代理未提供固定底层模型版本，只能记录请求 model ID、返回 model 和配置修订，不能伪造模型 digest 或声称锁定权重版本。
- T20 增加可选 RerankAdapter；在权限过滤的召回候选集合上重排，记录启用状态/模型修订；失败按显式策略报告或降级，不能悄悄把降级结果当作完成精排。
- T40 模型质量回归使用已确认的 provider/model 与配置修订，不再把旧本地小模型的结果视为当前模型证据。
- 先用合成文本做低成本连通与维度/排序检查，结果只记状态、模型、维度和安全错误码，不记录 Key、完整响应、真实候选人资料。

## 官方参考

- DeepSeek 模型和接口：https://api-docs.deepseek.com/
- 百炼 Embedding 模型与维度：https://help.aliyun.com/zh/model-studio/embedding
- 百炼 Rerank：https://help.aliyun.com/en/model-studio/rerank
- PostgreSQL JSON 类型：https://www.postgresql.org/docs/current/datatype-json.html

## 尚需用户提供的非秘密信息

1. DeepSeek 走官方还是已提供的第三方代理（已发起问题）。如走官方，只需提供本地 Key 配置位置，不在聊天中粘贴密钥。
2. 百炼服务地域/实际 API endpoint，必要时 workspace 信息；原 env 无该配置。没有此信息时暂不执行云端请求。


## 最新补查结果：rag_examples（2026-11-05）

用户追加授权检查 D:/wolin_learn-master/rag_examples/.env 及该目录配置代码。只读检查 .env、.env.example 与相关源代码，未显示或复制密钥，未执行旧项目代码，未发送模型 API 请求。

- .env 仍无 DEEPSEEK_API_KEY，.env.example 也未声明该项；DEEPSEEK_API_KEY 只在教程说明出现，不能当成可用凭据。OPENAI_BASE_URL 仍为 https://api.openai-proxy.org/v1，不能据此假定官方 deepseek-flash 已可用。该目录的 DASHSCOPE_API_KEY 与代理 Key 和先前指定项目分别相同；比较只记录相等性，不保存值或指纹。
- 找到百炼配置依据：0201_document_parse/mineru_parser.py、02_document_chunking/03_ai_chunking.py、04_summary_chunking.py、03_retrieval_methods/02_vector_search.py 中有 https://dashscope.aliyuncs.com/compatible-mode/v1。这是北京地域旧共享域名，官方文档确认目前仍可使用。故“缺少百炼地区/endpoint”不再需要用户补充；下一步可用该已发现地址进行合成输入连通验证，尚不能声称 Key 认证成功。
- embedding_examples/aliyun_embedding.py 使用 DashScope SDK 的 TextEmbedding.call，未覆盖 base_http_api_url；其中 ALIYUN_API_KEY 被明确作为模型调用的 api_key 使用。这提供了用途证据，但与 DASHSCOPE_API_KEY 是不同值，不能无记录地混用或自动尝试所有 Key。后续只为指定适配器映射明确选定的来源变量。
- 现阶段仍缺 DeepSeek 官方凭据或对代理渠道的明确选择。用户可将官方 Key 配置到本地文件并仅提供路径；不要在聊天中粘贴 Key。此项只阻塞相应模型接入，不阻塞 T06/T07。

官方地域/域名说明：https://help.aliyun.com/zh/model-studio/base-url


## 最新实际验证与凭据选择（T08 完成）

- 进一步区分字段存在和凭据可用：授权文件里的 DASHSCOPE_API_KEY 是占位项。旧 embedding_examples/aliyun_embedding.py 明确将 ALIYUN_API_KEY 作为 DashScope TextEmbedding.api_key 使用；据此选取该非占位项，而非把云账号凭据按名字猜成模型 Key。
- 已仅把选中的模型 Key 映射到本项目忽略文件 .env 的 TALENT_DASHSCOPE_API_KEY。源文件未修改，其他账号/代理 Key 未复制。加密主密钥由本项目随机生成并保留在主项目 .env，数据库只存加密值。临时 staging 的 .env 不含此用户 Key；同步脚本从此排除 .env。
- 实际北京接口调用成功：模型 text-embedding-v3、两条合成短文本、返回1024维，未发送真实简历；证据 code/ai-talent/artifacts/t08-live-dashscope.json。云端权重 digest 无法获取，保留None；不虚构模型版本锁定。
- provider_type 沿用已评审的 ollama/compatible_http；受控兼容HTTP适配根据允许的官方地址与模型ID派生 deepseek/dashscope，不扩大数据库 provider 枚举。
- 七个固定流程由迁移初始化且默认关闭。T08 配置接口完成不等于 T09 真实 LLM 输出质量或 T20 rerank 验收完成。DeepSeek 官方 Key/明确代理选择仍缺少，暂不调用 DeepSeek。
