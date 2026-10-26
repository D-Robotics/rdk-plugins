# RDK Plugins — D-Robotics 插件合集

D-Robotics RDK 生态的官方 MCP 插件合集：一个仓库、一份市场清单、四个开箱即用的
对话插件。支持 Qoder（市场级自动更新）、RDK Studio（插件目录）、Claude Desktop、
Cursor、Codex 及任何支持 streamable HTTP 的 MCP 宿主。

## 插件目录

| 插件 | 版本 | 能力 |
| --- | --- | --- |
| **duck-lab** | 0.2.0 | RDK 机器人学习平台全链路：示教轨迹导入、训练提交与实时进度、评测质量门、制品晋级、部署预检、板端策略与 D6A 机械臂、官方文档检索、血缘与回放视频（60 工具） |
| **rdk-camera-workshop** | 1.2.0 | 相机资料核对、点亮、采流诊断与 AI 看图 ISP 调试；连接用户自有 d-obs 相机服务 |
| **rdk-vision-workshop** | 0.1.0 | 四小时相机与 BPU 视觉 Workshop：点亮、ISP、标注、GPU 短程微调、PTQ、X5 BPU 与实时检测编排 |
| **d-obs-agent** | 0.1.0 | d-obs 可观测平台中文查询：指标、日志、链路、告警、设备与模型池（只读，复用现有身份权限） |

## 安装

### Qoder：市场源（推荐，自动更新）

把 `https://47.110.142.255/ducklab-mcp/marketplace.json` 添加为 Qoder 市场源
（或由管理员写进 `~/.qoder/plugins/known_marketplaces.json`），之后四个插件都在
「扩展管理 → 市场」里一键安装、自动更新。

### 单包安装

从 [marketplace.json](marketplace.json) 取对应 zip 的 URL 与 SHA-256，在
Qoder「扩展管理 → +」导入；或用 `examples/install.sh` 自动注册到检测到的客户端。

### RDK Studio

```bash
bash -c "$(curl -fsSL https://47.110.142.255/ducklab-mcp/install-rdkstudio.sh)"
```

安装 duck-lab 并接入版本清单自动更新；其他插件按 `plugins/<name>/` 目录形态放入
`~/.rdkstudio/plugins/`（与 rdk-camera-workshop 同构）。

### 纯 URL 直连（duck-lab，零 Header）

```
https://47.110.142.255/ducklab-mcp/mcp/<token>
```

## 仓库结构

| 路径 | 说明 |
| --- | --- |
| `plugins/<name>/` | 各插件源码（plugin.json + skills + MCP 连接器） |
| `marketplace.json` | 合集市场清单（Qoder marketplace schema，含 SHA-256） |
| `dist/` | 可直接安装的分发物（各插件 zip + duck-lab npm tarball + Studio 包） |
| `docs/duck-lab-mcp-guide.md` | duck-lab 完整指南 |
| `examples/` | 客户端配置样例、一键安装脚本、可运行演示 |

## 发布新版插件

1. 更新 `plugins/<name>/` 源码与版本号
2. 重新打包 zip 到 `dist/`，计算 SHA-256
3. 更新 `marketplace.json` 的 version/url/sha256
4. 同步到分发服务器（见 `examples/nginx-ducklab-mcp-location.inc`）

## 安全

- 本仓库分发物**不含任何凭据**：需要平台凭据的插件（如 duck-lab 工作台读写）
  在用户侧配置 token，或由管理员在服务端配置服务账号
- camera/vision/agent 插件连接**用户自有服务**，凭据外置于用户目录（POSIX 600），
  不进入插件包与对话
