#!/usr/bin/env bash
# Duck Lab MCP 一键安装：下载插件 → 全局安装（可选）→ 注册到检测到的 MCP 客户端。
#
# 用法：
#   curl -fsSL https://47.110.142.255/ducklab-mcp/install.sh -o install.sh
#   DUCK_LAB_MCP_TOKEN='<token>' bash install.sh            # 远程 HTTP 接入（推荐）
#   DUCK_LAB_PLATFORM_URL=http://127.0.0.1:18102 bash install.sh local   # 本地 stdio
#
# 每个被修改的配置文件都会先留 .duck-lab-backup.<ts> 备份；重复执行幂等。
set -euo pipefail

BASE="${DUCK_LAB_MCP_BASE:-https://47.110.142.255/ducklab-mcp}"
REMOTE_URL="${DUCK_LAB_MCP_URL:-https://47.110.142.255/ducklab-mcp/mcp}"
TOKEN="${DUCK_LAB_MCP_TOKEN:-}"
PLATFORM_URL="${DUCK_LAB_PLATFORM_URL:-http://127.0.0.1:18102}"
MODE="${1:-remote}"
TS=$(date +%Y%m%d-%H%M%S)

say() { printf '\n== %s\n' "$*"; }

download_tarball() {
  mkdir -p "$HOME/.duck-lab-mcp"
  curl -fsSL "$BASE/duck-lab-mcp.tgz" -o "$HOME/.duck-lab-mcp/duck-lab-mcp.tgz"
  echo "已下载插件包到 ~/.duck-lab-mcp/duck-lab-mcp.tgz"
}

install_global() {
  if command -v npm >/dev/null 2>&1; then
    npm install -g "$HOME/.duck-lab-mcp/duck-lab-mcp.tgz" && echo "已全局安装 duck-lab-mcp 命令"
  else
    echo "未检测到 npm：跳过本地安装（远程 HTTP 接入不需要）。"
  fi
}

merge_json_entry() { # <file> <entry-json>
  python3 - "$1" "$2" "$TS" << 'PY'
import json, shutil, sys, os
path, entry_json, ts = sys.argv[1], sys.argv[2], sys.argv[3]
entry = json.loads(entry_json)
if os.path.exists(path):
    shutil.copy2(path, f"{path}.duck-lab-backup.{ts}")
    try:
        cfg = json.load(open(path))
    except Exception:
        cfg = {}
else:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cfg = {}
cfg.setdefault("mcpServers", {})["duck-lab"] = entry
with open(path, "w") as handle:
    json.dump(cfg, handle, ensure_ascii=False, indent=2)
print(f"  已注册: {path}")
PY
}

append_codex_toml() {
  local path="$HOME/.codex/config.toml"
  mkdir -p "$(dirname "$path")"
  [ -f "$path" ] && cp "$path" "$path.duck-lab-backup.$TS"
  if [ -f "$path" ] && grep -q 'mcp_servers.duck-lab' "$path"; then
    echo "  已存在: $path（跳过）"
    return
  fi
  if [ "$MODE" = "remote" ]; then
    cat >> "$path" << EOF

[mcp_servers.duck-lab]
command = "npx"
args = ["-y", "mcp-remote", "$REMOTE_URL", "--header", "Authorization: Bearer $TOKEN"]
EOF
  else
    cat >> "$path" << EOF

[mcp_servers.duck-lab]
command = "duck-lab-mcp"
env = { "RDK_SIM2REAL_MCP_BASE_URL" = "$PLATFORM_URL" }
EOF
  fi
  echo "  已注册: $path"
}

say "1/3 下载并安装插件包"
download_tarball
install_global

say "2/3 注册客户端配置（模式：$MODE）"
if [ "$MODE" = "remote" ]; then
  [ -n "$TOKEN" ] || { echo "远程接入需要 DUCK_LAB_MCP_TOKEN（向平台维护者获取）"; exit 1; }
  # Qoder：settings.json 的 mcpServers，原生 HTTP 条目
  merge_json_entry "$HOME/.qoder/settings.json" \
    "{\"type\":\"http\",\"url\":\"$REMOTE_URL\",\"headers\":{\"Authorization\":\"Bearer $TOKEN\"}}"
  # Cursor：~/.cursor/mcp.json，远程 HTTP
  merge_json_entry "$HOME/.cursor/mcp.json" \
    "{\"url\":\"$REMOTE_URL\",\"headers\":{\"Authorization\":\"Bearer $TOKEN\"}}"
  # RDK Studio：data/mcp.json，stdio 约定走 mcp-remote 桥
  merge_json_entry "$HOME/Library/Application Support/rdk-studio/data/mcp.json" \
    "{\"transport\":\"stdio\",\"command\":\"npx\",\"args\":[\"-y\",\"mcp-remote\",\"$REMOTE_URL\",\"--header\",\"Authorization: Bearer $TOKEN\"]}"
  # Claude Desktop：存在才注册
  if [ -d "$HOME/Library/Application Support/Claude" ]; then
    merge_json_entry "$HOME/Library/Application Support/Claude/claude_desktop_config.json" \
      "{\"command\":\"npx\",\"args\":[\"-y\",\"mcp-remote\",\"$REMOTE_URL\",\"--header\",\"Authorization: Bearer $TOKEN\"]}"
  fi
  append_codex_toml
else
  merge_json_entry "$HOME/.qoder/settings.json" \
    "{\"command\":\"duck-lab-mcp\",\"env\":{\"RDK_SIM2REAL_MCP_BASE_URL\":\"$PLATFORM_URL\"}}"
  merge_json_entry "$HOME/.cursor/mcp.json" \
    "{\"command\":\"duck-lab-mcp\",\"env\":{\"RDK_SIM2REAL_MCP_BASE_URL\":\"$PLATFORM_URL\"}}"
  merge_json_entry "$HOME/Library/Application Support/rdk-studio/data/mcp.json" \
    "{\"transport\":\"stdio\",\"command\":\"duck-lab-mcp\",\"env\":{\"RDK_SIM2REAL_MCP_BASE_URL\":\"$PLATFORM_URL\"}}"
  if [ -d "$HOME/Library/Application Support/Claude" ]; then
    merge_json_entry "$HOME/Library/Application Support/Claude/claude_desktop_config.json" \
      "{\"command\":\"duck-lab-mcp\",\"env\":{\"RDK_SIM2REAL_MCP_BASE_URL\":\"$PLATFORM_URL\"}}"
  fi
  append_codex_toml
fi

say "3/3 完成"
echo "重启对应客户端后生效。WorkBuddy 请在其设置界面的 MCP 入口填："
[ "$MODE" = "remote" ] && echo "  URL: $REMOTE_URL" && echo "  Header: Authorization: Bearer <token>" \
  || echo "  命令: duck-lab-mcp（env RDK_SIM2REAL_MCP_BASE_URL=$PLATFORM_URL）"
echo "验证：对话里问「列出 duck-lab 工具」或运行 examples/duck-lab-mcp/http-session-demo.sh"
