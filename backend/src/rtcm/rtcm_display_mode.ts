/**
 * @file rtcm_display_mode.ts
 * @description RTCM 显示方式切换卡片 - Delta 生产验证态
 * 主会话中的显示方式切换卡片，4种视图切换
 */

import { ThreadDisplayMode } from './rtcm_thread_adapter';

// ============================================================================
// Types
// ============================================================================

export interface DisplayModeCard {
  cardType: 'display_mode_switcher';
  title: string;
  description: string;
  currentMode: ThreadDisplayMode;
  availableModes: DisplayModeOption[];
  hint: string;
}

export interface DisplayModeOption {
  mode: ThreadDisplayMode;
  label: string;
  description: string;
  icon: string;
}

// ============================================================================
// Display Mode Card Generator
// ============================================================================

export class DisplayModeCardGenerator {
  private static readonly MODE_OPTIONS: DisplayModeOption[] = [
    {
      mode: ThreadDisplayMode.CONCISE,
      label: '简洁视图',
      description: '仅显示当前阶段、问题、主持官总结、下一步动作',
      icon: '📋',
    },
    {
      mode: ThreadDisplayMode.MEMBER,
      label: '议员视图',
      description: '按角色逐条展示所有发言',
      icon: '👥',
    },
    {
      mode: ThreadDisplayMode.DEBATE,
      label: '辩论视图',
      description: '按提案、质疑、回应、缺口、裁决组织内容',
      icon: '⚔️',
    },
    {
      mode: ThreadDisplayMode.FULL_LOG,
      label: '全量纪要',
      description: '显示完整会议流，包含所有角色消息和gate结果',
      icon: '📜',
    },
  ];

  /**
   * 生成显示方式切换卡片
   */
  generateCard(currentMode: ThreadDisplayMode): DisplayModeCard {
    return {
      cardType: 'display_mode_switcher',
      title: '📺 会议显示方式',
      description: '选择不同的视图来查看会议内容',
      currentMode,
      availableModes: DisplayModeCardGenerator.MODE_OPTIONS,
      hint: '切换视图只改变展示方式，不影响会议状态',
    };
  }

  /**
   * 生成简洁视图内容
   */
  generateConciseViewContent(params: {
    currentStage: string;
    currentProblem: string;
    chairSummary: string | null;
    nextAction: string;
    latestConsensus: string[];
  }): object {
    return {
      view: 'concise',
      stage: params.currentStage,
      problem: params.currentProblem,
      consensus: params.latestConsensus,
      chairSummary: params.chairSummary,
      nextAction: params.nextAction,
    };
  }

  /**
   * 生成议员视图内容
   */
  generateMemberViewContent(roleMessages: Array<{
    roleId: string;
    roleName: string;
    content: string;
    round: number;
  }>): object {
    return {
      view: 'member',
      totalMessages: roleMessages.length,
      messages: roleMessages.map(m => ({
        round: m.round,
        role: m.roleName,
        content: m.content,
      })),
    };
  }

  /**
   * 生成辩论视图内容
   */
  generateDebateViewContent(messages: Array<{
    content: string;
    stage: 'proposal' | 'challenge' | 'response' | 'gap' | 'verdict';
  }>): object {
    const grouped = {
      proposals: messages.filter(m => m.stage === 'proposal').map(m => m.content),
      challenges: messages.filter(m => m.stage === 'challenge').map(m => m.content),
      responses: messages.filter(m => m.stage === 'response').map(m => m.content),
      gaps: messages.filter(m => m.stage === 'gap').map(m => m.content),
      verdict: messages.filter(m => m.stage === 'verdict').map(m => m.content),
    };

    return {
      view: 'debate',
      ...grouped,
    };
  }

