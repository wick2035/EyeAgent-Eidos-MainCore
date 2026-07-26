# 医问通平台附件接口与部署 Preflight

**最近状态复核：** 2026-07-26

**文档地位：** 本文是医问通附件发布、部署和回滚的唯一现行入口；历史
plan/spec 只保留当时的设计与执行证据。

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
| MainCore | 回合 `turn` 状态与幂等、科研文档 `ingestion`、派生 `segment`/私有 `dataset`、ResearchAgent 的瞬态可信上下文组装 | 对象存储生命周期、业务关系真相和面向 Browser 的下载授权 |

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
| `research_dataset` | 保存结构化科研附件的 ingestion 级汇总 | 只属于 MainCore 派生数据，不对 Browser 开放 |
| `research_dataset_sheet` | 保存逻辑 sheet、表头与结构计数 | 表头按不可信数据处理，不作为指令执行 |
| `research_dataset_row_chunk` | 保存私有 canonical 数据行 chunk | C3-3 受限工具上线前不得进入 prompt、SSE、history 或日志 |

部署和回滚都不得通过删除这六张表或批量清理现有行来切换功能。对象删除、关系解绑和保留策略仍由 Java 生命周期流程发起。

## 5. 部署 Preflight

### 5.1 运行依赖

- **parser image**：开发环境未配置时默认使用 `eyeagent/attachment-parser:research-c3-xlsx`。可通过 `PLATFORM_ATTACHMENT_PARSER_IMAGE` 指定镜像引用；生产必须使用 `repository@sha256:<64位小写十六进制digest>` 的不可变引用，并设置 `PLATFORM_ATTACHMENT_PARSER_REQUIRE_DIGEST=true`。该布尔变量只接受精确小写 `true` 或 `false`，空值、`1`、`yes` 和大小写变体都会失败关闭。部署节点须预取配置的镜像；MainCore 以非 root 用户运行，Docker daemon 可用，`scripts/run_attachment_parser_sandbox.sh` 可执行，镜像配置用户不是 root。该镜像必须同时通过图片、PDF、TXT、DOCX、CSV 和 XLSX 的无网络沙箱回归。CSV descriptor 必须使用 `text/csv`；XLSX descriptor 必须使用精确 MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`；两者均不携带 `page_count`且不超过 10 MiB。XLSX 最多 10 个工作表、全文件 50,000 行和 2,000,000 个非空单元格、每表 100 列；公式只作为字符串读取且不得执行，合并单元格只保留左上角值，日期转换为 ISO 字符串，`visible/hidden/veryHidden` 工作表均必须解析并记录可见性。CSV/XLSX canonical descriptor/chunk 各不超过 16 MiB，canonical artifact 总量不超过 31 MiB，host 仅接受 stored、non-Zip64、条目集精确匹配 manifest 的 bundle。
- **download allowlist**：`PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON` 非空且只包含 Java 内部下载端点的精确 scheme/host/port/IP；生产默认保持 `PLATFORM_ATTACHMENT_ALLOW_HTTP=false`，并验证 MainCore 可达、Browser 不可达。
- **JWT/JWKS**：Java 签名 key、`kid` 和 JWKS 发布一致，MainCore 可从 `INTERNAL_JWT_JWKS_URL` 拉取并刷新公钥；日志、探针和配置中不得出现私钥或 Bearer。
- **双端时钟**：Java 签发端与 MainCore 验签端均启用时钟同步，验证 `iat`/`exp` 和短期 token TTL；`INTERNAL_JWT_CLOCK_SKEW_SECONDS` 只能容忍小幅抖动，不能替代时钟同步。
- **数据库**：MainCore 的六张表不是由一份 DDL 创建。全新隔离数据库必须先执行 `scripts/create_chat_turn_request_table.sql` 与 `scripts/upgrade_chat_turn_request_v2_research.sql`，再执行 `scripts/create_research_document_tables.sql` 与 `scripts/upgrade_research_dataset_c3_2.sql`。随后验证六张表、索引、四级 cascade 和应用账号权限。Java 还必须在自己的目标数据库重放 `database/migration/add_platform_ai_conversation_document.sql`，验证 `(conversation_id, attachment_id)` 唯一键、乐观锁版本和最小 DML 权限。所有 DDL 必须先于 MainCore 新代码部署，更必须先于任何 Java 灰度流量。
- **可观测性**：能按安全事件、固定 route、回合状态和附件错误码聚合，不记录 download URL、storage key、原文 segment 或内部 Bearer。

生产 parser 镜像配置示例：

```bash
PLATFORM_ATTACHMENT_PARSER_IMAGE='registry.example.com/eyeagent/attachment-parser@sha256:<64位小写十六进制digest>'
PLATFORM_ATTACHMENT_PARSER_REQUIRE_DIGEST=true
```

`PLATFORM_ATTACHMENT_PARSER_REQUIRE_DIGEST` 未设置时默认为 `false`，仅用于保持本地开发 tag 工作流；生产不得依赖该默认值。digest 门禁只校验不可变引用格式，镜像预取、签名或 provenance 验证仍应由发布流水线完成。

仓库提供只读生产配置 Preflight：

```bash
.venv/bin/python scripts/platform_attachment_preflight.py config --json
```

该命令同时验证：

- parser 使用不可变 `repository@sha256:...`，digest 门禁已开启；
- sandbox runner、Docker daemon、非 root image user 可用；
- 本机 `RepoDigests` 包含配置的精确 registry digest；
- download allowlist 全部使用 HTTPS 且未放开 HTTP；
- MainCore 使用 `INTERNAL_AUTH_MODE=enforce`，JWKS 使用 HTTPS。

命令只输出状态和安全摘要，不输出密码、Bearer、私钥或预签名 query。任一检查失败
均以非零状态退出。本地 mutable tag、空 `RepoDigests` 或 `/health` 返回 200 都不能
代替该证据；镜像签名、SBOM 和 provenance 仍必须由 registry/发布流水线提供。

科研文档 claim/接管的真实 MySQL 并发门禁必须显式设置
`RUN_MYSQL_INTEGRATION=1`，并指向已加载
上述四份 MainCore DDL 的隔离数据库。推荐统一执行只读 schema/授权检查与真实
测试：

```bash
RUN_MYSQL_INTEGRATION=1 \
PLATFORM_ATTACHMENT_PREFLIGHT_DISPOSABLE_DB=true \
DB_HOST=<host> DB_PORT=<port> \
DB_USER=<user> DB_PASSWORD=<password> DB_NAME=<database> \
.venv/bin/python scripts/platform_attachment_preflight.py mysql --json
```

`PLATFORM_ATTACHMENT_PREFLIGHT_DISPOSABLE_DB` 只接受精确小写 `true`，用于要求
操作者明确确认这是允许写入和清理测试数据的隔离库。命令不建表、不改授权，也不
输出密码或完整 grants。它会验证六表、InnoDB、关键列的类型/null/default、索引
唯一性与列顺序、外键两端和 `ON DELETE CASCADE`、`utf8mb4_bin`，并逐条解析
`SHOW GRANTS`：只接受当前目标库或上述六表范围内的
`SELECT/INSERT/UPDATE/DELETE`（另允许 `USAGE ON *.*`）。额外权限、其他库 scope、
role、`GRANT OPTION` 或无法识别的 grant 都会失败关闭。随后运行 6 项真实 MySQL
测试；任一 skip、测试数量变化、失败或错误也会失败关闭。6 项覆盖并发
claim/接管、CSV/XLSX 同事务发布、XLSX final CAS miss 整事务回滚、已有
materialization 的原子替换与 cascade purge。

MySQL 5.7 的 `COLUMN_TYPE` 仍可能返回 `int(10) unsigned` 等整数 display
width。Preflight 比较前只移除 `tinyint`/`smallint`/`mediumint`/`int`/`bigint`
的 display width，仍严格保留 `unsigned`、`zerofill`、null/default 等语义；
`varchar(16)`、`datetime(6)` 和 `decimal(10,2)` 等非整数参数不会被放宽。

R1 共享环境浏览器门禁由 Web 仓库提供：

```bash
pnpm --filter web e2e:r1:install

