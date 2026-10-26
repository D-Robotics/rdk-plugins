# Duck Lab MCP 插件指南

> 把 RDK 机器人学习平台装进任意 MCP 客户端：RDK Studio、Codex、Claude Desktop、
> Cursor、Qoder 等都能通过 60 个 `rdk_*` 工具以自然语言对话驱动
> 数据 → 训练 → 评测 → 制品 → 部署 → 板端 全链路。
> 客户端配置样例与可运行脚本见 [`examples/duck-lab-mcp/`](../examples/duck-lab-mcp/)。

## 两种接入形态

| 形态 | 适合谁 | 地址/命令 | 鉴权 |
| --- | --- | --- | --- |
| **HTTP（已部署公网）** | 远程 agent、云端/其他机器上的客户端、任何支持 streamable HTTP 的 MCP 宿主 | `https://47.110.142.255/ducklab-mcp/mcp` | `Authorization: Bearer <token>`（服务端 `/etc/rdk-duck-lab-mcp.env`） |
| **stdio（本地安装）** | 桌面客户端、与平台同机的 agent | `duck-lab-mcp` 命令 | 平台侧会话（匿名/cookie/账号，见下文环境变量） |

两者能力完全一致（同一份代码、同一组 60 工具）；HTTP 形态多一层 Bearer Token。

## 安装方式

### A. 一键安装（推荐）

```bash
DUCK_LAB_MCP_TOKEN='<token>' bash -c "$(curl -fsSL https://47.110.142.255/ducklab-mcp/install.sh)"
```

脚本自动：下载 tarball → 全局安装 → 注册检测到的客户端（Qoder / RDK Studio /
Cursor / Claude Desktop / Codex；每个文件先留 `.duck-lab-backup.<ts>` 备份）。
默认远程 HTTP 接入；本机有平台时加参数 `local` 走 stdio 直连。
WorkBuddy 暂无自动注册（其数据目录无 MCP 配置面），在其设置界面的 MCP 入口
填下方 HTTP 地址与 Header 即可。

### A+. Qoder 插件形式（扩展管理可见、可开关、带使用技能）

`examples/duck-lab-mcp/qoder-plugin/` 是 Qoder 原生插件包（plugin.json + skills +
.mcp.json 连接器），已托管：`https://47.110.142.255/ducklab-mcp/duck-lab-qoder-plugin.zip`。
安装：Qoder「扩展管理 → + 」导入该 zip（或 `qoder-settings.install_extension`
本地归档）。安装后出现在「扩展管理 → 插件」列表，自带 `duck-lab` 使用技能与
HTTP 连接器；注意 zip 内嵌 token，仅分发给可信使用者。

**市场级自动更新（已上线）**：Qoder 市场插件之所以没有更新按钮，是因为市场源
是一份固定 URL 的 `marketplace.json` 清单（`autoUpdate: true`），版本由源管理。
我们的服务器已托管同款清单：`https://47.110.142.255/ducklab-mcp/marketplace.json`
（列出 duck-lab 0.2.0，含 zip 地址与 SHA-256）。把该 URL 添加为 Qoder 市场源
（或由管理员写进 `~/.qoder/plugins/known_marketplaces.json`，本机已注册）后，
即获得市场级自动更新。升级流程 = 服务器替换 zip + 更新清单 version/sha256，
客户端自动拉取。

**RDK Studio**：安装与自动更新走同一个幂等脚本（与 rdk-camera-workshop
同构的目录形态：plugin.json + skills + .mcp.json + 内嵌 `mcp/bundle.mjs`，零依赖）：

```bash
bash -c "$(curl -fsSL https://47.110.142.255/ducklab-mcp/install-rdkstudio.sh)"
```

脚本读 `rdkstudio-version.json` 版本清单：未安装 → 安装并登记
`plugins-registry.json`（duck-lab@user）；有新版 → 备份旧目录后替换；
版本相同且登记完整 → 什么都不动。`--check` 只查不动。装完重启 Studio 生效；
Studio 的插件导入入口（扩展页 → 导入 `duck-lab-rdkstudio-plugin.zip`）是等价
的图形化路径。匿名身份默认：状态/文档/检索类工具即用，工作台读写需按上文
配置平台凭据。

### B. HTTP 远程接入（零安装，手动配置）

任何能填 URL 的 MCP 客户端直接连：

```
URL:   https://47.110.142.255/ducklab-mcp/mcp
Header: Authorization: Bearer <token>
```

