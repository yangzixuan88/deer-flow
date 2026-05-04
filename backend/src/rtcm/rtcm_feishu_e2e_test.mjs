/**
 * @file rtcm_feishu_e2e_test.mjs
 * @description 飞书真实发送 E2E 测试 - 使用本地 .env 配置
 */

import { fileURLToPath } from 'url';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';
import * as crypto from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const TEST_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'test_artifacts');

// 加载本地 .env 配置
function loadEnv() {
  // 尝试多个可能路径
  const possiblePaths = [
    path.join(os.homedir(), '.deerflow', 'projects', 'e--OpenClaw-Base-openclaw------', 'deerflow', 'backend', '.env'),
    path.join(os.homedir(), '.deerflow', 'projects', 'e--OpenClaw-Base-openclaw------', 'deerflow', 'backend', 'src', 'infrastructure', 'env_adapter', '.env'),
    path.join(process.cwd(), '.env'),
    'e:/OpenClaw-Base/deerflow/backend/.env',
  ];

  for (const envFile of possiblePaths) {
    if (fs.existsSync(envFile)) {
      console.log(`Loading env from: ${envFile}`);
      const content = fs.readFileSync(envFile, 'utf-8');
      content.split('\n').forEach(line => {
        const trimmed = line.trim();
        if (trimmed && !trimmed.startsWith('#')) {
          const [key, ...valueParts] = trimmed.split('=');
          if (key && valueParts.length) {
            process.env[key] = valueParts.join('=');
          }
        }
      });
      break;
    }
  }
}

loadEnv();

const appId = process.env.FEISHU_APP_ID;
const appSecret = process.env.FEISHU_APP_SECRET;
const chatId = process.env.FEISHU_DEFAULT_CHAT_ID;

console.log('╔════════════════════════════════════════════════════════════════╗');
console.log('║     飞书 E2E 真实发送测试 - 大主管为主机器人                   ║');
console.log('╚════════════════════════════════════════════════════════════════╝\n');

console.log('【环境变量】');
console.log(`  FEISHU_APP_ID: ${appId ? appId.slice(0, 12) + '...' : '❌ 未配置'}`);
console.log(`  FEISHU_APP_SECRET: ${appSecret ? '✅ 已配置' : '❌ 未配置'}`);
console.log(`  FEISHU_DEFAULT_CHAT_ID: ${chatId || '❌ 未配置'}`);

if (!appId || !appSecret) {
  console.log('\n❌ 缺少必需环境变量，无法测试');
  process.exit(1);
}

// 结果文件
const resultFile = path.join(TEST_DIR, 'feishu_e2e_result.json');
fs.mkdirSync(TEST_DIR, { recursive: true });

