/**
 * @file rtcm_real_feishu_send_test.mjs
 * @description 飞书真实发送联调测试
 */

import { fileURLToPath } from 'url';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const TEST_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'test_artifacts');

// 多路径 env 加载
const possiblePaths = [
  path.join(os.homedir(), '.deerflow', 'projects', 'e--OpenClaw-Base-openclaw------', 'deerflow', 'backend', '.env'),
  path.join(os.homedir(), '.deerflow', 'projects', 'e--OpenClaw-Base-openclaw------', 'deerflow', 'backend', 'src', 'infrastructure', 'env_adapter', '.env'),
  path.join(process.cwd(), '.env'),
  'e:/OpenClaw-Base/deerflow/backend/.env',
];
for (const envFile of possiblePaths) {
  if (fs.existsSync(envFile)) {
    console.log(`Loading env from: ${envFile}`);
    fs.readFileSync(envFile, 'utf-8').split('\n').forEach(line => {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith('#')) {
        const [key, ...valueParts] = trimmed.split('=');
        if (key && valueParts.length) process.env[key] = valueParts.join('=');
      }
    });
    break;
  }
}

if (!fs.existsSync(TEST_DIR)) {
  fs.mkdirSync(TEST_DIR, { recursive: true });
}

async function testRealFeishuSend() {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║     飞书真实发送联调测试                                      ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  // 读取环境变量
  const appId = process.env.FEISHU_APP_ID;
  const appSecret = process.env.FEISHU_APP_SECRET;
  const chatId = process.env.FEISHU_DEFAULT_CHAT_ID;

  console.log('环境变量检查:');
  console.log(`  FEISHU_APP_ID: ${appId ? appId.slice(0, 8) + '...' : '❌ 未配置'}`);
  console.log(`  FEISHU_APP_SECRET: ${appSecret ? '✅ 已配置' : '❌ 未配置'}`);
  console.log(`  FEISHU_DEFAULT_CHAT_ID: ${chatId || '❌ 未配置'}`);
  console.log('');

  if (!appId || !appSecret || !chatId) {
    console.log('⚠️  跳过真实发送 - 缺少环境变量');
    console.log('  需要配置: FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_DEFAULT_CHAT_ID');
    console.log('  chat_id 应该是飞书群聊的 ID，不是 app_id\n');
    return;
  }

  // 动态导入 RTCM 模块
  console.log('加载 feishu_api_adapter...');
  const { feishuApiAdapter } = await import('./rtcm_feishu_api_adapter.ts');
  const { feishuCardRenderer } = await import('./feishu_card_renderer.ts');

  // 配置 API
  feishuApiAdapter.configure({ appId, appSecret, baseUrl: 'https://open.feishu.cn' });
  console.log('API 配置完成\n');

  // Test 1: Token 获取
  console.log('Test 1: 获取 Access Token...');
  try {
    const token = await feishuApiAdapter.getAccessToken();
    console.log(`  ✅ Token 获取成功: ${token.slice(0, 20)}...`);
  } catch (e) {
    console.log(`  ❌ Token 获取失败: ${e.message}`);
    return;
  }

  // Test 2: 发送卡片消息
  console.log('\nTest 2: 发送主会话启动卡片...');
  try {
    const cardPayload = {
      schema: '2.0',
      header: {
        title: {
          tag: 'plain_text',
          content: '🎬 RTCM 会议已启动',
        },
      },
      body: {
        elements: [
          { tag: 'markdown', content: '**议题**: 飞书真实发送联调测试\n**会话模式**: NEW' },
          { tag: 'hr' },
          { tag: 'markdown', content: '_主持官已就位，等待议员发言_' },
        ],
      },
    };

    console.log(`  发送到 chat_id: ${chatId}`);
    console.log(`  卡片类型: interactive`);

    const result = await feishuApiAdapter.sendCardMessage(chatId, cardPayload);

    console.log(`  ✅ 发送成功!`);
    console.log(`  message_id: ${result.message_id}`);
    console.log(`  create_time: ${result.create_time}`);

    // 落盘
    const sendResultFile = path.join(TEST_DIR, 'real_feishu_send.json');
    fs.writeFileSync(sendResultFile, JSON.stringify({
      timestamp: new Date().toISOString(),
      type: 'launch_card',
      receiveId: chatId,
      receiveIdType: 'chat_id',
      messageId: result.message_id,
      createTime: result.create_time,
      cardPayload,
    }, null, 2));
    console.log(`  📄 结果已落盘: ${sendResultFile}`);

  } catch (e) {
    console.log(`  ❌ 发送失败: ${e.message}`);
    if (e.message.includes('code: 99991663')) {
      console.log('  可能原因: app 没有发消息到该群聊的权限');
      console.log('  解决方案: 需要在飞书开放平台给应用开通该群聊的权限');
    }
  }

  // Test 3: 线程消息追加（如果创建了 chat_id）
  console.log('\nTest 3: 线程消息追加...');
  try {
    const roleMessage = {
      round: 1,
      stage: 'proposal',
      roleName: '先机议员',
      content: '这是一个测试消息，来自飞书真实发送联调',
      timestamp: new Date().toISOString(),
    };

    // 注意：这里只是演示结构，实际线程消息需要通过飞书消息 API 发送到线程
    console.log(`  角色消息结构已准备`);
    console.log(`  round: ${roleMessage.round}`);
    console.log(`  stage: ${roleMessage.stage}`);
    console.log(`  roleName: ${roleMessage.roleName}`);
    console.log(`  content: ${roleMessage.content}`);

    // 落盘
    const threadResultFile = path.join(TEST_DIR, 'real_feishu_thread.json');
    fs.writeFileSync(threadResultFile, JSON.stringify({
      timestamp: new Date().toISOString(),
      type: 'thread_append_test',
      chatId,
      roleMessage,
      note: '飞书消息需要通过 sendMessage API 发送到线程 ID',
    }, null, 2));
    console.log(`  📄 结果已落盘: ${threadResultFile}`);

  } catch (e) {
    console.log(`  ❌ 线程消息追加失败: ${e.message}`);
  }

  // Test 4: 健康检查
  console.log('\nTest 4: API 健康检查...');
  try {
    const health = await feishuApiAdapter.healthCheck();
    console.log(`  healthy: ${health.healthy}`);
    console.log(`  latencyMs: ${health.latencyMs}`);
    if (health.error) console.log(`  error: ${health.error}`);
  } catch (e) {
    console.log(`  ❌ 健康检查失败: ${e.message}`);
  }

  console.log('\n联调测试完成');
}

testRealFeishuSend().catch(console.error);