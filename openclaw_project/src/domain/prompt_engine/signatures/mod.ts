/**
 * M09 Signature 注册表
 * ================================================
 * 九大任务类型的 Signature 定义
 * DSPy 风格的提示词签名管理
 * ================================================
 */

import { DspySignature, TaskType } from '../types';

// ============================================
// 九大 Signature 定义
// ============================================

export const SIGNATURES: Record<string, DspySignature> = {
  SearchSynth: {
    name: 'SearchSynth',
    input_fields: ['query', 'context', 'num_sources'],
    output_fields: ['synthesized_answer', 'citations', 'confidence'],
    description: '信息搜索与综合 - 搜索多个来源并综合答案',
    task_types: [TaskType.SEARCH_SYNTH],
    is_compiled: false,
  },

  CodeGen: {
    name: 'CodeGen',
    input_fields: ['task_description', 'language', 'constraints'],
    output_fields: ['code', 'explanation', 'test_cases'],
    description: '代码生成 - 根据需求生成可运行代码',
    task_types: [TaskType.CODE_GEN],
    is_compiled: false,
  },

  DocWrite: {
    name: 'DocWrite',
    input_fields: ['topic', 'audience', 'doc_type', 'style'],
    output_fields: ['document', 'outline', 'key_points'],
    description: '文档写作 - 创建结构化文档',
    task_types: [TaskType.DOC_WRITE],
    is_compiled: false,
  },

  DataAnalysis: {
    name: 'DataAnalysis',
    input_fields: ['data_description', 'analysis_goal', 'available_columns'],
    output_fields: ['insights', 'charts', 'recommendations'],
    description: '数据分析 - 从数据中提取洞察',
    task_types: [TaskType.DATA_ANALYSIS],
    is_compiled: false,
  },

  Diagnosis: {
    name: 'Diagnosis',
    input_fields: ['symptoms', 'error_message', 'environment'],
    output_fields: ['root_cause', 'solution_steps', 'prevention'],
    description: '问题诊断 - 诊断问题并提供解决方案',
    task_types: [TaskType.DIAGNOSIS],
    is_compiled: false,
  },

  Planning: {
    name: 'Planning',
    input_fields: ['goal', 'constraints', 'resources'],
    output_fields: ['plan', 'milestones', 'risks'],
    description: '规划制定 - 创建可执行的计划',
    task_types: [TaskType.PLANNING],
    is_compiled: false,
  },

  Creative: {
    name: 'Creative',
    input_fields: ['brief', 'style', 'constraints'],
    output_fields: ['ideas', 'alternatives', 'recommendations'],
    description: '创意生成 - 产生创意和解决方案',
    task_types: [TaskType.CREATIVE],
    is_compiled: false,
  },

  SysConfig: {
    name: 'SysConfig',
    input_fields: ['system_type', 'current_config', 'target_state'],
    output_fields: ['config_changes', 'rollback_plan', 'verification_steps'],
    description: '系统配置 - 生成配置变更方案',
    task_types: [TaskType.SYS_CONFIG],
    is_compiled: false,
  },

  AALDecision: {
    name: 'AALDecision',
    input_fields: ['mission_context', 'options', 'risk_tolerance'],
    output_fields: ['decision', 'rationale', ' contingencies'],
    description: 'AAL自主决策 - 在使命约束下做出决策',
    task_types: [TaskType.AAL_DECISION],
    is_compiled: false,
  },
};

// ============================================
// Signature 注册表类
// ============================================

export class SignatureRegistry {
  private signatures: Map<string, DspySignature>;

  constructor() {
    this.signatures = new Map(Object.entries(SIGNATURES));
  }

  /**
   * 获取 Signature
   */
  get(name: string): DspySignature | undefined {
    return this.signatures.get(name);
  }

  /**
   * 获取所有 Signatures
   */
  getAll(): DspySignature[] {
    return Array.from(this.signatures.values());
  }

  /**
   * 根据任务类型获取 Signatures
   */
  getByTaskType(taskType: TaskType): DspySignature[] {
    return this.getAll().filter(s => s.task_types.includes(taskType));
  }

  /**
   * 注册或更新 Signature
   */
  register(signature: DspySignature): void {
    this.signatures.set(signature.name, signature);
  }

  /**
   * 标记为已编译
   */
  markCompiled(name: string, model: string): void {
    const sig = this.signatures.get(name);
    if (sig) {
      sig.is_compiled = true;
      sig.compiled_for = model;
      sig.last_compiled = new Date().toISOString();
    }
  }

  /**
   * 检查是否需要编译
   */
  needsCompilation(name: string, currentModel: string): boolean {
    const sig = this.signatures.get(name);
    if (!sig) return false;
    if (!sig.is_compiled) return true;
    return sig.compiled_for !== currentModel;
  }
}

// 导出单例
export const signatureRegistry = new SignatureRegistry();
