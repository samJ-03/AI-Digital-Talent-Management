# Context
以docs/specs/04、05、09的T16为约束，复用T15身份写入短锁、CanonicalResolver和HR权限事务。

# Decisions
锁根按ID排序，随后application和attempt按ID锁定；检查完全部冲突才写入。MergePlanner绑定服务端case上下文，cmd不允许注入来源档案。目标当前简历/画像与联系人保持；别名下的未决外部重复继续阻断ready。部门重叠关系的读取及写入须当前岗位权限，无权限不返回冲突ID。

# Risks
命名锁串行短身份写入；将来考试/招聘写入必须遵循canonical根锁。活动状态含未完成评分，次关系有未关闭考试即冲突，主关系保留可继续的唯一考试。

# Migration Plan
无表变更。T17消费pipeline.resume并复验状态，不在本轮伪称已恢复实际画像。