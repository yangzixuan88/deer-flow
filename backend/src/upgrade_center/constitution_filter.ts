/**
 * @file constitution_filter.ts
 * @description U2: 宪法初筛
 * 按宪法规则对每个候选进行第一层分流
 */

import {
  UpgradeDemandPool,
  UpgradeDemand,
  ConstitutionFilterResult,
  FilterResult,
  FilterResultItem,
  ConstitutionState,
} from './types';

export class ConstitutionFilter {
  /**
   * 对需求池进行宪法过滤
   */
  public async filter(demandPool: UpgradeDemandPool): Promise<ConstitutionFilterResult> {
    console.log('[ConstitutionFilter] 开始宪法初筛...');

    const results: FilterResultItem[] = [];
    const poolCounts = {
      excluded: 0,
      observation: 0,
      experiment: 0,
      deep_analysis: 0,
    };

    for (const demand of demandPool.demands) {
      const result = this.evaluateDemand(demand);
      results.push(result);

      switch (result.filter_result) {
        case 'excluded':
          poolCounts.excluded++;
          break;
        case 'observation_pool':
          poolCounts.observation++;
          break;
        case 'experiment_pool':
          poolCounts.experiment++;
          break;
        case 'deep_analysis_pool':
          poolCounts.deep_analysis++;
          break;
      }
    }

    console.log(`[ConstitutionFilter] 筛选完成: 排除${poolCounts.excluded}, 观察${poolCounts.observation}, 实验${poolCounts.experiment}, 深度分析${poolCounts.deep_analysis}`);

    return {
      date: new Date().toISOString().split('T')[0],
      results,
      pool_counts: poolCounts,
    };
  }

  /**
   * 评估单个需求
   */
  private evaluateDemand(demand: UpgradeDemand): FilterResultItem {
    const result: FilterResultItem = {
      demand_id: demand.id,
      project: demand.project,
      filter_result: 'excluded',
      reason: '',
      // R34 fix: propagate capability_gain so U3 local_mapper can use it for scoring
      capability_gain: demand.capability_gain || [],
    };

    // R170 FIX: governance_priority field routes governance-origin demands to observation_pool
    // before immutable-zone bypass can redirect them to deep_analysis_pool.
    // asset_promotion signals are observational, not upgrade directives.
    if ((demand as any).governance_priority === 'observation_pool') {
      // R206-B fix: propagate governance_priority through FilterResultItem so U3→U4→U5 can read it
      (result as any).governance_priority = (demand as any).governance_priority;
      result.filter_result = 'observation_pool';
      result.reason = '治理信号（asset_promotion），路由到观察池';
      return result;
    }

    // R168 FIX: Healthy-system demands should be excluded FIRST — before immutable zone check.
    // This prevents a "系统运行平稳" demand from consuming U4-U8 full pipeline resources.
    // R168 check must run BEFORE immutable-zone check because bottleneck_healthy has
    // related_module='M04_unified_executor' which is in immutable zones — immutable-zone
    // check would fire first and route to deep_analysis_pool, bypassing R168 exclusion.
    if (demand.source === 'internal_bottleneck' && demand.description?.includes('无显著瓶颈')) {
      console.log(`[ConstitutionFilter] R168: 排除健康系统demand ${demand.id} — ${demand.description}`);
      result.filter_result = 'excluded';
      result.reason = '系统运行平稳，无升级需求';
      return result;
    }

    // 1. 检查是否触碰不可变区
    if (demand.related_module) {
      const immutableZones = this.getImmutableZones();
      if (immutableZones.includes(demand.related_module)) {
        result.filter_result = 'deep_analysis_pool';
        result.reason = `触及不可变区 ${demand.related_module}，需要深度分析`;
        return result;
      }
    }

    // 2. 检查是否纯包装/无真实增强
    if (this.isPureWrapper(demand)) {
      result.filter_result = 'excluded';
      result.reason = '纯包装项目，无真实能力增强';
      return result;
    }

    // 3. 检查是否与主方向弱相关
    if (!this.isRelevantToDirection(demand)) {
      result.filter_result = 'excluded';
      result.reason = '与OpenClaw主方向弱相关';
      return result;
    }

    // 4. 评估候选潜力
    const potential = this.assessPotential(demand);

    if (potential === 'low') {
      result.filter_result = 'excluded';
      result.reason = '潜力不足';
    } else if (potential === 'high_but_immature') {
      result.filter_result = 'observation_pool';
      result.reason = '高潜力但不成熟，进入观察池';
    } else if (potential === 'advanced_high_risk') {
      result.filter_result = 'experiment_pool';
      result.reason = '先进但工程风险高，进入实验层';
    } else {
      result.filter_result = 'deep_analysis_pool';
      result.reason = '有明确增强潜力/补短板/0→1，进入深度分析池';
    }

    return result;
  }

