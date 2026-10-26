# d-obs Agent 插件

将平台现有 AI 助手与统一业务目录提供给其他 Agent。无需另建模型服务、复制数据库或开放数据库连接。业务查询强制只读，所有请求沿用服务端身份、租户隔离和原 API 校验。对话调用会保存助手任务。

## 安装与连接

需要 Node.js >=22，以及可访问的 d-obs 服务。支持插件目录的宿主可加载本目录；`.codex-plugin/plugin.json` 提供插件元数据。`.mcp.json` 使用 `${CLAUDE_PLUGIN_ROOT}`，其他宿主应将该变量替换为插件绝对路径。宿主安装流程和变量支持以其实际能力为准。

任何支持 stdio MCP 的 Agent 都可以手动注册，无需插件安装器：

```json
{
  "mcpServers": {
    "d-obs-agent": {
      "command": "node",
      "args": ["/插件绝对路径/d-obs-agent/mcp/bridge.mjs"]
    }
  }
}
```

默认读取 `~/.config/d-obs-agent/connection.json`；可由 MCP 配置的 `env.DOBS_AGENT_CONFIG` 指向另一个绝对路径。私有配置和凭据均放在插件和仓库之外。

```json
{
  "url": "https://你的平台地址/dobs/api/ops/mcp",
  "auth": {
    "type": "admin",
    "credentialFile": "/私有目录/dobs-token"
  },
  "timeoutMs": 240000
}
```

`url` 是完整 MCP 地址，保留部署的 `/dobs` 前缀；仅接受 HTTPS 或 loopback HTTP，拒绝重定向。凭据文件为纯文本 token/session，末尾可带换行。不要粘贴凭据到对话或包中。POSIX 上两份文件都需当前用户所有、权限 `0600`；Windows 需自行配置 owner-only ACL，连接器不验证 ACL。

`auth.type` 支持 `admin`（x-admin-token）、`sso`（x-rdk-sso-session）和 `tenant`（x-tenant-token）。SSO 租户组员还需配置 `tenant` 为真实租户 ID（发送 x-rdk-obs-tenant）；服务端继续校验成员资格。租户配置不能提升权限。

## RDK Studio 接入

推荐在 Studio 的 MCP 设置中导入配置。解压本包后，运行：

```bash
node mcp/studio-config.mjs > studio-mcp.json
```

此命令只输出配置，不修改 Studio 已有设置。导入时使用生成的 `studio-mcp.json`，不要直接导入带 `${CLAUDE_PLUGIN_ROOT}` 的通用 `.mcp.json`。生成器使用当前 Node 与 bridge 的实际绝对路径，并设置 270 秒宿主超时及五个查询工具的只读权限；其他工具默认拒绝。移动插件目录后重新生成配置。

如私有连接文件不在默认位置，可运行 `node mcp/studio-config.mjs /私有目录/connection.json`。配置生成器不读取或包含凭据。按前文准备 connection.json 与凭据后，在 Studio 中测试连接并启用该 MCP，再在新对话中说“先检查 d-obs 连接，再查最近一小时异常”。真实连接结果以 `dobs_status` 为准。

本地 Studio/Electron 的 Node 与文件路径位于运行 Studio 服务的电脑；远程 Web Studio 则必须在其服务端安装连接器并配置该账号的连接，浏览器本机路径不可作为远端路径。不要将共享管理员凭据配置为所有云端账号的通用身份。

已对本机 Studio 源码的 JSON 导入解析器与其安装的 MCP SDK 验证：配置导入、stdio 握手、五个工具发现和带只读/认证头的实际 HTTP 调用。HTTP 数据使用明确的本地 fixture；这不代表已安装进正在运行的 Studio，也不代表生产数据查询通过。

## 对话和工具

可以说：“查一下最近一小时平台主要异常”“这个用户最近发生了什么”“模型池现在健康吗，fallback 怎么配置的？”“列出离线设备及最近日志”。

| 工具 | 用途 |
| --- | --- |
| dobs_status | 验证连接、只读契约，返回模型状态与可见分组 |
| dobs_ask | 平台 AI 对话查询，返回 taskId、答复和实际操作回执 |
| dobs_capabilities | 按当前身份发现只读操作与参数 |
| dobs_query | 精确查询目录里的 operationId，支持 params/query/body |
| dobs_tasks | 列出本身份任务，或按 taskId 恢复对话 |

`dobs_ask` 首次省略 taskId。服务端支持任务持久化时，相关追问传返回的 taskId，另起话题重新省略；旧服务返回 `conversationMode: client-history`，使用 `history` 传最近至多十二条 user/assistant 消息，助手消息使用平台返回的 `historyContent` 安全摘要。旧服务不能按任务 ID 恢复对话，`dobs_status` 如实显示该能力。模型配置复用平台的 `RDK_COPILOT_MODEL_ENABLED` 和平台助手网关配置；没有模型时用 capabilities/query 直接查数据。

范围包括当前服务已注册、当前身份可见的指标、日志、链路、会话、告警、事故、SLO、设备、用户活动、租户、看板、数据库查询/导出元数据、模型池、学习及插件模块等。实际目录为准，未接入的数据源、无权数据和已删除数据不能查询。附件下载链接仍需原身份认证，当前桥不自动下载附件。

连接器对查询和对话先验证服务端 `readOnlyExecutionSupported`，查询必须匹配实时只读目录；每次请求都携带 `x-rdk-ops-read-only: 1`。只读 POST（例如看板查询）保留。旧服务缺少该契约时拒绝执行。自然语言回复和结构化结果保留来源状态与截断标记，不承诺完整数据库转储。

输入上限 128 KiB，远端响应上限 8 MiB；超时和失败不自动重试。stdio 串行执行，避免同一助手身份并发冲突。`tools/list` 仅列出本地适配工具，连接就绪以 `dobs_status` 为准。未配置、401/403、模型不可用、限流等均返回真实失败；目录可发现性不等于授权执行成功。

## 本地验证与打包

在仓库根目录执行：

```bash
node --test plugins/d-obs-agent/mcp/bridge.test.mjs
node --import tsx --test tools/dobs-agent.integration.test.mts
node --import tsx tools/package-dobs-agent.mts
```

产物位于 `output/d-obs-agent-0.1.0.zip`，包内附 SHA-256 文件清单。仅包含本插件白名单文件和许可证，不包含连接配置或凭据。本地协议测试不代表生产连接或每个 Agent 宿主的安装验收。