只支持 `POST`（无状态 streamable HTTP）；批量请求返回数组，通知返回 202，
无服务端主动推送流。token 在服务器 `/etc/rdk-duck-lab-mcp.env` 的
`RDK_SIM2REAL_MCP_HTTP_TOKEN`。

**stdio-only 客户端桥接**（Claude Desktop、Codex 等只支持 stdio 的宿主）：

```json
{
  "mcpServers": {
    "duck-lab": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://47.110.142.255/ducklab-mcp/mcp",
               "--header", "Authorization: Bearer ${TOKEN}"]
    }
  }
}
```

### C. tarball 本地安装（stdio）

从 `https://47.110.142.255/ducklab-mcp/duck-lab-mcp.tgz` 下载（或向平台维护者要包），然后：

```bash
npm install -g ./duck-lab-mcp-0.2.0.tgz   # 全局安装，得到 duck-lab-mcp 命令
duck-lab-mcp                              # 默认 stdio；Ctrl-C 退出
```

客户端配置（Claude Desktop / Cursor / 通用）：

```json
{
  "mcpServers": {
    "duck-lab": {
      "command": "duck-lab-mcp",
      "env": { "RDK_SIM2REAL_MCP_BASE_URL": "http://127.0.0.1:18102" }
    }
  }
}
```

Codex（`~/.codex/config.toml`）：

```toml
[mcp_servers.duck-lab]
command = "duck-lab-mcp"
env = { "RDK_SIM2REAL_MCP_BASE_URL" = "http://127.0.0.1:18102" }
```

### D. 仓库开发模式

```bash
git clone <本仓库> && cd rdk-robot-learning-platform-public
npm ci
node --import tsx/esm services/duck-lab-mcp/server.ts          # stdio
RDK_SIM2REAL_MCP_HTTP_PORT=18103 node --import tsx/esm services/duck-lab-mcp/server.ts  # HTTP
```

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `RDK_SIM2REAL_MCP_BASE_URL` | `http://127.0.0.1:18102` | 平台地址（本机 standalone 即默认值） |
| `RDK_SIM2REAL_MCP_API_PREFIX` | `/api/v1/duck` | 平台版本化 API 前缀 |
| `RDK_SIM2REAL_MCP_COOKIE` | — | 静态会话 cookie（studio-cookie 嫁接部署用） |
| `RDK_SIM2REAL_MCP_USERNAME` / `RDK_SIM2REAL_MCP_PASSWORD` | — | 账号登录（自动换会话 cookie，401 自动重登一次） |
| `RDK_SIM2REAL_MCP_TIMEOUT_MS` | `120000` | 单请求超时下限 1s |
| `RDK_SIM2REAL_MCP_HTTP_PORT` | —（stdio） | 设置后切换为 HTTP 传输 |
| `RDK_SIM2REAL_MCP_HTTP_HOST` | `127.0.0.1` | HTTP 监听地址；对外服务改 `0.0.0.0` 并**必须**配 token |
| `RDK_SIM2REAL_MCP_HTTP_TOKEN` | —（可选） | 设置后所有 /mcp 请求必须带 `Authorization: Bearer <token>` |

三个都不配 = standalone 匿名模式（本机单用户部署）；多用户/Studio 嫁接部署用
COOKIE 或 USERNAME/PASSWORD。

## 工具目录（60 个）

| 领域 | 工具 |
| --- | --- |
| 工作台 | `rdk_workspace_overview` `rdk_workspace_summary` `rdk_golden_path` `rdk_platform_status` |
| 项目/数据 | `rdk_projects_list` `rdk_project_create` `rdk_datasets_list` `rdk_dataset_register` `rdk_trajectory_check` `rdk_trajectory_import` |
| 模型 | `rdk_models_list` `rdk_model_validate` `rdk_model_register` |
| 训练 | `rdk_training_submit` `rdk_training_status`（含结构化进度点列） `rdk_training_wait`（有界等待到终态，超时如实返回当前进度） `rdk_run_logs` `rdk_runs_list` `rdk_runs_replay` `rdk_retraining_advice` |
| 评测 | `rdk_evaluations_list` `rdk_evaluation_summarize` `rdk_feedback_summary` |
| 制品/部署 | `rdk_artifacts_list` `rdk_artifact_promote` `rdk_deployment_preflight` `rdk_deployment_status` `rdk_deployment_history` `rdk_deployment_version_switch` `rdk_deployment_cancel` |
| 板端 | `rdk_device_*`（3） `rdk_board_health` `rdk_board_onboarding_preflight` `rdk_board_station_*`（2） `rdk_board_policy_*`（6） `rdk_board_arm_*`（4） `rdk_board_stop` `rdk_board_sessions` |
| 演示视频 | `rdk_demo_video_upload` `rdk_replay_video` |
| 算力 | `rdk_compute_resources_list` `rdk_compute_resource_test` |
| 知识 | `rdk_docs_search` `rdk_docs_manuals` `rdk_docs_toc` `rdk_docs_page` `rdk_web_search` |
| 血缘 | `rdk_lineage_get` `rdk_telemetry_list` `rdk_simulator_open` |