async function runTests() {
  const results = {
    timestamp: new Date().toISOString(),
    tests: [],
  };

  // Test 1: Token 获取
  console.log('\n【Test 1】获取 Access Token...');
  try {
    const { feishuApiAdapter } = await import('./rtcm_feishu_api_adapter.js');
    feishuApiAdapter.configure({ appId, appSecret, baseUrl: 'https://open.feishu.cn' });

    const token = await feishuApiAdapter.getAccessToken();
    console.log(`  ✅ Token: ${token.slice(0, 15)}...`);
    results.tests.push({ name: 'token_fetch', success: true, tokenPrefix: token.slice(0, 15) });
  } catch (e) {
    console.log(`  ❌ Token 获取失败: ${e.message}`);
    results.tests.push({ name: 'token_fetch', success: false, error: e.message });
    return;
  }

  // Test 2: 发送主会话启动卡片
  console.log('\n【Test 2】发送主会话启动卡片...');
  if (!chatId) {
    console.log('  ⚠️  FEISHU_DEFAULT_CHAT_ID 未配置，创建新群聊...');

    try {
      const { feishuApiAdapter } = await import('./rtcm_feishu_api_adapter.js');
      const chatResult = await feishuApiAdapter.createChat({
        name: `RTCM-Test-${Date.now()}`,
        description: '大主管测试群',
        chat_mode: 'group',
        chat_type: 'private',
      });

      const newChatId = chatResult.chat_id;
      console.log(`  ✅ 群聊创建成功: ${newChatId}`);

      const cardPayload = {
        schema: '2.0',
        header: {
          title: {
            tag: 'plain_text',
            content: '🎬 RTCM 会议已启动 - 大主管模式',
          },
        },
        body: {
          elements: [
            { tag: 'markdown', content: '**🤖 大主管已就位**\n\n主持 RTCM 圆桌讨论会议' },
            { tag: 'hr' },
            { tag: 'markdown', content: '**会话模式**: NEW\n**状态**: 等待议员加入' },
            { tag: 'markdown', content: '_主持官正在初始化会议框架_' },
          ],
        },
      };

      const sendResult = await feishuApiAdapter.sendCardMessage(newChatId, cardPayload);
      console.log(`  ✅ 卡片发送成功!`);
      console.log(`  message_id: ${sendResult.message_id}`);

      results.tests.push({
        name: 'create_chat_and_send_card',
        success: true,
        chatId: newChatId,
        messageId: sendResult.message_id,
      });

      // 保存 chatId 到环境变量文件供后续使用
      const envUpdateFile = path.join(os.homedir(), '.deerflow', 'rtcm', 'test_artifacts', 'feishu_env_update.txt');
      fs.writeFileSync(envUpdateFile, `FEISHU_DEFAULT_CHAT_ID=${newChatId}\n`);
      console.log(`  💾 chatId 已保存: ${envUpdateFile}`);

    } catch (e) {
      console.log(`  ❌ 创建群聊/发送卡片失败: ${e.message}`);
      results.tests.push({ name: 'create_chat_and_send_card', success: false, error: e.message });
    }
  } else {
    console.log(`  使用已有群聊: ${chatId}`);

    try {
      const { feishuApiAdapter } = await import('./rtcm_feishu_api_adapter.js');
      const { feishuCardRenderer } = await import('./rtcm_feishu_card_renderer.js');

      const sessionState = {
        session_id: `session-${Date.now()}`,
        current_stage: 'issue_definition',
        current_round: 0,
        active_members: ['大主管'],
        pending_user_acceptance: false,
        created_at: new Date().toISOString(),
        current_issue_id: null,
      };

      const cardPayload = feishuCardRenderer.renderProgressCard(sessionState, 'RTCM 会议已启动，等待议员发言');

      console.log(`  发送卡片到 chat_id: ${chatId}`);
      const sendResult = await feishuApiAdapter.sendCardMessage(chatId, cardPayload);
      console.log(`  ✅ 卡片发送成功!`);
      console.log(`  message_id: ${sendResult.message_id}`);

      results.tests.push({
        name: 'send_card_to_existing_chat',
        success: true,
        chatId,
        messageId: sendResult.message_id,
      });

    } catch (e) {
      console.log(`  ❌ 发送卡片失败: ${e.message}`);
      if (e.message.includes('99991663')) {
        console.log('  💡 权限不足: 应用可能没有发消息到该群聊的权限');
      }
      results.tests.push({ name: 'send_card_to_existing_chat', success: false, error: e.message });
    }
  }

  // Test 3: 健康检查
  console.log('\n【Test 3】API 健康检查...');
  try {
    const { feishuApiAdapter } = await import('./rtcm_feishu_api_adapter.js');
    const health = await feishuApiAdapter.healthCheck();
    console.log(`  healthy: ${health.healthy}, latency: ${health.latencyMs}ms`);
    results.tests.push({ name: 'health_check', success: health.healthy, ...health });
  } catch (e) {
    console.log(`  ❌ 健康检查失败: ${e.message}`);
    results.tests.push({ name: 'health_check', success: false, error: e.message });
  }

  // 保存结果
  fs.writeFileSync(resultFile, JSON.stringify(results, null, 2));
  console.log(`\n📄 结果已落盘: ${resultFile}`);

  // 总结
  const allPassed = results.tests.every(t => t.success);
  console.log(`\n${allPassed ? '🎉' : '⚠️'} 总体结果: ${allPassed ? '全部通过' : '部分失败'}`);
  results.tests.forEach(t => {
    console.log(`  ${t.success ? '✅' : '❌'} ${t.name}`);
  });
}

runTests().catch(console.error);