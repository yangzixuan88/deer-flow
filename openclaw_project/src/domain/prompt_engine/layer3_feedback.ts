/**
 * M09 Layer3 反馈采集层
 * ================================================
 * PostToolUse 触发
 * 职责：
 * 1. 自动质量信号采集
 * 2. 显式用户反馈解析
 * 3. 贡献度归因
 * ================================================
 */

import {
  FeedbackSignal,
  FeedbackSource,
  PromptFragment,
  TaskType,
  ContributionAttribution,
} from './types';

// ============================================
// 自动质量信号采集器
// ============================================

/**
 * 自动质量信号采集器
 * 从任务执行结果中提取质量信号
 */
export class AutoQualitySignal {
  /**
   * 从后续任务成功率推断质量
   * @param followUpSuccessRate 后续任务成功率
   * @returns 质量信号
   */
  inferFromFollowUpSuccess(followUpSuccessRate: number): FeedbackSignal {
    return {
      source: FeedbackSource.TASK_SUCCESS,
      follow_up_success_rate: followUpSuccessRate,
      captured_at: new Date().toISOString(),
    };
  }

  /**
   * 从用户重做请求推断质量
   * @param userRequestedRedo 是否要求重做
   * @returns 质量信号
   */
  inferFromRedoRequest(userRequestedRedo: boolean): FeedbackSignal {
    return {
      source: FeedbackSource.AUTO_QUALITY,
      user_requested_redo: userRequestedRedo,
      captured_at: new Date().toISOString(),
    };
  }

  /**
   * 从搜索引用置信度推断质量
   * @param confidence 置信度
   * @returns 质量信号
   */
  inferFromSearchConfidence(confidence: number): FeedbackSignal {
    return {
      source: FeedbackSource.SEARCH_CONFIDENCE,
      search_citation_confidence: confidence,
      captured_at: new Date().toISOString(),
    };
  }

  /**
   * 综合多个信号计算任务完成度
   */
  calculateTaskCompletion(signals: FeedbackSignal[]): number {
    let score = 1.0;
    let weight = 0;

    for (const signal of signals) {
      if (signal.follow_up_success_rate !== undefined) {
        score *= signal.follow_up_success_rate;
        weight++;
      }
      if (signal.user_requested_redo !== undefined && signal.user_requested_redo) {
        score *= 0.5;
        weight++;
      }
    }

    return weight > 0 ? score : 0.8; // 默认0.8
  }
}

// ============================================
// 用户反馈解析器
// ============================================

/**
 * 用户反馈解析器
 * 从飞书等渠道捕获显式用户反馈
 */
export class UserFeedbackParser {
  // 负面反馈关键词
  private negativeKeywords = [
    '太啰嗦', '太长', '简洁点', '说重点',
    '格式不对', '不是我想要的', '重新来',
    '不对', '错了', '不行', '不好',
    '简化', '精简', 'short', 'brief', 'concise',
    'wrong', 'incorrect', 'not what I wanted',
  ];

  // 正面反馈关键词
  private positiveKeywords = [
    '很好', '不错', '正是', '正是我想要的',
    'ok', 'good', 'great', 'perfect', 'excellent',
    '正是如此', '对了', '可以',
  ];

  /**
   * 解析用户反馈文本
   * @param feedbackText 用户反馈文本
   * @returns 解析结果
   */
  parse(feedbackText: string): {
    sentiment: 'positive' | 'negative' | 'neutral';
    matchedKeywords: string[];
    improvementDirection?: string;
  } {
    const lowerText = feedbackText.toLowerCase();
    const matchedNegative = this.negativeKeywords.filter(k =>
      lowerText.includes(k.toLowerCase())
    );
    const matchedPositive = this.positiveKeywords.filter(k =>
      lowerText.includes(k.toLowerCase())
    );

    let sentiment: 'positive' | 'negative' | 'neutral' = 'neutral';
    if (matchedNegative.length > matchedPositive.length) {
      sentiment = 'negative';
    } else if (matchedPositive.length > matchedNegative.length) {
      sentiment = 'positive';
    }

    // 推断改进方向
    let improvementDirection: string | undefined;
    if (sentiment === 'negative') {
      if (lowerText.includes('啰嗦') || lowerText.includes('长') || lowerText.includes('short') || lowerText.includes('brief')) {
        improvementDirection = '需要更简洁';
      } else if (lowerText.includes('格式') || lowerText.includes('format')) {
        improvementDirection = '格式需要调整';
      } else if (lowerText.includes('不对') || lowerText.includes('wrong')) {
        improvementDirection = '内容需要修正';
      }
    }

    return {
      sentiment,
      matchedKeywords: [...matchedNegative, ...matchedPositive],
      improvementDirection,
    };
  }

  /**
   * 将反馈转换为信号
   */
  toSignal(parsed: {
    sentiment: 'positive' | 'negative' | 'neutral';
    improvementDirection?: string;
  }): FeedbackSignal {
    return {
      source: FeedbackSource.EXPLICIT_USER,
      explicit_feedback: parsed.improvementDirection,
      captured_at: new Date().toISOString(),
    };
  }

