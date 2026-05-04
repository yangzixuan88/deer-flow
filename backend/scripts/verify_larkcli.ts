#!/usr/bin/env ts-node
/**
 * 飞书CLI集成验证脚本
 * 用于手动验证lark-cli配置是否正确
 */

import { spawn } from 'child_process';
import { larkCLIAdapter } from '../src/domain/m11/adapters/lark_cli_adapter';

async function main() {
  console.log('===========================================');
  console.log('飞书CLI集成验证');
  console.log('===========================================\n');

  // 1. 检查lark-cli可用性
  console.log('[1/5] 检查lark-cli可用性...');
  const available = await larkCLIAdapter.isAvailable();
  console.log(`  lark-cli可用: ${available}`);
  if (!available) {
    console.error('  错误: lark-cli未正确安装或配置');
    process.exit(1);
  }

  // 2. 列出配置的profile
  console.log('\n[2/5] 检查配置的Bot Profile...');
  const profiles = larkCLIAdapter.getProfiles();
  console.log(`  已配置Profile数量: ${profiles.length}`);
  profiles.forEach((p, i) => {
    console.log(`  ${i + 1}. ${p}`);
  });

  // 3. 检查默认profile
  console.log('\n[3/5] 检查默认Profile...');
  const defaultProfile = larkCLIAdapter.getDefaultProfile();
  console.log(`  默认Profile: ${defaultProfile}`);

  // 4. 执行calendar agenda测试
  console.log('\n[4/5] 执行日历议程测试...');
  try {
    const calendarResult = await larkCLIAdapter.execute('calendar +agenda --days 1', {
      profile: 'daguan_zhu',
      timeout_ms: 30000,
      as_bot: true,
    });
    console.log(`  执行成功: ${calendarResult.success}`);
    console.log(`  退出码: ${calendarResult.exit_code}`);
    console.log(`  执行时间: ${calendarResult.execution_time_ms}ms`);
    if (calendarResult.stdout) {
      const parsed = calendarResult.parsed_output || calendarResult.stdout;
      console.log(`  输出: ${JSON.stringify(parsed).substring(0, 200)}...`);
    }
  } catch (e: any) {
    console.error(`  测试失败: ${e.message}`);
  }

  // 5. 测试消息历史查询
  console.log('\n[5/5] 测试消息历史查询...');
  try {
    const msgResult = await larkCLIAdapter.execute('im messages list --chat-id oc_test --count 1', {
      profile: 'daguan_zhu',
      timeout_ms: 15000,
      as_bot: true,
    });
    console.log(`  执行成功: ${msgResult.success}`);
    console.log(`  退出码: ${msgResult.exit_code}`);
  } catch (e: any) {
    console.log(`  测试跳过(可能无权限): ${e.message}`);
  }

  console.log('\n===========================================');
  console.log('验证完成');
  console.log('===========================================');
}

main().catch(console.error);
