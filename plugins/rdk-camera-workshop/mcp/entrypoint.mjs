import { realpathSync } from 'node:fs';
import { relative } from 'node:path';
import { fileURLToPath } from 'node:url';

export function isEntrypoint(meta) {
  if (typeof meta.main === 'boolean') return meta.main;
  if (!process.argv[1]) return false;
  try {
    const resolved = name => realpathSync.native(name);
    return relative(resolved(process.argv[1]), resolved(fileURLToPath(meta.url))) === '';
  } catch {
    return false;
  }
}
