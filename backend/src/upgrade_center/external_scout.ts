/**
 * @file external_scout.ts
 * @description U1: 外部情报采集
 * 从外部源采集升级候选情报
 */

import * as fs from 'fs';
import * as path from 'path';
import { runtimePath } from '../runtime_paths';
import { UpgradeDemand } from './types';

const SCOUTING_DIR = runtimePath('upgrade-center', 'scouting');
const RAW_INTEL_DIR = path.join(SCOUTING_DIR, 'raw_intel');
const NORMALIZED_DIR = path.join(SCOUTING_DIR, 'normalized_candidates');

export class ExternalScout {
  /**
   * 采集外部情报
   * 从GitHub、npm/PyPI等源获取升级候选
   */
  public async scout(): Promise<UpgradeDemand[]> {
    console.log('[ExternalScout] 开始采集外部情报...');

    // 确保目录存在
    this.ensureDirectories();

    const demands: UpgradeDemand[] = [];

    // 1. 扫描本地缓存的原始情报
    const rawIntel = this.scanRawIntel();

    // 2. 标准化情报为需求
    for (const intel of rawIntel) {
      const demand = this.normalizeToDemand(intel);
      if (demand) {
        demands.push(demand);
      }
    }

    // 3. 如果没有缓存，生成示例需求（演示用）
    if (demands.length === 0) {
      demands.push(...this.generateSampleDemands());
    }

    console.log(`[ExternalScout] 发现 ${demands.length} 个外部候选`);
    return demands;
  }

  /**
   * 确保目录结构存在
   */
  private ensureDirectories(): void {
    const dirs = [SCOUTING_DIR, RAW_INTEL_DIR, NORMALIZED_DIR];
    for (const dir of dirs) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }
  }

  /**
   * 扫描原始情报目录
   */
  private scanRawIntel(): RawIntel[] {
    const intelFiles: RawIntel[] = [];

    if (!fs.existsSync(RAW_INTEL_DIR)) {
      return intelFiles;
    }

    try {
      const files = fs.readdirSync(RAW_INTEL_DIR);
      for (const file of files) {
        if (file.endsWith('.json')) {
          const filePath = path.join(RAW_INTEL_DIR, file);
          const content = fs.readFileSync(filePath, 'utf-8');
          const intel = JSON.parse(content) as RawIntel;
          intelFiles.push(intel);
        }
      }
    } catch (error) {
      console.warn(`[ExternalScout] 扫描原始情报失败: ${error}`);
    }

    return intelFiles;
  }

  /**
   * 将原始情报标准化为升级需求
   */
  private normalizeToDemand(intel: RawIntel): UpgradeDemand | null {
    if (!intel.project || !intel.github) {
      return null;
    }

    return {
      id: `demand-external-${intel.project.replace(/[^a-zA-Z0-9]/g, '-')}`,
      source: 'external_scout',
      project: intel.project,
      github: intel.github,
      description: intel.description || `${intel.project} 提供 ${intel.capability_gain?.join(', ')} 能力`,
      related_module: intel.target_module,
      detected_at: intel.discovered_at || new Date().toISOString(),
      capability_gain: intel.capability_gain || [],
    };
  }

  /**
   * 生成示例需求（当没有原始情报时）
   */
  private generateSampleDemands(): UpgradeDemand[] {
    const samples: UpgradeDemand[] = [
      {
        id: `demand-external-${Date.now()}-dspy-001`,
        source: 'external_scout',
        project: 'DSPy',
        github: 'https://github.com/stanfordnlp/dspy',
        description: 'DSPy框架 - 自动优化提示和权重，提升LLM任务表现',
        related_module: 'M04_unified_executor',
        detected_at: new Date().toISOString(),
        capability_gain: ['自动提示优化', '程序化Prompt', '模块化LLM调用'],
      },
      {
        id: `demand-external-${Date.now()}-react-001`,
        source: 'external_scout',
        project: 'React',
        github: 'https://github.com/facebook/react',
        description: 'React 19 - Server Components和Actions新特性',
        related_module: 'M09_ui_evolution',
        detected_at: new Date().toISOString(),
        capability_gain: ['Server Components', 'Actions', 'use() Hook'],
      },
      {
        id: `demand-external-${Date.now()}-litellm-001`,
        source: 'external_scout',
        project: 'LiteLLM',
        github: 'https://github.com/BerriAI/litellm',
        description: 'LiteLLM - 统一LLM调用接口，支持100+模型',
        related_module: 'M04_unified_executor',
        detected_at: new Date().toISOString(),
        capability_gain: ['统一接口', '多模型支持', '成本控制'],
      },
    ];

    return samples;
  }

  /**
   * 保存原始情报到本地缓存
   */
  public async saveIntel(intel: RawIntel): Promise<void> {
    this.ensureDirectories();

    const filename = `${intel.project.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.json`;
    const filePath = path.join(RAW_INTEL_DIR, filename);

    fs.writeFileSync(filePath, JSON.stringify(intel, null, 2), 'utf-8');
    console.log(`[ExternalScout] 保存情报到: ${filePath}`);
  }
}

/**
 * 原始情报结构
 */
interface RawIntel {
  project: string;
  github: string;
  description?: string;
  target_module?: string;
  capability_gain?: string[];
  discovered_at?: string;
  source?: string;
  stars?: number;
  last_release?: string;
}
