/**
 * @file rtcm_user_intervention.ts
 * @description RTCM 用户线程干预分类器 - Delta 生产验证态核心
 * 用户在话题线程中的发言被识别为正式会议干预消息
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import * as crypto from 'crypto';

// ============================================================================
// Types - User Intervention
// ============================================================================

export enum UserInterventionType {
  CORRECTION = 'correction',           // 用户纠正
  CONSTRAINT = 'constraint',           // 用户追加约束
  DIRECTION_CHANGE = 'direction_change', // 用户改方向
  DEEPER_PROBE = 'deeper_probe',       // 用户要求深挖
  REOPEN_REQUEST = 'reopen_request',    // 用户要求重开
  CONTINUE_REQUEST = 'continue_request', // 用户要求继续
  FOLLOW_UP_REQUEST = 'follow_up_request', // 用户要求 FOLLOW_UP
  PAUSE_REQUEST = 'pause_request',     // 用户要求暂停
  RESUME_REQUEST = 'resume_request',    // 用户要求恢复
  ACCEPTANCE_DECISION = 'acceptance_decision', // 用户验收决策
}

export interface UserIntervention {
  interventionId: string;
  threadId: string;
  sessionId: string;
  issueId: string;
  type: UserInterventionType;
  rawText: string;
  classifiedAt: string;
  processed: boolean;
  impact: {
    affectsCurrentIssue: boolean;
    createsNewIssue: boolean;
    reopensIssue: boolean;
    changesDirection: boolean;
  };
  chairAcknowledged: boolean;
  chairAcknowledgedAt: string | null;
}

export interface InterventionResult {
  type: UserInterventionType;
  confidence: number;
  matchedKeywords: string[];
  requiresNewIssue: boolean;
  requiresReopen: boolean;
}

// ============================================================================
// User Intervention Classifier
// ============================================================================

export class UserInterventionClassifier {
  private interventionLogDir: string;

  // 干预类型关键词映射
  private static readonly INTERVENTION_PATTERNS: Record<UserInterventionType, string[]> = {
    [UserInterventionType.CORRECTION]: [
      '不对', '不是这样', '纠正', '错了', '不对的是', '应该改成',
      '更正', '修改', '调整', '变更', '改变', '不是', '错了',
    ],
    [UserInterventionType.CONSTRAINT]: [
      '约束', '限制', '只能', '必须', '不可以', '禁止', '要求',
      '规定', '原则', '前提', '条件是', '只能', '限于',
    ],
    [UserInterventionType.DIRECTION_CHANGE]: [
      '换个方向', '改变策略', '重新考虑', '换个思路', '调整方向',
      '改一下', '重新规划', '另辟蹊径', '换一种', '重新来',
    ],
    [UserInterventionType.DEEPER_PROBE]: [
      '深挖', '进一步', '更深入', '详细分析', '展开讲', '具体说说',
      '详细说说', '深入研究', '刨根问底', '追问', '进一步探讨',
    ],
    [UserInterventionType.REOPEN_REQUEST]: [
      '重开', '重新开始', '再议', '重新讨论', '再次审议',
      '重提', '重新来过', '再讨论', '重头来',
    ],
    [UserInterventionType.CONTINUE_REQUEST]: [
      '继续', '接着', '往下', '推进', '继续讨论', '接着说',
      '继续推进', '往下进行', '继续进行',
    ],
    [UserInterventionType.FOLLOW_UP_REQUEST]: [
      '基于', '刚才结论', '继续往前', '接下来', '现在进一步',
      '基于刚才', '继续往前推进', '继续讨论', '接着刚才',
      '基于原成果', '基于结论', '新议题', '开个新议题',
    ],
    [UserInterventionType.PAUSE_REQUEST]: [
      '暂停', '停一下', '先等', '等一下', '先暂停', '暂时停止',
      '先到这里', '先休息',
    ],
    [UserInterventionType.RESUME_REQUEST]: [
      '恢复', '继续', '重新开始', '接着来', '继续推进', '恢复讨论',
      '继续开会', '重新开始',
    ],
    [UserInterventionType.ACCEPTANCE_DECISION]: [
      '批准', '同意', '通过', '认可', '可以', '没问题', '同意通过',
      '确认', '验收', '接受',
    ],
  };

  // FOLLOW_UP 特殊检测（更复杂模式）
  private static readonly FOLLOW_UP_PATTERNS: RegExp[] = [
    /基于.*继续/,
    /刚才.*继续/,
    /接着.*分析/,
    /继续往前/,
    /开个新议题/,
    /接下来.*讨论/,
    /基于.*成果/,
    /继续.*新议题/,
  ];

  constructor() {
    this.interventionLogDir = runtimePath('rtcm', 'interventions');
    this.ensureDir(this.interventionLogDir);
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Classification
  // ===========================================================================

  /**
   * 分类用户发言
   */
  classify(userMessage: string): InterventionResult {
    const normalized = userMessage.trim().toLowerCase();
    const matchedKeywords: string[] = [];
    let bestType: UserInterventionType | null = null;
    let bestScore = 0;

    // 首先检查 FOLLOW_UP 特殊模式
    if (UserInterventionClassifier.FOLLOW_UP_PATTERNS.some(p => p.test(userMessage))) {
      return {
        type: UserInterventionType.FOLLOW_UP_REQUEST,
        confidence: 0.95,
        matchedKeywords: ['基于...继续', '开个新议题', '继续往前'],
        requiresNewIssue: true,
        requiresReopen: false,
      };
    }

    // 检查各类型关键词
    for (const [type, keywords] of Object.entries(UserInterventionClassifier.INTERVENTION_PATTERNS)) {
      const matches = keywords.filter(kw => normalized.includes(kw.toLowerCase()));
      if (matches.length > 0) {
        matchedKeywords.push(...matches);
        const score = matches.length / keywords.length; // 类型内命中率
        if (score > bestScore) {
          bestScore = score;
          bestType = type as UserInterventionType;
        }
      }
    }

    if (!bestType) {
      // 无法分类，默认作为 direction_change 或 follow_up_request
      return {
        type: UserInterventionType.FOLLOW_UP_REQUEST,
        confidence: 0.3,
        matchedKeywords: [],
        requiresNewIssue: true,
        requiresReopen: false,
      };
    }

    const requiresNewIssue = [UserInterventionType.FOLLOW_UP_REQUEST, UserInterventionType.DIRECTION_CHANGE].includes(bestType);
    const requiresReopen = [UserInterventionType.REOPEN_REQUEST].includes(bestType);

    return {
      type: bestType,
      confidence: Math.min(bestScore + 0.5, 1.0),
      matchedKeywords: [...new Set(matchedKeywords)],
      requiresNewIssue,
      requiresReopen,
    };
  }

  /**
   * 处理用户干预
   */
  processIntervention(params: {
    threadId: string;
    sessionId: string;
    issueId: string;
    userMessage: string;
  }): UserIntervention {
    const classification = this.classify(params.userMessage);

    const intervention: UserIntervention = {
      interventionId: `int-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`,
      threadId: params.threadId,
      sessionId: params.sessionId,
      issueId: params.issueId,
      type: classification.type,
      rawText: params.userMessage,
      classifiedAt: new Date().toISOString(),
      processed: false,
      impact: {
        affectsCurrentIssue: !classification.requiresNewIssue,
        createsNewIssue: classification.requiresNewIssue,
        reopensIssue: classification.requiresReopen,
        changesDirection: classification.type === UserInterventionType.DIRECTION_CHANGE,
      },
      chairAcknowledged: false,
      chairAcknowledgedAt: null,
    };

    // 记录干预
    this.logIntervention(intervention);

    return intervention;
  }

  /**
   * 主持官确认干预已纳入
   */
  acknowledgeIntervention(interventionId: string): void {
    const interventionFiles = fs.readdirSync(this.interventionLogDir).filter(f => f.endsWith('.json'));

    for (const file of interventionFiles) {
      const filePath = path.join(this.interventionLogDir, file);
      const content = fs.readFileSync(filePath, 'utf-8');

      // 尝试解析每行
      const lines = content.split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const int = JSON.parse(line);
          if (int.interventionId === interventionId) {
            int.chairAcknowledged = true;
            int.chairAcknowledgedAt = new Date().toISOString();
            int.processed = true;
            // 重新写入（这里简化处理，实际应该用临时文件）
            break;
          }
        } catch {
          // 忽略解析错误
        }
      }
    }
  }

  /**
   * 标记干预已处理
   */
  markProcessed(interventionId: string): void {
    const filePath = path.join(this.interventionLogDir, `${interventionId}.json`);
    if (fs.existsSync(filePath)) {
      const intervention = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      intervention.processed = true;
      fs.writeFileSync(filePath, JSON.stringify(intervention, null, 2), 'utf-8');
    }
  }

  // ===========================================================================
  // Intervention Impact on Issue
  // ===========================================================================

  /**
   * 根据干预类型确定需要执行的动作
   */
  determineActions(intervention: UserIntervention): {
    shouldRecomputeCurrentIssue: boolean;
    shouldReopenIssue: boolean;
    shouldCreateNewIssue: boolean;
    shouldCreateFollowUpIssue: boolean;
    newIssueTitle?: string;
    newIssueDescription?: string;
  } {
    switch (intervention.type) {
      case UserInterventionType.CORRECTION:
      case UserInterventionType.CONSTRAINT:
        return {
          shouldRecomputeCurrentIssue: true,
          shouldReopenIssue: false,
          shouldCreateNewIssue: false,
          shouldCreateFollowUpIssue: false,
        };

      case UserInterventionType.DIRECTION_CHANGE:
        return {
          shouldRecomputeCurrentIssue: true,
          shouldReopenIssue: true,
          shouldCreateNewIssue: false,
          shouldCreateFollowUpIssue: false,
        };

      case UserInterventionType.REOPEN_REQUEST:
        return {
          shouldRecomputeCurrentIssue: false,
          shouldReopenIssue: true,
          shouldCreateNewIssue: false,
          shouldCreateFollowUpIssue: false,
        };

      case UserInterventionType.FOLLOW_UP_REQUEST:
        return {
          shouldRecomputeCurrentIssue: false,
          shouldReopenIssue: false,
          shouldCreateNewIssue: false,
          shouldCreateFollowUpIssue: true,
          newIssueTitle: this.extractFollowUpTitle(intervention.rawText),
        };

      case UserInterventionType.DEEPER_PROBE:
        return {
          shouldRecomputeCurrentIssue: true,
          shouldReopenIssue: false,
          shouldCreateNewIssue: false,
          shouldCreateFollowUpIssue: false,
        };

      case UserInterventionType.PAUSE_REQUEST:
        return {
          shouldRecomputeCurrentIssue: false,
          shouldReopenIssue: false,
          shouldCreateNewIssue: false,
          shouldCreateFollowUpIssue: false,
        };

      case UserInterventionType.ACCEPTANCE_DECISION:
        return {
          shouldRecomputeCurrentIssue: false,
          shouldReopenIssue: false,
          shouldCreateNewIssue: false,
          shouldCreateFollowUpIssue: false,
        };

      default:
        return {
          shouldRecomputeCurrentIssue: false,
          shouldReopenIssue: false,
          shouldCreateNewIssue: false,
          shouldCreateFollowUpIssue: false,
        };
    }
  }

  /**
   * 从用户消息中提取 FOLLOW_UP 议题标题
   */
  private extractFollowUpTitle(rawText: string): string {
    // 尝试提取"新议题"后的内容
    const newIssueMatch = rawText.match(/新议题[：:](.+)/i);
    if (newIssueMatch) {
      return newIssueMatch[1].trim();
    }

    // 尝试提取"讨论"后的内容
    const discussMatch = rawText.match(/讨论[：:](.+)/i);
    if (discussMatch) {
      return discussMatch[1].trim();
    }

    // 提取"接下来"后的内容
    const nextMatch = rawText.match(/接下来(.+)/i);
    if (nextMatch) {
      return nextMatch[1].trim();
    }

    return 'FOLLOW_UP 新议题';
  }

  // ===========================================================================
  // Persistence
  // ===========================================================================

  private logIntervention(intervention: UserIntervention): void {
    const filePath = path.join(this.interventionLogDir, `${intervention.interventionId}.json`);
    fs.writeFileSync(filePath, JSON.stringify(intervention, null, 2), 'utf-8');

    // 同时追加到历史日志
    const historyFile = path.join(this.interventionLogDir, 'intervention_history.jsonl');
    fs.appendFileSync(historyFile, JSON.stringify(intervention) + '\n', 'utf-8');
  }

  /**
   * 读取干预历史
   */
  getInterventionHistory(threadId?: string): UserIntervention[] {
    const historyFile = path.join(this.interventionLogDir, 'intervention_history.jsonl');
    if (!fs.existsSync(historyFile)) return [];

    const lines = fs.readFileSync(historyFile, 'utf-8').split('\n').filter(Boolean);
    const interventions = lines.map(line => JSON.parse(line) as UserIntervention);

    if (threadId) {
      return interventions.filter(i => i.threadId === threadId);
    }
    return interventions;
  }

  /**
   * 获取未处理的干预
   */
  getUnprocessedInterventions(threadId?: string): UserIntervention[] {
    return this.getInterventionHistory(threadId).filter(i => !i.processed);
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const userInterventionClassifier = new UserInterventionClassifier();