  /**
   * 检查是否为负面反馈
   */
  isNegativeFeedback(feedbackText: string): boolean {
    const parsed = this.parse(feedbackText);
    return parsed.sentiment === 'negative';
  }
}

// ============================================
// 贡献度归因器
// ============================================

/**
 * 贡献度归因器
 * 分析哪个提示词片段对输出质量贡献最大
 */
export class ContributionAttributor {
  /**
   * 归因计算（简化版）
   * 实际应使用 LLM 分析或 trace 分析
   *
   * @param fragments 使用的片段列表
   * @param qualityScore 最终质量分
   * @param taskType 任务类型
   * @returns 各片段的贡献度列表
   */
  attribute(
    fragments: PromptFragment[],
    qualityScore: number,
    taskType: TaskType
  ): ContributionAttribution[] {
    // 简化：均匀分配 + 考虑历史质量
    const baseContribution = qualityScore / fragments.length;

    return fragments.map(fragment => {
      // 考虑该片段的历史质量表现
      const historicalAvg = this.calculateHistoricalAverage(fragment);
      const contribution = baseContribution * (0.5 + 0.5 * historicalAvg);

      return {
        fragment_id: fragment.id,
        contribution_score: Math.min(contribution, 1.0),
        is_promotion_candidate: qualityScore >= 0.85 && contribution >= 0.3,
        attribution_reason: `历史质量均值: ${historicalAvg.toFixed(2)}, 最终分: ${qualityScore}`,
      };
    });
  }

  /**
   * 计算片段历史质量均值
   */
  private calculateHistoricalAverage(fragment: PromptFragment): number {
    if (!fragment.quality_score_history || fragment.quality_score_history.length === 0) {
      return 0.5; // 默认0.5
    }
    return fragment.quality_score_history.reduce((a, b) => a + b, 0) /
      fragment.quality_score_history.length;
  }

  /**
   * 识别晋升候选
   */
  identifyPromoteCandidates(
    attributions: ContributionAttribution[]
  ): string[] {
    return attributions
      .filter(a => a.is_promotion_candidate)
      .map(a => a.fragment_id);
  }
}

// ============================================
// 反馈采集器（主入口）
// ============================================

/**
 * 反馈采集器
 * Layer3 的主入口类
 */
export class FeedbackCollector {
  private autoSignal: AutoQualitySignal;
  private userFeedbackParser: UserFeedbackParser;
  private contributor: ContributionAttributor;
  private pendingSignals: Map<string, FeedbackSignal[]>;

  constructor() {
    this.autoSignal = new AutoQualitySignal();
    this.userFeedbackParser = new UserFeedbackParser();
    this.contributor = new ContributionAttributor();
    this.pendingSignals = new Map();
  }

  /**
   * 采集自动质量信号
   */
  collectAutoSignal(params: {
    followUpSuccessRate?: number;
    userRequestedRedo?: boolean;
    searchCitationConfidence?: number;
  }): FeedbackSignal[] {
    const signals: FeedbackSignal[] = [];

    if (params.followUpSuccessRate !== undefined) {
      signals.push(this.autoSignal.inferFromFollowUpSuccess(params.followUpSuccessRate));
    }
    if (params.userRequestedRedo !== undefined) {
      signals.push(this.autoSignal.inferFromRedoRequest(params.userRequestedRedo));
    }
    if (params.searchCitationConfidence !== undefined) {
      signals.push(this.autoSignal.inferFromSearchConfidence(params.searchCitationConfidence));
    }

    return signals;
  }

  /**
   * 采集用户反馈
   */
  collectUserFeedback(feedbackText: string): FeedbackSignal {
    const parsed = this.userFeedbackParser.parse(feedbackText);
    return this.userFeedbackParser.toSignal(parsed);
  }

  /**
   * 归因贡献度
   */
  attribute(
    fragments: PromptFragment[],
    qualityScore: number,
    taskType: TaskType
  ): ContributionAttribution[] {
    return this.contributor.attribute(fragments, qualityScore, taskType);
  }

  /**
   * 存储待处理信号
   */
  storeSignal(taskId: string, signals: FeedbackSignal[]): void {
    this.pendingSignals.set(taskId, signals);
  }

  /**
   * 获取并清除待处理信号
   */
  flushSignals(taskId: string): FeedbackSignal[] {
    const signals = this.pendingSignals.get(taskId) || [];
    this.pendingSignals.delete(taskId);
    return signals;
  }

  /**
   * 检查是否需要重试
   */
  shouldRetryBasedOnFeedback(signals: FeedbackSignal[]): boolean {
    for (const signal of signals) {
      if (signal.source === FeedbackSource.EXPLICIT_USER && signal.explicit_feedback) {
        if (this.userFeedbackParser.isNegativeFeedback(signal.explicit_feedback)) {
          return true;
        }
      }
      if (signal.user_requested_redo) {
        return true;
      }
    }
    return false;
  }
}
