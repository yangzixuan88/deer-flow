/**
 * M01 意图分类器
 * ================================================
 * 三条路由路径分类: 直答 / 追问 / 编排
 * ================================================
 */

import {
  IntentRoute,
  IntentClassification,
  ComplexityAssessment,
  ROUTING_CONFIG,
} from './types';

import { SystemType } from '../m04/types';

// ============================================
// 复杂度评分关键词
// ============================================

const SEARCH_INDICATORS = [
  '搜索', '查找', '查询', '找', '搜', '检索',
  'search', 'find', 'lookup', 'query',
];

const TOOL_INDICATORS = [
  '搜索', '查找', '查询', '检索',
  '执行', '运行', '启动', '停止', '部署', '构建',
  'execute', 'run', 'start', 'stop', 'deploy', 'build', 'search', 'find',
];

const FILE_OPS_INDICATORS = [
  '创建', '删除', '修改', '编辑', '写入', '读取', '移动', '复制',
  'create', 'delete', 'edit', 'write', 'read', 'move', 'copy',
];

const MULTI_STEP_INDICATORS = [
  '首先', '然后', '接着', '之后', '最后', '下一步',
  'first', 'then', 'next', 'after', 'finally', 'step',
];

const COMPLEXITY_PATTERNS = [
  /首先.*然后/,
  /(\d+).*步/,
  /多.*步/,
  /流程/,
  /自动化/,
];

// ============================================
// 意图分类器
// ============================================

export class IntentClassifier {
  /**
   * 分类用户输入
   */
  classify(input: string): IntentClassification {
    const trimmedInput = input.trim();
    const complexity = this.estimateComplexity(trimmedInput);

    // 路径A: 直接回答 - 简短、无需工具
    if (this.isDirectAnswerCandidate(trimmedInput, complexity)) {
      return {
        route: IntentRoute.DIRECT_ANSWER,
        complexity,
        confidence: 0.9,
        reasoning: '简短查询，无需工具，可直接回答',
      };
    }

    // 路径B: 追问补全 - 意图模糊、缺参数
    if (this.needsClarification(trimmedInput, complexity)) {
      return {
        route: IntentRoute.CLARIFICATION,
        complexity,
        confidence: 0.75,
        suggestedSystem: undefined,
        reasoning: '意图不明确或缺少关键参数，需要澄清',
      };
    }

    // 路径C: 编排 - 多步骤、需要搜索/执行
    return {
      route: IntentRoute.ORCHESTRATION,
      complexity,
      confidence: 0.85,
      suggestedSystem: this.suggestSystemType(trimmedInput, complexity),
      reasoning: '复杂任务，需要DAG规划和多系统协同',
    };
  }

  /**
   * 评估复杂度
   */
  estimateComplexity(input: string): ComplexityAssessment {
    const normalizedInput = input.toLowerCase();
    let score = 1;
    let needsSearch = false;
    let needsTools = false;
    let needsFileOps = false;

    // 检查搜索需求
    for (const indicator of SEARCH_INDICATORS) {
      if (normalizedInput.includes(indicator)) {
        needsSearch = true;
        score += 2;
        break;
      }
    }

    // 检查工具需求
    for (const indicator of TOOL_INDICATORS) {
      if (normalizedInput.includes(indicator)) {
        needsTools = true;
        score += 3;
        break;
      }
    }

    // 检查文件操作需求
    for (const indicator of FILE_OPS_INDICATORS) {
      if (normalizedInput.includes(indicator)) {
        needsFileOps = true;
        score += 2;
        break;
      }
    }

    // 检查多步骤模式
    for (const pattern of COMPLEXITY_PATTERNS) {
      if (pattern.test(input)) {
        score += 3;
        break;
      }
    }

    // 检查步骤关键词
    for (const indicator of MULTI_STEP_INDICATORS) {
      if (normalizedInput.includes(indicator)) {
        score += 1;
        break;
      }
    }

    // 输入长度也增加复杂度
    if (input.length > 100) score += 1;
    if (input.length > 300) score += 2;

    // 限制分数范围
    score = Math.min(10, Math.max(1, score));

    // 估算耗时
    let estimatedDuration = score * 3; // 每分约3秒
    if (needsSearch) estimatedDuration += 5;
    if (needsTools) estimatedDuration += 10;
    if (needsFileOps) estimatedDuration += 5;

    // 风险评估
    let riskLevel: 'low' | 'medium' | 'high' = 'low';
    if (needsTools && normalizedInput.includes('rm')) riskLevel = 'high';
    else if (needsTools || needsFileOps) riskLevel = 'medium';

    return {
      score,
      estimatedDuration,
      needsSearch,
      needsTools,
      needsFileOps,
      riskLevel,
    };
  }

  /**
   * 是否为直接回答候选
   */
  private isDirectAnswerCandidate(input: string, complexity: ComplexityAssessment): boolean {
    // 字数限制
    if (input.length > ROUTING_CONFIG.DIRECT_ANSWER_MAX_CHARS) {
      return false;
    }

    // 复杂度限制
    if (complexity.score >= ROUTING_CONFIG.ORCHESTRATION_MIN_COMPLEXITY) {
      return false;
    }

    // 无需工具和文件操作
    if (complexity.needsTools || complexity.needsFileOps) {
      return false;
    }

    // 排除模糊指代词（这些应该走澄清路径）
    const vagueIndicators = ['这个', '那个', '它', '这个事', '那个问题', '上述'];
    for (const indicator of vagueIndicators) {
      if (input.includes(indicator)) {
        return false;
      }
    }

    return true;
  }

  /**
   * 是否需要澄清
   */
  private needsClarification(input: string, complexity: ComplexityAssessment): boolean {
    // 过于简短
    if (input.length < 5) {
      return true;
    }

    // 包含模糊指代词 - 直接触发澄清，无需看复杂度
    const vagueIndicators = ['这个', '那个', '它', '这个事', '那个问题', '上述'];
    for (const indicator of vagueIndicators) {
      if (input.includes(indicator)) {
        return true;
      }
    }

    // 复杂度中等但意图不明确
    if (complexity.score >= 3 && complexity.score < 5) {
      // 检查是否缺少关键信息
      const missingPatterns = [
        /帮我.*但不告诉我.*/,
        /做.*但.*没说.*/,
      ];
      for (const pattern of missingPatterns) {
        if (pattern.test(input)) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * 推荐系统类型
   */
  private suggestSystemType(input: string, complexity: ComplexityAssessment): SystemType | undefined {
    const normalizedInput = input.toLowerCase();

    // 搜索优先
    if (complexity.needsSearch || SEARCH_INDICATORS.some(i => normalizedInput.includes(i))) {
      return 'search' as SystemType;
    }

    // 工作流优先
    if (COMPLEXITY_PATTERNS.some(p => p.test(input))) {
      return 'workflow' as SystemType;
    }

    // 默认任务系统
    return 'task' as SystemType;
  }

  /**
   * 检查是否需要搜索
   */
  needsSearch(input: string): boolean {
    const complexity = this.estimateComplexity(input);
    return complexity.needsSearch;
  }

  /**
   * 检查是否需要工具
   */
  needsTools(input: string): boolean {
    const complexity = this.estimateComplexity(input);
    return complexity.needsTools;
  }
}

// ============================================
// 单例导出
// ============================================

export const intentClassifier = new IntentClassifier();
