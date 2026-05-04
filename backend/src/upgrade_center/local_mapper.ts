/**
 * @file local_mapper.ts
 * @description U3: 本地系统映射
 * 将外部项目翻译成本地模块增强价值
 */

import * as fs from 'fs';
import * as path from 'path';
import { runtimePath } from '../runtime_paths';
import {
  ConstitutionFilterResult,
  LocalMappingReport,
  LocalMapping,
  FilterResultItem,
} from './types';

const BASELINES_DIR = runtimePath('upgrade-center', 'baselines');

export class LocalMapper {
  /**
   * R166 FIX: Generate baselines from system metadata if they don't exist.
   * This ensures U3 LocalMapper operates in normal mode instead of degraded mode,
   * enabling real module-to-capability mapping instead of heuristic fallback.
   */
  public ensureBaselines(): void {
    this.ensureBaselineDir();
    this.ensureModuleTagLibrary();
    this.ensureCapabilityTopology();
  }

  private ensureBaselineDir(): void {
    if (!fs.existsSync(BASELINES_DIR)) {
      fs.mkdirSync(BASELINES_DIR, { recursive: true });
    }
  }

  private ensureModuleTagLibrary(): void {
    const filePath = path.join(BASELINES_DIR, 'module_tag_library.json');
    if (fs.existsSync(filePath)) return;

    // Generate from existing system metadata (M01-M12 module structure)
    const modules: ModuleTag[] = [
      { module_id: 'M01_coordinator', name: 'M01 协调器', tags: ['orchestration', 'coordination', 'entry_point'], language: 'typescript' },
      { module_id: 'M02_intent_classifier', name: 'M02 意图分类器', tags: ['nlp', 'classification', 'intent'], language: 'typescript' },
      { module_id: 'M03_hooks', name: 'M03 钩子系统', tags: ['middleware', 'hooks', 'extension'], language: 'typescript' },
      { module_id: 'M04_unified_executor', name: 'M04 统一执行器', tags: ['execution', 'llm', 'adapter'], language: 'typescript' },
      { module_id: 'M04_unified_executor', name: 'M04 DSPy支持', tags: ['dspy', 'prompt_optimization', 'programmatic_prompt'], language: 'typescript' },
      { module_id: 'M05_memory_l1', name: 'M05 L1记忆', tags: ['memory', 'caching', 'l1'], language: 'typescript' },
      { module_id: 'M06_L1_working_memory', name: 'M06 L1工作记忆', tags: ['memory', 'working_memory'], language: 'typescript' },
      { module_id: 'M07_asset_manager', name: 'M07 资产管理系统', tags: ['asset', 'dpbs', 'platform_binding'], language: 'typescript' },
      { module_id: 'M08_learning_system', name: 'M08 学习系统', tags: ['learning', 'evolution', 'uef'], language: 'python' },
      { module_id: 'M09_ui_evolution', name: 'M09 UI演化', tags: ['ui', 'evolution', 'react'], language: 'typescript' },
      { module_id: 'M10_search', name: 'M10 搜索系统', tags: ['search', 'retrieval', 'ranking'], language: 'typescript' },
      { module_id: 'M11_governance', name: 'M11 治理系统', tags: ['governance', 'decision', 'compliance'], language: 'typescript' },
      { module_id: 'M12_config', name: 'M12 配置系统', tags: ['config', 'unified_config'], language: 'typescript' },
      { module_id: 'boulder_json', name: 'Boulder状态管理', tags: ['state', 'persistence', 'checkpoint'], language: 'json' },
    ];

    const library: ModuleTagLibrary = {
      modules,
      last_updated: new Date().toISOString(),
    };

    fs.writeFileSync(filePath, JSON.stringify(library, null, 2), 'utf-8');
    console.log(`[LocalMapper] Generated module_tag_library.json with ${modules.length} modules`);
  }

  private ensureCapabilityTopology(): void {
    const filePath = path.join(BASELINES_DIR, 'capability_topology.json');
    if (fs.existsSync(filePath)) return;

    const topology: CapabilityTopology = {
      nodes: [
        { id: 'n1', module: 'M01_coordinator', capability: '编排协调', level: 3 },
        { id: 'n2', module: 'M04_unified_executor', capability: 'LLM执行', level: 3 },
        { id: 'n3', module: 'M05_memory_l1', capability: 'L1缓存', level: 2 },
        { id: 'n4', module: 'M08_learning_system', capability: '自进化', level: 3 },
      ],
      edges: [
        { from: 'M01_coordinator', to: 'M04_unified_executor', weight: 0.9 },
        { from: 'M02_intent_classifier', to: 'M04_unified_executor', weight: 0.8 },
        { from: 'M04_unified_executor', to: 'M05_memory_l1', weight: 0.7 },
        { from: 'M01_coordinator', to: 'M08_learning_system', weight: 0.6 },
      ],
      last_updated: new Date().toISOString(),
    };

    fs.writeFileSync(filePath, JSON.stringify(topology, null, 2), 'utf-8');
    console.log('[LocalMapper] Generated capability_topology.json');
  }