  /**
   * 生成全量纪要视图内容
   */
  generateFullLogViewContent(messages: {
    roleMessages: Array<{ round: number; roleName: string; content: string; timestamp: string }>;
    chairSummaries: Array<{ round: number; consensus: string[]; timestamp: string }>;
    supervisorGates: Array<{ round: number; passed: boolean; recommendation: string }>;
  }): object {
    return {
      view: 'full_log',
      totalRounds: messages.roleMessages.length > 0
        ? Math.max(...messages.roleMessages.map(m => m.round))
        : 0,
      roleMessages: messages.roleMessages,
      chairSummaries: messages.chairSummaries,
      supervisorGates: messages.supervisorGates,
    };
  }

  /**
   * 生成 Feishu 卡片 payload
   */
  generateFeishuCardPayload(currentMode: ThreadDisplayMode, threadId: string): object {
    const card = this.generateCard(currentMode);

    // 生成 Feishu 兼容的卡片元素
    const elements = [
      {
        tag: 'markdown',
        content: `**当前显示**: ${this.getModeLabel(currentMode)}`,
      },
      { tag: 'hr' },
    ];

    // 添加模式选项
    for (const option of card.availableModes) {
      const isSelected = option.mode === currentMode;
      const prefix = isSelected ? '✅' : '⬜';
      elements.push({
        tag: 'markdown',
        content: `${prefix} **[${option.icon} ${option.label}](select_mode:${option.mode})**\n${option.description}`,
      });
    }

    elements.push(
      { tag: 'hr' },
      {
        tag: 'markdown',
        content: `_${card.hint}_`,
      }
    );

    return {
      card_type: 'interactive',
      schema: '2.0',
      title: card.title,
      elements,
    };
  }

  private getModeLabel(mode: ThreadDisplayMode): string {
    const option = DisplayModeCardGenerator.MODE_OPTIONS.find(o => o.mode === mode);
    return option ? `${option.icon} ${option.label}` : mode;
  }
}

// ============================================================================
// Main Session Display Card
// ============================================================================

export interface MainSessionCard {
  cardType: 'rtcm_launch' | 'rtcm_summary' | 'rtcm_status_update';
  title: string;
  threadId: string;
  projectName: string;
  content: object;
  actions: MainSessionAction[];
}

export interface MainSessionAction {
  type: 'click' | 'link';
  text: string;
  value: string;
}

export class MainSessionCardGenerator {
  /**
   * 生成会议启动卡片
   */
  generateLaunchCard(params: {
    threadId: string;
    projectName: string;
    issueTitle: string;
  }): MainSessionCard {
    return {
      cardType: 'rtcm_launch',
      title: '🎬 RTCM 会议已启动',
      threadId: params.threadId,
      projectName: params.projectName,
      content: {
        issue: params.issueTitle,
        mode: 'new_meeting',
      },
      actions: [
        {
          type: 'click',
          text: '进入话题线程',
          value: `enter_thread:${params.threadId}`,
        },
      ],
    };
  }

  /**
   * 生成摘要卡片
   */
  generateSummaryCard(params: {
    threadId: string;
    projectName: string;
    currentStage: string;
    latestConclusion: string;
    nextAction: string;
  }): MainSessionCard {
    return {
      cardType: 'rtcm_summary',
      title: '📊 RTCM 会议摘要',
      threadId: params.threadId,
      projectName: params.projectName,
      content: {
        currentStage: params.currentStage,
        latestConclusion: params.latestConclusion,
        nextAction: params.nextAction,
      },
      actions: [
        {
          type: 'click',
          text: '查看详情',
          value: `enter_thread:${params.threadId}`,
        },
      ],
    };
  }

  /**
   * 生成状态更新卡片
   */
  generateStatusUpdateCard(params: {
    threadId: string;
    projectName: string;
    status: string;
    message: string;
  }): MainSessionCard {
    return {
      cardType: 'rtcm_status_update',
      title: `📢 ${params.status}`,
      threadId: params.threadId,
      projectName: params.projectName,
      content: {
        status: params.status,
        message: params.message,
      },
      actions: [
        {
          type: 'click',
          text: '查看线程',
          value: `enter_thread:${params.threadId}`,
        },
      ],
    };
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const displayModeCardGenerator = new DisplayModeCardGenerator();
export const mainSessionCardGenerator = new MainSessionCardGenerator();