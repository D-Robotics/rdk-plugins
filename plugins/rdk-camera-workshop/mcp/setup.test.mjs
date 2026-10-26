import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, writeFile, readFile, chmod, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createServer } from 'node:http';
import { spawnSync } from 'node:child_process';
import { configure, doctor, clientConfig, wireErrorCode, chainReadiness } from './setup.mjs';

async function fixture(fn) {
  const directory = await mkdtemp(path.join(tmpdir(), 'camera-onboarding-'));
  const credentialFile = path.join(directory, 'credential'); const config = path.join(directory, 'connection.json');
  await writeFile(credentialFile, 'private-fixture-token', { mode: 0o600 });
  try { await fn({ directory, credentialFile, config }); } finally { await rm(directory, { recursive: true, force: true }); }
}
test('configure creates private validated config without overwriting existing files', async () => fixture(async ({ credentialFile, config }) => {
  const input = { url: 'http://127.0.0.1:9/api/ops/vision-workshop/mcp', auth: 'sso', credentialFile, config };
  assert.equal((await configure(input)).status, 'configured');
  assert.equal((await stat(config)).mode & 0o777, 0o600);
  const before = await readFile(config, 'utf8'); assert.equal(JSON.parse(before).auth.type, 'sso');
  await assert.rejects(configure({ ...input, auth: 'admin' }), { code: 'EEXIST' });
  assert.equal(await readFile(config, 'utf8'), before);
}));
test('invalid URL and public credential permissions cannot create a config', async () => fixture(async ({ credentialFile, config }) => {
  for (const url of ['http://external.invalid/api/ops/vision-workshop/mcp', 'https://example.invalid/wrong', 'https://example.invalid/api/ops/vision-workshop/mcp?secret=x']) {
    await assert.rejects(configure({ url, auth: 'sso', credentialFile, config }), /camera_bridge_url_invalid/);
    await assert.rejects(stat(config), { code: 'ENOENT' });
  }
  await chmod(credentialFile, 0o644);
  await assert.rejects(configure({ url: 'https://example.invalid/api/ops/vision-workshop/mcp', auth: 'admin', credentialFile, config }), /permissions_invalid/);
}));
test('doctor traverses actual stdio bridge and only calls read-only runtime status', async () => fixture(async ({ credentialFile, config }) => {
  const calls = [];
  const server = createServer(async (request, response) => {
    assert.equal(request.headers['x-rdk-sso-session'], 'private-fixture-token');
    let body = ''; for await (const part of request) body += part;
    const message = JSON.parse(body); calls.push(message);
    const result = message.method === 'tools/list' ? { tools: [{ name: 'vision_workshop_runtime_status', description: 'Runtime fixture', inputSchema: { type: 'object' } }] } : { content: [{ type: 'text', text: 'fixture-private-device-state' }], isError: false };
    response.setHeader('content-type', 'application/json'); response.end(JSON.stringify({ jsonrpc: '2.0', id: message.id, result }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    await configure({ url: 'http://127.0.0.1:' + server.address().port + '/api/ops/vision-workshop/mcp', auth: 'sso', credentialFile, config });
    const result = await doctor(config);
    assert.equal(result.status, 'connected'); assert.equal(result.hardware, 'unverified'); assert.equal(result.toolCount, 1);
    assert.deepEqual(calls.map(call => call.method), ['tools/list', 'tools/call']);
    assert.equal(calls[1].params.name, 'vision_workshop_runtime_status');
    assert.ok(!JSON.stringify(result).includes('fixture-private'));
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
}));
test('doctor distinguishes unconfigured, service refusal and tool execution errors', async () => fixture(async ({ credentialFile, config }) => {
  await assert.rejects(doctor(config), /unconfigured/);
  const server = createServer((_request, response) => { response.writeHead(403); response.end('private error'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    await configure({ url: 'http://127.0.0.1:' + server.address().port + '/api/ops/vision-workshop/mcp', auth: 'sso', credentialFile, config });
    await assert.rejects(doctor(config), /camera_bridge_remote_http_403/);
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
}));
test('fallback configuration uses executable and bridge absolute paths independent of cwd', () => {
  const config = clientConfig().mcpServers['rdk-camera-workshop'];
  assert.ok(path.isAbsolute(config.command)); assert.ok(path.isAbsolute(config.args[0]));
  const result = spawnSync(config.command, config.args, { cwd: tmpdir(), input: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2024-11-05' } }) + '\n', encoding: 'utf8' });
  assert.equal(result.status, 0); assert.equal(JSON.parse(result.stdout).result.protocolVersion, '2024-11-05');
});

test('wire messages with appended hints normalize to the bare CLI error code', () => {
  assert.equal(wireErrorCode('camera_bridge_remote_transport_failed: 无法访问相机服务，请检查服务运行状态、地址和网络。'), 'camera_bridge_remote_transport_failed');
  assert.equal(wireErrorCode('camera_bridge_unconfigured'), 'camera_bridge_unconfigured');
  assert.equal(wireErrorCode('camera_bridge_remote_http_403: 认证失效，请在原服务更新凭据后重试。'), 'camera_bridge_remote_http_403');
  assert.equal(wireErrorCode('Unexpected token < in JSON'), 'camera_setup_response_invalid');
  assert.equal(wireErrorCode(undefined), 'camera_setup_response_invalid');
});

test('chainReadiness names the missing typed tools per workflow without inventing a fallback', () => {
  const chains = chainReadiness(['vision_workshop_runtime_status', 'vision_camera_probe', 'vision_workshop_delivery']);
  assert.equal(chains.core.status, 'missing');
  assert.deepEqual(chains.core.missing, ['vision_experiment_create', 'vision_experiment_list', 'vision_experiment_get', 'vision_camera_readiness']);
  assert.equal(chains.bringup.status, 'missing');
  assert.ok(chains.bringup.missing.includes('vision_pipeline_validate'));
  assert.equal(chains.delivery.status, 'missing');
  assert.ok(chains.delivery.missing.includes('vision_acceptance_record'));
  const ready = chainReadiness(['vision_workshop_delivery', 'vision_delivery_target_select', 'vision_acceptance_plan_save', 'vision_acceptance_record', 'vision_workshop_export']);
  assert.equal(ready.delivery.status, 'ready');
  assert.ok(!('missing' in ready.delivery));
});

test('doctor reports per-chain readiness from the actual remote tools directory', async () => fixture(async ({ credentialFile, config }) => {
  const remoteTools = ['vision_workshop_runtime_status', 'vision_experiment_create', 'vision_experiment_list', 'vision_experiment_get', 'vision_camera_readiness',
    'vision_camera_knowledge_search', 'vision_camera_knowledge_get',
    'vision_camera_probe', 'vision_pipeline_validate', 'vision_camera_bringup', 'vision_camera_capture_frame', 'vision_camera_controls_get',
    'vision_ai_debug_start', 'vision_ai_debug_status', 'vision_ai_debug_cancel', 'vision_ai_debug_restore_original',
    'vision_raw_capture', 'vision_isp_generate', 'vision_isp_process_raw', 'vision_isp_apply', 'vision_isp_restore', 'vision_isp_tuning_get', 'vision_isp_tuning_load',
    'vision_calibration_task_create', 'vision_calibration_task_run', 'vision_calibration_task_result', 'vision_calibration_apply_plan', 'vision_calibration_apply',
    'vision_workshop_delivery', 'vision_workshop_export'];
  const server = createServer(async (request, response) => {
    let body = ''; for await (const part of request) body += part;
    const message = JSON.parse(body);
    const result = message.method === 'tools/list'
      ? { tools: remoteTools.map(name => ({ name, description: 'fixture', inputSchema: { type: 'object' } })) }
      : { content: [{ type: 'text', text: 'fixture-runtime-ok' }], isError: false };
    response.setHeader('content-type', 'application/json'); response.end(JSON.stringify({ jsonrpc: '2.0', id: message.id, result }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    await configure({ url: 'http://127.0.0.1:' + server.address().port + '/api/ops/vision-workshop/mcp', auth: 'sso', credentialFile, config });
    const result = await doctor(config);
    assert.equal(result.chains.core.status, 'ready');
    assert.equal(result.chains.knowledge.status, 'ready');
    assert.equal(result.chains.bringup.status, 'ready');
    assert.equal(result.chains.aiDebug.status, 'ready');
    assert.equal(result.chains.isp.status, 'ready');
    assert.equal(result.chains.calibration.status, 'ready');
    assert.equal(result.chains.delivery.status, 'missing');
    assert.deepEqual(result.chains.delivery.missing, ['vision_delivery_target_select', 'vision_acceptance_plan_save', 'vision_acceptance_record']);
    assert.ok(result.next.includes('升级服务端'));
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
}));
