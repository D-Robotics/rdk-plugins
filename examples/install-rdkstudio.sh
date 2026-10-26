#!/usr/bin/env bash
# RDK Studio 版 Duck Lab 插件：安装 + 自动更新（幂等）。
#
# 用法：
#   bash install-rdkstudio.sh              # 安装或更新到服务器最新版
#   bash install-rdkstudio.sh --check      # 只检查是否有新版本
#
# 行为：
#   1. 读取服务器版本清单 version.json（version + zip 地址 + SHA-256）
#   2. 与本地 ~/.rdkstudio/plugins/duck-lab/plugin.json 的版本比较
#   3. 版本相同 → 什么都不动；有新版/未安装 → 下载、校验、替换目录、更新注册表
#   4. 每次替换前把旧目录与注册表各留一份时间戳备份
#
# 注意：Studio 运行中执行更新后，需要重启 Studio 才会加载新版本。
set -euo pipefail

BASE="${DUCK_LAB_MCP_BASE:-https://47.110.142.255/ducklab-mcp}"
PLUGIN_DIR="${RDK_STUDIO_PLUGIN_DIR:-$HOME/.rdkstudio/plugins/duck-lab}"
REGISTRY="${RDK_STUDIO_PLUGIN_REGISTRY:-$HOME/Library/Application Support/rdk-studio/data/plugins-registry.json}"
TS=$(date +%Y%m%d-%H%M%S)
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

manifest=$(curl -fsSL "$BASE/rdkstudio-version.json")
remote_version=$(printf '%s' "$manifest" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')
remote_zip=$(printf '%s' "$manifest" | python3 -c 'import json,sys; print(json.load(sys.stdin)["url"])')
remote_sha=$(printf '%s' "$manifest" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha256"])')

local_version="未安装"
if [ -f "$PLUGIN_DIR/plugin.json" ]; then
  local_version=$(python3 -c 'import json;print(json.load(open("'"$PLUGIN_DIR"'/plugin.json"))["version"])')
fi
echo "本地版本: $local_version | 服务器版本: $remote_version"

if [ "$local_version" = "$remote_version" ]; then
  # 版本相同也可能需要补登记：目录在而注册表条目缺失（手工清理或导入失败）。
  if python3 - "$REGISTRY" << 'PY'
import json, os, sys
path = sys.argv[1]
if not os.path.exists(path):
    sys.exit(1)
d = json.load(open(path))
entry = d.get("plugins", {}).get("duck-lab@user", {})
sys.exit(0 if entry.get("installPath") and entry.get("enabled") is not False else 1)
PY
  then
    echo "已是最新版本，无需更新。"
    exit 0
  fi
  echo "版本相同但注册表条目缺失，补登记。"
fi
if [ "$CHECK_ONLY" = "1" ]; then
  echo "有新版本可用：$remote_version（当前 $local_version）。去掉 --check 再执行即更新。"
  exit 0
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$remote_zip" -o "$tmp/plugin.zip"
actual_sha=$(shasum -a 256 "$tmp/plugin.zip" | awk '{print $1}')
if [ "$actual_sha" != "$remote_sha" ]; then
  echo "SHA-256 不匹配（期望 $remote_sha，实际 $actual_sha），拒绝安装。" >&2
  exit 1
fi

# 旧目录备份后替换
if [ -d "$PLUGIN_DIR" ]; then
  mv "$PLUGIN_DIR" "$PLUGIN_DIR.backup.$TS"
fi
mkdir -p "$PLUGIN_DIR"
unzip -q "$tmp/plugin.zip" -d "$PLUGIN_DIR"
echo "已安装/更新到 $PLUGIN_DIR（版本 $remote_version）"

# 注册表登记（镜像现有条目结构；Studio 运行中时以应用为准）
python3 - "$REGISTRY" "$PLUGIN_DIR" "$remote_version" "$TS" << 'PY'
import json, os, shutil, sys, time
registry, plugin_dir, version, ts = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
if not os.path.exists(registry):
    print("未找到 Studio 插件注册表，跳过登记（插件目录已就位）。")
    sys.exit(0)
shutil.copy2(registry, f"{registry}.backup.{ts}")
d = json.load(open(registry))
plugins = d.setdefault("plugins", {})
template = plugins.get("rdk-camera-workshop@user", {})
entry = json.loads(json.dumps(template))
entry.update({
    "scope": "user",
    "installPath": plugin_dir,
    "version": version,
    "enabled": True,
    "installedAt": entry.get("installedAt") or int(time.time() * 1000),
    "lastUpdated": int(time.time() * 1000),
    "source": "import",
    "id": "duck-lab@user",
    "name": "duck-lab",
})
plugins["duck-lab@user"] = entry
json.dump(d, open(registry, "w"), ensure_ascii=False, indent=2)
print("注册表已更新：duck-lab@user ->", plugin_dir)
PY

echo "完成。若 Studio 正在运行，重启 Studio 后生效。"
