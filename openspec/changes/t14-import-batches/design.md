# Design

## Context
承接原09的T14/API023～026，遵循已确认“缺项保留/缺邮箱阻止自动邀考”。本任务只受理文件，不判断候选人是否合格。

## Decisions
- ImportService.create(actor,files,job_id,request_key)、retry_item(actor,item_id,reason)、get_batch、list_batches沿原签名；files为UploadDescriptor列表。HTTP使用multipart files和可选job_id。
- 每份输入循环读取、真实哈希，SpooledTemporaryFile限制内存；总请求预算为max_files*单文件预算+1MiB。超总预算拒绝整请求；单份超限/格式失败独立failed。默认50份，服务构造可降低max_files，单文件/页数沿FileService配置。Nginx现有1024MiB上限足够默认批次。
- 先复验import.write/read及岗位归属，再准备文件。短事务比对同操作者/key的批次与幂等指纹；重放不再上传对象。首次对象上传在事务外，随后批次/条目/JobSpec(resume.parse)/outbox/审计同事务提交；并发落败的staged对象由T07年龄门清理，绝不覆盖胜出批次。
- 原ImportItem.file_id非空与前置校验失败冲突；0007仅改可空性并加CHECK(file_id IS NOT NULL OR status='failed')。不新增虚假StoredFile或空文件；降级发现null先拒绝，不删除业务数据。表数/字段数不变，同步数据库字典。
- 权限使用持久岗位或创建者的部门，不相信前端自报部门。岗位关联批次即使本人创建也受当前岗位部门权限约束，创建者身份不绕过撤回的范围。列表同一过滤条件用于总数与分页；响应不返回对象key、原始异常或模型输出。
- 任务input_refs只传file_id/import_item_id/可选job_id，默认不产生邀请事件。T15之前resume.parse未注册，查询可见任务的HANDLER_NOT_REGISTERED等失败；不能把受理说成解析成功。读视图将任务失败反映为条目失败，不以虚假完成填补下游空白。
- 重试在READ COMMITTED事务锁批次→条目，然后非锁定读取最新任务（不反向等待worker先持有的任务锁）；最新任务queued/running/retry则返回既有任务；failed且有有效文件才追加以先前task ID区分的新任务。文件前置失败无file_id要求更换重传；parsed或已成功任务不能重跑。poll_url指批次详情。
- request_key在ImportBatch中永久唯一；24小时幂等记录过期/缺失后旧key不能用于新批次，无足够指纹时409并要求新key，不猜测为同一输入。

## Boundaries
没有T15真实解析/建档或前端；仅本地合成资料、独立talent_test，不发真实模型/邮件。保留未提交架构文档和原有配置，不混入本任务。