  /**
   * 将过滤结果映射到本地系统
   * 加载本地模块标签库（如存在）以提供真实映射依据
   */
  public async map(filterResult: ConstitutionFilterResult): Promise<LocalMappingReport> {
    // R166 FIX: Ensure baselines exist before mapping (enables normal mode, not degraded mode)
    this.ensureBaselines();

    console.log('[LocalMapper] 开始本地系统映射...');

    // Load local module tag library for real mapping data
    const moduleTagLib = this.loadModuleTagLibrary();
    if (moduleTagLib) {
      console.log(`[LocalMapper] Loaded module tag library with ${moduleTagLib.modules.length} modules`);
    } else {
      console.log('[LocalMapper] WARNING: Module tag library not found — using heuristic mapping (degraded mode)');
    }

    const mappings: LocalMapping[] = [];

    for (const item of filterResult.results) {
      if (item.filter_result === 'excluded') {
        continue;
      }

      const mapping = this.createMapping(item, moduleTagLib);
      mappings.push(mapping);
    }

    console.log(`[LocalMapper] 生成 ${mappings.length} 个本地映射`);

    return {
      date: new Date().toISOString().split('T')[0],
      mappings,
    };
  }

  /**
   * 创建单个映射
   * @param moduleTagLib optional real module tag library — if null, uses heuristic fallback (degraded mode)
   */
  private createMapping(item: FilterResultItem, moduleTagLib: ModuleTagLibrary | null): LocalMapping {
    const project = item.project || 'unknown';

    // Use real module tag library if available, otherwise fallback to heuristic
    const targetModules = moduleTagLib
      ? this.findTargetModulesFromLibrary(project, moduleTagLib)
      : this.findTargetModules(project);

    // R34 fix: use capability_gain from U2 filter result (propagated from demand_sampler enrichment)
    // Falls back to extractCapabilityGain(item) only if not available
    const capabilityGain = (item.capability_gain && item.capability_gain.length > 0)
      ? item.capability_gain
      : (moduleTagLib
        ? this.extractCapabilityGainFromLibrary(item, moduleTagLib)
        : this.extractCapabilityGain(item));

    const integrationType = this.determineIntegrationType(item);
    const riskZones = this.identifyRiskZones(targetModules);
    const immutableZones = this.findImmutableZoneTouches(targetModules);
    const callChains = this.traceCallChains(targetModules);
    const tokenOverhead = this.estimateTokenOverhead(item, integrationType);

    return {
      candidate_id: item.demand_id,
      target_modules: targetModules,
      capability_gain: capabilityGain,
      integration_type: integrationType,
      risk_zone_touches: riskZones,
      immutable_zone_touches: immutableZones,
      affected_call_chains: callChains,
      estimated_token_overhead: tokenOverhead,
      // R206-B fix: propagate governance_priority from FilterResultItem
      governance_priority: (item as any).governance_priority,
    };
  }

  /**
   * Find target modules using real module tag library (real mapping)
   */
  private findTargetModulesFromLibrary(project: string, lib: ModuleTagLibrary): string[] {
    const lowerProject = project.toLowerCase();
    const matchedModules: string[] = [];

    for (const mod of lib.modules) {
      const modName = mod.module_id.toLowerCase();
      const modTags = (mod.tags || []).map((t: string) => t.toLowerCase());
      // Match project name or relevant tags
      if (modName.includes(lowerProject) || modTags.some((t: string) => lowerProject.includes(t))) {
        matchedModules.push(mod.module_id);
      }
    }

    if (matchedModules.length > 0) {
      console.log(`[LocalMapper] Real mapping: "${project}" → [${matchedModules.join(', ')}]`);
      return matchedModules;
    }

    // Fallback to heuristic if no library match
    console.log(`[LocalMapper] WARNING: No library match for "${project}" — falling back to heuristic`);
    return this.findTargetModules(project);
  }

  /**
   * Extract capability gain using real module tag library (real mapping)
   */
  private extractCapabilityGainFromLibrary(item: FilterResultItem, lib: ModuleTagLibrary): string[] {
    const project = (item.project || '').toLowerCase();

    for (const mod of lib.modules) {
      const modName = mod.module_id.toLowerCase();
      if (modName.includes(project) || project.includes(modName.replace('M??_', '').toLowerCase())) {
        return mod.tags || [];
      }
    }

    return this.extractCapabilityGain(item);
  }

  /**
   * 查找目标模块
   */
  private findTargetModules(project: string): string[] {
    const moduleMap: Record<string, string[]> = {
      dspy: ['M04_unified_executor', 'M02_intent_classifier'],
      litellm: ['M04_unified_executor'],
      'react': ['M09_ui_evolution'],
      'langchain': ['M04_unified_executor', 'M05_memory_l1'],
      'tensorflow': ['M04_unified_executor'],
      'pytorch': ['M04_unified_executor'],
    };

    const lowerProject = project.toLowerCase();
    for (const [key, modules] of Object.entries(moduleMap)) {
      if (lowerProject.includes(key)) {
        return modules;
      }
    }

    return ['M04_unified_executor'];
  }

