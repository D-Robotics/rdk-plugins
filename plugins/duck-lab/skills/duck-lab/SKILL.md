---
name: duck-lab
description: 用 67 个 rdk_* 工具以对话驱动 RDK 机器人学习平台全链路：设备连接、示教轨迹导入、强化学习训练提交与实时进度、评测质量门、制品晋级、部署预检、板端策略与 D6A 机械臂、量化就绪、官方文档检索、血缘与回放视频、远程开发机连接与环境安装。当用户提到「机器人学习平台」「Duck Lab」「训练策略」「提交训练」「评测」「部署到板卡」「机械臂」「rdk_ 工具」「示教轨迹」「演示视频」「量化」「Workshop」「连接开发机」或要求查询平台数据时使用。
trigger: Duck Lab, 机器人学习平台, rdk, 提交训练, 训练进度, 评测, 制品, 部署预检, 板端策略, 机械臂, 示教轨迹, 演示视频, Workshop, 量化
version: 0.2.0
risk: medium
requires_board: false
permissions: network
category: device
enabled: true
---

# Duck Lab：RDK 机器人学习平台对话驱动

## 工具选择地图

| 用户意图 | 工具序列 |
| --- | --- |
| 看平台状态 | `rdk_platform_status` → `rdk_workspace_overview` |
| 看模型/项目/数据 | `rdk_models_list` / `rdk_projects_list` / `rdk_datasets_list` |
| 连接设备 | `rdk_device_discover` → `rdk_device_connect` → `rdk_board_health` |
| 给设备起名 | `rdk_device_rename`（Workshop 第一关） |
| 导入示教轨迹 | `rdk_trajectory_check`（先校验）→ `rdk_trajectory_import`（登记） |
| 提交训练 | `rdk_training_submit` → `rdk_training_wait`（不要重复提交） |
| 训练进度/画面 | `rdk_training_status`（`snapshot:true` 内嵌画面）|
| 训练日志 | `rdk_run_logs`（`after` 游标增量） |
| 评测 | `rdk_evaluation_summarize` / `rdk_evaluations_list` |
| 量化 | `rdk_quantize`（就绪检查 + 指引） |
| 制品发布 | `rdk_artifacts_list` → `rdk_deployment_preflight` → `rdk_artifact_promote` |
| 部署上板 | `rdk_board_policy_stage` → `rdk_board_policy_load` → `rdk_board_policy_start` |
| 演示视频 | `rdk_replay_video` / `rdk_demo_video_upload` |
| 机械臂 | `rdk_board_arm_status` → `rdk_board_arm_move` / `rdk_board_arm_gripper` |
| 急停 | `rdk_board_stop`（随时可用） |
| 查文档 | `rdk_docs_search` / `rdk_docs_page`（官方优先于 `rdk_web_search`） |
| Workshop 进度 | `rdk_workshop_status`（三关卡追踪 + 下一步建议） |
| 连接远程开发机 | `rdk_remote_connect`（SSH）→ `rdk_remote_provision`（自动装环境）→ `rdk_remote_exec` |
| 重训建议 | `rdk_retraining_advice`（只读分析，不自动重训） |

## 训练结果解读

工具返回的 `verdict` 字段告诉你训练是否成功，直接告诉用户：

| verdict | 含义 | 怎么跟学生说 |
| --- | --- | --- |
| `model-usable` | 成功率 ≥70% | "训练成功了！这个模型可以部署上板。" |
| `model-partially-learned` | 有一些成功但不到70% | "模型学到了一些东西，但还不够稳定。可以再训练更多轮次。" |
| `model-fell-often` | 摔倒率 >50% | "模型经常摔倒，训练不充分。建议增加训练轮次或检查参数。" |
| `model-insufficient-evidence` | 没有成功率数据 | "训练完成了，但缺少成功率数据，无法判断模型质量。" |
| `training-failed` | 训练过程出错 | "训练失败了。我来查看日志找原因。" |
| `training-in-progress` | 还在训练 | "还在训练中，我来等待完成。" |

## Workshop 三关引导

当用户提到「Workshop」「第几关」时，先调 `rdk_workshop_status` 获取进度。

**第一关 唤醒鸭子**：学生 USB 连鸭 → `rdk_device_connect` → `rdk_board_health` → `rdk_device_rename`
**第二关 仿真训练**：`rdk_training_submit` → `rdk_training_wait` → `rdk_training_status`（`snapshot:true`）→ 告诉学生 verdict
**第三关 量化部署**：`rdk_quantize`（检查就绪）→ `rdk_board_policy_stage` → `rdk_board_policy_load` → `rdk_board_policy_start`

## 五条纪律

1. **被拒绝时如实转述**平台返回的原因与错误码（如 `[SIM2REAL_RUN_NOT_FOUND]`），不要自行重试写操作或物理动作。
2. **异步任务用等待工具**（`rdk_training_wait`），不要为查进度而重复提交训练。
3. **写操作传 `idempotencyKey`**：同一逻辑操作重试时复用同一值，平台按幂等键去重。
4. **破坏性工具**（`rdk_artifact_promote`、`rdk_board_stop` 等 5 个）执行前先向用户确认。
5. 机械臂/策略启动失败后不要自行重试，先向用户确认。
