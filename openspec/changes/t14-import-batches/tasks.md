# T14 Import Batches Implementation Plan

**Goal:** 实现批量导入受理、查询与可追溯重试，不提前宣称T15闭环。
**Architecture:** FileService事务外存文件；HrServiceBase/UoW、幂等和BackgroundJobService同事务创建引用。
**Tech Stack:** 当前FastAPI/SQLAlchemy/MySQL/MinIO/pytest，无新依赖。
**Spec:** 本变更spec、design及原详细计划T14。

## Global Constraints
只使用合成文件和talent_test；迁移追加，不删除失败记录；不调用真实模型或邮件。

## Review Focus
部分失败与file_id约束、真字节哈希、并发重复批次/重试、部门查询分页、读权限前置与审计回滚、未注册处理器边界。

## Tasks
- [x] 1. 建立混合批次/幂等/权限等失败场景并记录RED。
- [x] 2. 实现0007、schemas/service/router及main装配，定向测试通过。
- [x] 3. 并发/回滚/迁移回归、独立审阅与完整验证，保存证据。
- [ ] 4. 更新计划/数据库字典/续接，限定提交上传并核对远端。
