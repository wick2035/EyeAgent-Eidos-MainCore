# 医问通平台附件接口与部署 Preflight

本文是 MainCore 内医问通医生端 platform 附件权威链路、双数据面职责和部署/回滚边界的统一入口。本文不表示生产 `enforce` 已就绪；生产认证切换仍需真实环境中的流量、网络和回滚演练证据。

## 1. 权威链路

```text
Browser -> Java upload -> MainCore prepare/execute
```

1. Browser 只向 Java upload 上传文件。Java 完成医生身份、附件归属和业务关系校验，并创建附件与对象记录。
2. Java 使用内部 Bearer 调用 `POST /api/platform/chat/turns/prepare`。MainCore 校验 JWT 主体、会话/患者资源归属、请求指纹和 `attachment_ids`，再固化本回合状态。
3. `prepare` 成功后，Java 调用 `POST /api/platform/chat/turns/execute`，携带同一请求快照及仅供服务间使用的附件描述。MainCore 下载、解析附件并执行回合，Java 将 SSE 安全事件转发给 Browser。
4. 状态查询和取消分别使用 `GET /api/platform/chat/turns/{request_id}` 与 `POST /api/platform/chat/turns/{request_id}/abort`；它们不改变上传入口和附件权威数据面。

Browser 不直连 MainCore platform 接口，也不把本地文件、base64 或客户端拼装的附件权限信息直接交给 MainCore。

## 2. 双数据面职责

| 数据面 | 权威职责 | 不负责 |
|--------|----------|--------|
| Java | 附件元数据、对象存储、会话/患者/医生关系、访问审计、保留/删除等生命周期 | 附件解析结果、科研文档分段和 ResearchAgent 上下文 |
| MainCore | 回合 `turn` 状态与幂等、科研文档 `ingestion`、派生 `segment`、ResearchAgent 的瞬态可信上下文组装 | 对象存储生命周期、业务关系真相和面向 Browser 的下载授权 |

Java 是附件、对象、关系、审计和生命周期的权威数据面。MainCore 只消费 Java 已授权的附件快照，并维护执行该回合所需的派生数据；MainCore 的派生记录不得反向覆盖 Java 的附件状态。

## 3. Browser 信息边界

Browser 可以获得业务所需的附件标识、展示元数据、回合状态和经过 Java 转发的安全 SSE 事件。禁止浏览器获得或由 SSE/错误体/日志回显以下服务端信息：

- 内部 download URL；
- 对象存储 storage key；
- `research_document_segment` 的原文 segment；
- Java 调用 MainCore 使用的内部 Bearer。

内部 download URL 只允许 Java 在 `execute` 的服务间请求中按短时、最小权限原则提供；MainCore 必须按 download allowlist 校验后下载，不能把该 URL 持久化为 Browser 可见字段。

## 4. MainCore 数据库边界

上线前必须完成并验证以下表的迁移：

| 表 | 用途 | 边界 |
|----|------|------|
| `chat_turn_request` | 保存请求指纹、附件 ID 快照、回合状态和终态，用于幂等与恢复 | 不保存附件二进制，不替代 Java 的附件关系与生命周期 |
| `research_document_ingestion` | 保存科研附件版本、摘要、处理状态、租约和失败结果 | 是 MainCore 派生处理状态，不是附件业务真相 |
| `research_document_segment` | 保存 ingestion 产生的受控文本片段，供 ResearchAgent 选择上下文 | 原文 segment 仅限 MainCore 内部使用，不返回 Browser |

部署和回滚都不得通过删除这三张表或批量清理现有行来切换功能。对象删除、关系解绑和保留策略仍由 Java 生命周期流程发起。

## 5. 部署 Preflight

### 5.1 运行依赖

