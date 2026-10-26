# @d-robotics/duck-lab-mcp

RDK Duck Lab MCP —— 把 RDK 机器人学习平台（Duck Lab）的能力以 MCP 工具形式交给任意
MCP 客户端（RDK Studio、Codex、Claude Desktop、Cursor、Qoder 等）：数据集、模型、
训练、评测、制品晋级、部署预检、板端策略与机械臂、官方文档检索、血缘与回放视频。

- **60 个 `rdk_*` 工具**，全部经平台版本化 `/api/v1/duck` API 操作，RBAC / 幂等 /
  配额 / 运动安全开关均由平台执行
- **双传输**：默认 stdio（桌面客户端惯例）；设 `RDK_SIM2REAL_MCP_HTTP_PORT` 即切换
  streamable HTTP（远程 agent / 云端接入，可选 Bearer Token）
- **单文件 bundle**：`dist/bundle.mjs` 零外部依赖，Node ≥ 20 即可运行

## 快速开始（stdio）

任意 MCP 客户端配置：

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

## 快速开始（HTTP，远程接入）

```bash
RDK_SIM2REAL_MCP_HTTP_PORT=18103 \
RDK_SIM2REAL_MCP_HTTP_TOKEN='请换成随机长token' \
RDK_SIM2REAL_MCP_BASE_URL=http://127.0.0.1:18102 \
duck-lab-mcp
```

客户端以 `http://<host>:18103/mcp` + `Authorization: Bearer <token>` 接入；
仅支持 POST（无状态传输），批量请求返回数组，通知返回 202。

完整安装矩阵、环境变量表、工具目录与示例见仓库
`docs/duck-lab-mcp-guide.md` 与 `examples/duck-lab-mcp/`。
