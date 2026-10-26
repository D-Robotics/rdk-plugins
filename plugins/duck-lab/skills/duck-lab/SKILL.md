---
name: duck-lab
description: 用 60 个 rdk_* 工具以对话驱动 RDK 机器人学习平台全链路：数据集与示教轨迹导入、强化学习/模仿学习训练提交与实时进度、评测质量门、制品晋级、部署预检、板端策略与 D6A 机械臂、官方文档检索、血缘与回放视频。当用户提到「机器人学习平台」「Duck Lab」「训练策略」「提交训练」「评测」「部署到板卡」「机械臂」「rdk_ 工具」「示教轨迹」「演示视频」或要求查询平台数据时使用。写操作全部经平台 RBAC/审批/安全开关，被拒绝时如实转述平台错误码。
trigger: Duck Lab, 机器人学习平台, rdk, 提交训练, 训练进度, 评测, 制品, 部署预检, 板端策略, 机械臂, 示教轨迹, 演示视频, MicroDuck
version: 0.2.0
risk: medium
requires_board: false
permissions: network
category: device
enabled: true
---

# Duck Lab：RDK 机器人学习平台对话驱动

本插件通过 `duck_lab` MCP 服务器（60 个 `rdk_*` 工具）操作 RDK 机器人学习平台。
完整指南在平台仓库 `docs/duck-lab-mcp-guide.md`；本文件只给对话中的决策规则。

## 工具选择地图

| 用户意图 | 工具序列 |
| --- | --- |
| 看平台状态/健康 | `rdk_platform_status` → `rdk_workspace_overview` |
| 导入示教轨迹（ACT/DP 训练数据） | `rdk_trajectory_check`（先校验）→ `rdk_trajectory_import`（登记为数据集） |
| 提交训练 | `rdk_training_submit`（写操作，可传 `idempotencyKey` 保证重试幂等）→ 用 `rdk_training_status` 轮询（含结构化进度点列，勿重复提交） |
| 看训练日志/曲线 | `rdk_run_logs`（有界日志）+ `rdk_training_status` 的 progress 字段 |
| 评测与对比 | `rdk_evaluation_summarize` / `rdk_evaluations_list` / `rdk_runs_replay` |
| 制品发布 | `rdk_artifacts_list` → `rdk_deployment_preflight`（只读预检）→ `rdk_artifact_promote`（破坏性，先向用户确认） |
| 演示视频 | `rdk_replay_video`（板端相机帧）/ `rdk_demo_video_upload`（引擎渲染 MP4 挂到运行） |
| 板端策略 | `rdk_board_policy_stage` → `rdk_board_policy_load` → `rdk_board_policy_start`（三步各自独立，启动受平台多重安全开关约束） |
| 查资料 | `rdk_docs_search` / `rdk_docs_page`（官方文档优先于 `rdk_web_search` 网络结果） |

## 纪律

1. **被拒绝时如实转述**平台返回的原因与错误码（如 `[SIM2REAL_AUTH_REQUIRED]`），
   不要自行重试写操作或物理动作。
2. **异步任务用轮询工具**（`rdk_training_status` / `rdk_run_logs`），不要为查进度
   而重复提交。
3. **写操作传 `idempotencyKey`**：同一逻辑操作重试时复用同一值，平台按幂等键去重。
4. **破坏性工具**（`rdk_artifact_promote`、`rdk_deployment_cancel`、
   `rdk_device_disconnect`、`rdk_board_policy_reset`、`rdk_board_stop`）执行前先
   向用户确认。
5. 机械臂/策略启动失败后先向用户确认，绝不自动重试。

## Workshop 模式

当用户提到「Workshop」「第一关」「第二关」「第三关」「训练鸭子」「量化」「上板」时，进入 Workshop 模式：

1. 先调 `rdk_workshop_status` 查看各关卡完成状态
2. 按下一步建议引导学员操作
3. 第二关引导：`rdk_training_submit`（模板 microduck-stand）→ `rdk_training_wait` → `rdk_training_status`（带进度点列）
4. 第三关引导：`rdk_quantize`（检查就绪）→ `rdk_board_policy_stage` → `rdk_board_policy_load` → `rdk_board_policy_start`
5. 每步完成后调 `rdk_workshop_status` 确认进度，给学员正向反馈
