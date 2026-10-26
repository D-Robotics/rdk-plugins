#!/usr/bin/env node
/** Local onboarding. No token arguments, host-settings edits or camera writes. */
import { mkdir, mkdtemp, writeFile, rm, link, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { resolveConfigPath, validateConfiguration, describeError } from './bridge.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
export { describeError };
export async function configure({ url, auth, credentialFile, config = resolveConfigPath() }) {
  if (!path.isAbsolute(config) || !path.isAbsolute(credentialFile ?? '') || !['sso', 'admin'].includes(auth)) throw new Error('camera_setup_arguments_invalid');
  // Runtime validator checks URL, private-file ownership and contents on a temporary file first.
  const scratch = await mkdtemp(path.join(tmpdir(), 'camera-setup-'));
  const temporary = path.join(scratch, 'connection.json');
  try {
    const content = JSON.stringify({ url, auth: { type: auth, credentialFile: await realpath(credentialFile) } }, null, 2) + '\n';
    await writeFile(temporary, content, { mode: 0o600, flag: 'wx' });
    await validateConfiguration(temporary);
    await mkdir(path.dirname(config), { recursive: true, mode: 0o700 });
    // Validate the final location too; refuse credentials/configs inside the distribution or repository.
    const candidate = path.join(path.dirname(config), '.camera-setup-' + path.basename(scratch) + '.json');
    let created = false;
    try {
      await writeFile(candidate, content, { mode: 0o600, flag: 'wx' });
      created = true;
      await validateConfiguration(candidate);
      await link(candidate, config); // Atomic creation; never overwrite an existing config or follow a symlink.
    } finally { if (created) await rm(candidate, { force: true }); }
    return { status: 'configured', next: '运行 doctor 检查 MCP 工具与服务能力。' };
  } finally { await rm(scratch, { recursive: true, force: true }); }
}
export function clientConfig() {
  return { mcpServers: { 'rdk-camera-workshop': { type: 'stdio', command: process.execPath, args: [path.join(here, 'bridge.mjs')], env: { RDK_CAMERA_WORKSHOP_ONBOARDING: '1' } } } };
}
// Workflow chains must match the reviewed bridge TOOL_ARGUMENTS; a missing entry means the d-obs service needs an upgrade, never a bridge-side fallback.
const CAPABILITY_CHAINS = {
  core: ['vision_workshop_runtime_status', 'vision_experiment_create', 'vision_experiment_list', 'vision_experiment_get', 'vision_camera_readiness'],
  knowledge: ['vision_camera_knowledge_search', 'vision_camera_knowledge_get'],
  bringup: ['vision_camera_probe', 'vision_pipeline_validate', 'vision_camera_bringup', 'vision_camera_capture_frame', 'vision_camera_controls_get'],
  aiDebug: ['vision_ai_debug_start', 'vision_ai_debug_status', 'vision_ai_debug_cancel', 'vision_ai_debug_restore_original'],
  isp: ['vision_raw_capture', 'vision_isp_generate', 'vision_isp_process_raw', 'vision_isp_apply', 'vision_isp_restore', 'vision_isp_tuning_get', 'vision_isp_tuning_load'],
  calibration: ['vision_calibration_task_create', 'vision_calibration_task_run', 'vision_calibration_task_result', 'vision_calibration_apply_plan', 'vision_calibration_apply'],
  delivery: ['vision_workshop_delivery', 'vision_delivery_target_select', 'vision_acceptance_plan_save', 'vision_acceptance_record', 'vision_workshop_export'],
};
export function chainReadiness(names) {
  const present = new Set(names); const chains = {};
  for (const [chain, required] of Object.entries(CAPABILITY_CHAINS)) {
    const missing = required.filter(tool => !present.has(tool));
    chains[chain] = missing.length ? { status: 'missing', missing } : { status: 'ready' };
  }
  return chains;
}
const connectedNext = chains => {
  const base = '在宿主中读取 runtime_status，选择实际登记的设备；连接成功不代表相机已点亮。';
  const delivery = chains?.delivery;
  return delivery?.status === 'ready' ? base
    : base + '服务端缺少交付/验收工具：' + (delivery?.missing ?? []).join('、') + '；workshop 交付与验收前先升级服务端。';
};
async function probe(config) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(here, 'bridge.mjs')], {
      env: { ...process.env, RDK_CAMERA_WORKSHOP_CONFIG: config, RDK_CAMERA_WORKSHOP_ONBOARDING: '0' }, stdio: ['pipe', 'pipe', 'ignore'],
    });
    let output = ''; let settled = false; let toolCount = 0; let chains = null;
    const finish = (error, result) => { if (settled) return; settled = true; clearTimeout(timer); child.kill(); error ? reject(error) : resolve(result); };
    const timer = setTimeout(() => finish(new Error('camera_setup_probe_timeout')), 20_000);
    child.on('error', () => finish(new Error('camera_setup_bridge_start_failed')));
    child.stdout.on('data', chunk => {
      output += chunk;
      if (Buffer.byteLength(output) > 1024 * 1024) return finish(new Error('camera_setup_response_too_large'));
      while (output.includes('\n')) {
        const end = output.indexOf('\n'); const line = output.slice(0, end); output = output.slice(end + 1);
        let message; try { message = JSON.parse(line); } catch { return finish(new Error('camera_setup_response_invalid')); }
        if (message.error) return finish(new Error(wireErrorCode(message.error.message)));
        if (message.id === 0) {
          child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
          child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list', params: {} }) + '\n');
        }
        if (message.id === 1) {
          if (!Array.isArray(message.result?.tools)) return finish(new Error('camera_setup_response_invalid'));
          const names = message.result.tools.map(tool => tool.name);
          if (!names.some(name => name !== 'vision_connection_status')) return finish(new Error('camera_setup_no_remote_tools'));
          toolCount = names.length; chains = chainReadiness(names);
          if (!names.includes('vision_workshop_runtime_status')) return finish(null, { status: 'tools_available', toolCount: names.length, runtime: 'unverified', hardware: 'unverified', chains });
          child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'vision_workshop_runtime_status', arguments: {} } }) + '\n');
        }
        if (message.id === 2) {
          // Do not echo upstream bodies: they may contain device addresses or private runtime details.
          if (message.result?.isError || !message.result || !Array.isArray(message.result.content)) return finish(new Error('camera_setup_runtime_unavailable'));
          finish(null, { status: 'connected', toolCount, runtime: 'responded', hardware: 'unverified', chains, next: connectedNext(chains) });
        }
      }
    });
    child.on('close', () => finish(new Error('camera_setup_bridge_closed')));
    child.stdin.on('error', () => {});
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: 0, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'camera-connection-doctor', version: '1.0.0' } } }) + '\n');
  });
}
// Wire messages carry "code: hint"; the CLI contract keys advice and exit paths on the bare code.
export function wireErrorCode(message) {
  const match = typeof message === 'string' && /^camera_(?:bridge|setup)_[a-z0-9_]+/.exec(message);
  return match ? match[0] : 'camera_setup_response_invalid';
}
export async function doctor(config = resolveConfigPath()) {
  if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('camera_setup_node_22_required');
  await validateConfiguration(config);
  return probe(config);
}
export async function main(argv = process.argv.slice(2)) {
  const [command, ...rest] = argv; const options = {};
  for (let i = 0; i < rest.length; i += 2) {
    if (!['--url', '--auth', '--credential-file', '--config'].includes(rest[i]) || !rest[i + 1] || rest[i + 1].startsWith('--') || rest[i] in options) throw new Error('camera_setup_arguments_invalid');
    options[rest[i]] = rest[i + 1];
  }
  if (command === 'configure') return configure({ url: options['--url'], auth: options['--auth'], credentialFile: options['--credential-file'], config: options['--config'] });
  if (command === 'doctor' && Object.keys(options).every(key => key === '--config')) return doctor(options['--config']);
  if (command === 'client-config' && !rest.length) return clientConfig();
  if (command === 'help' || !command) return { usage: [
    'node mcp/setup.mjs configure --url SERVICE_MCP_URL --auth sso --credential-file ABSOLUTE_PRIVATE_FILE',
    'node mcp/setup.mjs doctor', 'node mcp/setup.mjs client-config',
  ], notes: 'configure 不覆盖已有配置，不接收 token；client-config 仅打印本机绝对路径配置，不修改宿主设置。' };
  throw new Error('camera_setup_arguments_invalid');
}
if (process.argv[1] && await realpath(process.argv[1]).catch(() => '') === fileURLToPath(import.meta.url)) {
  main().then(result => process.stdout.write(JSON.stringify(result, null, 2) + '\n')).catch(error => {
    // Only locally defined error codes; never print paths, URLs, secrets or raw OS errors.
    const code = /^camera_(?:bridge|setup)_[a-z0-9_]+$/.test(error.message) ? error.message : error.code === 'EEXIST' ? 'camera_setup_config_exists' : 'camera_setup_failed';
    console.error(JSON.stringify({ status: 'failed', code, advice: code === 'camera_setup_config_exists' ? '已有配置保持不变；如需新配置请指定另一 --config 路径。' : describeError(code) }));
    process.exitCode = 1;
  });
}
