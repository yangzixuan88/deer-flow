/**
 * @file test_yaml_loader.ts
 * @description RTCM YAML Loader 验证脚本
 * 验证所有 7 个配置文件能正确加载
 */

import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

// ESM 兼容的 __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 直接测试 js-yaml 加载
// @ts-ignore - js-yaml 自带类型定义
import yaml from 'js-yaml';

const CONFIG_ROOT = path.join(__dirname, '..', '..', '..', 'rtcm', 'config');

const CONFIG_FILES = [
  'role_registry.final.yaml',
  'agent_registry.rtcm.final.yaml',
  'issue_debate_protocol.final.yaml',
  'project_dossier_schema.final.yaml',
  'prompt_loader_and_assembly_spec.final.yaml',
  'runtime_orchestrator_spec.final.yaml',
  'feishu_rendering_spec.final.yaml',
];

interface ParseResult {
  file: string;
  success: boolean;
  error?: string;
  topLevelKeys: string[];
  rolesCount?: number;
  agentsCount?: number;
}

async function testYamlParsing(): Promise<ParseResult[]> {
  const results: ParseResult[] = [];

  for (const file of CONFIG_FILES) {
    const filePath = path.join(CONFIG_ROOT, file);
    const result: ParseResult = {
      file,
      success: false,
      topLevelKeys: [],
    };

    try {
      if (!fs.existsSync(filePath)) {
        result.error = `文件不存在: ${filePath}`;
        results.push(result);
        continue;
      }

      const content = fs.readFileSync(filePath, 'utf-8');
      const parsed = yaml.load(content, { filename: file }) as Record<string, unknown>;

      result.success = true;
      result.topLevelKeys = Object.keys(parsed);

      // 检查特定文件的特殊字段
      if (file === 'role_registry.final.yaml') {
        const roles = parsed['roles'];
        result.rolesCount = Array.isArray(roles) ? roles.length : 0;
      }
      if (file === 'agent_registry.rtcm.final.yaml') {
        const agents = (parsed as Record<string, unknown>)['agents'];
        result.agentsCount = Array.isArray(agents) ? agents.length : 0;
      }

    } catch (error) {
      result.success = false;
      result.error = error instanceof Error ? error.message : String(error);
    }

    results.push(result);
  }

  return results;
}

// 运行测试
async function main() {
  console.log('========================================');
  console.log('RTCM YAML Loader 验证');
  console.log('========================================\n');
  console.log(`配置目录: ${CONFIG_ROOT}\n`);

  const results = await testYamlParsing();

  let allPassed = true;
  for (const r of results) {
    const status = r.success ? '✅ PASS' : '❌ FAIL';
    console.log(`${status}: ${r.file}`);
    console.log(`       Top-level keys: ${r.topLevelKeys.join(', ')}`);
    if (r.rolesCount !== undefined) {
      console.log(`       Roles count: ${r.rolesCount}`);
    }
    if (r.agentsCount !== undefined) {
      console.log(`       Agents count: ${r.agentsCount}`);
    }
    if (r.error) {
      console.log(`       Error: ${r.error}`);
      allPassed = false;
    }
    console.log();
  }

  console.log('========================================');
  if (allPassed) {
    console.log('✅ 所有配置文件加载成功!');
  } else {
    console.log('❌ 部分配置文件加载失败');
    process.exit(1);
  }
}

main().catch(console.error);
