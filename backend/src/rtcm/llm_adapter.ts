/**
 * @file llm_adapter.ts
 * @description RTCM LLM Adapter v2 - 多 Provider 支持与结构化输出稳健性
 * 支持 Anthropic/OpenAI/MiniMax/Mock
 * 包含 Response Sanitizer 和 Parser Telemetry
 */

import * as https from 'https';
import { MemberOutput } from './types';
import { parseMemberOutput, ParseResult } from './output_parser';

// ============================================================================
// LLM Provider Types
// ============================================================================

export enum RTCMModelProvider {
  ANTHROPIC = 'anthropic',
  OPENAI = 'openai',
  MINIMAX = 'minimax',
  CLAUDE_CODE = 'claude_code',
  MOCK = 'mock',
}

// ============================================================================
// Provider Profile - 策略抽象
// ============================================================================

export interface ProviderProfile {
  name: RTCMModelProvider;
  model: string;
  baseUrl: string;
  endpoint: string;
  authHeader: string;
  authKey: string;
  systemRoleSupported: boolean;
  extractionStrategy: 'json_block' | 'first_brace' | 'last_brace' | 'lenient';
  structuredPromptSuffix: string;
  timeout: number;
}

export const PROVIDER_PROFILES: Record<RTCMModelProvider, ProviderProfile> = {
  [RTCMModelProvider.ANTHROPIC]: {
    name: RTCMModelProvider.ANTHROPIC,
    model: 'claude-sonnet-4-20250514',
    baseUrl: 'https://api.anthropic.com/v1',
    endpoint: '/messages',
    authHeader: 'x-api-key',
    authKey: 'ANTHROPIC_API_KEY',
    systemRoleSupported: true,
    extractionStrategy: 'json_block',
    structuredPromptSuffix: '。你的输出必须是严格的 JSON 格式，禁止额外解释。',
    timeout: 60000,
  },
  [RTCMModelProvider.OPENAI]: {
    name: RTCMModelProvider.OPENAI,
    model: 'gpt-4o',
    baseUrl: 'https://api.openai.com/v1',
    endpoint: '/chat/completions',
    authHeader: 'Authorization',
    authKey: 'OPENAI_API_KEY',
    systemRoleSupported: true,
    extractionStrategy: 'json_block',
    structuredPromptSuffix: 'Your output must be strict JSON only, no extra explanation.',
    timeout: 60000,
  },
  [RTCMModelProvider.MINIMAX]: {
    name: RTCMModelProvider.MINIMAX,
    model: 'MiniMax-M2.7',
    baseUrl: 'https://api.minimaxi.com/v1',
    endpoint: '/chat/completions',
    authHeader: 'Authorization',
    authKey: 'MINIMAX_API_KEY',
    systemRoleSupported: false,  // MiniMax 不支持 system role
    extractionStrategy: 'lenient',  // MiniMax 有思考内容干扰
    structuredPromptSuffix: '。输出必须是严格的 JSON 格式，禁止额外解释。',
    timeout: 120000,
  },
  [RTCMModelProvider.CLAUDE_CODE]: {
    name: RTCMModelProvider.CLAUDE_CODE,
    model: 'claude-sonnet-4-20250514',
    baseUrl: 'http://localhost:8080',
    endpoint: '/chat',
    authHeader: 'Authorization',
    authKey: 'CLAUDE_CODE_API_KEY',
    systemRoleSupported: true,
    extractionStrategy: 'json_block',
    structuredPromptSuffix: '。你的输出必须是严格的 JSON 格式。',
    timeout: 120000,
  },
  [RTCMModelProvider.MOCK]: {
    name: RTCMModelProvider.MOCK,
    model: 'mock',
    baseUrl: '',
    endpoint: '',
    authHeader: '',
    authKey: '',
    systemRoleSupported: true,
    extractionStrategy: 'json_block',
    structuredPromptSuffix: '',
    timeout: 1000,
  },
};

// ============================================================================
// Telemetry Types
// ============================================================================

