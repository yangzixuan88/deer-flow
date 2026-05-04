/**
 * @file test_yaml_loader.mjs
 * @description RTCM YAML Loader 验证脚本 (ESM)
 */

import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';
import yaml from 'js-yaml';

// ESM 兼容的 __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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

async function testYamlParsing() {
  console.log('========================================');
  console.log('RTCM YAML Loader 验证');
  console.log('========================================\n');
  console.log(`配置目录: ${CONFIG_ROOT}\n`);

  let allPassed = true;

  for (const file of CONFIG_FILES) {
    const filePath = path.join(CONFIG_ROOT, file);

    try {
      if (!fs.existsSync(filePath)) {
        console.log(`❌ FAIL: ${file} - 文件不存在`);
        allPassed = false;
        continue;
      }

      const content = fs.readFileSync(filePath, 'utf-8');
      const parsed = yaml.load(content, { filename: file });

      console.log(`✅ PASS: ${file}`);
      console.log(`       Top-level keys: ${Object.keys(parsed).join(', ')}`);

      if (file === 'role_registry.final.yaml' && parsed.roles) {
        console.log(`       Roles count: ${Array.isArray(parsed.roles) ? parsed.roles.length : 0}`);
      }
      if (file === 'agent_registry.rtcm.final.yaml' && parsed.agents) {
        console.log(`       Agents count: ${Array.isArray(parsed.agents) ? parsed.agents.length : 0}`);
      }

    } catch (error) {
      console.log(`❌ FAIL: ${file}`);
      console.log(`       Error: ${error instanceof Error ? error.message : String(error)}`);
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

testYamlParsing().catch(console.error);
