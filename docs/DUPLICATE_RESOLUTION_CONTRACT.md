# 人工去重与历史合并（T16）

基线：docs/specs/04、05与09的T16；API033/034。

## 接口

- GET /api/v1/duplicates：HR共享talent.read，status过滤与分页，只展示身份待核实线索及版本，不返回岗位考试或评价。
- POST /api/v1/duplicates/{id}/resolve：HR当前talent.write/read、CSRF、If-Match；decision为same_person或different_person。same_person必须指定属于两方主身份/别名的target_candidate_id。不同人裁决不得携带目标或关系映射。
- 同岗位有多个有效application时，application_resolutions必须完整指定一个主关系及其余有效次关系；已合并历史关系自动归并映射，不由客户端重新指定。每个重叠岗位的evaluation.read及recruitment.write必须均授权，否则通用拒绝且不返回冲突ID。
- 同岗位未指定主关系、次关系存在活动考次、历史映射损坏时409 MERGE_CONFLICT，原状态完全保留。冲突只含已授权的岗位/招聘关系ID和固定原因。

## 历史与状态

只修改candidates.merged_into_id/status和次应聘relationship_state/canonical_application_id；简历、画像、application.candidate_id、考试application_id、成绩和当前轮次全部保持。目标的联系人、当前简历/画像保留，不从来源自动覆盖。

活动考次包括in_progress、submitted、grading、pending_review，以及尚有效且未撤销/过期的not_started邀请。唯一活动考次在所选主关系可继续，次关系有活动考次则必须先人工处理或等待定稿，系统不自动撤销考试。

合并组内部待审线索同事务确认为同人；任何别名关联的外部待审线索继续阻断ready，包括后续邮箱/电话修改。归档目标保持归档；有效邮箱且无待审线索时才ready。裁决使root从非ready变ready时追加一次pipeline.resume Outbox事件（仅candidate_id引用）；T17消费者与实际画像恢复仍未完成，不能把事件受理当作画像成功。

不同人裁决保留双方独立身份，canonical_candidate_id为null；同人裁决返回目标根ID及已授权次→主application映射。重复裁决或旧版本请求409，不重复事件。

## 事务边界

DuplicateService持有T15数据库身份短锁直到提交。MergePlanner由服务端case和actor构造，plan/apply签名沿用基线；plan只可在原session/transaction应用。依次按ID锁canonical根、别名、case、application及考次，先完整授权/预检后写入；身份、关系、裁决、恢复事件和审计同事务。未来新建application及考试必须先锁canonical根，并仅自动操作主关系。

无新增表、字段、依赖、模型调用、外部邮件或生产部署。