export interface ParserTelemetry {
  provider: RTCMModelProvider;
  model: string;
  rawLength: number;
  sanitizedLength: number;
  extractionStrategy: string;
  jsonExtractionSuccess: boolean;
  parseSuccess: boolean;
  regenerationCount: number;
  finalFallback: boolean;
  timestamp: string;
}

// ============================================================================
// LLM Config
// ============================================================================

export interface RTCMModelConfig {
  provider: RTCMModelProvider;
  apiKey?: string;
  model?: string;
  maxTokens?: number;
  temperature?: number;
}

export interface RTCMCallResult {
  raw: string;
  parsed: ParseResult;
  usage?: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
  };
  model: string;
  success: boolean;
  error?: string;
  telemetry: ParserTelemetry;
}

// ============================================================================
// Default Configuration
// ============================================================================

function getDefaultConfig(): RTCMModelConfig {
  // 优先级: MINIMAX > ANTHROPIC > OPENAI > MOCK
  if (process.env.MINIMAX_API_KEY) {
    return {
      provider: RTCMModelProvider.MINIMAX,
      model: 'MiniMax-M2.7',
    };
  }
  if (process.env.ANTHROPIC_API_KEY) {
    return {
      provider: RTCMModelProvider.ANTHROPIC,
      model: 'claude-sonnet-4-20250514',
    };
  }
  if (process.env.OPENAI_API_KEY) {
    return {
      provider: RTCMModelProvider.OPENAI,
      model: 'gpt-4o',
    };
  }
  return {
    provider: RTCMModelProvider.MOCK,
  };
}

// ============================================================================
// Response Sanitizer
// ============================================================================

export class ResponseSanitizer {
  /**
   * 清洗 Provider 特有噪声
   */
  static sanitize(raw: string, provider: RTCMModelProvider): string {
    let cleaned = raw;

    switch (provider) {
      case RTCMModelProvider.MINIMAX:
        // MiniMax 思考内容清理
        cleaned = this.removeThinkTags(cleaned);
        cleaned = this.removeMinimaxThinkTags(cleaned);
        break;

      case RTCMModelProvider.ANTHROPIC:
      case RTCMModelProvider.OPENAI:
      default:
        // 通用清理
        cleaned = this.removeGenericThinkTags(cleaned);
        break;
    }

    return cleaned.trim();
  }

  private static removeThinkTags(text: string): string {
    // 移除 <n thinkers>...</n thinkers>
    return text.replace(/<n thinkers>[\s\S]*?<\/n thinkers>/gi, '');
  }

  private static removeMinimaxThinkTags(text: string): string {
    // 移除 MiniMax 特有的思考标签
    return text
      .replace(/<think>[\s\S]*?<\/think>/gi, '')
      .replace(/<\/n thinkers>[\s\S]*$/gi, '')
      .replace(/<n think>[\s\S]*?<\/n think>/gi, '');
  }

  private static removeGenericThinkTags(text: string): string {
    return text
      .replace(/<think>[\s\S]*?<\/think>/gi, '')
      .replace(/<thinking>[\s\S]*?<\/thinking>/gi, '')
      .replace(/<plan>[\s\S]*?<\/plan>/gi, '');
  }
}

// ============================================================================
// JSON Extractor
// ============================================================================

export class JsonExtractor {
  /**
   * 根据策略提取 JSON
   */
  static extract(
    raw: string,
    strategy: ProviderProfile['extractionStrategy']
  ): { json: string; success: boolean } {
    switch (strategy) {
      case 'json_block':
        return this.extractJsonBlock(raw);
      case 'first_brace':
        return this.extractFirstBrace(raw);
      case 'last_brace':
        return this.extractLastBrace(raw);
      case 'lenient':
        return this.extractLenient(raw);
      default:
        return this.extractJsonBlock(raw);
    }
  }

  private static extractJsonBlock(raw: string): { json: string; success: boolean } {
    const match = raw.match(/```json\s*([\s\S]*?)\s*```/);
    if (match) {
      return { json: match[1].trim(), success: true };
    }
    // 尝试 ``` 块
    const anyBlock = raw.match(/```\s*([\s\S]*?)\s*```/);
    if (anyBlock) {
      return { json: anyBlock[1].trim(), success: true };
    }
    return { json: raw, success: false };
  }

