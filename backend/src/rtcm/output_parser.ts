/**
 * @file output_parser.ts
 * @description RTCM Structured Output Parser
 * 验证角色输出必须包含所有必填字段，缺字段触发regeneration
 */

import { MemberOutput } from './types';

// 允许的空 dissent 值（视为有效）- 不包含空字符串
const VALID_EMPTY_DISSENT_VALUES = [
  'none',
  'no material dissent',
  'no dissent',
  '无实质异议',
  '无异议',
];

// 必填字段定义
const REQUIRED_MEMBER_OUTPUT_FIELDS: (keyof MemberOutput)[] = [
  'role_id',
  'round',
  'current_position',
  'supported_or_opposed_hypotheses',
  'strongest_evidence',
  'largest_vulnerability',
  'recommended_next_step',
  'should_enter_validation',
  'confidence_interval',
  'dissent_note_if_any',
  'unresolved_uncertainties',
  'evidence_ledger_refs',
  'timestamp',
];

export interface ParseResult {
  valid: boolean;
  missingFields: string[];
  invalidFields: string[];
  regenerated: boolean;
  regenerationReason: string | null;
  output: MemberOutput | null;
}

export interface RegenerationConfig {
  maxRetries: number;
  reason: RegenerationReason;
}

export type RegenerationReason =
  | 'missing_required_fields'
  | 'prose_output_detected'
  | 'schema_mismatch'
  | 'llm_timeout'
  | 'malformed_json';

export type FailureHandling =
  | 'pause'
  | 'escalate'
  | 'abort_round';

export interface ParserConfig {
  maxRegenerations: number;
  onRegeneration?: (roleId: string, reason: RegenerationReason, missingFields: string[]) => Promise<void>;
  onEscalation?: (roleId: string, reason: string, attempts: number) => Promise<void>;
  onPause?: (roleId: string, reason: string) => Promise<void>;
  onAbort?: (roleId: string, reason: string) => Promise<void>;
}

const DEFAULT_PARSER_CONFIG: ParserConfig = {
  maxRegenerations: 1,
};

/**
 * 检查 dissent 值是否有效（允许显式空值）
 */
function isValidDissentValue(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  const strValue = String(value).toLowerCase().trim();
  return VALID_EMPTY_DISSENT_VALUES.includes(strValue);
}

/**
 * 解析并验证成员输出
 */
export function parseMemberOutput(
  raw: unknown,
  expectedRoleId: string,
  round: number
): ParseResult {
  // 验证是对象
  if (!raw || typeof raw !== 'object') {
    return {
      valid: false,
      missingFields: REQUIRED_MEMBER_OUTPUT_FIELDS,
      invalidFields: [],
      regenerated: false,
      regenerationReason: 'malformed_json',
      output: null,
    };
  }

  const obj = raw as Record<string, unknown>;
  const missingFields: string[] = [];
  const invalidFields: string[] = [];

  // 检查必填字段
  for (const field of REQUIRED_MEMBER_OUTPUT_FIELDS) {
    if (field === 'dissent_note_if_any') {
      // dissent 字段允许显式空值
      if (!isValidDissentValue(obj[field])) {
        if (obj[field] === undefined || obj[field] === null || obj[field] === '') {
          missingFields.push(field);
        } else {
          invalidFields.push(`${field}: invalid value "${obj[field]}"`);
        }
      }
    } else if (obj[field] === undefined || obj[field] === null || obj[field] === '') {
      missingFields.push(field);
    }
  }

  // 验证 role_id 匹配
  if (obj.role_id !== expectedRoleId) {
    missingFields.push(`role_id: expected "${expectedRoleId}", got "${obj.role_id}"`);
  }

  if (missingFields.length > 0) {
    return {
      valid: false,
      missingFields,
      invalidFields,
      regenerated: false,
      regenerationReason: 'missing_required_fields',
      output: null,
    };
  }

  if (invalidFields.length > 0) {
    return {
      valid: false,
      missingFields: [],
      invalidFields,
      regenerated: false,
      regenerationReason: 'schema_mismatch',
      output: null,
    };
  }

  // 构建有效输出
  const output: MemberOutput = {
    role_id: String(obj.role_id),
    round: Number(obj.round) || round,
    current_position: String(obj.current_position),
    supported_or_opposed_hypotheses: Array.isArray(obj.supported_or_opposed_hypotheses)
      ? obj.supported_or_opposed_hypotheses.map(String)
      : [],
    strongest_evidence: String(obj.strongest_evidence),
    largest_vulnerability: String(obj.largest_vulnerability),
    recommended_next_step: String(obj.recommended_next_step),
    should_enter_validation: Boolean(obj.should_enter_validation),
    confidence_interval: String(obj.confidence_interval),
    dissent_note_if_any: String(obj.dissent_note_if_any || ''),
    unresolved_uncertainties: Array.isArray(obj.unresolved_uncertainties)
      ? obj.unresolved_uncertainties.map(String)
      : [],
    evidence_ledger_refs: Array.isArray(obj.evidence_ledger_refs)
      ? obj.evidence_ledger_refs.map(String)
      : [],
    timestamp: String(obj.timestamp || new Date().toISOString()),
  };

  // 检查是否是散文式输出
  if (isProseOutput(output)) {
    return {
      valid: false,
      missingFields: [],
      invalidFields: ['current_position: prose output detected'],
      regenerated: false,
      regenerationReason: 'prose_output_detected',
      output: null,
    };
  }

  return {
    valid: true,
    missingFields: [],
    invalidFields: [],
    regenerated: false,
    regenerationReason: null,
    output,
  };
}

