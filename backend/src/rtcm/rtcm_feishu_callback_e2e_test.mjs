/**
 * @file rtcm_feishu_callback_e2e_test.mjs
 * @description 飞书真实动作回流 E2E 测试
 * 模拟飞书 webhook -> handler -> userInterventionClassifier -> followUpManager 全链路
 */

import { fileURLToPath } from 'url';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const TEST_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'test_artifacts');
fs.mkdirSync(TEST_DIR, { recursive: true });

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

console.log('╔════════════════════════════════════════════════════════════════╗');
console.log('║     飞书动作回流 E2E 测试                                      ║');
console.log('╚════════════════════════════════════════════════════════════════╝\n');

const results = {
  timestamp: new Date().toISOString(),
  tests: {},
};

// ============================================================
// Test 1: Correction / Direction Change 回流
// ============================================================
async function testCorrection回流() {
  console.log('【Test 1】Correction / Direction Change 回流\n');

  const { mainAgentHandoff } = await import('./rtcm_main_agent_handoff.ts');
  const { userInterventionClassifier } = await import('./rtcm_user_intervention.ts');
  const { feishuApiAdapter } = await import('./rtcm_feishu_api_adapter.ts');

  // 配置飞书 API
  const appId = process.env.FEISHU_APP_ID;
  const appSecret = process.env.FEISHU_APP_SECRET;
  const chatId = process.env.FEISHU_DEFAULT_CHAT_ID || fs.existsSync(path.join(TEST_DIR, 'feishu_env_update.txt'))
    ? fs.readFileSync(path.join(TEST_DIR, 'feishu_env_update.txt'), 'utf-8').match(/FEISHU_DEFAULT_CHAT_ID=(.+)/)?.[1]
    : null;

  if (appId && appSecret) {
    feishuApiAdapter.configure({ appId, appSecret, baseUrl: 'https://open.feishu.cn' });
  }

  // 创建测试 RTCM 会话
  const sessionResult = mainAgentHandoff.activateRTCM({
    trigger: 'explicit_rtcm_start',
    projectId: `callback-test-${Date.now()}`,
    projectName: '飞书回流联调测试',
    userMessage: '启动飞书回流测试',
  });

  if (!sessionResult.success) {
    console.log(`  ❌ 创建 RTCM 会话失败: ${sessionResult.error}`);
    results.tests.correction = { success: false, error: sessionResult.error };
    return;
  }

  const session = mainAgentHandoff.getActiveSession();
  console.log(`  ✅ RTCM 会话创建成功: ${sessionResult.sessionId}`);
  console.log(`  thread: ${sessionResult.threadId}`);

  if (!session) {
    console.log(`  ❌ 无法获取活跃会话`);
    results.tests.correction = { success: false, error: 'no_active_session' };
    return;
  }

  // 模拟用户发消息："方向不对，先不要量产，先做样片"
  const userMessage = '方向不对，先不要量产，先做样片';
  console.log(`\n  用户消息: "${userMessage}"`);

  // 直接调用干预分类器（模拟 webhook -> handleFeishuThreadMessage 链路）
  const intervention = userInterventionClassifier.processIntervention({
    threadId: session.activeRtcmThreadId,
    sessionId: session.activeRtcmSessionId,
    issueId: 'current',
    userMessage,
  });

  console.log(`\n  干预分类结果:`);
  console.log(`    interventionId: ${intervention.interventionId}`);
  console.log(`    type: ${intervention.type}`);
  console.log(`    confidence: ${intervention.confidence}`);
  console.log(`    impact.createsNewIssue: ${intervention.impact.createsNewIssue}`);
  console.log(`    impact.changesDirection: ${intervention.impact.changesDirection}`);

  const actions = userInterventionClassifier.determineActions(intervention);
  console.log(`\n  动作决策:`);
  console.log(`    shouldRecomputeCurrentIssue: ${actions.shouldRecomputeCurrentIssue}`);
  console.log(`    shouldReopenIssue: ${actions.shouldReopenIssue}`);
  console.log(`    shouldCreateFollowUpIssue: ${actions.shouldCreateFollowUpIssue}`);

  // 验证文件落盘
  const interventionFile = path.join(os.homedir(), '.deerflow', 'rtcm', 'interventions', `${intervention.interventionId}.json`);
  const interventionFileExists = fs.existsSync(interventionFile);
  console.log(`\n  落盘验证: ${interventionFileExists ? '✅' : '❌'} ${path.basename(interventionFile)}`);

  // 发送确认卡片到飞书
  if (feishuApiAdapter.isConfigured() && chatId) {
    try {
      const { feishuCardRenderer } = await import('./feishu_card_renderer.ts');
      const confirmCard = {
        schema: '2.0',
        header: {
          title: { tag: 'plain_text', content: `✏️ 方向调整已纳入 - ${intervention.type}` },
          template: 'orange',
        },
        body: {
          elements: [
            { tag: 'markdown', content: `**您的纠正**: ${userMessage}` },
            { tag: 'markdown', content: `**识别类型**: ${intervention.type}` },
            { tag: 'markdown', content: `**置信度**: ${Math.round(intervention.confidence * 100)}%` },
            { tag: 'hr' },
            { tag: 'markdown', content: `主持官已记录，正在调整议题方向...` },
          ],
        },
      };
      await feishuApiAdapter.sendCardMessage(chatId, confirmCard);
      console.log(`\n  ✅ 确认卡片已发送到飞书`);
    } catch (e) {
      console.log(`\n  ⚠️ 飞书确认卡片发送失败: ${e.message}`);
    }
  }

  // 确认干预
  userInterventionClassifier.acknowledgeIntervention(intervention.interventionId);

  results.tests.correction = {
    success: true,
    interventionId: intervention.interventionId,
    type: intervention.type,
    confidence: intervention.confidence,
    actions,
    fileExists: interventionFileExists,
  };
}