  private static extractFirstBrace(raw: string): { json: string; success: boolean } {
    const firstBrace = raw.indexOf('{');
    const lastBrace = raw.lastIndexOf('}');
    if (firstBrace >= 0 && lastBrace > firstBrace) {
      return { json: raw.substring(firstBrace, lastBrace + 1), success: true };
    }
    return { json: raw, success: false };
  }

  private static extractLastBrace(raw: string): { json: string; success: boolean } {
    const lastBrace = raw.lastIndexOf('}');
    if (lastBrace > 0) {
      return { json: raw.substring(0, lastBrace + 1), success: true };
    }
    return { json: raw, success: false };
  }

  private static extractLenient(raw: string): { json: string; success: boolean } {
    // 先尝试 JSON block
    const block = this.extractJsonBlock(raw);
    if (block.success) {
      try {
        JSON.parse(block.json);
        return block;
      } catch {}
    }

    // 尝试找到完整的 JSON 对象
    const firstBrace = raw.indexOf('{');
    const lastBrace = raw.lastIndexOf('}');
    if (firstBrace >= 0 && lastBrace > firstBrace) {
      return { json: raw.substring(firstBrace, lastBrace + 1), success: true };
    }

    return { json: raw, success: false };
  }
}

// ============================================================================
// Lenient Parser - 处理不完整的 JSON
// ============================================================================