YIWENTONG_E2E_BASE_URL=<shared-web-url> \
YIWENTONG_E2E_PHONE=<disposable-doctor-phone> \
YIWENTONG_E2E_PASSWORD=<disposable-doctor-password> \
pnpm --filter web e2e:r1
```

Web URL 必须是无 credential/path/query/fragment 的 HTTPS origin。本机
loopback HTTP 只允许额外显式设置
`YIWENTONG_E2E_ALLOW_LOOPBACK_HTTP=true`，共享 HTTP 地址一律拒绝。该用例使用
运行时生成的无患者数据 TXT 和随机哨兵值，验证登录、科研上传、回答确实来自附件、
固定、刷新回读和取消固定。测试默认关闭 screenshot、video 和 trace，且缺少任一
环境变量时直接失败，不能用 skip 或现有浏览器登录态替代。`finally` 会尝试取消
固定，并只向上传请求实际使用的同一 Java API origin 删除本次测试会话与附件；
若附件尚未绑定，会进入对象删除与 research purge 补偿流程，发布流水线应等待其
终态；若附件已经形成回合，则删除会话并按医疗数据保留规则隐藏关联，不得为通过
测试而物理删除已绑定附件。两种路径必须分别记录清理结果，最后销毁一次性账号。

生产 `enforce` 仍是独立部署 gate。缺少真实平台/患者流量、JWKS 网络边界、目标
环境跨实例 SSE drain 和回滚演练证据时，只能维持已批准的 `off`/`observe` 配置，
不得宣称生产 `enforce` 已完成。

### 5.1.1 门禁状态矩阵

| 门禁 | 仓库内命令/证据 | 外部依赖 | 2026-07-26 状态 |
|------|-----------------|----------|------------------|
| parser 配置与节点预取 | `platform_attachment_preflight.py config --json` | registry digest、签名、SBOM/provenance、目标节点 | 当前复核 5 项通过、5 项失败；本地镜像非 root 且生成 112-package SPDX SBOM，但仍是 mutable tag、无 `RepoDigests` 和 registry attestation，未通过 |
| MainCore 六表与真实并发 | `platform_attachment_preflight.py mysql --json`，必须 11 个检查通过、6 项测试且零 skip | 隔离目标 MySQL、DDL 账号、最小 DML 账号 | 一次性本地 MySQL 8 已通过；MySQL 5.7 display width 兼容已修复，当前共享 MySQL 六项只读结构检查通过，但不是 disposable/minimal-DML，目标写入门禁未通过 |
| Java C4-2A membership | `PlatformConversationDocumentMigrationTest` 与迁移连续重放 | Java 目标 MySQL、跨实例恢复 | 本地开发库已通过；目标环境未通过 |
| 共享 MinIO 下载边界 | Java presign → MainCore allowlist download → Browser 不可达 | 私有 bucket、TLS、DNS/IP、最小权限 | 当前共享 MinIO 业务链路通过，但仍使用 HTTP，生产 TLS 边界未通过 |
| JWT/JWKS 生产切换 | key overlap、真实签发/验签、日志与时钟证据 | HTTPS/mTLS/mesh、K1/K2、NTP | loopback JWKS 下 `enforce` 已验证；生产 HTTPS/mTLS/mesh 未通过 |
| R1 真实浏览器 | `pnpm --filter web e2e:r1` | 共享 Web/Java/MainCore、一次性医生账号 | 当前共享 MySQL/MinIO 加 loopback JWKS 已通过；生产 HTTPS 目标环境未执行 |
| SSE drain、灰度、回滚 | Java/MainCore drain 单测；停止新流量、等待/abort 在途回合、指标与回滚记录 | LB/编排器、监控、受控医生 cohort | 隔离双实例/LB 中 Java 活跃流自然排空、J2/M2 接管及 J1/M1 回滚均通过；真实编排器与目标 LB 未执行 |

### 5.2 上线顺序

1. **DDL 先行、MainCore 随后**：先迁移并验证六张表，再部署兼容版本，完成 parser image、allowlist、JWT/JWKS 和双端时钟 preflight；功能开关保持关闭。
2. **Java 灰度**：再灰度 Java upload、附件关系/审计和 MainCore `prepare`/`execute` 调用，仅对受控医生与会话放量，观察错误率、延迟、解析资源和 SSE 终态。
3. **Web 最后**：Java 灰度稳定后才发布并开启医生端入口；Web 不包含内部服务地址、download URL、storage key 或 Bearer。
4. **滚动期间 SSE drain**：实例下线或版本切换前停止接收新回合，等待在途 SSE 完成或安全取消，再终止实例；不得直接切断仍在解析或流式输出的回合。

### 5.2.1 R1 排空合同

- Java readiness 使用 `/actuator/health/readiness`。收到 Spring shutdown 后先发布
  `REFUSING_TRAFFIC`，新 platform 附件流返回 `SERVICE_DRAINING`，自然等待默认
  60 秒；仍未完成的回合通过既有恢复服务发出 abort，再等待默认 30 秒。
- MainCore readiness 使用 `/health/ready`。进入 drain 后返回 `503`，拒绝新的
  `prepare`/`execute`，但 status/abort 保持开放；自然等待默认 60 秒，随后向仍在
  执行的本地回合发出停止信号，再等待默认 30 秒，最后才停止 watchdog 和数据库
  连接池。
- Java 配置为
  `AI_DIAGNOSIS_DRAIN_NATURAL_TIMEOUT_SECONDS` /
  `AI_DIAGNOSIS_DRAIN_ABORT_TIMEOUT_SECONDS`；MainCore 配置为
  `PLATFORM_TURN_DRAIN_NATURAL_TIMEOUT_SECONDS` /
  `PLATFORM_TURN_DRAIN_ABORT_TIMEOUT_SECONDS`。Uvicorn reload 默认关闭，
  graceful shutdown 默认 100 秒。
- MainCore 发布进程必须用 `python main.py` 启动，由 `PlatformDrainServer` 在关闭
  listener 前切换 readiness 并执行 drain。直接
  `uvicorn main:app --reload ...` 只用于本地开发，不能作为 R1 发布入口。
- 编排顺序必须先从 LB 摘除 Java 并完成 Java drain，再允许 MainCore 进入
  shutdown。两个服务不能同时被强杀；Java termination grace 必须大于自然等待与
  abort 总预算之和，MainCore 还必须加上
  `UVICORN_GRACEFUL_SHUTDOWN_SECONDS`，并为进程关闭预留余量。

2026-07-26 在不影响原有服务的隔离端口完成双 Java、双 MainCore 与临时 Nginx LB
演练。基线 R1 通过；在科研 SSE 活跃时退出 Java J1，日志记录
`platform_attachment_drain_started active_at_start=1` 和
`platform_attachment_drain_complete active_at_start=1 forced_abort=0`，在途 R1
仍通过。Java 排空后才切换并退出 MainCore M1，其日志记录
`active=0, signalled=0, idle=True`；J2/M2 接管 R1 通过。恢复 J1/M1 并重新加入
双实例池后，R1 再次通过，LB 日志确认四个 upstream 均承接请求。

该演练证明进程级 drain 合同和顺序可工作，但不是目标编排器验收。MainCore
`ChatTurnExecutionRegistry` 是进程内 registry，共享数据库终态才是跨实例事实。
若 abort 请求命中非 owner 实例，它可以更新共享终态，却不能立即设置 owner
进程内的 cancel event；目标 LB/控制面必须提供 owner 路由、实例定向 abort 或
等价机制，并验证 owner 在下一检查点停止，不能只以非 owner 的 HTTP 200 判定
跨实例取消完成。

### 5.3 回滚边界

1. 先关闭医问通医生端 platform 附件功能开关，停止创建新的附件回合。
2. 对 Java 与 MainCore 执行 SSE drain，等待在途 `execute` 完成或经 `abort` 进入终态。
3. 先撤回 Web 入口和 Java 灰度调用；MainCore 兼容版本保留到所有在途和重试请求结束。若认证模式需要回滚，先将 MainCore `enforce` 降为 `observe`，再调整 Java 签发侧。
4. 不删除对象、关系、审计记录、六张 MainCore 表或已有 ingestion/segment/dataset；后续清理由 Java 生命周期与既定数据保留策略处理。
5. parser image、download allowlist 和旧 JWKS key 保留到 drain、重试窗口及 key overlap 结束，确认无旧流量后再清理。

关闭功能开关回滚只停止新流量，不等于清理数据，也不扩大 Browser 权限；任何破坏性数据操作都需要独立变更与审计。
