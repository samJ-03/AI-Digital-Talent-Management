## ADDED Requirements

### Requirement: Independent upload acceptance
系统 SHALL 对授权HR的最多50份文件逐份校验，合法文件存私有对象并入队；单份失败不回滚其他文件。仅前置校验失败条目允许file_id为null，且status必须failed。

#### Scenario: Mixed valid and invalid inputs
- **WHEN** 同批有合法图片和损坏PDF
- **THEN** 返回202批次，合法条目queued且有任务，非法条目failed且返回安全原因

### Requirement: Idempotent atomic batch
系统 MUST 根据操作者、请求键、真实文件哈希及有序元数据保证重复请求返回同批次，不重复创建任务；相同键不同输入409。任务、条目、批次及审计同事务，外部文件I/O在事务外。

#### Scenario: Repeated request
- **WHEN** HR以相同键和输入重试
- **THEN** 返回同一批次和任务，不能重复邀请

### Requirement: Authorized polling and safe retry
系统 SHALL 仅向具有当前持久部门范围的HR展示批次与安全任务状态；岗位关联批次即使本人创建也必须保留对应岗位部门访问权；管理员不能管理招聘。失败解析可再次受理且并发重试防重，成功条目不重复解析；没有有效文件的失败需换文件重新上传。

#### Scenario: Cross department request
- **WHEN** 另一部门HR读取或重试批次
- **THEN** 返回404且无状态变化
