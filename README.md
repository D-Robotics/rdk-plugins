# RDK Plugins — D-Robotics 插件合集

D-Robotics RDK 生态的官方 MCP 插件合集：一个仓库、一份市场清单、四个开箱即用的
对话插件。支持 Qoder（市场级自动更新）、RDK Studio（插件目录）、Claude Desktop、
Cursor、Codex 及任何支持 streamable HTTP 的 MCP 宿主。

## 插件目录

> 每个插件有独立介绍（点目录名查看 README）与独立安装命令；Studio 通用安装器
> 会从合集市场清单解析版本并做 SHA-256 校验，重复执行安全。

### duck-lab — RDK 机器人学习平台（0.2.0）

对话驱动学习平台全链路：示教轨迹导入、训练提交与**实时训练进度**、评测质量门、
制品晋级、部署预检、板端策略与 D6A 机械臂、官方文档检索、血缘与回放视频（60 工具）。

```bash
# RDK Studio 安装/更新
bash -c "$(curl -fsSL https://47.110.142.255/ducklab-mcp/install-rdkstudio.sh)"
# 任意 MCP 客户端：纯 URL 直连
https://47.110.142.255/ducklab-mcp/mcp/<token>
```
详见 [plugins/duck-lab/README.md](plugins/duck-lab/README.md) ·
[完整指南](docs/duck-lab-mcp-guide.md)

### rdk-camera-workshop — 相机点亮与 ISP 调试（1.2.0）

新型号相机资料核对、点亮、采流诊断与 AI 看图 ISP 调试；连接**用户自有**
d-obs 相机服务，凭据外置用户目录。

```bash
bash -c "$(curl -fsSL https://47.110.142.255/ducklab-mcp/install-studio-plugin.sh) rdk-camera-workshop"
```
插件包：[dist/rdk-camera-workshop-1.2.0.zip](dist/rdk-camera-workshop-1.2.0.zip) ·
详见 [plugins/rdk-camera-workshop/README.md](plugins/rdk-camera-workshop/README.md)

### rdk-vision-workshop — 相机与 BPU 视觉 Workshop（0.1.0）

四小时 Workshop 编排：点亮、ISP、数据标注、GPU 短程微调、PTQ、X5 BPU 与
实时检测；提供只读课程工具与阶段技能，实际执行复用宿主设备/开发工具。

```bash
bash -c "$(curl -fsSL https://47.110.142.255/ducklab-mcp/install-studio-plugin.sh) rdk-vision-workshop"
```
插件包：[dist/rdk-vision-workshop-0.1.0.zip](dist/rdk-vision-workshop-0.1.0.zip) ·
详见 [plugins/rdk-vision-workshop/README.md](plugins/rdk-vision-workshop/README.md)

### d-obs-agent — 可观测平台查询助手（0.1.0）

中文对话查询 d-obs 的指标、日志、链路、告警、设备与模型池；只读，
复用现有身份权限。

```bash
bash -c "$(curl -fsSL https://47.110.142.255/ducklab-mcp/install-studio-plugin.sh) d-obs-agent"
```
插件包：[dist/d-obs-agent-0.1.0.zip](dist/d-obs-agent-0.1.0.zip) ·
详见 [plugins/d-obs-agent/README.md](plugins/d-obs-agent/README.md)

## 安装

### RDK Studio：市场源（给一个链接即可）

把仓库链接添加到 Studio 插件中心的市场源：

```
https://github.com/D-Robotics/rdk-plugins
```

Studio 按 GitHub 风格 `marketplace.json`（本仓库根部即此清单，条目指向
`plugins/<name>/` 源码目录）浅克隆并解析，四个插件列出后一键安装
（拷入 `~/.rdkstudio/plugins/`，登记 `source: "store"`）；仓库更新后重进
市场即可拉到新版本。

### Qoder：市场源（推荐，自动更新）

把 `https://47.110.142.255/ducklab-mcp/marketplace.json` 添加为 Qoder 市场源
（或由管理员写进 `~/.qoder/plugins/known_marketplaces.json`），之后四个插件都在
「扩展管理 → 市场」里一键安装、自动更新。

> 两份清单分工：仓库根部 `marketplace.json` 是 Studio 的 git 形态（条目指向
> 仓库内源码目录）；`https://47.110.142.255/ducklab-mcp/marketplace.json` 是
> Qoder 的 archive 形态（zip + SHA-256）。

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
| `plugins/<name>/` | 各插件源码与独立介绍（plugin.json + skills + MCP 连接器 + README） |
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
