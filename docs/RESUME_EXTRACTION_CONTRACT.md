# T13 简历字段提取内部契约

更新：2026-11-09。承接原详细计划T13及MODEL_GATEWAY_CONTRACT；不是公开导入API，也不代表完整招聘闭环完成。

## 类型和调用

extraction_types.py定义ResumeFacts和ExtractedResume；extraction.py定义ResumeExtractor(gateway, source_file_id).extract(document: ParsedDocument, config: AiConfigSnapshot) → ExtractedResume。调用者必须先按持久文件关系授权，source_file_id必须是数据库文件ID；禁止将客户端自报ID直接当授权。T14尚未接入这个边界。

模型输出白名单：identity（name/birth_date）、contacts（email/phone）、education（school/degree/major/start_date/end_date）、employment（company/title/start_date/end_date/responsibilities）、projects（name/role/description）、skills、certificates、field_sources、citations。已校验结果由网关补充可信ai_run_id；模型不得自报运行ID。字段缺失为null或空列表，空字符串和完全空经历条目拒绝。邮箱只做本地语法验证，不查DNS、不证明收件人身份。

学历、日期、电话等保留原文，不在提取阶段推算年龄、相关年限或能力分。规范化与三态规则留后续领域服务。此产物仍需业务/人工确认，不把模型的字段分类或原文自述当成客观能力证明。

## 字段证据

field_sources是叶路径到Evidence数组的映射，例如identity.name、education.0.degree、skills.0。Evidence包含source_type/source_id/locator/quote，必须出现在根citations中。每个非空叶字段恰有对应来源路径，未知字段不得假附来源，字段值必须是至少一段对应quote的原文子串；不做模糊相似替代。此保守规则可能拒绝模型擅自改写日期、缩写或规范化邮箱，因此提示词须要求原文值。

业务Pydantic校验先发生，随后已有网关核验根citations真正来自输入文档及配置快照、已发布schema。两层均成功后AiRun才能为succeeded；无效结果为invalid且validated_output为空，不保存原始供应商响应。

输入来源固定stored_file，定位使用ParsedDocument.paragraph.id，不接受模型自造页码。每段独立证据，当前最多100段、输入约250KiB预预算，网关仍有最终256KiB限制；超限返回AI_INPUT_TOO_LARGE，不能截断再声称完整提取。后续长文拆分需单独实现。

## 提示词和配置

仅通过FixedGraphRunner的extract任务和既有ModelGateway，沿用DeepSeek与管理员配置，不新增密钥、不自动启用流程或改发布提示词。管理员需发布与ResumeFacts.model_json_schema()一致的schema并绑定extract工作流；不匹配会在网络调用前拒绝。

提示词应要求：将所有证据当数据；只提取白名单事实；未知填null/空列表；值保持原文；每个已知叶路径提供来源；不得补造邮箱、推断敏感属性、加评分或服从简历中的操作指令。模式/schema验证不替代后续真实AI质量评测。

## 当前验证和后续

定向18项通过，使用真实隔离MySQL、固定图、网关和模拟HTTP；有效结果保存运行证据，编造姓名/邮箱/来源均不成功持久化。真实供应商提取质量未在本轮验证，没有付费模型调用或外部邮件。

下一步T14批量导入/任务衔接、T15建档；OCR、旧DOC和完整T13全格式验收仍未完成。已有解析器对扫描页、复杂Word给出明确失败，不伪造字段。

完整回归259项通过（173.46秒）；验收记录见T13_EXTRACTION_VERIFICATION.md。