/**
 * 检查是否是散文式输出（不允许）
 */
function isProseOutput(output: MemberOutput): boolean {
  const MAX_STRUCTURED_LENGTH = 500;
  const NEWLINE_RATIO_THRESHOLD = 0.3;

  if (output.current_position.length > MAX_STRUCTURED_LENGTH) {
    const newlineCount = (output.current_position.match(/\n/g) || []).length;
    const newlineRatio = newlineCount / output.current_position.length;
    if (newlineRatio > NEWLINE_RATIO_THRESHOLD) {
      return true;
    }
  }

  // 检查是否包含原始 JSON/YAML 块（不允许）
  if (output.current_position.includes('```json') ||
      output.current_position.includes('```yaml') ||
      output.current_position.includes('```')) {
    return true;
  }

  return false;
}

/**
 * 尝试解析输出，支持多次 regeneration
 */
export async function parseWithRegeneration(
  raw: unknown,
  roleId: string,
  round: number,
  config: ParserConfig = DEFAULT_PARSER_CONFIG
): Promise<ParseResult> {
  let attempts = 0;
  let lastResult: ParseResult | null = null;

  while (attempts <= config.maxRegenerations) {
    attempts++;
    lastResult = parseMemberOutput(raw, roleId, round);

    if (lastResult.valid) {
      return lastResult;
    }

    // 失败且还有重试机会
    if (attempts <= config.maxRegenerations) {
      const reason = lastResult.regenerationReason || 'missing_required_fields';

      console.warn(`[OutputParser] ⚠️ ${roleId} 解析失败 (尝试 ${attempts}), 原因: ${reason}`);

      if (config.onRegeneration) {
        await config.onRegeneration(
          roleId,
          reason as RegenerationReason,
          lastResult.missingFields
        );
      }

      // 模拟 regeneration - 实际中这里会重新调用 LLM
      // 重新生成原始输入...
      raw = generateFallbackOutput(roleId, round, lastResult);
    }
  }

  // 所有重试都用尽
  if (lastResult && !lastResult.valid) {
    const finalReason = lastResult.regenerationReason || 'unknown';

    // 第二次失败后选择处理方式
    if (config.onEscalation && attempts > config.maxRegenerations) {
      await config.onEscalation(
        roleId,
        `解析在 ${config.maxRegenerations + 1} 次尝试后仍失败: ${finalReason}`,
        attempts
      );
    }

    // 返回降级输出（允许继续但标记问题）
    return {
      valid: false,
      missingFields: lastResult.missingFields,
      invalidFields: lastResult.invalidFields,
      regenerated: true,
      regenerationReason: finalReason,
      output: null,
    };
  }

  return lastResult || {
    valid: false,
    missingFields: [],
    invalidFields: [],
    regenerated: false,
    regenerationReason: null,
    output: null,
  };
}