标注约定：只读工具带「只读操作」；`rdk_artifact_promote` / `rdk_deployment_cancel` /
`rdk_device_disconnect` / `rdk_board_policy_reset` / `rdk_board_stop` 五个是破坏性操作
（`destructiveHint`）。**业务裁决全部在平台侧**：RBAC、审批、运动安全开关、质量门
都由平台执行，插件只如实转述拒绝原因（含平台错误码，如
`[DSH_CAPABILITY_REJECTED] … [SIM2REAL_RUN_NOT_FOUND]`）。

## 典型对话流

- **示教→训练→出视频**：`rdk_simulator_open`（人录制轨迹）→ `rdk_trajectory_check` →
  `rdk_trajectory_import` → `rdk_training_submit`（datasetIds）→
  `rdk_training_status`（轮询进度点列）→ `rdk_evaluation_summarize` → 引擎渲染 MP4 →
  `rdk_demo_video_upload` → 工作台运行详情可直接播放
- **发布前检查**：`rdk_golden_path` 看主链路 → `rdk_deployment_preflight` →
  `rdk_artifact_promote` → `rdk_deployment_status`
- **重训飞轮**：`rdk_retraining_advice` 给出建议信号 → 操作员显式确认后才重训

## 排障

| 症状 | 原因与处理 |
| --- | --- |
| HTTP 401 | token 缺失/不匹配；核对 `Authorization: Bearer` 与服务端 env |
| stdio 起来但工具全报连接失败 | `RDK_SIM2REAL_MCP_BASE_URL` 不对，或平台未启动（`curl http://127.0.0.1:18102/healthz`） |
| 平台返回 401（认证类） | 多用户部署需配 `RDK_SIM2REAL_MCP_COOKIE` 或 USERNAME/PASSWORD |
| 本机 CLI 全部 403/CONNECT denied | 公司 Squid 代理白名单问题，按 `squid-proxy-403-fix` 排障 |
| 工具结果被截断 | 响应超过 240 KiB 时插件做无损投影并带 `projection.truncated` 标记；用对应 `*_list` 工具拿精确列表 |

## 服务器端运维（47.110.142.255）

- systemd：`rdk-duck-lab-mcp.service`（env 在 `/etc/rdk-duck-lab-mcp.env`，token 同文件）
- nginx：`/etc/nginx/ducklab-mcp-location.inc`（挂进 rdkstudio-ip-ssl / rdkstudio-ssl 两个 vhost；含 tarball 下载端点）
- 升级：重打 tarball → `scp` 到 `/opt/duck-lab-mcp-plugin.tgz` → `npm install -g` 重装 →
  `systemctl restart rdk-duck-lab-mcp`
- **平台凭据（已配置，服务账号 `svc-duck-lab-mcp`，operator 角色）**：多用户部署下
  工作台读写类工具需要服务端会话。生产做法是在服务器上用平台自己的签名模块铸造
  服务 cookie（密钥轮换或 180 天到期后重铸一次）：

  ```bash
  # 在 47 上执行：
  set -a; source /etc/sim2real-web-auth.env; set +a
  node --input-type=module -e "
    import { encodeStudioWebCloudCookie } from '/opt/sim2real-web/current/dist-server/server/sim2real/studio-cookie-auth.js';
    const user = { id: 'svc-duck-lab-mcp', name: 'Duck Lab MCP Service',
                   email: 'svc-duck-lab-mcp@rdkstudio.local', roles: ['operator'] };
    console.log('rdk_sso_web_session=' + encodeStudioWebCloudCookie(user, Date.now() + 180*24*3600*1000));
  " > /root/duck-lab-service-cookie.txt
  # 把输出整行写进 /etc/rdk-duck-lab-mcp.env 的 RDK_SIM2REAL_MCP_COOKIE= 后，重启服务
  ```

  角色必须在 `admin/owner/operator/editor/viewer` 内（RBAC 白名单），未配置时
  工具如实返回 `[SIM2REAL_AUTH_REQUIRED]`。服务账号拥有独立台账命名空间，与
  人工账号的数据天然隔离
