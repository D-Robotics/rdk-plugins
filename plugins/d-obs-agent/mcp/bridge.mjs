#!/usr/bin/env node
/** Read-only d-obs MCP adapter. Node >=22; no dependencies. */
import { open, realpath } from 'node:fs/promises';
import { constants } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';
const API = '/api/ops/observability/assistant';
const LIMIT = 8 * 1024 * 1024;
const INPUT_LIMIT = 128 * 1024;
const record = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const only = (v, keys) => record(v) && Object.keys(v).every(k => keys.includes(k));
const error = code => { throw new Error(code); };
const schema = (properties, required = []) => ({ type: 'object', properties, required, additionalProperties: false });
const string = { type: 'string', minLength: 1 };
const tool = (name, description, inputSchema) => ({ name, description, inputSchema, annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: name !== 'dobs_ask', openWorldHint: true } });
export const tools = [
  tool('dobs_status', '检查真实连接、身份可见查询数量与平台 AI 模型状态；失败时报告真实错误。', schema({})),
  tool('dobs_ask', '用中文对话查询平台数据，复用平台 AI 助手。支持持久化的服务用 taskId 追问；旧服务用 history 追问。', schema({ message: string, taskId: string, context: { type: 'object' }, history: { type: 'array', maxItems: 12, items: { type: 'object', properties: { role: { enum: ['user', 'assistant'] }, content: string }, required: ['role', 'content'], additionalProperties: false } } }, ['message'])),
  tool('dobs_capabilities', '发现当前身份可查询的全部模块、准确 operationId 和参数说明，可按 group/search 筛选。', schema({ group: string, search: string })),
  tool('dobs_query', '执行目录返回的只读 operationId，查询指标、日志、链路、设备、告警、用户、模型池等真实数据。禁止写入。', schema({ operationId: string, params: { type: 'object' }, query: { type: 'object' }, body: { type: 'object' } }, ['operationId'])),
  tool('dobs_tasks', '列出本身份的对话任务；提供 taskId 时恢复该任务历史和查询回执。', schema({ taskId: string })),
];
async function privateText(filename, limit) {
  if (typeof filename !== 'string' || !path.isAbsolute(filename)) error('dobs_private_path_invalid');
  const resolved = await realpath(filename);
  const packageRoot = await realpath(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'));
  const relative = path.relative(packageRoot, resolved);
  if (!relative || !relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative)) error('dobs_private_file_inside_plugin');
  const handle = await open(resolved, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const stat = await handle.stat();
    if (!stat.isFile() || stat.size > limit || process.platform !== 'win32' && ((stat.mode & 0o777) !== 0o600 || stat.uid !== process.getuid())) error('dobs_private_file_invalid');
    const bytes = await handle.readFile();
    if (bytes.length > limit) error('dobs_private_file_too_large');
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } finally { await handle.close(); }
}
export async function loadConnection(filename = process.env.DOBS_AGENT_CONFIG || path.join(homedir(), '.config/d-obs-agent/connection.json')) {
  const config = JSON.parse(await privateText(filename, 16384));
  if (!only(config, ['url', 'auth', 'tenant', 'timeoutMs']) || !only(config.auth, ['type', 'credentialFile']) || !['admin', 'sso', 'tenant'].includes(config.auth.type)) error('dobs_config_invalid');
  const url = new URL(config.url);
  if (!['https:', 'http:'].includes(url.protocol) || url.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    || url.username || url.password || url.search || url.hash || /[\u0000-\u0020\u007f\\%]/.test(config.url)
    || !url.pathname.endsWith('/api/ops/mcp')) error('dobs_url_invalid');
  if (config.tenant !== undefined && (typeof config.tenant !== 'string' || !/^[a-zA-Z0-9_-]{1,128}$/.test(config.tenant))) error('dobs_tenant_invalid');
  const timeoutMs = config.timeoutMs ?? 240000;
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 300000) error('dobs_timeout_invalid');
  const credential = (await privateText(config.auth.credentialFile, 16384)).trim();
  if (!credential || /[\u0000-\u0020\u007f]/.test(credential)) error('dobs_credential_invalid');
  return { url: url.href, prefix: url.href.slice(0, -'/api/ops/mcp'.length), timeoutMs, credential, tenant: config.tenant,
    header: { admin: 'x-admin-token', sso: 'x-rdk-sso-session', tenant: 'x-tenant-token' }[config.auth.type] };
}
async function request(config, endpoint, body) {
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), config.timeoutMs);
  try {
    const response = await fetch(config.prefix + endpoint, { method: body === undefined ? 'GET' : 'POST', redirect: 'error', signal: controller.signal,
      headers: { accept: 'application/json', 'content-type': 'application/json', [config.header]: config.credential,
        'x-rdk-ops-read-only': '1', 'x-rdk-ops-action': 'observability', ...(config.tenant ? { 'x-rdk-obs-tenant': config.tenant } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    if (!response.ok) error('dobs_http_' + response.status);
    if (!response.body || !response.headers.get('content-type')?.includes('application/json')) error('dobs_response_invalid');
    const reader = response.body.getReader(); const chunks = []; let size = 0;
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > LIMIT) { controller.abort(); error('dobs_response_too_large'); }
      chunks.push(Buffer.from(value));
    }
    const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (!record(value) || value.ok === false) error('dobs_remote_failed');
    // Never return the active credential even if it appears in a backend error/log.
    return JSON.parse(JSON.stringify(value, (_key, item) => typeof item === 'string' ? item.split(config.credential).join('[redacted]') : item));
  } catch (e) {
    if (/^dobs_[a-z0-9_]+$/.test(e.message)) throw e;
    error('dobs_transport_or_response_failed');
  } finally { clearTimeout(timer); }
}
export async function callTool(name, args, config) {
  const definition = tools.find(t => t.name === name);
  if (!definition || !only(args, Object.keys(definition.inputSchema.properties))) error('dobs_invalid_arguments');
  for (const [key, value] of Object.entries(args)) {
    const expected = definition.inputSchema.properties[key].type;
    if (expected === 'array') {
      if (!Array.isArray(value) || value.length > 12 || value.some(item => !only(item, ['role', 'content']) || !['user', 'assistant'].includes(item.role) || typeof item.content !== 'string' || item.content.length > 8000)) error('dobs_invalid_arguments');
      continue;
    }
    if (expected === 'string' ? typeof value !== 'string' || !value.trim() || value.length > 16000 : !record(value)) error('dobs_invalid_arguments');
  }
  if (definition.inputSchema.required.some(key => args[key] === undefined)) error('dobs_invalid_arguments');
  config ??= await loadConnection();
  if (name === 'dobs_tasks') return request(config, API + '/tasks' + (args.taskId ? '/' + encodeURIComponent(args.taskId) : ''));
  // Refuse old servers before any execution: all query paths require server-side read-only support.
  const capabilities = await request(config, API + '/capabilities');
  if (capabilities.readOnlyExecutionSupported !== true || !Array.isArray(capabilities.operations)
    || capabilities.operations.some(op => !record(op) || op.mutating !== false || typeof op.id !== 'string')) error('dobs_read_only_contract_required');
  if (name === 'dobs_status') return { connected: true, readOnly: true, modelEnabled: capabilities.modelEnabled === true,
    taskPersistenceSupported: capabilities.taskPersistenceSupported === true, operationCount: capabilities.operations.length,
    groups: [...new Set(capabilities.operations.map(op => op.group))] };
  if (name === 'dobs_capabilities') return { operations: capabilities.operations.filter(op => (!args.group || op.group === args.group)
    && (!args.search || JSON.stringify(op).toLowerCase().includes(args.search.toLowerCase()))) };
  if (name === 'dobs_ask') {
    if (!capabilities.modelEnabled) error('dobs_platform_model_unavailable_use_capabilities_and_query');
    if (capabilities.taskPersistenceSupported !== true) {
      if (args.taskId) error('dobs_task_persistence_unavailable_use_history');
      const result = await request(config, API + '/chat', args);
      return { ...result, conversationMode: 'client-history', taskPersistenceSupported: false };
    }
    const result = await request(config, API + '/chat', { ...args, taskId: args.taskId ?? null });
    if (!record(result.task) || typeof result.task.id !== 'string') error('dobs_task_response_invalid');
    return { ...result, taskId: result.task.id };
  }
  if (!capabilities.operations.some(op => op.id === args.operationId && op.mutating === false)) error('dobs_operation_denied');
  const result = await request(config, '/api/ops/mcp', { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'execute_platform_operation', arguments: args } });
  if (result.jsonrpc !== '2.0' || result.id !== 1 || result.error || !record(result.result)) error('dobs_mcp_response_invalid');
  return result.result;
}
const rpcError = (id, code, message) => ({ jsonrpc: '2.0', id: id ?? null, error: { code, message } });
export async function dispatch(message) {
  if (!record(message) || message.jsonrpc !== '2.0' || typeof message.method !== 'string'
    || message.id !== undefined && typeof message.id !== 'string' && !(typeof message.id === 'number' && Number.isFinite(message.id))) return rpcError(null, -32600, 'invalid request');
  if (message.id === undefined) return null;
  const { id, method } = message; const params = message.params ?? {};
  if (!record(params)) return rpcError(id, -32602, 'invalid params');
  if (method === 'initialize') return { jsonrpc: '2.0', id, result: { protocolVersion: ['2024-11-05', '2025-03-26', '2025-06-18'].includes(params.protocolVersion) ? params.protocolVersion : '2025-06-18', capabilities: { tools: {} }, serverInfo: { name: 'd-obs-agent', version: '0.1.0' } } };
  if (method === 'ping') return { jsonrpc: '2.0', id, result: {} };
  if (method === 'tools/list') return { jsonrpc: '2.0', id, result: { tools } };
  if (method !== 'tools/call') return rpcError(id, -32601, 'unknown method');
  try {
    if (!only(params, ['name', 'arguments', '_meta'])) error('dobs_invalid_arguments');
    const value = await callTool(params.name, params.arguments ?? {});
    // Preserve MCP tool failures rather than wrapping them as success.
    return { jsonrpc: '2.0', id, result: value.content ? value : { content: [{ type: 'text', text: JSON.stringify(value) }], isError: false } };
  } catch (e) {
    return { jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: /^dobs_[a-z0-9_]+$/.test(e.message) ? e.message : 'dobs_configuration_or_connection_unavailable' }], isError: true } };
  }
}
export async function runBridge() {
  let pending = Buffer.alloc(0); let oversized = false;
  async function output(value) { if (value && !process.stdout.write(JSON.stringify(value) + '\n')) await once(process.stdout, 'drain'); }
  async function line() {
    if (oversized) await output(rpcError(null, -32600, 'dobs_input_too_large'));
    else if (pending.length) {
      let message;
      try { message = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(pending)); }
      catch { await output(rpcError(null, -32700, 'parse error')); return; }
      await output(await dispatch(message));
    }
  }
  for await (const chunk of process.stdin) {
    let start = 0;
    for (let i = 0; i <= chunk.length; i++) {
      if (i !== chunk.length && chunk[i] !== 10) continue;
      if (!oversized) {
        const fragment = chunk.subarray(start, i);
        if (pending.length + fragment.length > INPUT_LIMIT) { pending = Buffer.alloc(0); oversized = true; }
        else pending = Buffer.concat([pending, fragment]);
      }
      if (i !== chunk.length) { await line(); pending = Buffer.alloc(0); oversized = false; }
      start = i + 1;
    }
  }
  await line();
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) runBridge().catch(() => { process.stderr.write('dobs_stdio_failed\n'); process.exitCode = 1; });
