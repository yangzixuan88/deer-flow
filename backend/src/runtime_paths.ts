import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const DEERFLOW_ROOT = path.resolve(process.env.DEERFLOW_ROOT || path.join(__dirname, '..', '..'));
export const DEERFLOW_RUNTIME_ROOT = path.resolve(
  process.env.DEERFLOW_RUNTIME_ROOT || path.join(DEERFLOW_ROOT, '.deerflow')
);

export function runtimePath(...segments: string[]): string {
  return path.join(DEERFLOW_RUNTIME_ROOT, ...segments);
}

export function upgradeCenterStateDir(): string {
  return runtimePath('upgrade-center', 'state');
}