export function lenientParse(text: string, expectedRoleId: string, round: number): MemberOutput | null {
  const result: MemberOutput = {
    role_id: expectedRoleId,
    round,
    current_position: '',
    supported_or_opposed_hypotheses: [],
    strongest_evidence: '',
    largest_vulnerability: '',
    recommended_next_step: '',
    should_enter_validation: false,
    confidence_interval: '0.5-0.7',
    dissent_note_if_any: 'none',
    unresolved_uncertainties: [],
    evidence_ledger_refs: [],
    timestamp: new Date().toISOString(),
  };

  let hasAnyField = false;

  // 提取字符串字段
  const extractString = (field: keyof MemberOutput) => {
    const pattern = new RegExp(`"${field}"\\s*:\\s*"([^"]*)"`, 'i');
    const match = text.match(pattern);
    if (match) {
      (result as any)[field] = match[1];
      hasAnyField = true;
    }
  };

  // 提取数组字段
  const extractArray = (field: keyof MemberOutput) => {
    const pattern = new RegExp(`"${field}"\\s*:\\s*\\[([^\\]]*)\\]`, 'i');
    const match = text.match(pattern);
    if (match) {
      const items = match[1].match(/"([^"]*)"/g);
      if (items) {
        (result as any)[field] = items.map((i: string) => i.replace(/"/g, ''));
        hasAnyField = true;
      }
    }
  };

  // 提取布尔字段
  const extractBoolean = (field: keyof MemberOutput) => {
    const pattern = new RegExp(`"${field}"\\s*:\\s*(true|false)`, 'i');
    const match = text.match(pattern);
    if (match) {
      (result as any)[field] = match[1].toLowerCase() === 'true';
      hasAnyField = true;
    }
  };

  // 提取所有字段
  extractString('current_position');
  extractString('strongest_evidence');
  extractString('largest_vulnerability');
  extractString('recommended_next_step');
  extractString('confidence_interval');
  extractString('dissent_note_if_any');
  extractArray('supported_or_opposed_hypotheses');
  extractArray('unresolved_uncertainties');
  extractArray('evidence_ledger_refs');
  extractBoolean('should_enter_validation');

  if (hasAnyField && result.current_position) {
    return result;
  }

  return null;
}

// ============================================================================
// RTCM LLM Adapter
// ============================================================================

export class RTCMModelAdapter {
  private config: RTCMModelConfig;
  private profile: ProviderProfile;

  constructor(config: Partial<RTCMModelConfig> = {}) {
    this.config = { ...getDefaultConfig(), ...config };
    this.profile = PROVIDER_PROFILES[this.config.provider];
  }

  /**
   * 检查是否已配置
   */
  isConfigured(): boolean {
    if (this.config.provider === RTCMModelProvider.MOCK) {
      return true;
    }
    const apiKey = process.env[this.profile.authKey];
    return !!apiKey;
  }

  /**
   * 获取 Provider Profile
   */
  getProfile(): ProviderProfile {
    return this.profile;
  }

  /**
   * 调用模型生成成员输出
   */
  async generateMemberOutput(
    roleId: string,
    prompt: string,
    round: number,
    expectedRoleId: string
  ): Promise<RTCMCallResult> {
    const telemetry: ParserTelemetry = {
      provider: this.config.provider,
      model: this.profile.model,
      rawLength: 0,
      sanitizedLength: 0,
      extractionStrategy: this.profile.extractionStrategy,
      jsonExtractionSuccess: false,
      parseSuccess: false,
      regenerationCount: 0,
      finalFallback: false,
      timestamp: new Date().toISOString(),
    };

    console.log(`[RTCMModel] 调用 ${roleId} (${this.config.provider})...`);

    if (!this.isConfigured()) {
      console.warn(`[RTCMModel] 未配置 API，使用 Mock 模式`);
      telemetry.finalFallback = true;
      const result = this.mockOutput(roleId, round);
      return { ...result, telemetry };
    }

    try {
      const result = await this.callProvider(roleId, prompt, round, expectedRoleId);
      return {
        ...result,
        telemetry: {
          ...telemetry,
          rawLength: result.raw.length,
        },
      };
    } catch (error) {
      console.error(`[RTCMModel] 调用失败: ${error}`);
      telemetry.finalFallback = true;
      return {
        raw: '',
        parsed: {
          valid: false,
          missingFields: ['llm_timeout'],
          invalidFields: [],
          regenerated: false,
          regenerationReason: 'llm_timeout',
          output: null,
        },
        success: false,
        error: error instanceof Error ? error.message : String(error),
        model: this.profile.model,
        telemetry,
      };
    }
  }

  /**
   * 调用 Provider
   */
  private async callProvider(
    roleId: string,
    prompt: string,
    round: number,
    expectedRoleId: string
  ): Promise<RTCMCallResult> {
    const systemPrompt = this.buildSystemPrompt(roleId);
    const fullPrompt = `${prompt}${this.profile.structuredPromptSuffix}`;

    let raw: string;

    switch (this.config.provider) {
      case RTCMModelProvider.ANTHROPIC:
        raw = await this.callAnthropic(systemPrompt, fullPrompt);
        break;
      case RTCMModelProvider.OPENAI:
        raw = await this.callOpenAI(systemPrompt, fullPrompt);
        break;
      case RTCMModelProvider.MINIMAX:
        raw = await this.callMinimax(systemPrompt, fullPrompt);
        break;
      default:
        return this.mockOutput(roleId, round);
    }

    // Sanitize
    const sanitized = ResponseSanitizer.sanitize(raw, this.config.provider);

    // Extract JSON
    const { json: jsonStr, success: extractSuccess } = JsonExtractor.extract(
      sanitized,
      this.profile.extractionStrategy
    );

    // Parse
    let parsed: ParseResult;
    try {
      const obj = JSON.parse(jsonStr);
      parsed = parseMemberOutput(obj, expectedRoleId, round);
    } catch {
      // 尝试 lenient parsing
      const lenient = lenientParse(sanitized, expectedRoleId, round);
      if (lenient) {
        parsed = {
          valid: true,
          missingFields: [],
          invalidFields: [],
          regenerated: false,
          regenerationReason: null,
          output: lenient,
        };
      } else {
        parsed = {
          valid: false,
          missingFields: ['json_parse_failed'],
          invalidFields: [],
          regenerated: false,
          regenerationReason: 'malformed_json',
          output: null,
        };
      }
    }

    return {
      raw,
      parsed,
      model: this.profile.model,
      success: parsed.valid,
      telemetry: {
        provider: this.config.provider,
        model: this.profile.model,
        rawLength: raw.length,
        sanitizedLength: sanitized.length,
        extractionStrategy: this.profile.extractionStrategy,
        jsonExtractionSuccess: extractSuccess,
        parseSuccess: parsed.valid,
        regenerationCount: 0,
        finalFallback: false,
        timestamp: new Date().toISOString(),
      },
    };
  }

  /**
   * 调用 Anthropic
   */
  private async callAnthropic(systemPrompt: string, prompt: string): Promise<string> {
    const apiKey = process.env.ANTHROPIC_API_KEY || '';
    const body = JSON.stringify({
      model: this.config.model || this.profile.model,
      max_tokens: this.config.maxTokens || 2048,
      temperature: this.config.temperature || 0.5,
      system: systemPrompt,
      messages: [{ role: 'user', content: prompt }],
    });

    const urlObj = new URL(this.profile.endpoint, this.profile.baseUrl);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || 443,
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [this.profile.authHeader]: apiKey,
        'anthropic-version': '2023-06-01',
        'Content-Length': Buffer.byteLength(body),
      },
      timeout: this.profile.timeout,
    };

    return this.makeRequest(options, body);
  }

  /**
   * 调用 OpenAI
   */
  private async callOpenAI(systemPrompt: string, prompt: string): Promise<string> {
    const apiKey = process.env.OPENAI_API_KEY || '';
    const body = JSON.stringify({
      model: this.config.model || this.profile.model,
      max_tokens: this.config.maxTokens || 2048,
      temperature: this.config.temperature || 0.5,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: prompt },
      ],
    });

    const urlObj = new URL(this.profile.endpoint, this.profile.baseUrl);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || 443,
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [this.profile.authHeader]: `Bearer ${apiKey}`,
        'Content-Length': Buffer.byteLength(body),
      },
      timeout: this.profile.timeout,
    };

    return this.makeRequest(options, body);
  }

  /**
   * 调用 MiniMax（不支持 system role）
   */
  private async callMinimax(systemPrompt: string, prompt: string): Promise<string> {
    const apiKey = process.env.MINIMAX_API_KEY || '';
    // MiniMax 不支持 system role，需要合并到 user message
    const combinedPrompt = `[系统提示] ${systemPrompt}\n\n[用户输入] ${prompt}`;

    const body = JSON.stringify({
      model: this.config.model || this.profile.model,
      max_tokens: this.config.maxTokens || 2048,
      temperature: this.config.temperature || 0.5,
      messages: [{ role: 'user', content: combinedPrompt }],
    });

    const urlObj = new URL(this.profile.endpoint, this.profile.baseUrl);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || 443,
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [this.profile.authHeader]: `Bearer ${apiKey}`,
        'Content-Length': Buffer.byteLength(body),
      },
      timeout: this.profile.timeout,
    };

    return this.makeRequest(options, body);
  }

  /**
   * 发起 HTTPS 请求
   */
  private makeRequest(options: any, body: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const req = https.request(options, (res) => {
        let responseBody = '';
        res.on('data', chunk => responseBody += chunk);
        res.on('end', () => {
          if (res.statusCode && res.statusCode >= 400) {
            reject(new Error(`HTTP ${res.statusCode}: ${responseBody.substring(0, 200)}`));
            return;
          }
          try {
            const data = JSON.parse(responseBody);
            if (data.error) {
              reject(new Error(data.error.message || JSON.stringify(data.error)));
              return;
            }
            // 统一提取 content
            let content = '';
            if (this.config.provider === RTCMModelProvider.ANTHROPIC) {
              content = data.content?.[0]?.text || '';
            } else {
              content = data.choices?.[0]?.message?.content || '';
            }
            resolve(content);
          } catch (e) {
            reject(new Error(`解析响应失败: ${responseBody.substring(0, 100)}`));
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('请求超时')); });
      req.write(body);
      req.end();
    });
  }

  /**
   * 构建角色系统提示
   */
  private buildSystemPrompt(roleId: string): string {
    const rolePrompts: Record<string, string> = {
      'rtcm-trend-agent': '你是趋势分析师，专注于行业趋势、市场动向和技术发展方向。',
      'rtcm-value-agent': '你是价值判断官，专注于价值评估、成本效益分析和优先级排序。',
      'rtcm-architecture-agent': '你是架构设计师，专注于系统架构、技术选型和可扩展性。',
      'rtcm-automation-agent': '你是自动化专家，专注于流程自动化、效率优化和工具选择。',
      'rtcm-quality-agent': '你是质量评估官，专注于质量标准、测试策略和风险评估。',
      'rtcm-efficiency-agent': '你是效率优化官，专注于资源利用、性能优化和成本控制。',
      'rtcm-challenger-agent': '你是质疑官，专注于挑战假设、识别漏洞和提出反对意见。',
      'rtcm-validator-agent': '你是验证官，专注于验证方案、测试设计和结果评估。',
      'rtcm-chair-agent': '你是圆桌主持官，负责主持讨论、总结共识和管理会议流程。',
      'rtcm-supervisor-agent': '你是圆桌监督官，负责检查协议执行、识别违规和维护讨论质量。',
    };
    return rolePrompts[roleId] || '你是 RTCM 圆桌会议成员。';
  }

  /**
   * Mock 输出
   */
  private mockOutput(roleId: string, round: number): RTCMCallResult {
    const mockOutputs: Record<string, Partial<MemberOutput>> = {
      'rtcm-trend-agent': {
        current_position: `趋势分析师认为：当前市场趋势显示情感AI将成为下一代交互的核心。`,
        strongest_evidence: '根据 Gartner 2025 报告，情感AI市场年复合增长率达 34%',
        largest_vulnerability: '技术成熟度可能低于预期，法规风险存在',
        recommended_next_step: '建议进入假设构建阶段',
        confidence_interval: '0.65-0.82',
        dissent_note_if_any: 'none',
        unresolved_uncertainties: ['监管政策走向不明'],
      },
      'rtcm-value-agent': {
        current_position: `价值判断官认为：ROI 取决于情感真实度提升能否直接转化为留存率提升。`,
        strongest_evidence: '用户调研显示 78% 用户表示情感真实度影响留存',
        largest_vulnerability: '成本投入较高，需要显著留存提升才能覆盖',
        recommended_next_step: '建议进入证据收集阶段',
        confidence_interval: '0.58-0.75',
        dissent_note_if_any: 'none',
        unresolved_uncertainties: ['留存提升幅度待验证'],
      },
      'rtcm-architecture-agent': {
        current_position: `架构设计师认为：当前架构支持情感增强，但需要引入新的情感模型层。`,
        strongest_evidence: '现有 transformer 架构可直接扩展支持情感token',
        largest_vulnerability: '延迟增加可能影响实时交互体验',
        recommended_next_step: '建议进入解决方案生成阶段',
        confidence_interval: '0.72-0.88',
        dissent_note_if_any: 'none',
        unresolved_uncertainties: ['延迟增加幅度待测量'],
      },
      'rtcm-automation-agent': {
        current_position: `自动化专家建议：情感数据收集和标注流程需要高度自动化。`,
        strongest_evidence: '自动化pipeline可将标注成本降低60%',
        largest_vulnerability: '情感标注主观性强，完全自动化可能降低质量',
        recommended_next_step: '建议进入验证设计阶段',
        confidence_interval: '0.68-0.82',
        dissent_note_if_any: 'none',
        unresolved_uncertainties: ['人机协作模式待设计'],
      },
      'rtcm-quality-agent': {
        current_position: `质量评估官关注：A/B测试方案需确保统计显著性。`,
        strongest_evidence: '参考行业基准，样本量需 >= 1000/组',
        largest_vulnerability: '用户反馈主观性强，量化评估困难',
        recommended_next_step: '建议设计验证方案',
        confidence_interval: '0.70-0.85',
        dissent_note_if_any: 'none',
        unresolved_uncertainties: ['情感评分标准待制定'],
      },
      'rtcm-efficiency-agent': {
        current_position: `效率优化官评估：情感增强带来的计算成本增加需控制在 15% 以内。`,
        strongest_evidence: '通过模型蒸馏可将参数量减少40%而精度损失 < 5%',
        largest_vulnerability: '情感模型可能需要独立推理，增加基础设施复杂度',
        recommended_next_step: '建议进入下一阶段',
        confidence_interval: '0.62-0.78',
        dissent_note_if_any: 'none',
        unresolved_uncertainties: ['基础设施改造成本待评估'],
      },
      'rtcm-challenger-agent': {
        current_position: `质疑官提出：情感AI是否真的是用户核心需求，还是伪需求？`,
        strongest_evidence: '部分用户访谈显示功能实用性比情感真实度更重要',
        largest_vulnerability: '可能高估了情感真实度的重要性',
        recommended_next_step: '建议补充用户调研数据',
        confidence_interval: '0.45-0.65',
        dissent_note_if_any: 'no material dissent',
        unresolved_uncertainties: ['情感需求与功能需求优先级对比'],
      },
      'rtcm-validator-agent': {
        current_position: `验证官设计验证方案：可通过用户留存率和情感评分双指标验证。`,
        strongest_evidence: 'A/B 测试是验证因果关系的金标准',
        largest_vulnerability: '测试周期长，可能需要 4-6 周才能收集足够数据',
        recommended_next_step: '建议开始验证执行',
        confidence_interval: '0.75-0.90',
        dissent_note_if_any: 'none',
        unresolved_uncertainties: ['测试周期内的用户流失风险'],
      },
      'rtcm-chair-agent': {
        current_position: `主持官总结：议题讨论充分，建议进入裁决阶段。`,
        strongest_evidence: '8位议员已完成讨论，共识已形成',
        largest_vulnerability: '部分议员对 ROI 仍存疑虑',
        recommended_next_step: '建议进入裁决',
        confidence_interval: '0.70-0.85',
        dissent_note_if_any: '质疑官对需求真实性提出挑战',
        unresolved_uncertainties: ['情感AI是否是核心需求'],
      },
      'rtcm-supervisor-agent': {
        current_position: `监督官检查：协议执行正常，全员按时提交输出。`,
        strongest_evidence: '10个角色全部按时发言，无违规',
        largest_vulnerability: '部分输出证据引用不足',
        recommended_next_step: '允许进入下一阶段',
        confidence_interval: '0.85-0.95',
        dissent_note_if_any: 'none',
        unresolved_uncertainties: [],
      },
    };

    const mock = mockOutputs[roleId] || {
      current_position: `[Mock] ${roleId} 的立场`,
      strongest_evidence: 'mock evidence',
      largest_vulnerability: 'mock vulnerability',
      recommended_next_step: '继续下一阶段',
      confidence_interval: '0.5-0.7',
      dissent_note_if_any: 'none',
      unresolved_uncertainties: [],
    };

    const output: MemberOutput = {
      role_id: roleId,
      round,
      current_position: mock.current_position!,
      supported_or_opposed_hypotheses: [],
      strongest_evidence: mock.strongest_evidence!,
      largest_vulnerability: mock.largest_vulnerability!,
      recommended_next_step: mock.recommended_next_step!,
      should_enter_validation: false,
      confidence_interval: mock.confidence_interval!,
      dissent_note_if_any: mock.dissent_note_if_any!,
      unresolved_uncertainties: mock.unresolved_uncertainties || [],
      evidence_ledger_refs: [],
      timestamp: new Date().toISOString(),
    };

    return {
      raw: JSON.stringify(output),
      parsed: {
        valid: true,
        missingFields: [],
        invalidFields: [],
        regenerated: false,
        regenerationReason: null,
        output,
      },
      usage: { inputTokens: 100, outputTokens: 200, totalTokens: 300 },
      model: 'mock',
      success: true,
      telemetry: {
        provider: RTCMModelProvider.MOCK,
        model: 'mock',
        rawLength: 0,
        sanitizedLength: 0,
        extractionStrategy: 'json_block',
        jsonExtractionSuccess: true,
        parseSuccess: true,
        regenerationCount: 0,
        finalFallback: false,
        timestamp: new Date().toISOString(),
      },
    };
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const rtcmModelAdapter = new RTCMModelAdapter();
