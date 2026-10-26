# @d-robotics/duck-lab-mcp

RDK Duck Lab MCP —— 把 RDK 机器人学习平台（Duck Lab）的能力以 MCP 工具形式交给任意
MCP 客户端（RDK Studio、Codex、Claude Desktop、Cursor、Qoder 等）。

- **61 个 `rdk_*` 工具**覆盖平台全链路，全部经版本化 `/api/v1/duck` API 操作，
  RBAC / 幂等 / 配额 / 运动安全开关均由平台执行
- **双传输**：默认 stdio（桌面客户端惯例）；设 `RDK_SIM2REAL_MCP_HTTP_PORT` 即切换
  streamable HTTP（远程 agent / 云端接入，支持路径 token 与 Bearer Header 双形态）
- **单文件 bundle**：`dist/bundle.mjs` 零外部依赖，Node ≥ 20 即可运行

## 安装

```bash
# npm 包（推荐）
npm install -g duck-lab-mcp-0.2.0.tgz

# 或从源码构建
git clone <仓库> && npm ci && npm run build && npm pack
```

### Claude Desktop / Cursor / 通用 stdio 客户端

```json
{ "mcpServers": { "duck-lab": {
    "command": "duck-lab-mcp",
    "env": { "RDK_SIM2REAL_MCP_BASE_URL": "http://127.0.0.1:18102" }
} } }
```

### HTTP 远程接入（零 Header）

```bash
RDK_SIM2REAL_MCP_HTTP_PORT=18103 \
RDK_SIM2REAL_MCP_HTTP_TOKEN='随机长token' \
RDK_SIM2REAL_MCP_BASE_URL=http://127.0.0.1:18102 \
duck-lab-mcp
```

客户端以 `http://<host>:18103/mcp/<token>` 或
`http://<host>:18103/mcp` + `Authorization: Bearer <token>` 接入。

## 工具目录（61 个）

### 工作台概览
| 工具 | 说明 |
|---|---|
| `rdk_platform_status` | 平台健康、就绪、会话身份 |
| `rdk_workspace_overview` | 模型、设备、训练资源、运行状态 |
| `rdk_workspace_summary` | 项目/数据/运行/部署计数摘要 |
| `rdk_golden_path` | 任务→数据→训练→RDK 反馈主链路进度 |

### 项目与数据
| 工具 | 说明 |
|---|---|
| `rdk_projects_list` / `rdk_project_create` | 项目列表与创建 |
| `rdk_datasets_list` / `rdk_dataset_register` | 数据集列表与登记 |
| `rdk_trajectory_check` / `rdk_trajectory_import` | 示教轨迹 JSONL 校验与导入 |

### 模型
| 工具 | 说明 |
|---|---|
| `rdk_models_list` / `rdk_model_validate` / `rdk_model_register` | 模型 manifest 校验与登记 |

### 训练
| 工具 | 说明 |
|---|---|
| `rdk_training_submit` | 提交训练任务（支持 idempotencyKey 幂等） |
| `rdk_training_status` | 状态 + 指标 + 结构化进度点列 |
| `rdk_training_wait` | 有界等待到终态（超时如实返回进度） |
| `rdk_run_logs` / `rdk_runs_list` / `rdk_runs_replay` | 日志、列表、回放 |
| `rdk_retraining_advice` | 重训建议（只读，不自动重训） |

### 评测
| 工具 | 说明 |
|---|---|
| `rdk_evaluation_summarize` / `rdk_evaluations_list` | 评测汇总与列表 |
| `rdk_feedback_summary` | 用户反馈汇总 |

### 制品与部署
| 工具 | 说明 |
|---|---|
| `rdk_artifacts_list` / `rdk_artifact_promote` | 制品生命周期（promote 为破坏性） |
| `rdk_deployment_preflight` | 只读部署预检 |
| `rdk_deployment_status` / `_history` / `_version_switch` / `_cancel` | 部署管理 |

### 板端运行
| 工具 | 说明 |
|---|---|
| `rdk_board_health` / `rdk_board_onboarding_preflight` | 板端健康与预检 |
| `rdk_board_policy_stage` / `_load` / `_start` / `_reset` | 策略装卸与启动（安全开关门控） |
| `rdk_board_arm_move` / `_gripper` / `_stop` | D6A 机械臂（双开关+工作空间钳制） |
| `rdk_board_stop` | 紧停（随时可用） |

### 可视化
| 工具 | 说明 |
|---|---|
| `rdk_replay_video` | 真机相机帧渲染 MP4 |
| `rdk_demo_video_upload` | 引擎渲染的策略演示视频挂到运行 |
| `rdk_training_status` + `snapshot:true` | 内嵌训练画面（base64 PNG） |

### 知识
| 工具 | 说明 |
|---|---|
| `rdk_docs_search` / `rdk_docs_manuals` / `rdk_docs_toc` / `rdk_docs_page` | D-Robotics 官方文档 |
| `rdk_web_search` | 全网搜索（结果标注非官方） |

## 安全

- 所有写操作经平台 RBAC / 审批 / 运动安全开关，本服务不做任何业务裁决
- 被拒绝时如实转述平台返回的原因与错误码
- 破坏性工具（`rdk_artifact_promote` 等 5 个）带 `destructiveHint` 标注
- 机械臂/策略启动失败后不要自行重试，先向用户确认

## 典型工作流

### 示教 → 训练 → 可视化
1. `rdk_simulator_open` → 人在浏览器录制轨迹
2. `rdk_trajectory_check` → 校验轨迹文件
3. `rdk_trajectory_import` → 登记为数据集
4. `rdk_training_submit`（datasetIds）→ 发起训练
5. `rdk_training_wait` → 等到训完（或 `rdk_training_status` 轮询）
6. `rdk_evaluation_summarize` → 评测汇总
7. `rdk_demo_video_upload` → 渲染 MP4 挂到运行

### 发布到板端
1. `rdk_deployment_preflight` → 只读预检
2. `rdk_artifact_promote`（validated → published）
3. `rdk_board_policy_stage` → `rdk_board_policy_load` → `rdk_board_policy_start`
