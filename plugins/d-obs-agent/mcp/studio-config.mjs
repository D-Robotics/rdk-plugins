#!/usr/bin/env node
/** Generate importable Studio configuration; never modify the user's MCP registry. */
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { tools } from './bridge.mjs';
export function studioConfig({ node = process.execPath, bridge = fileURLToPath(new URL('./bridge.mjs', import.meta.url)), connectionFile } = {}) {
  if (![node, bridge].every(value => typeof value === 'string' && path.isAbsolute(value))) throw new Error('dobs_studio_absolute_paths_required');
  if (connectionFile !== undefined && !path.isAbsolute(connectionFile)) throw new Error('dobs_studio_absolute_config_required');
  return { mcpServers: { 'd-obs-agent': { transport: 'stdio', command: node, args: [bridge], requestTimeoutMs: 270000,
    ...(connectionFile ? { env: { DOBS_AGENT_CONFIG: connectionFile } } : {}),
    permissions: { default: 'deny', tools: Object.fromEntries(tools.map(tool => [tool.name, 'readonly'])) } } } };
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.length > 3) throw new Error('Usage: node mcp/studio-config.mjs [absolute-private-connection-file]');
  process.stdout.write(JSON.stringify(studioConfig({ connectionFile: process.argv[2] }), null, 2) + '\n');
}