  /**
   * 获取不可变区列表
   */
  private getImmutableZones(): string[] {
    return [
      'M01_coordinator',
      'M03_hooks',
      'M04_unified_executor',
      'boulder_json',
    ];
  }

  /**
   * 检查是否纯包装项目
   */
  private isPureWrapper(demand: UpgradeDemand): boolean {
    const wrapperIndicators = [
      'wrapper',
      'wrapper',
      'thin wrapper',
      '简单封装',
      '包装器',
    ];

    const desc = demand.description.toLowerCase();
    return wrapperIndicators.some((indicator) => desc.includes(indicator));
  }

  /**
   * 检查是否与主方向相关
   */
  private isRelevantToDirection(demand: UpgradeDemand): boolean {
    const coreDirections = [
      'autonomous',
      'agent',
      'execution',
      'learning',
      'evolution',
      'memory',
      '搜索',
      '执行',
      '学习',
      '进化',
      '记忆',
    ];

    const desc = demand.description.toLowerCase();
    const capabilities = (demand.capability_gain || []).map((c) => c.toLowerCase());

    const allText = [desc, ...capabilities].join(' ');

    return coreDirections.some((dir) => allText.includes(dir));
  }

  /**
   * 评估潜力等级
   */
  private assessPotential(demand: UpgradeDemand): 'low' | 'high_but_immature' | 'advanced_high_risk' | 'high_value' {
    // 检查工程成熟度
    const isExperimental = demand.project && this.isExperimentalProject(demand.project);
    const isIndustryStandard = this.isIndustryStandardProject(demand.project || '');

    // 检查是否0→1或补短板
    const isFoundational = this.isFoundationalCapability(demand);
    const fillsCriticalGap = this.fillsCriticalGap(demand);

    if (isFoundational || fillsCriticalGap) {
      return 'high_value';
    }

    if (isExperimental && !isIndustryStandard) {
      return 'high_but_immature';
    }

    if (isIndustryStandard) {
      return 'advanced_high_risk';
    }

    return 'low';
  }

  /**
   * 检查是否为实验性项目
   */
  private isExperimentalProject(project: string): boolean {
    const experimentalIndicators = ['alpha', 'beta', 'rc', 'experimental', 'proof-of-concept'];
    return experimentalIndicators.some((ind) => project.toLowerCase().includes(ind));
  }

  /**
   * 检查是否为行业标准项目
   */
  private isIndustryStandardProject(project: string): boolean {
    const standardProjects = [
      'react',
      'vue',
      'angular',
      'tensorflow',
      'pytorch',
      'langchain',
      'dspy',
      'litellm',
    ];
    return standardProjects.includes(project.toLowerCase());
  }

  /**
   * 检查是否为基础能力
   */
  private isFoundationalCapability(demand: UpgradeDemand): boolean {
    const foundationalCapabilities = [
      'llm',
      '推理',
      'reasoning',
      'memory',
      '记忆',
      'execution',
      '执行',
      'planning',
      '规划',
    ];

    const text = [
      demand.description,
      ...(demand.capability_gain || []),
    ].join(' ').toLowerCase();

    return foundationalCapabilities.some((cap) => text.includes(cap));
  }

  /**
   * 检查是否填补关键短板
   */
  private fillsCriticalGap(demand: UpgradeDemand): boolean {
    const criticalGaps = [
      'reliability',
      '可靠性',
      'performance',
      '性能',
      'scalability',
      '扩展性',
      'fault tolerance',
      '容错',
    ];

    const text = [
      demand.description,
      ...(demand.capability_gain || []),
    ].join(' ').toLowerCase();

    return criticalGaps.some((gap) => text.includes(gap));
  }
}