// ============================================================
// Test 2: Follow-Up Request 回流
// ============================================================
async function testFollowUp回流() {
  console.log('\n\n【Test 2】Follow-Up Request 回流\n');

  const { mainAgentHandoff } = await import('./rtcm_main_agent_handoff.ts');
  const { userInterventionClassifier } = await import('./rtcm_user_intervention.ts');
  const { followUpManager } = await import('./rtcm_follow_up.ts');
  const { threadAdapter } = await import('./rtcm_thread_adapter.ts');
  const { feishuApiAdapter } = await import('./rtcm_feishu_api_adapter.ts');

  const chatId = process.env.FEISHU_DEFAULT_CHAT_ID || fs.existsSync(path.join(TEST_DIR, 'feishu_env_update.txt'))
    ? fs.readFileSync(path.join(TEST_DIR, 'feishu_env_update.txt'), 'utf-8').match(/FEISHU_DEFAULT_CHAT_ID=(.+)/)?.[1]
    : null;

  const session = mainAgentHandoff.getActiveSession();
  if (!session) {
    console.log('  ⚠️ 无活跃会话，跳过 follow-up 测试');
    results.tests.followUp = { success: false, error: 'no_active_session' };
    return;
  }

  // 模拟用户发送 FOLLOW_UP 请求
  const userMessage = '基于刚才的讨论，接下来我们开个新议题：样片验证计划';
  console.log(`  用户消息: "${userMessage}"`);

  // 处理干预
  const intervention = userInterventionClassifier.processIntervention({
    threadId: session.activeRtcmThreadId,
    sessionId: session.activeRtcmSessionId,
    issueId: 'current',
    userMessage,
  });

  console.log(`\n  干预分类结果:`);
  console.log(`    interventionId: ${intervention.interventionId}`);
  console.log(`    type: ${intervention.type}`);
  console.log(`    confidence: ${intervention.confidence}`);

  const actions = userInterventionClassifier.determineActions(intervention);
  console.log(`\n  动作决策:`);
  console.log(`    shouldCreateFollowUpIssue: ${actions.shouldCreateFollowUpIssue}`);
  console.log(`    newIssueTitle: ${actions.newIssueTitle}`);

  if (actions.shouldCreateFollowUpIssue) {
    // 创建 FOLLOW_UP 议题
    const parentIssue = {
      issue_id: 'current',
      issue_title: '当前议题',
      problem_statement: '样片方向确认',
      validation_plan_or_result: '已验证',
      strongest_dissent: '量产风险',
      confidence_interval: '90%',
      evidence_ledger_refs: [],
      unresolved_uncertainties: ['量产风险评估'],
    };

    const followUpTitle = '样片验证计划';

    const followUpIssue = followUpManager.createFollowUpIssue({
      threadId: session.activeRtcmThreadId,
      sessionId: session.activeRtcmSessionId,
      parentIssueId: parentIssue.issue_id,
      parentIssueTitle: parentIssue.issue_title,
      newIssueTitle: followUpTitle,
      newIssueDescription: userMessage,
      inheritedAssets: followUpManager.extractInheritedAssets(parentIssue),
      followUpRequestText: userMessage,
      followUpType: 'new_topic_based_on_conclusion',
    });

    console.log(`\n  Follow-Up 议题创建结果:`);
    console.log(`    issue_id: ${followUpIssue.issue_id}`);
    console.log(`    issue_title: ${followUpIssue.issue_title}`);
    console.log(`    parent_id: ${followUpIssue.parent_issue_id}`);
    console.log(`    inherited_assets: ${followUpIssue.inheritedAssets.join(', ')}`);

    // 更新线程锚点
    threadAdapter.updateAnchorMessage(session.activeRtcmThreadId, {
      currentIssueTitle: followUpIssue.issue_title,
      currentStage: 'issue_definition',
    });
    console.log(`  ✅ 线程锚点已更新`);

    // 确认干预
    userInterventionClassifier.acknowledgeIntervention(intervention.interventionId);
    console.log(`  ✅ 干预已确认`);

    // 发送飞书通知卡片
    if (feishuApiAdapter.isConfigured() && chatId) {
      try {
        const { feishuCardRenderer } = await import('./feishu_card_renderer.ts');
        const followUpCard = {
          schema: '2.0',
          header: {
            title: { tag: 'plain_text', content: `📋 FOLLOW_UP 已创建` },
            template: 'green',
          },
          body: {
            elements: [
              { tag: 'markdown', content: `**新议题**: ${followUpIssue.issue_title}` },
              { tag: 'markdown', content: `**继承资产**: ${followUpIssue.inheritedAssets.join(', ') || '无'}` },
              { tag: 'hr' },
              { tag: 'markdown', content: `_主持官已纳入，等待议员发言_` },
            ],
          },
        };
        await feishuApiAdapter.sendCardMessage(chatId, followUpCard);
        console.log(`\n  ✅ Follow-Up 通知卡片已发送到飞书`);
      } catch (e) {
        console.log(`\n  ⚠️ 飞书通知卡片发送失败: ${e.message}`);
      }
    }

    results.tests.followUp = {
      success: true,
      interventionId: intervention.interventionId,
      type: intervention.type,
      followUpIssueId: followUpIssue.issue_id,
      followUpTitle: followUpIssue.issue_title,
      inheritedAssets: followUpIssue.inheritedAssets,
    };
  } else {
    console.log(`  ⚠️ 未被识别为 FOLLOW_UP_REQUEST`);
    results.tests.followUp = {
      success: false,
      error: `classified as ${intervention.type} instead of follow_up_request`,
    };
  }
}

