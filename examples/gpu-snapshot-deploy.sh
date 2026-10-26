#!/usr/bin/env bash
# GPU 快照一键部署（在有 GPU box SSH 权限的机器上执行）。
# 部署内容：worker（含快照端点）+ legged 引擎包装器（含 --snapshot-interval）
# 前提：GPU box 的 microduck_rl checkout 已存在（~/microduck_rl）
set -euo pipefail
GPU_HOST="${GPU_HOST:-120.48.90.140}"
GPU_PORT="${GPU_PORT:-2222}"
GPU_USER="${GPU_USER:-root}"
GPU_KEY="${GPU_KEY:-~/.ssh/id_ed25519}"

SSH_CMD="ssh -p $GPU_PORT -i $GPU_KEY -o StrictHostKeyChecking=accept-new $GPU_USER@$GPU_HOST"
echo "== 1. 检查连接与 microduck_rl"
$SSH_CMD 'ls ~/microduck_rl/src/mjlab_microduck/robot/microduck/scene.xml && echo upstream-ok'

echo "== 2. 上传 worker + 快照能力"
rsync -az -e "ssh -p $GPU_PORT -i $GPU_KEY" \
  "$(dirname "$0")/../../services/sim2real-web/local-training-worker.mjs" \
  "$GPU_USER@$GPU_HOST:~/worker/local-training-worker.mjs"

echo "== 3. 注册 legged 引擎（写入 worker env）"
$SSH_CMD 'grep -q RDK_SIM2REAL_TRAIN_ENGINES_JSON ~/.bashrc 2>/dev/null || cat >> ~/.bashrc << ENVEOF
export RDK_SIM2REAL_LOCAL_RUNNER_TOKEN="${RDK_SIM2REAL_LOCAL_RUNNER_TOKEN:-legged-snap-0000000000000000}"
export RDK_SIM2REAL_TRAIN_ENGINES_JSON="{\"microduck-legged\":{\"executable\":\"/root/legged-engine.sh\",\"args\":[]}}"
ENVEOF
cat > ~/legged-engine.sh << '"'"'ENGEOF'"'"'
#!/bin/bash
exec python3 /root/microduck_rl/scripts/train_legged.py \
  --snapshot-interval 3 "$@"
ENGEOF
chmod +x ~/legged-engine.sh'

echo "== 4. 重启 worker"
$SSH_CMD 'pkill -f local-training-worker 2>/dev/null; sleep 1; source ~/.bashrc; nohup node ~/worker/local-training-worker.mjs > ~/worker/worker.log 2>&1 & sleep 2; curl -s http://127.0.0.1:19091/healthz'

echo "完成。平台侧注册：runnerUrl=http://$(curl -s ifconfig.me):19091/train"