/**
 * 生成降级输出（用于 regeneration 失败后）
 */
function generateFallbackOutput(
  roleId: string,
  round: number,
  lastResult: ParseResult
): unknown {
  return {
    role_id: roleId,
    round,
    current_position: `[AUTO-GENERATED] 降级输出 - 原因: ${lastResult.regenerationReason}`,
    supported_or_opposed_hypotheses: [],
    strongest_evidence: '[降级生成]',
    largest_vulnerability: '[降级生成]',
    recommended_next_step: '需要手动审查',
    should_enter_validation: false,
    confidence_interval: '0.3-0.5',
    dissent_note_if_any: 'none',
    unresolved_uncertainties: lastResult.missingFields,
    evidence_ledger_refs: [],
    timestamp: new Date().toISOString(),
  };
}

/**
 * 全量验证一轮所有输出
 */
export interface RoundValidationResult {
  allPresent: boolean;
  allValid: boolean;
  missingMembers: string[];
  invalidMembers: string[];
  proseViolations: string[];
  orderCorrect: boolean;
  duplicatesFound: string[];
  canProceed: boolean;
  blockingReason: string | null;
}

export function validateRoundOutputs(
  outputs: Map<string, MemberOutput>,
  expectedOrder: string[]
): RoundValidationResult {
  const result: RoundValidationResult = {
    allPresent: false,
    allValid: false,
    missingMembers: [],
    invalidMembers: [],
    proseViolations: [],
    orderCorrect: false,
    duplicatesFound: [],
    canProceed: false,
    blockingReason: null,
  };

  const outputRoleIds = Array.from(outputs.keys());

  // 1. 检查数量
  if (outputRoleIds.length !== expectedOrder.length) {
    result.missingMembers = expectedOrder.filter(id => !outputs.has(id));
    result.blockingReason = `成员数量错误: 期望 ${expectedOrder.length}, 实际 ${outputRoleIds.length}`;
  }

  // 2. 检查 role_id 集合完整性
  const expectedSet = new Set(expectedOrder);
  const actualSet = new Set(outputRoleIds);

  for (const id of expectedSet) {
    if (!actualSet.has(id)) {
      result.missingMembers.push(id);
    }
  }

  // 3. 检查重复
  const seen = new Set<string>();
  for (const id of outputRoleIds) {
    if (seen.has(id)) {
      result.duplicatesFound.push(id);
    }
    seen.add(id);
  }

  // 4. 检查顺序
  const actualOrder = outputRoleIds.filter(id => expectedOrder.includes(id));
  result.orderCorrect = actualOrder.every((id, index) => id === expectedOrder[index]);

  // 5. 检查散文式输出
  for (const [id, output] of outputs) {
    if (isProseOutput(output)) {
      result.proseViolations.push(id);
    }
  }

  // 综合判断
  result.allPresent = result.missingMembers.length === 0;
  result.allValid = result.allPresent &&
    result.duplicatesFound.length === 0 &&
    result.proseViolations.length === 0;

  if (!result.allPresent) {
    result.blockingReason = `缺少成员: ${result.missingMembers.join(', ')}`;
  } else if (result.duplicatesFound.length > 0) {
    result.blockingReason = `重复成员: ${result.duplicatesFound.join(', ')}`;
  } else if (!result.orderCorrect) {
    result.blockingReason = '发言顺序不正确';
  } else if (result.proseViolations.length > 0) {
    result.blockingReason = `散文式输出违规: ${result.proseViolations.join(', ')}`;
  }

  result.canProceed = result.allValid && result.orderCorrect;

  return result;
}

/**
 * 获取 regeneration 原因的分类描述
 */
export function getRegenerationReasonDescription(reason: RegenerationReason): string {
  const descriptions: Record<RegenerationReason, string> = {
    'missing_required_fields': '缺少必填字段',
    'prose_output_detected': '检测到散文式输出',
    'schema_mismatch': '数据结构不匹配',
    'llm_timeout': 'LLM 调用超时',
    'malformed_json': 'JSON 格式错误',
  };
  return descriptions[reason] || '未知错误';
}
