# Duck Lab MCP 客户端示例

配套指南：[`docs/duck-lab-mcp-guide.md`](../../docs/duck-lab-mcp-guide.md)。

| 文件 | 用途 |
| --- | --- |
| `claude-desktop.mcp.json` | Claude Desktop / 通用 stdio 客户端：本地 tarball 安装 + 远程 mcp-remote 桥接两种写法 |
| `codex.config.toml` | Codex CLI 的 `[mcp_servers.*]` 片段 |
| `cursor.mcp.json` | Cursor 的全局 `mcp.json` 片段 |
| `qoder-plugin/` | Qoder 原生插件包源码（plugin.json + skills + .mcp.json），zip 已托管在服务器 |
| `http-session-demo.sh` | 可运行脚本：对公网端点走 initialize → tools/list → 平台健康（只读演示） |

## 一键安装（Qoder / RDK Studio / Cursor / Claude / Codex 自动注册）

```bash
DUCK_LAB_MCP_TOKEN='<token>' bash -c "$(curl -fsSL https://47.110.142.255/ducklab-mcp/install.sh)"
```

## 最小可用配置（三选一）

**远程 HTTP（零安装）**——任何支持 streamable HTTP 的客户端，两种写法等价：

```
纯 URL（零 Header）：https://47.110.142.255/ducklab-mcp/mcp/<token>
Header 形态：        URL https://47.110.142.255/ducklab-mcp/mcp
                     Header Authorization: Bearer <token>
```

**stdio-only 客户端桥接远程**：

```json
{ "command": "npx", "args": ["-y", "mcp-remote", "https://47.110.142.255/ducklab-mcp/mcp",
  "--header", "Authorization: Bearer <token>"] }
```

**本地 tarball 安装后 stdio 直连同机平台**：

```bash
npm install -g duck-lab-mcp-0.2.0.tgz
```

```json
{ "command": "duck-lab-mcp", "env": { "RDK_SIM2REAL_MCP_BASE_URL": "http://127.0.0.1:18102" } }
```

token 与平台地址向平台维护者获取；写操作全部经过平台侧 RBAC/审批/安全开关，
插件层不持有任何绕过通道。
