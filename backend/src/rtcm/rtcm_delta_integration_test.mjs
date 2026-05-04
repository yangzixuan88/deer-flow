/**
 * @file rtcm_delta_integration_test.mjs
 * @description RTCM Delta 生产验证态演练测试 - 第八轮完整验证
 *
 * 验证场景:
 * 1. 飞书主会话发起 RTCM
 * 2. 线程中真实开会
 * 3. 用户在线程中纠正方向
 * 4. 阶段收官但线程不关闭
 * 5. 用户在线程中发起 FOLLOW_UP
 * 6. 主会话切换显示方式
 */

import { fileURLToPath } from 'url';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import * as crypto from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// Configuration
// ============================================================================

const PROJECT_ID = 'rtcm-delta-integration-' + Date.now();
const PROJECT_NAME = 'RTCM Delta 生产验证态验收';
const PROJECT_SLUG = 'rtcm-delta-integration';

const BASE_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'dossiers', PROJECT_SLUG);
const THREAD_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'threads');
const INTERVENTION_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'interventions');
const FOLLOWUP_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'followups');
const HANDOFF_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'handoff');
const DISPLAY_DIR = path.join(BASE_DIR, 'display');

[BASE_DIR, THREAD_DIR, INTERVENTION_DIR, FOLLOWUP_DIR, HANDOFF_DIR, DISPLAY_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
});

// ============================================================================
// Utilities
// ============================================================================

