# 环境配置说明

先运行 python scripts/init_env.py 创建本项目独立.env。脚本随机生成MySQL、Redis、MinIO、监控令牌和Fernet主密钥，并构造容器内部URL；已有.env会拒绝覆盖。完整配置项、单位、默认值和必填/可选说明见根目录.env_example，.env.example是相同内容的兼容名称。

.env仅由Compose显式加载；应用本身从进程环境读取TALENT_变量。开发库talent_dev与测试库talent_test分离；后者专供破坏性测试，不能替换为个人已有数据库。容器内部用mysql/mysql-test/redis/minio主机名，宿主机直连时使用Compose映射到127.0.0.1的端口。

两个模板都不包含真实API Key、数据库密码、SMTP密码、加密主密钥或演示账号密码。不能把填过真实值的模板提交回Git。模型Key为可选，留空不影响基础账号和题库服务，但不能使用真实AI流程。

模型连接和SMTP连接通过管理员配置服务保存为修订。模型与SMTP秘密在数据库里仅保存Fernet密文；恢复数据库必须同时保留原TALENT_ENCRYPTION_KEY。AI流程初始关闭，能力探测通过也不自动开启。只使用受支持的官方地址与白名单模型，不把第三方代理Key发送到另一个供应商。

当前本地SMTP只允许Mailpit，捕获测试邮件而不对外投递。企业SMTP需要配置主机白名单、真实认证、TLS和HTTPS候选人入口；本次仓库上传不包含企业SMTP接入或生产部署。

配置类别包括：运行环境；基础服务凭据；数据库/Redis连接；MinIO及上传限制；会话命名空间与JSON格式trusted origins；加密主密钥；可选官方模型Key；JSON格式SMTP主机白名单。所有这些配置均在Settings或Compose中有实际读取，未加入无法生效的占位配置。

## T20 语义检索参数

|变量|默认值|用途|
|---|---|---|
|TALENT_MILVUS_URI|http://milvus:19530|本项目Milvus SDK连接地址|
|TALENT_SEMANTIC_TOP_K|200|召回上限1～1000，逐条MySQL复验后再按page_size截取|
|TALENT_SEMANTIC_MIN_RELEVANCE|0.0|余弦阈值-1～1，与岗位匹配分无关|

两个.env模板保持一致，Compose将这些变量传给API/Worker/Scheduler。仅配置地址不会启用付费模型。embedding和match由管理员选用已验证模型、发布匹配schema并明确启用；说明见SEMANTIC_SEARCH_AND_MATCH_CONTRACT.md。

## 一期核心与可选语义启动

默认Compose只启动核心服务；Milvus/etcd使用semantic profile，现有数据/定义保留。启用为python scripts/compose.py --profile semantic up -d milvus。默认preflight dev/test不要求Milvus；若验收该可选能力，在required_services显式列milvus并提供实际协议探针。完整后端回归包含T20，必须先显式启动semantic，不能跳过已有测试冒充通过。
