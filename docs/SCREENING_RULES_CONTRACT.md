# T18 岗位硬条件三态规则引擎

基线FR-05、docs/specs/09 T18。仅内部纯函数能力，无新增公开API、持久化、模型调用或邀考副作用，T19再接通应聘评估与人工覆盖。

## 输入输出

ScreeningEngine(as_of=冻结日期,dictionary_revision=core-major-v1,relevant_employment_indices=已确认索引元组或None).evaluate(ResumeFacts,conditions)。ScreeningCondition直接复用T12 Condition；白名单education/major/relevant_years/skill/certificate，拒绝年龄、性别、婚育、健康、忠诚度等字段与不支持操作符。条件键唯一、最多50条。

输出ScreeningReport：result、details、as_of、dictionary_revision、normalization_revision。每项condition_key/required/expected/actual/result/evidence/reason_code保留。证据确定性先于met/unmet判断，待核实引用不能变成硬拒；学历只用学位/日期，专业按符合学历的同段记录，年限只用已选经历起止日期，不让无关职责/其他专业污染结论。任一required unmet→fail；否则required unknown→unknown；其余pass。preferred缺失不硬拒；空required集合逻辑pass，不代表可以自动邀请。

## 学历与专业

学历按最高已取得层次。明确毕业日期完整落在评估日期之前，或原文字段明确已取得/毕业才确认；原文仍含在读/肄业/结业等状态时，不能因提取出本科字样就认定已取得；未来、在读不算取得，缺日期或混合描述不猜测。高中与中专在gte比较同层次，eq仍区分。对未认识的学历或可能影响最高层次的未知记录保留unknown。

专业只用代码版本化精确别名字典。当前是业务示例词典，不宣称完整国家专业目录；未知/CS/计算机相关等模糊值待核实，置信度仅表示是否精确命中字典，不是岗位能力分。不将机械工程与机械设计制造及其自动化强行视为同专业。存在required学历条件时，专业必须来自满足这些学历条件的同一段已取得教育记录，不能借低学历的相关专业拼出高学历达标。

## 年限

日期保留年/月/日的精度区间，明确至今使用as_of；缺失、颠倒或未来日期不伪造为0。分别对保守下界和上界做区间并集，以完整月数/12表示，重叠不重复计算。上下界的Decimal取整分别向下/向上，避免四舍五入误过线。gte/lte/between只有整个范围能证明结论时met/unmet，跨门槛unknown。

ExperienceCalculator.relevant_years仅在上下界一致时返回Decimal，其他情况None；Engine可用bounds作安全区间判断。就业记录本身没有岗位相关性标记，未确认相关经历索引时，不能用总工龄代替相关工龄，默认unknown。T19需冻结评估日期、词典修订与已确认相关性选择；未确认就留HR核实，不交给模型硬判。

## 技能、证书和证据

只做NFKC/大小写/空白规范化后全词匹配，C、C++、C#不同；不把Python/Java复合字符串随意拆开。没有列出的技能/证书不能推断为实际不会，记unknown；也不自动判断已失效证书。命中的事实引文含否定/未定状态则待核实，另一项技能的否定不污染独立、明确的正向来源。复杂否定无法在纯规则中可靠解读时交人工。

所有输入重新执行ResumeFacts证据一致性校验，输出不修改原事实。T19还须按持久化应聘归属校验简历来源并保存冻结版本；纯函数不承担部门授权。只读取相关条件事实的证据，不使用出生日期或其他敏感属性。

## 版本与限制

normalization_revision=screening-core-v1；词典不可运行时原地修改，新增映射须新修订并保留旧版。没有规则评分或整体能力分。相关性未确认、日期精度不足、未毕业/模糊专业等会增加人工核实，但不以假精确自动通过或硬拒。无表/字段/依赖/密钥变更。