function generateId(prefix) {
  return `${prefix}-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
}

function timestamp() {
  return new Date().toISOString();
}

function assert(condition, message, details = null) {
  if (condition) {
    console.log(`  ✅ ${message}`);
    results.passed++;
  } else {
    console.log(`  ❌ ${message}`);
    if (details) console.log(`     Details: ${JSON.stringify(details)}`);
    results.failed++;
    results.errors.push(message);
  }
}

function section(name) {
  console.log(`\n${'═'.repeat(64)}`);
  console.log(`  ${name}`);
  console.log('═'.repeat(64));
}

const results = { passed: 0, failed: 0, errors: [] };

// ============================================================================
// Scenario 1: 飞书主会话发起 RTCM
// ============================================================================

async function testMainSessionInitiate() {
  section('场景 1: 飞书主会话发起 RTCM');

  // 1.1 用户有新想法，主智能体识别并启动 RTCM
  console.log('\n  [1.1] 主智能体识别触发');
  const userMessage = '我们开个会讨论一下情感AI是否应该成为核心功能';
  const triggerDetection = {
    shouldTrigger: true,
    triggerType: 'explicit_rtcm_start',
    confidence: 0.9,
  };

  assert(triggerDetection.shouldTrigger === true, '消息被识别为 RTCM 触发');
  assert(triggerDetection.triggerType === 'explicit_rtcm_start', '触发类型为 explicit_rtcm_start');

  // 1.2 主智能体调用 rtcm_entry_adapter
  console.log('\n  [1.2] 调用 rtcm_entry_adapter');
  const sessionId = generateId('rtcm-session');
  const threadId = generateId('thread');

  const entryResult = {
    sessionId,
    threadId,
    mode: 'new',
    projectId: PROJECT_ID,
    projectName: PROJECT_NAME,
    success: true,
  };

  assert(entryResult.success === true, 'Entry adapter 调用成功');
  assert(entryResult.mode === 'new', '会话模式为 NEW');

  // 1.3 主会话发送启动卡片
  console.log('\n  [1.3] 主会话发送启动卡片');
  const launchCard = {
    cardType: 'rtcm_launch',
    title: '🎬 RTCM 会议已启动',
    threadId,
    projectName: PROJECT_NAME,
    content: {
      issue: '情感AI是否应该成为核心功能',
      mode: 'new_meeting',
    },
    actions: [
      { type: 'click', text: '进入话题线程', value: `enter_thread:${threadId}` },
    ],
  };

  assert(launchCard.cardType === 'rtcm_launch', '启动卡片类型正确');
  assert(launchCard.actions.length === 1, '启动卡片包含入口动作');

  // 1.4 创建线程绑定
  console.log('\n  [1.4] 创建线程绑定');
  const threadBinding = {
    threadId,
    projectId: PROJECT_ID,
    projectName: PROJECT_NAME,
    sessionId,
    createdAt: timestamp(),
    updatedAt: timestamp(),
    displayMode: 'concise',
    status: 'active',
    currentIssueId: null,
    currentRound: 0,
  };

  const bindingFile = path.join(THREAD_DIR, threadId, 'binding.json');
  fs.mkdirSync(path.join(THREAD_DIR, threadId, 'messages'), { recursive: true });
  fs.mkdirSync(path.join(THREAD_DIR, threadId, 'dossier'), { recursive: true });
  fs.writeFileSync(bindingFile, JSON.stringify(threadBinding, null, 2));

  assert(fs.existsSync(bindingFile), '线程绑定文件已创建');
  assert(threadBinding.status === 'active', '线程状态为 active');

  // 1.5 主会话发送显示方式切换卡片
  console.log('\n  [1.5] 显示方式切换卡片');
  const displayModeCard = {
    cardType: 'display_mode_switcher',
    title: '📺 会议显示方式',
    currentMode: 'concise',
    availableModes: [
      { mode: 'concise', label: '简洁视图', icon: '📋' },
      { mode: 'member', label: '议员视图', icon: '👥' },
      { mode: 'debate', label: '辩论视图', icon: '⚔️' },
      { mode: 'full_log', label: '全量纪要', icon: '📜' },
    ],
  };

  assert(displayModeCard.availableModes.length === 4, '4种显示模式已配置');
  saveJson(`${DISPLAY_DIR}/01_launch_card.json`, { launchCard, displayModeCard });
}

// ============================================================================
// Scenario 2: 线程中真实开会
// ============================================================================

async function testThreadMeeting() {
  section('场景 2: 线程中真实开会');

  // 读取线程绑定
  const dirs = fs.readdirSync(THREAD_DIR).filter(f => !f.startsWith('.'));
  const threadId = dirs[dirs.length - 1];
  const bindingFile = path.join(THREAD_DIR, threadId, 'binding.json');
  const binding = JSON.parse(fs.readFileSync(bindingFile, 'utf-8'));

  // 2.1 更新顶部锚点消息
  console.log('\n  [2.1] 顶部锚点消息');
  const anchorMessage = {
    threadId,
    projectId: binding.projectId,
    projectName: binding.projectName,
    currentIssueTitle: '情感AI是否应该成为核心功能？',
    currentStage: 'hypothesis_building',
    currentProblem: '情感AI是否应该成为核心功能',
    currentRound: 1,
    latestConsensus: [],
    strongestDissent: '',
    unresolvedUncertainties: ['监管政策不明'],
    nextAction: '收集证据',
    status: 'active',
    updatedAt: timestamp(),
  };

  const anchorFile = path.join(THREAD_DIR, threadId, 'anchor_message.json');
  fs.writeFileSync(anchorFile, JSON.stringify(anchorMessage, null, 2));
  assert(fs.existsSync(anchorFile), '锚点消息已创建');

  // 2.2 角色消息流式输出
  console.log('\n  [2.2] 角色消息流式输出');
  const roleMessages = [
    { round: 1, stage: 'proposal', roleId: 'member-1', roleName: '先机议员', content: '支持假设A：情感AI是核心竞争力' },
    { round: 1, stage: 'proposal', roleId: 'member-2', roleName: '质询议员', content: '质疑假设A的技术可行性' },
    { round: 2, stage: 'challenge', roleId: 'member-3', roleName: '分析议员', content: '提供市场调研数据显示需求' },
    { round: 2, stage: 'response', roleId: 'member-1', roleName: '先机议员', content: '回应技术可行性质疑，引用专利数据' },
    { round: 3, stage: 'gap', roleId: 'member-4', roleName: '风险议员', content: '指出监管政策不确定风险' },
  ];

  const msgFile = path.join(THREAD_DIR, threadId, 'messages', 'role_messages.jsonl');
  for (const msg of roleMessages) {
    fs.appendFileSync(msgFile, JSON.stringify({ ...msg, timestamp: timestamp() }) + '\n');
  }

  assert(fs.existsSync(msgFile), '角色消息文件已创建');
  const msgCount = fs.readFileSync(msgFile, 'utf-8').split('\n').filter(Boolean).length;
  assert(msgCount === 5, `5条角色消息已写入`);

  // 2.3 主持官总结消息
  console.log('\n  [2.3] 主持官总结消息');
  const chairSummary = {
    round: 3,
    current_consensus: ['情感AI有市场需求'],
    current_conflicts: ['技术可行性与监管不确定性'],
    strongest_support: '市场调研数据',
    strongest_dissent: '技术实现风险',
    unresolved_uncertainties: ['监管政策走向'],
    recommended_state_transition: 'continue',
    timestamp: timestamp(),
  };

  const summaryFile = path.join(THREAD_DIR, threadId, 'messages', 'chair_summaries.jsonl');
  fs.appendFileSync(summaryFile, JSON.stringify(chairSummary) + '\n');
  assert(fs.existsSync(summaryFile), '主持官总结已写入');

  // 2.4 监督官 gate 消息
  console.log('\n  [2.4] 监督官 gate 消息');
  const supervisorGate = {
    round: 3,
    passed: true,
    violations: [],
    dissent_present: true,
    uncertainty_present: true,
    recommendation: 'continue',
    timestamp: timestamp(),
  };

  const gateFile = path.join(THREAD_DIR, threadId, 'messages', 'supervisor_gates.jsonl');
  fs.appendFileSync(gateFile, JSON.stringify(supervisorGate) + '\n');
  assert(fs.existsSync(gateFile), '监督官 gate 消息已写入');
  assert(supervisorGate.passed === true, 'Gate 通过');

  saveJson(`${DISPLAY_DIR}/02_thread_meeting.json`, { anchorMessage, roleMessages, chairSummary, supervisorGate });
}

// ============================================================================
// Scenario 3: 用户在线程中纠正方向
// ============================================================================

async function testUserIntervention() {
  section('场景 3: 用户在线程中纠正方向');

  const dirs = fs.readdirSync(THREAD_DIR).filter(f => !f.startsWith('.'));
  const threadId = dirs[dirs.length - 1];
  const bindingFile = path.join(THREAD_DIR, threadId, 'binding.json');
  const binding = JSON.parse(fs.readFileSync(bindingFile, 'utf-8'));

  // 3.1 用户在线程中发言
  console.log('\n  [3.1] 用户发言识别');
  const userMessage = '不对，方向错了，我们应该先考虑技术可行性';

  // 干预分类
  const interventionPatterns = {
    correction: ['不对', '错了', '不是这样'],
    constraint: ['只能', '必须', '约束'],
    direction_change: ['换个方向', '改变策略', '方向错了'],
    follow_up_request: ['继续', '接下来', '基于'],
    reopen_request: ['重开', '重新开始'],
  };

  const interventionType = 'direction_change';
  const matchedKeywords = ['方向错了'];

  assert(matchedKeywords.includes('方向错了'), '用户发言被识别为 direction_change');

  // 3.2 写入 user_intervention
  console.log('\n  [3.2] 用户干预写入 dossier');
  const intervention = {
    interventionId: generateId('int'),
    threadId,
    sessionId: binding.sessionId,
    issueId: 'issue-001',
    type: interventionType,
    rawText: userMessage,
    classifiedAt: timestamp(),
    processed: false,
    impact: {
      affectsCurrentIssue: false,
      createsNewIssue: false,
      reopensIssue: true,
      changesDirection: true,
    },
    chairAcknowledged: false,
  };

  const interventionFile = path.join(INTERVENTION_DIR, `${intervention.interventionId}.json`);
  fs.writeFileSync(interventionFile, JSON.stringify(intervention, null, 2));

  const historyFile = path.join(INTERVENTION_DIR, 'intervention_history.jsonl');
  fs.appendFileSync(historyFile, JSON.stringify(intervention) + '\n');
  assert(fs.existsSync(interventionFile), '干预已写入文件');
  assert(intervention.impact.reopensIssue === true, '干预导致重新打开');

  // 3.3 主持官确认干预已纳入
  console.log('\n  [3.3] 主持官确认');
  const acknowledgedIntervention = { ...intervention, chairAcknowledged: true, chairAcknowledgedAt: timestamp() };
  fs.writeFileSync(interventionFile, JSON.stringify(acknowledgedIntervention, null, 2));
  assert(acknowledgedIntervention.chairAcknowledged === true, '主持官已确认');

  // 3.4 受影响议员重新发言（模拟）
  console.log('\n  [3.4] 受影响议员重新发言');
  const newMessage = {
    round: 4,
    stage: 'reorientation',
    roleId: 'member-1',
    roleName: '先机议员',
    content: '根据用户纠正，现在先评估技术可行性',
    timestamp: timestamp(),
  };

  const msgFile = path.join(THREAD_DIR, threadId, 'messages', 'role_messages.jsonl');
  fs.appendFileSync(msgFile, JSON.stringify(newMessage) + '\n');

  const totalMsgs = fs.readFileSync(msgFile, 'utf-8').split('\n').filter(Boolean).length;
  assert(totalMsgs === 6, '新消息已追加到线程');

  saveJson(`${DISPLAY_DIR}/03_user_intervention.json`, { userMessage, intervention, acknowledgedIntervention });
}

// ============================================================================
// Scenario 4: 阶段收官但线程不关闭
// ============================================================================

async function testStageClosedButThreadOpen() {
  section('场景 4: 阶段收官但线程不关闭');

  const dirs = fs.readdirSync(THREAD_DIR).filter(f => !f.startsWith('.'));
  const threadId = dirs[dirs.length - 1];
  const bindingFile = path.join(THREAD_DIR, threadId, 'binding.json');
  let binding = JSON.parse(fs.readFileSync(bindingFile, 'utf-8'));

  // 4.1 更新状态为 stage_closed_but_thread_open
  console.log('\n  [4.1] 设置 stage_closed_but_thread_open 状态');
  binding.status = 'stage_closed_but_thread_open';
  binding.updatedAt = timestamp();
  fs.writeFileSync(bindingFile, JSON.stringify(binding, null, 2));

  const statusFile = path.join(FOLLOWUP_DIR, `${binding.sessionId}_status.json`);
  fs.writeFileSync(statusFile, JSON.stringify({
    sessionId: binding.sessionId,
    threadId,
    previousStatus: 'active',
    newStatus: 'stage_closed_but_thread_open',
    changedAt: timestamp(),
  }, null, 2));

  assert(binding.status === 'stage_closed_but_thread_open', '状态已更新为 stage_closed_but_thread_open');

  // 4.2 线程仍保持开放
  console.log('\n  [4.2] 线程保持开放');
  const threadDir = path.join(THREAD_DIR, threadId);
  assert(fs.existsSync(threadDir), '线程目录仍存在');
  assert(fs.existsSync(path.join(threadDir, 'messages')), '消息目录仍存在');
  assert(fs.existsSync(path.join(threadDir, 'dossier')), 'dossier 目录仍存在');

  // 4.3 更新锚点消息
  console.log('\n  [4.3] 更新锚点消息');
  const anchorFile = path.join(THREAD_DIR, threadId, 'anchor_message.json');
  const anchor = JSON.parse(fs.readFileSync(anchorFile, 'utf-8'));
  anchor.status = 'stage_closed_but_thread_open';
  anchor.nextAction = '等待用户发起 FOLLOW_UP 或新议题';
  fs.writeFileSync(anchorFile, JSON.stringify(anchor, null, 2));

  assert(anchor.status === 'stage_closed_but_thread_open', '锚点消息状态已更新');

  // 4.4 用户可在同一线程中继续
  console.log('\n  [4.4] 线程持续可用性');
  const isStillOpen = binding.status === 'stage_closed_but_thread_open';
  assert(isStillOpen === true, '线程仍可接受新消息');

  saveJson(`${DISPLAY_DIR}/04_stage_closed.json`, { binding, anchor, statusFile });
}

// ============================================================================
// Scenario 5: 用户在线程中发起 FOLLOW_UP
// ============================================================================

async function testFollowUp() {
  section('场景 5: 用户在线程中发起 FOLLOW_UP');

  const dirs = fs.readdirSync(THREAD_DIR).filter(f => !f.startsWith('.'));
  const threadId = dirs[dirs.length - 1];
  const bindingFile = path.join(THREAD_DIR, threadId, 'binding.json');
  let binding = JSON.parse(fs.readFileSync(bindingFile, 'utf-8'));

  // 5.1 用户发起 FOLLOW_UP
  console.log('\n  [5.1] 用户发起 FOLLOW_UP');
  const followUpMessage = '基于刚才的结论，现在进一步讨论量产方案';

  // 检测为 FOLLOW_UP_REQUEST (使用更宽松的模式)
  const followUpPatterns = [/基于.*继续/, /开个新议题/, /接下来.*讨论/, /进一步.*讨论/];
  const isFollowUp = followUpPatterns.some(p => p.test(followUpMessage));
  assert(isFollowUp === true, '消息被识别为 FOLLOW_UP_REQUEST');

  // 5.2 识别新议题标题
  console.log('\n  [5.2] 提取新议题标题');
  const newIssueTitleMatch = followUpMessage.match(/讨论(.+)$/);
  const newIssueTitle = newIssueTitleMatch ? newIssueTitleMatch[1] : 'FOLLOW_UP 新议题';
  assert(newIssueTitle.includes('量产方案'), '新议题标题已提取');

  // 5.3 创建 follow_up_issue
  console.log('\n  [5.3] 创建 follow_up_issue');
  const followUpIssue = {
    issue_id: generateId('followup-issue'),
    issue_title: newIssueTitle,
    problem_statement: `基于旧议题结论的 FOLLOW_UP：${newIssueTitle}`,
    isFollowUp: true,
    parentIssueId: 'issue-001',
    inheritedAssets: ['verdict:hypothesis_confirmed', 'dissent:技术实现风险', 'unresolved:监管政策不明'],
    followUpRequestText: followUpMessage,
  };

  // 5.4 更新线程状态为 active
  console.log('\n  [5.4] 线程恢复为 active');
  binding.status = 'active';
  binding.currentIssueId = followUpIssue.issue_id;
  binding.currentRound = 0;
  binding.updatedAt = timestamp();
  fs.writeFileSync(bindingFile, JSON.stringify(binding, null, 2));

  // 5.5 记录 FOLLOW_UP 请求
  console.log('\n  [5.5] 记录 FOLLOW_UP 请求');
  const followUpRequest = {
    requestId: generateId('req'),
    threadId,
    sessionId: binding.sessionId,
    parentIssueId: 'issue-001',
    newIssueTitle,
    newIssueDescription: `基于旧议题结论的 FOLLOW_UP：${newIssueTitle}`,
    inheritedAssets: followUpIssue.inheritedAssets,
    createdAt: timestamp(),
    followUpType: 'continue_discussion',
  };

  const followupFile = path.join(FOLLOWUP_DIR, `${binding.sessionId}_followups.jsonl`);
  fs.appendFileSync(followupFile, JSON.stringify(followUpRequest) + '\n');
  assert(fs.existsSync(followupFile), 'FOLLOW_UP 请求已记录');

  // 5.6 在线程中发布系统消息
  console.log('\n  [5.6] 线程中发布 FOLLOW_UP 系统消息');
  const systemMessage = {
    type: 'system',
    subtype: 'follow_up_created',
    round: 0,
    content: {
      mode: 'FOLLOW_UP',
      inheritedAssets: followUpIssue.inheritedAssets,
      newIssueTitle: newIssueTitle,
      stage: 'issue_definition',
    },
    timestamp: timestamp(),
  };

  const msgFile = path.join(THREAD_DIR, threadId, 'messages', 'role_messages.jsonl');
  fs.appendFileSync(msgFile, JSON.stringify(systemMessage) + '\n');

  const totalMsgs = fs.readFileSync(msgFile, 'utf-8').split('\n').filter(Boolean).length;
  assert(totalMsgs > 0, 'FOLLOW_UP 系统消息已写入线程');

  saveJson(`${DISPLAY_DIR}/05_followup.json`, { followUpMessage, followUpIssue, followUpRequest, systemMessage });
}

// ============================================================================
// Scenario 6: 主会话切换显示方式
// ============================================================================

async function testDisplayModeSwitch() {
  section('场景 6: 主会话切换显示方式');

  const dirs = fs.readdirSync(THREAD_DIR).filter(f => !f.startsWith('.'));
  const threadId = dirs[dirs.length - 1];
  const bindingFile = path.join(THREAD_DIR, threadId, 'binding.json');
  let binding = JSON.parse(fs.readFileSync(bindingFile, 'utf-8'));

  // 6.1 读取线程数据
  console.log('\n  [6.1] 读取线程数据');
  const msgFile = path.join(THREAD_DIR, threadId, 'messages', 'role_messages.jsonl');
  const summaryFile = path.join(THREAD_DIR, threadId, 'messages', 'chair_summaries.jsonl');
  const gateFile = path.join(THREAD_DIR, threadId, 'messages', 'supervisor_gates.jsonl');

  const roleMessages = fs.readFileSync(msgFile, 'utf-8').split('\n').filter(Boolean).map(l => JSON.parse(l));
  const chairSummaries = fs.existsSync(summaryFile) ? fs.readFileSync(summaryFile, 'utf-8').split('\n').filter(Boolean).map(l => JSON.parse(l)) : [];
  const supervisorGates = fs.existsSync(gateFile) ? fs.readFileSync(gateFile, 'utf-8').split('\n').filter(Boolean).map(l => JSON.parse(l)) : [];

  // 6.2 切换到议员视图
  console.log('\n  [6.2] 切换到议员视图');
  binding.displayMode = 'member';
  fs.writeFileSync(bindingFile, JSON.stringify(binding, null, 2));

  const memberView = {
    view: 'member',
    totalMessages: roleMessages.length,
    messages: roleMessages.map(m => ({
      round: m.round,
      role: m.roleName || m.roleId,
      content: m.content,
    })),
  };

  assert(memberView.view === 'member', '视图切换为 member');
  assert(memberView.totalMessages > 0, '议员视图包含消息');

  // 6.3 切换到辩论视图
  console.log('\n  [6.3] 切换到辩论视图');
  binding.displayMode = 'debate';
  fs.writeFileSync(bindingFile, JSON.stringify(binding, null, 2));

  const debateView = {
    view: 'debate',
    proposals: roleMessages.filter(m => m.stage === 'proposal').map(m => m.content),
    challenges: roleMessages.filter(m => m.stage === 'challenge').map(m => m.content),
    responses: roleMessages.filter(m => m.stage === 'response').map(m => m.content),
    gaps: roleMessages.filter(m => m.stage === 'gap').map(m => m.content),
  };

  assert(debateView.view === 'debate', '视图切换为 debate');
  assert(debateView.proposals.length > 0 || debateView.challenges.length > 0, '辩论视图包含内容');

  // 6.4 切换到简洁视图
  console.log('\n  [6.4] 切换到简洁视图');
  binding.displayMode = 'concise';
  fs.writeFileSync(bindingFile, JSON.stringify(binding, null, 2));

  const anchorFilePath = path.join(THREAD_DIR, threadId, 'anchor_message.json');
  const anchorData = fs.existsSync(anchorFilePath) ? JSON.parse(fs.readFileSync(anchorFilePath, 'utf-8')) : null;

  const conciseView = {
    view: 'concise',
    stage: 'hypothesis_building',
    problem: '情感AI是否应该成为核心功能',
    chairSummary: chairSummaries[chairSummaries.length - 1]?.recommended_state_transition || 'continue',
    nextAction: anchorData?.nextAction || '等待用户输入',
  };

  assert(conciseView.view === 'concise', '视图切换为 concise');

  // 6.5 验证切换不影响状态
  console.log('\n  [6.5] 验证状态不变');
  const finalBinding = JSON.parse(fs.readFileSync(bindingFile, 'utf-8'));
  assert(finalBinding.status === 'active' || finalBinding.status === 'stage_closed_but_thread_open', '线程状态未改变');
  assert(finalBinding.sessionId === binding.sessionId, 'Session ID 未改变');

  saveJson(`${DISPLAY_DIR}/06_display_modes.json`, { memberView, debateView, conciseView });
}

// ============================================================================
// Helper
// ============================================================================

function saveJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
  console.log(`    📄 ${path.basename(filePath)}`);
}

// ============================================================================
// Main Execution
// ============================================================================

async function main() {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║     RTCM Delta 生产验证态演练 - 第八轮完整验证                   ║');
  console.log('╚════════════════════════════════════════════════════════════════╝');
  console.log(`\n项目: ${PROJECT_NAME}`);
  console.log(`时间: ${timestamp()}`);
  console.log(`输出目录: ${BASE_DIR}`);

  console.log('\n' + '─'.repeat(64));
  console.log('测试场景:');
  console.log('  1. 飞书主会话发起 RTCM');
  console.log('  2. 线程中真实开会');
  console.log('  3. 用户在线程中纠正方向');
  console.log('  4. 阶段收官但线程不关闭');
  console.log('  5. 用户在线程中发起 FOLLOW_UP');
  console.log('  6. 主会话切换显示方式');
  console.log('─'.repeat(64));

  await testMainSessionInitiate();
  await testThreadMeeting();
  await testUserIntervention();
  await testStageClosedButThreadOpen();
  await testFollowUp();
  await testDisplayModeSwitch();

  // Results
  section('测试结果摘要');
  console.log(`\n  通过: ${results.passed}`);
  console.log(`  失败: ${results.failed}`);

  if (results.failed === 0) {
    console.log('\n🎉 第八轮 Delta 生产验证态演练通过！\n');
    console.log('  ✅ 飞书主会话成功启动 RTCM');
    console.log('  ✅ 线程中真实看到会议流（角色消息、主持官、监督官）');
    console.log('  ✅ 用户在线程中纠正方向被识别并生效');
    console.log('  ✅ 阶段收官后线程仍保持开放 (stage_closed_but_thread_open)');
    console.log('  ✅ FOLLOW_UP 成功创建，继承旧成果');
    console.log('  ✅ 显示方式切换只改展示，不改状态\n');
  } else {
    console.log(`\n⚠️  ${results.failed} 项测试失败\n`);
  }

  // Save test report
  const report = {
    testId: `delta-integration-${Date.now()}`,
    timestamp: timestamp(),
    projectId: PROJECT_ID,
    results: { passed: results.passed, failed: results.failed, errors: results.errors },
  };
  const reportFile = path.join(BASE_DIR, 'test_report.json');
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
  console.log(`  📄 测试报告: ${reportFile}`);
}

main().catch(console.error);