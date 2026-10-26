import assert from 'node:assert/strict';
import { test, before, after, beforeEach } from 'node:test';
import { createServer } from 'node:http';
import { mkdtemp, writeFile, chmod, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { callTool, dispatch, loadConnection } from './bridge.mjs';
let server, origin, dir, config, seen = [], old = false, model = true, rpcFailure = false, redirect = false, large = false, persistent = true;
const operation = { id: 'GET /api/ops/observability/test', mutating: false, group: 'test', parameters: {} };
const post = { id: 'POST /api/ops/observability/boards/query', mutating: false, group: 'boards' };
before(async () => {
  server = createServer(async (req, res) => {
    let body = ''; for await (const chunk of req) body += chunk;
    seen.push({ url: req.url, headers: req.headers, body: body ? JSON.parse(body) : undefined });
    if (redirect) { res.writeHead(302, { location: origin + '/leak' }); res.end(); return; }
    res.setHeader('content-type', 'application/json');
    if (req.headers['x-admin-token'] !== 'fixture-private-token') { res.writeHead(403); res.end('{}'); return; }
    if (large) { res.end(JSON.stringify({ data: 'x'.repeat(9 * 1024 * 1024) })); return; }
    if (req.url.endsWith('/capabilities')) res.end(JSON.stringify({ ok: true, readOnlyExecutionSupported: !old, taskPersistenceSupported: persistent, modelEnabled: model, operations: [operation, post] }));
    else if (req.url.endsWith('/chat')) res.end(JSON.stringify({ ok: true, ...(persistent ? { task: { id: 'task-one' } } : {}), reply: 'fixture-private-token', operations: [{ id: operation.id, data: { sourceAvailability: { logs: 'unavailable' }, truncated: true } }] }));
    else if (req.url.endsWith('/mcp')) res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: { content: [{ type: 'text', text: 'real fixture result' }], isError: rpcFailure } }));
    else res.end(JSON.stringify({ ok: true, tasks: [], requested: req.url }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = 'http://127.0.0.1:' + server.address().port;
  dir = await mkdtemp(path.join(tmpdir(), 'dobs-agent-test-'));
  await writeFile(path.join(dir, 'token'), 'fixture-private-token\n', { mode: 0o600 });
  await writeFile(path.join(dir, 'connection.json'), JSON.stringify({ url: origin + '/dobs/api/ops/mcp', auth: { type: 'admin', credentialFile: path.join(dir, 'token') } }), { mode: 0o600 });
  config = await loadConnection(path.join(dir, 'connection.json'));
});
after(async () => { await new Promise(resolve => server.close(resolve)); await rm(dir, { recursive: true, force: true }); });
beforeEach(() => { seen = []; old = false; model = true; rpcFailure = false; redirect = false; large = false; persistent = true; });
test('real HTTP status keeps deployment prefix, authentication and read-only headers', async () => {
  const result = await callTool('dobs_status', {}, config);
  assert.equal(result.connected, true); assert.equal(result.operationCount, 2);
  assert.equal(seen[0].url, '/dobs/api/ops/observability/assistant/capabilities');
  assert.equal(seen[0].headers['x-rdk-ops-read-only'], '1');
});
test('catalog filtering and exact query preserve arguments and MCP failure', async () => {
  assert.equal((await callTool('dobs_capabilities', { group: 'boards' }, config)).operations.length, 1);
  rpcFailure = true;
  const result = await callTool('dobs_query', { operationId: operation.id, params: { id: 'a' }, query: { limit: 10 } }, config);
  assert.equal(result.isError, true);
  assert.deepEqual(seen.at(-1).body.params.arguments.query, { limit: 10 });
});
test('read-only POST query is supported with body and server read-only guard', async () => {
  await callTool('dobs_query', { operationId: post.id, body: { panels: [] } }, config);
  assert.deepEqual(seen.at(-1).body.params.arguments.body, { panels: [] });
  assert.equal(seen.at(-1).headers['x-rdk-ops-read-only'], '1');
});
test('mutation, fabricated operation and credential injection never reach executor', async () => {
  for (const args of [{ operationId: 'DELETE /api/ops/observability/test' }, { operationId: 'GET /unknown' }, { operationId: operation.id, headers: {} }]) {
    await assert.rejects(callTool('dobs_query', args, config), /dobs_(operation_denied|invalid_arguments)/);
  }
  assert.equal(seen.some(req => req.url.endsWith('/mcp')), false);
});
test('old server is refused before query or conversation', async () => {
  old = true;
  await assert.rejects(callTool('dobs_ask', { message: '查询错误' }, config), /read_only_contract/);
  await assert.rejects(callTool('dobs_query', { operationId: operation.id }, config), /read_only_contract/);
  assert.equal(seen.every(req => req.url.endsWith('/capabilities')), true);
});
test('conversation creates and resumes server tasks, preserving source failures and redacting active credential', async () => {
  const first = await callTool('dobs_ask', { message: '查询错误' }, config);
  assert.equal(first.reply, '[redacted]'); assert.equal(first.operations[0].data.truncated, true);
  assert.equal(seen.at(-1).body.taskId, null);
  await callTool('dobs_ask', { message: '然后呢', taskId: first.taskId }, config);
  assert.equal(seen.at(-1).body.taskId, 'task-one');
});
test('unavailable model blocks chat while exact queries remain usable', async () => {
  model = false;
  await assert.rejects(callTool('dobs_ask', { message: '查询' }, config), /model_unavailable/);
  await callTool('dobs_query', { operationId: operation.id }, config);
  assert.equal(seen.some(req => req.url.endsWith('/chat')), false);
});
test('tasks keep scope header and encode IDs without route traversal', async () => {
  await callTool('dobs_tasks', { taskId: 'a/b?c' }, { ...config, tenant: 'team-a' });
  assert.equal(seen[0].url, '/dobs/api/ops/observability/assistant/tasks/a%2Fb%3Fc');
  assert.equal(seen[0].headers['x-rdk-obs-tenant'], 'team-a');
});
test('redirects and oversized responses fail closed without retries', async () => {
  redirect = true;
  await assert.rejects(callTool('dobs_status', {}, config), /transport/);
  assert.equal(seen.length, 1);
  redirect = false; large = true;
  await assert.rejects(callTool('dobs_status', {}, config), /too_large/);
});
test('private configuration validation rejects non-private files and unsafe targets', async () => {
  const filename = path.join(dir, 'bad.json');
  for (const url of ['http://example.com/api/ops/mcp', origin + '/api/ops/mcp?token=x', origin + '/api/ops/not-mcp']) {
    await writeFile(filename, JSON.stringify({ url, auth: { type: 'admin', credentialFile: path.join(dir, 'token') } }), { mode: 0o600 });
    await assert.rejects(loadConnection(filename));
  }
  if (process.platform !== 'win32') {
    await chmod(filename, 0o644); await assert.rejects(loadConnection(filename), /private_file_invalid/);
  }
});
test('MCP notifications never execute and unknown tools fail', async () => {
  assert.equal(await dispatch({ jsonrpc: '2.0', method: 'tools/call', params: { name: 'dobs_ask', arguments: { message: 'x' } } }), null);
  assert.equal((await dispatch({ jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'unknown' } })).result.isError, true);
  assert.equal(seen.length, 0);
});
test('actual stdio process supports discovery, parse errors and request limits', async () => {
  const child = spawn(process.execPath, [fileURLToPath(new URL('./bridge.mjs', import.meta.url))], { stdio: ['pipe', 'pipe', 'pipe'] });
  let output = ''; child.stdout.on('data', chunk => output += chunk);
  const completed = new Promise(resolve => child.on('close', resolve));
  child.stdin.end('{broken}\n' + 'x'.repeat(130 * 1024) + '\n' + JSON.stringify({ jsonrpc: '2.0', id: 3, method: 'tools/list' }) + '\n');
  assert.equal(await completed, 0);
  const messages = output.trim().split('\n').map(line => JSON.parse(line));
  assert.equal(messages[0].error.code, -32700);
  assert.equal(messages[1].error.message, 'dobs_input_too_large');
  assert.equal(messages[2].result.tools.length, 5);
});

test('deployed legacy assistant supports natural-language queries and bounded followup history without taskId', async () => {
  persistent = false;
  const first = await callTool('dobs_ask', { message: '查询错误' }, config);
  assert.equal(first.conversationMode, 'client-history');
  assert.equal('taskId' in seen.at(-1).body, false);
  const history = [{ role: 'user', content: '查询错误' }, { role: 'assistant', content: '已查询' }];
  await callTool('dobs_ask', { message: '然后呢', history }, config);
  assert.deepEqual(seen.at(-1).body.history, history);
  await assert.rejects(callTool('dobs_ask', { message: 'x', taskId: 'unsupported' }, config), /use_history/);
  await assert.rejects(callTool('dobs_ask', { message: 'x', history: [{role:'system',content:'x'}] }, config), /invalid_arguments/);
});
