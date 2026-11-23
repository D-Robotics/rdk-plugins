#!/usr/bin/env node
// Print configuration for the two MCP entries present in this installed package.
import { existsSync, readFileSync, realpathSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
export function studioConfig(node = process.execPath) {
  const {mcpServers} = JSON.parse(readFileSync(path.join(root, '.mcp.json'), 'utf8'));
  const names = ['RDK_CAMERA_WORKSHOP_CONFIG', 'RDK_VISION_COURSE_TRAINING_RECEIPT', 'RDK_VISION_COURSE_BOARD_ARCHIVE',
    'RDK_VISION_COURSE_PRESET_BOARD_ARCHIVE', 'RDK_VISION_ROBOGO_TRAINING_PROFILE', 'RDK_VISION_COURSE_SESSION_DIR', 'RDK_VISION_COURSE_PREVIOUS_SESSION'];
  const paths = Object.fromEntries(names.filter(key => process.env[key]).map(key => [key, process.env[key]]));
  for (const entry of Object.values(mcpServers)) {
    entry.command = node;
    entry.args = [path.resolve(root, entry.args[0])];
    entry.env = {...entry.env, ...paths};
    if (process.versions.electron) entry.env.ELECTRON_RUN_AS_NODE = '1';
  }
  return {mcpServers};
}
const entry = process.argv[1];
if (entry && existsSync(entry) && import.meta.url === pathToFileURL(realpathSync(entry)).href) {
  console.log(JSON.stringify(studioConfig(), null, 2));
}
