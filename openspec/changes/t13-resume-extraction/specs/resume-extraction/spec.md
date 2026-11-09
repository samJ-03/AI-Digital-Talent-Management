## ADDED Requirements

### Requirement: Evidence grounded resume facts
系统 SHALL 仅提取identity、contacts、education、employment、projects、skills、certificates白名单事实；每个非空叶字段必须有field_sources且值能在引用原文中找到，来源由网关核验。

#### Scenario: Missing email
- **WHEN** 原文没有邮箱
- **THEN** contacts.email保持null，不补造邮箱

### Requirement: Fixed authorized generation
系统 MUST 只经现有extract固定图/模型网关调用，采用固定业务schema与配置快照，持久来源由调用方预先授权；超出100段或输入预算明确拒绝，不能截断。

#### Scenario: Invented value or citation
- **WHEN** 模型返回无原文依据字段或伪造引用
- **THEN** 网关拒绝结果，不保存为成功提取
