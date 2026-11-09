# T14 批量导入受理与重试契约

实施：2026-11-09。对应API023～026及原详细计划T14，无新表/字段或依赖。实际解析处理器、人才建档和邮箱门槛由T15承接；202是受理，不是成功入人才库。

## 接口与权限

- POST /api/v1/imports：multipart重复files字段、可选job_id，Idempotency-Key必填；返回202 ImportBatchView。
- GET /api/v1/imports：page默认1、page_size默认20且最多100，返回授权范围内分页；总数与列表同样过滤。
- GET /api/v1/imports/{id}：返回BatchDetail及按source_order排列的items。
- POST /api/v1/import-items/{id}/retry：JSON reason必填，返回202 TaskAccepted。poll_url为批次详情。

只有HR，写入与重试同时要求import.write/import.read；关联岗位还需job.read。权限范围来自持久岗位部门或无岗位批次的创建者当前部门，不信任前端自报部门。岗位批次即使本人创建，也不能绕过已撤回的跨部门权限；列表与详情一致。管理员不能招聘写入。

## 文件与独立失败

默认最多50份/每份20MiB/PDF100页；max_files可在服务构造时降低，单文件与页数沿FileService配置。文件循环读取并按真实内容计算SHA256，不信任声明大小；内存缓存超过1MiB转临时文件，结束/失败均关闭。总预算为max_files*单文件预算+1MiB，超总预算拒绝整请求；单文件超过大小、页数、格式/加密/损坏等则单份失败，不撤销其他文件。

合法文件在私有MinIO存储，关联后创建queued条目及resume.parse任务。初步校验失败条目status=failed、file_id=null，无虚假空文件或StoredFile。每份失败返回固定安全代码和说明；无文件的失败不能原文件重试，须更换文件重传。不会返回对象key、原始异常或供应商输出。

0007_import_upload_failures仅将import_items.file_id改可空并加CHECK(file_id IS NOT NULL OR status='failed')；表数40/字段478不变。降级前如果有无文件失败记录，先拒绝降级且不执行DDL，不删除业务数据。

## 幂等与事务

同操作者同请求键以岗位、文件顺序、名称/MIME、真实长度和哈希绑定。相同输入返回同一批次/任务；不同输入409，正常重放不再上传对象。请求键对批次永久唯一，幂等指纹记录清理后不能靠旧键猜测新建，返回409 IMPORT_KEY_EXPIRED并要求新键。

文件上传在数据库业务事务外；批次、条目、文件ready关联、BackgroundJob、Outbox、审计同事务。并发请求只有一个批次/任务胜出，落败staged对象与审计失败留下的staged对象由T07宽限期清理，不删除有引用文件。

任务input_refs仅file_id/import_item_id及可选job_id，不传简历正文、邮箱或密钥。只产生job.dispatch，不直接建考次或发邮件。

## 查询与重试

ImportBatchView包含id/job_id/created_by/file_count/status/created_at。BatchDetail.items包含id、零起点source_order、可空file_id/filename、status、安全error_code/error_detail_safe、task_id/task_state、resume_version_id。创建时间为UTC。状态由条目及最新任务事实投影：全部parsed为completed，任一failed为partial_failed，否则running映射processing，其余queued。

重试在READ COMMITTED事务锁批次和条目，非锁定读取最新任务，避免与worker先锁任务再锁领域行的顺序反转。queued/running/retry返回现有任务；failed/cancelled且原文件有效才创建带前序task ID的新任务；parsed或已成功不重跑。并发重试只创建一次新任务。

T15之前resume.parse未注册，现有worker可能将任务标为HANDLER_NOT_REGISTERED；查询如实显示失败并允许稍后重试，不把排队伪造成解析完成。T15接上后需要在任务完成事务更新条目/批次与后续产物。

## 已验证边界

21项定向测试通过，含真实私有MinIO/隔离MySQL、并发创建/重试、防反向等待任务锁、审计回滚、权限撤回、SQL CHECK错误码3819及迁移往返/降级保护。曾发现创建者范围撤回后列表仍显示批次，已用真实RED/回归修复。约束测试曾将驱动的OperationalError误写为IntegrityError，已改为严格核验3819，不将测试异常类型差异算领域RED。

本地合成批次7项受理检查通过，4个真实API路由已加载；无真实候选人、付费模型或外部邮件。业务前端和实际人才建档尚未完成。
