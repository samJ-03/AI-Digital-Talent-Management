# T20/T21 语义检索与岗位匹配契约

## 能力边界

T20实现API032 POST /api/v1/talents/search与API036 GET /api/v1/jobs/{job_id}/recommendations。T21为内部固定匹配流程，不增加公开API；结果沿T19评估详情展示。T22/T23邀请、考试、业务页面仍属于后续任务。

语义相关度semantic_relevance使用COSINE原值，绝不乘100冒充匹配分。匹配分来自模型提出skills/experience/responsibilities分项，再用已发布岗位权重在服务端Decimal加权并四舍五入2位，例如80/60/100按50/35/15得到76.00。分项未知时无总分，不以0替代未知。

## 分层与真实依赖

search/router → TalentSearchService → ModelGateway.embed / MilvusStore → MySQL逐条复验。IndexService负责源快照和两阶段一致性；IndexRecovery从当前可信画像恢复持久profile.index任务。MilvusStore使用锁定的pymilvus SDK、显式schema、COSINE AUTOINDEX与Strong读取，不用内存列表模拟生产索引。

evaluation/match_worker消费T19的evaluation.match.requested引用事件，创建application.match任务；MatchHandler在prepare阶段调用固定LangGraph/受控网关，不持身份锁；finalize在有效任务租约事务内复验并保存MatchResult。模型没有发信、改阶段或录用工具。

## 索引安全与代际

只索引T17已核查、当前且ready的共享画像summary/skills/experiences。来源证据、简历版本和内容参与hash；不拼接部门面试、考试、联系方式或authorized_application_views。Milvus只保存向量与ID、类型、scope、部门占位、内容摘要，不保存简历原文。知识chunk不进入人才集合，未来知识检索另定义集合与权限。

集合名含受控命名空间、实体类型、模型配置ID/修订、维度与真实digest摘要（云端无digest时明确按配置修订标识）。更换模型、维度或修订进入另一集合，旧向量不混召。MySQL index_records记录当前collection/key/hash/state；无需修改数据库字段。

embedding外部调用前后复验来源与模型流程修订。Milvus写入成功但MySQL提交失败不会被检索采信；过期画像、合并别名、归档、未决重复和ready以外人才均在召回后排除。索引是可删除、可重建的派生数据，MySQL为事实来源。

模型关闭、连接失败、集合丢失、查询失败均明确503 SEMANTIC_INDEX_UNAVAILABLE；不将基础设施故障伪装成空搜索。sync可重建失败或丢失集合；同来源和配置的后台任务不会无限新增绕过重试上限。管理员可在维护入口调用内部IndexService.sync重建，本任务未增加公开管理API。

## API与筛选

搜索需要HR共享talent.read和CSRF，拒绝额外字段；推荐另需岗位job.read及部门范围，返回前复验权限。所有响应no-store。GET推荐只读，不补索引、不加入招聘、不发卷。

搜索请求query、filters和page_size。filters现支持skills全部精确匹配、education原始degree和major精确匹配；不使用私有评价作过滤。page_size1～100；召回上限与阈值由TALENT_SEMANTIC_TOP_K（默认200，上限1000）和TALENT_SEMANTIC_MIN_RELEVANCE（默认0，-1～1）配置。过期/无权命中过多时结果可少于page_size，调整召回上限增加覆盖。TALENT_MILVUS_URI默认容器内http://milvus:19530；模板与Compose一致传递。

## 匹配证据、冻结与失败

只从本EvaluationRun冻结的简历事实与岗位描述/条件构造证据，不读取其他评估、考试、面试。排除姓名作为评分证据；输入引用严格为本run的resume_version/job_version。网关schema/完整原文引文校验后持久AiRun，业务再核验每个维度/优势/差距证据。

JSON数值按严格number边界接收，计算时Decimal(str(score))，没有降低网关严格校验。只岗位证据或无简历证据的维度为unknown；无总分且state=needs_review。来源引用校验不能证明模型的自然语言推理准确，最终仍需HR判断与T40质量样本验收。

只有硬筛pass或已人工覆盖的当前有效评估可调用模型。迟到、来源切换、配置改变、模型/证据失败均不发布有效分数、不当作不合格，也不自动邀考。人工覆盖和重评保持manual_only。每run一个MatchResult，重复消费/重试复用，旧运行不更改当前评估。模型配置关闭时保留待交付事件，绝不自行启用模型。

## 验证方式

常规pytest使用真实talent_test、真实Milvus SDK和独立talent_test集合，供应商使用httpx.MockTransport合成响应。测试不调用付费模型、不发外部邮件；现有官方供应商鉴权证据沿用，不重复付费探测。测试集合只删除本fixture创建的唯一命名空间；开发库与其他集合保留。

SDK参考：[Milvus schema](https://milvus.io/api-reference/pymilvus/v2.5.x/MilvusClient/Collections/create_schema.md)、[Milvus 2.6 consistency](https://blog.milvus.io/docs/v2.6.x/consistency.md)。代码与锁文件以及实际真实SDK往返为本地验证依据。

## 管理员启用准备

匹配提示词参考backend/app/evaluation/prompts/match.txt；用scripts/export_match_contract.py导出准确输出schema，创建/发布task_type=match提示词并绑定已验证deepseek-flash连接。embedding绑定已验证百炼text-embedding-v3及实测维度。默认不自动开启两个流程；管理员明确启用后才产生付费调用。模型已停用/复测失败时保留待交付事件，不能将配置故障固化为候选人低分。

## 审查后的一致性加强

IndexService.prepare只生成SDK派生产物，不提交可信ready/failed；finalize在有效任务租约事务中复验后发布。同来源同代际已有ready时，迟到失败保留成功状态。显式sync复用同一两阶段边界。

匹配准备和提交之间除workflow修订外，还冻结/复验实际ModelConfig的启用、verified/text/json能力、digest、连接修订及凭据密文摘要；模型独立复测无需改变workflow也会被检测。停用模型时待交付事件保留pending，不发起生成。

可直接复制docs/schemas/match-output.schema.json作为发布schema；它由本次实际MatchDraft模型生成并通过JSON解析核验，不是手写的近似结构。
