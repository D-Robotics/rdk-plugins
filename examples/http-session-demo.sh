#!/usr/bin/env bash
# Duck Lab MCP 远程会话演示：对公网端点走一遍只读流程。
#
# 用法：
#   export DUCK_LAB_MCP_TOKEN='<向平台维护者获取>'
#   bash http-session-demo.sh
#
# 只调用只读工具（状态/健康/工作台概览），不会写台账、不会触发训练或板端动作。
# 多用户部署下，rdk_workspace_* 需要服务端已配置平台凭据（服务器
# /etc/rdk-duck-lab-mcp.env 加 RDK_SIM2REAL_MCP_COOKIE 或 USERNAME/PASSWORD）；
# 未配置时工具会如实返回登录要求——这正是错误透传的预期行为。
set -euo pipefail

URL="${DUCK_LAB_MCP_URL:-https://47.110.142.255/ducklab-mcp/mcp}"
TOKEN="${DUCK_LAB_MCP_TOKEN:?请设置 DUCK_LAB_MCP_TOKEN}"

call() { # call <id> <method> [params-json]
  curl -fsS -X POST "$URL" \
    -H 'content-type: application/json' \
    -H "authorization: Bearer $TOKEN" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":$1,\"method\":$2${3:+,\"params\":$3}}"
}

echo "== 1. initialize（协议协商）"
call 1 '"initialize"' '{"protocolVersion":"2025-06-18"}' |
  python3 -c 'import json,sys; r=json.load(sys.stdin)["result"]; print("   server:", r["serverInfo"]["name"], r["serverInfo"]["version"], "| protocol:", r["protocolVersion"])'

echo "== 2. tools/list（60 个 rdk_* 工具）"
call 2 '"tools/list"' | python3 -c '
import json, sys
tools = json.load(sys.stdin)["result"]["tools"]
print("   count:", len(tools))
print("   sample:", ", ".join(t["name"] for t in tools[:6]))'

echo "== 3. rdk_platform_status（平台健康与会话身份）"
call 3 '"tools/call"' '{"name":"rdk_platform_status","arguments":{}}' |
  python3 -c 'import json,sys; s=json.load(sys.stdin)["result"]["structuredContent"]; print("   ok:", s["ok"], "| ready:", s["health"]["ready"], "| auth:", s["authMode"])'

echo "== 4. rdk_workspace_overview（工作台只读概览）"
call 4 '"tools/call"' '{"name":"rdk_workspace_overview","arguments":{}}' |
  python3 -c '
import json, sys
r = json.load(sys.stdin)["result"]
if r.get("isError"):
    print("   (工作台读取失败：", r["content"][0]["text"][:80], ")")
else:
    s = r["structuredContent"]
    print("   models:", len(s.get("models", [])), "| runs:", len(s.get("runs", [])), "| devices:", len(s.get("devices", [])))'

echo "== 完成。写操作示例（示教→训练→演示视频）见 docs/duck-lab-mcp-guide.md 的「典型对话流」。"
