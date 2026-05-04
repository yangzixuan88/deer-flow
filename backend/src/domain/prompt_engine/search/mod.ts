/**
 * M09 搜索模块
 * 四种搜索触发场景处理
 */

import {
  SearchTrigger,
  SearchScenario,
  SearchTriggerStatus,
} from '../types';

/**
 * 搜索触发检测器
 */
export class TriggerDetector {
  /**
   * 检测是否应该触发搜索
   */
  shouldTrigger(
    scenario: SearchScenario,
    context: {
      newTaskTypeEncountered?: boolean;
      consecutiveLowQualityCount?: number;
      modelVersionChanged?: boolean;
      isWeeklyNightTime?: boolean;
    }
  ): boolean {
    switch (scenario) {
      case SearchScenario.NEW_TASK_TYPE:
        return context.newTaskTypeEncountered || false;

      case SearchScenario.QUALITY_DECLINE:
        return (context.consecutiveLowQualityCount || 0) >= 3;

      case SearchScenario.MODEL_UPDATE:
        return context.modelVersionChanged || false;

      case SearchScenario.NIGHTLY_INTEL:
        return context.isWeeklyNightTime || false;

      default:
        return false;
    }
  }

  /**
   * 创建搜索触发记录
   */
  createTrigger(
    scenario: SearchScenario,
    conditionDescription: string
  ): SearchTrigger {
    return {
      scenario,
      condition_description: conditionDescription,
      status: SearchTriggerStatus.PENDING,
    };
  }
}

/**
 * 搜索结果处理器
 */
export class ResultProcessor {
  /**
   * 从搜索结果提炼候选提示词
   */
  async extractCandidates(
    searchResults: { title: string; content: string; url: string }[]
  ): Promise<{ content: string; source: string }[]> {
    // 简化：直接返回前3个结果的内容摘要
    return searchResults.slice(0, 3).map(r => ({
      content: r.content.substring(0, 500),
      source: r.url,
    }));
  }
}

/**
 * 提示词资产转换器
 */
export class AssetConverter {
  /**
   * 将搜索结果转换为提示词资产候选
   */
  convertToAssetCandidate(params: {
    content: string;
    source: string;
    taskType: string;
  }): {
    content: string;
    source: string;
    gepa_version: number;
  } {
    return {
      content: params.content,
      source: params.source,
      gepa_version: 0,
    };
  }
}