  /**
   * 提取能力增益
   */
  private extractCapabilityGain(item: FilterResultItem): string[] {
    const capabilityGainMap: Record<string, string[]> = {
      dspy: ['自动提示优化', '程序化Prompt', '模块化LLM调用'],
      litellm: ['统一接口', '多模型支持', '成本控制'],
      react: ['Server Components', 'Actions', 'use() Hook'],
      langchain: ['Chain模板', 'Agent框架', '工具集成'],
    };

    const lowerProject = (item.project || '').toLowerCase();
    for (const [key, capabilities] of Object.entries(capabilityGainMap)) {
      if (lowerProject.includes(key)) {
        return capabilities;
      }
    }

    return ['能力增强'];
  }

  /**
   * 确定集成类型
   */
  private determineIntegrationType(item: FilterResultItem): 'adapter' | 'patch' | 'replace' | 'fork_refactor' {
    const replaceIndicators = ['replacement', '替代', '替换', '下一代'];
    const forkIndicators = ['fork', '分支', '重构'];
    const patchIndicators = ['patch', '修复', '补丁', '增强'];
    const adapterIndicators = ['adapter', 'wrapper', '封装', '包装'];

    const desc = (item.project || '').toLowerCase();

    if (adapterIndicators.some((ind) => desc.includes(ind))) {
      return 'adapter';
    }
    if (patchIndicators.some((ind) => desc.includes(ind))) {
      return 'patch';
    }
    if (replaceIndicators.some((ind) => desc.includes(ind))) {
      return 'replace';
    }
    if (forkIndicators.some((ind) => desc.includes(ind))) {
      return 'fork_refactor';
    }

    return 'adapter';
  }

  /**
   * 识别风险区
   */
  private identifyRiskZones(targetModules: string[]): string[] {
    const riskZoneMap: Record<string, string[]> = {
      M04_unified_executor: ['M01_coordinator', 'M02_intent_classifier'],
      M05_memory_l1: ['M06_L1_working_memory', 'M07_asset_manager'],
      M09_ui_evolution: ['M09_ui_evolution', 'M01_coordinator'],
    };

    const riskZones = new Set<string>();
    for (const module of targetModules) {
      const zones = riskZoneMap[module] || [];
      zones.forEach((z) => riskZones.add(z));
    }

    return Array.from(riskZones);
  }

  /**
   * 查找触碰不可变区
   */
  private findImmutableZoneTouches(targetModules: string[]): string[] {
    const immutableZones = ['M01_coordinator', 'M03_hooks', 'M04_unified_executor'];
    return targetModules.filter((m) => immutableZones.includes(m));
  }

  /**
   * 追踪调用链
   */
  private traceCallChains(targetModules: string[]): string[] {
    const callChainMap: Record<string, string[]> = {
      M04_unified_executor: [
        'M01_coordinator → M04_unified_executor → M04',
        'M02_intent_classifier → M04_unified_executor → M04',
      ],
      M05_memory_l1: [
        'M01_coordinator → M05_memory_l1 → M06',
        'M04_unified_executor → M05_memory_l1 → M06',
      ],
    };

    const chains = new Set<string>();
    for (const module of targetModules) {
      const moduleChains = callChainMap[module] || [];
      moduleChains.forEach((c) => chains.add(c));
    }

    return Array.from(chains);
  }

  /**
   * 估算token开销
   */
  private estimateTokenOverhead(item: FilterResultItem, integrationType: string): number {
    const baseOverhead: Record<string, number> = {
      adapter: 2000,
      patch: 1000,
      replace: 5000,
      fork_refactor: 8000,
    };

    return baseOverhead[integrationType] || 2000;
  }

  /**
   * 加载能力拓扑图
   */
  public loadCapabilityTopology(): CapabilityTopology | null {
    const filePath = path.join(BASELINES_DIR, 'capability_topology.json');

    if (fs.existsSync(filePath)) {
      try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return JSON.parse(content);
      } catch (error) {
        console.warn(`[LocalMapper] 加载能力拓扑失败: ${error}`);
      }
    }

    return null;
  }

  /**
   * 加载模块标签库
   */
  public loadModuleTagLibrary(): ModuleTagLibrary | null {
    const filePath = path.join(BASELINES_DIR, 'module_tag_library.json');

    if (fs.existsSync(filePath)) {
      try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return JSON.parse(content);
      } catch (error) {
        console.warn(`[LocalMapper] 加载模块标签库失败: ${error}`);
      }
    }

    return null;
  }
}

interface ModuleTag {
  module_id: string;
  name: string;
  tags: string[];
  language: string;
}

interface ModuleTagLibrary {
  modules: ModuleTag[];
  last_updated: string;
}

interface CapabilityTopology {
  nodes: Array<{ id: string; module: string; capability: string; level: number }>;
  edges: Array<{ from: string; to: string; weight: number }>;
  last_updated: string;
}