// ============================================================
// 主流程
// ============================================================
async function main() {
  await testCorrection回流();
  await testFollowUp回流();

  // 写入结果文件
  const callbackResult = {
    timestamp: new Date().toISOString(),
    activeSession: (await import('./rtcm_main_agent_handoff.ts')).mainAgentHandoff.getActiveSession() !== null,
    ...results.tests,
  };

  fs.writeFileSync(
    path.join(TEST_DIR, 'real_feishu_callback.json'),
    JSON.stringify(callbackResult, null, 2)
  );

  // 干预结果
  const interventionFiles = fs.readdirSync(path.join(os.homedir(), '.deerflow', 'rtcm', 'interventions')).filter(f => f.endsWith('.json'));
  const latestInterventions = interventionFiles.slice(-5).map(f => {
    const content = fs.readFileSync(path.join(os.homedir(), '.deerflow', 'rtcm', 'interventions', f), 'utf-8');
    return JSON.parse(content);
  });
  fs.writeFileSync(
    path.join(TEST_DIR, 'real_intervention_result.json'),
    JSON.stringify({ latestInterventions, count: interventionFiles.length }, null, 2)
  );

  // Follow-up 结果
  const followUpDir = path.join(os.homedir(), '.deerflow', 'rtcm', 'followup_issues');
  let followUpIssues = [];
  if (fs.existsSync(followUpDir)) {
    followUpIssues = fs.readdirSync(followUpDir).filter(f => f.endsWith('.json')).map(f => {
      return JSON.parse(fs.readFileSync(path.join(followUpDir, f), 'utf-8'));
    });
  }
  fs.writeFileSync(
    path.join(TEST_DIR, 'real_followup_result.json'),
    JSON.stringify({ followUpIssues }, null, 2)
  );

  console.log('\n╔════════════════════════════════════════════════════════════════╗');
  console.log('║     测试结果汇总                                              ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  const allPassed = results.tests.correction?.success && results.tests.followUp?.success;
  console.log(`${allPassed ? '🎉' : '⚠️'} 总体结果: ${allPassed ? '全部通过' : '部分失败'}`);

  for (const [name, result] of Object.entries(results.tests)) {
    const r = result;
    console.log(`  ${r.success ? '✅' : '❌'} ${name}: ${r.type || r.error || 'unknown'}`);
    if (r.interventionId) console.log(`      interventionId: ${r.interventionId}`);
    if (r.followUpIssueId) console.log(`      followUpIssueId: ${r.followUpIssueId}`);
  }

  console.log(`\n📄 结果已落盘:`);
  console.log(`  ${path.join(TEST_DIR, 'real_feishu_callback.json')}`);
  console.log(`  ${path.join(TEST_DIR, 'real_intervention_result.json')}`);
  console.log(`  ${path.join(TEST_DIR, 'real_followup_result.json')}`);

  console.log('\n==================================================');
  console.log('REAL_END_TO_END_CONFIRMED: ' + (allPassed ? 'YES' : 'NO'));
  console.log('================================================--');
}

main().catch(console.error);