- **parser image**：部署节点已预取 `eyeagent/attachment-parser:research-c2b`；MainCore 以非 root 用户运行，Docker daemon 可用，`scripts/run_attachment_parser_sandbox.sh` 可执行，镜像配置用户不是 root。该镜像必须同时通过图片、PDF、TXT和DOCX的无网络沙箱回归。
- **download allowlist**：`PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON` 非空且只包含 Java 内部下载端点的精确 scheme/host/port/IP；生产默认保持 `PLATFORM_ATTACHMENT_ALLOW_HTTP=false`，并验证 MainCore 可达、Browser 不可达。
- **JWT/JWKS**：Java 签名 key、`kid` 和 JWKS 发布一致，MainCore 可从 `INTERNAL_JWT_JWKS_URL` 拉取并刷新公钥；日志、探针和配置中不得出现私钥或 Bearer。
- **双端时钟**：Java 签发端与 MainCore 验签端均启用时钟同步，验证 `iat`/`exp` 和短期 token TTL；`INTERNAL_JWT_CLOCK_SKEW_SECONDS` 只能容忍小幅抖动，不能替代时钟同步。
- **数据库**：三张表、索引和应用账号权限已在目标环境验证；迁移先于任何 Java 灰度流量。
- **可观测性**：能按安全事件、固定 route、回合状态和附件错误码聚合，不记录 download URL、storage key、原文 segment 或内部 Bearer。

科研文档 claim/接管的真实 MySQL 并发门禁必须显式设置
`RUN_MYSQL_INTEGRATION=1`，并指向已加载
`scripts/create_research_document_tables.sql` 的隔离数据库：

```bash
RUN_MYSQL_INTEGRATION=1 \
DB_HOST=<host> DB_PORT=<port> \
DB_USER=<user> DB_PASSWORD=<password> DB_NAME=<database> \
.venv/bin/python -m unittest \
  tests.test_research_document_repository_mysql_integration -v
```

未设置开关时测试保持 skip，避免普通单元测试误连数据库；正式验收必须明确输出
`Ran 2 tests`、`OK`，且不能出现 `skipped`。

生产 `enforce` 仍是独立部署 gate。缺少真实平台/患者流量、JWKS 网络边界、SSE drain 和回滚演练证据时，只能维持已批准的 `off`/`observe` 配置，不得宣称生产 `enforce` 已完成。

### 5.2 上线顺序

1. **MainCore 先行**：先部署兼容版本，完成数据库、parser image、allowlist、JWT/JWKS 和双端时钟 preflight；功能开关保持关闭。
2. **Java 灰度**：再灰度 Java upload、附件关系/审计和 MainCore `prepare`/`execute` 调用，仅对受控医生与会话放量，观察错误率、延迟、解析资源和 SSE 终态。
3. **Web 最后**：Java 灰度稳定后才发布并开启医生端入口；Web 不包含内部服务地址、download URL、storage key 或 Bearer。
4. **滚动期间 SSE drain**：实例下线或版本切换前停止接收新回合，等待在途 SSE 完成或安全取消，再终止实例；不得直接切断仍在解析或流式输出的回合。

### 5.3 回滚边界

1. 先关闭医问通医生端 platform 附件功能开关，停止创建新的附件回合。
2. 对 Java 与 MainCore 执行 SSE drain，等待在途 `execute` 完成或经 `abort` 进入终态。
3. 先撤回 Web 入口和 Java 灰度调用；MainCore 兼容版本保留到所有在途和重试请求结束。若认证模式需要回滚，先将 MainCore `enforce` 降为 `observe`，再调整 Java 签发侧。
4. 不删除对象、关系、审计记录、三张 MainCore 表或已有 ingestion/segment；后续清理由 Java 生命周期与既定数据保留策略处理。
5. parser image、download allowlist 和旧 JWKS key 保留到 drain、重试窗口及 key overlap 结束，确认无旧流量后再清理。

关闭功能开关回滚只停止新流量，不等于清理数据，也不扩大 Browser 权限；任何破坏性数据操作都需要独立变更与审计。
