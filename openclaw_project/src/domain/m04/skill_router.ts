/**
 * GStack 技能路由器
 * ================================================
 * 将自然语言意图路由到对应 GStack Skill
 * 支持: /review, /qa, /ship, /office-hours, /investigate 等
 * ================================================
 */

import * as path from 'path';
import * as fs from 'fs';

export interface SkillRoute {
  patterns: RegExp[];
  skill: string;
  instruction: string;
  description: string;
  category: 'development' | 'product' | 'review' | 'release' | 'debug' | 'safety';
}

const SKILL_ROUTES: SkillRoute[] = [
  // 代码审查
  {
    patterns: [
      /code.*review/i,
      /审查.*代码/i,
      /review.*code/i,
      /检查.*代码/i,
      /代码.*审查/i,
      /安全.*审查/i,
      /性能.*审查/i,
    ],
    skill: '/review',
    instruction: '执行高级代码审查，检查安全性、性能、最佳实践',
    description: '代码审查专家',
    category: 'review',
  },

  // QA 测试
  {
    patterns: [
      /test.*case/i,
      /测试.*用例/i,
      /qa/i,
      /run.*test/i,
      /单元.*测试/i,
      /集成.*测试/i,
      /e2e.*test/i,
      /端到端.*测试/i,
      /功能.*测试/i,
      /regression.*test/i,
    ],
    skill: '/qa',
    instruction: '执行全面 QA 测试，发现并修复 bug',
    description: 'QA 测试专家',
    category: 'development',
  },

  // 发布部署
  {
    patterns: [
      /deploy/i,
      /ship/i,
      /发布/i,
      /部署/i,
      /release/i,
      /发布.*代码/i,
      /上线/i,
    ],
    skill: '/ship',
    instruction: '执行自动化发布流程，合并分支、运行测试、创建 PR',
    description: '发布工程师',
    category: 'release',
  },

  // YC 办公时间 - 产品构思
  {
    patterns: [
      /product.*idea/i,
      /产品.*构思/i,
      /office.*hour/i,
      /创意.*验证/i,
      /产品.*创意/i,
      /startup.*idea/i,
      /商业.*创意/i,
      /商业模式.*验证/i,
    ],
    skill: '/office-hours',
    instruction: '使用 YC 方法论验证产品想法',
    description: 'YC 办公时间',
    category: 'product',
  },

  // 调试调查
  {
    patterns: [
      /investigate/i,
      /调试/i,
      /debug/i,
      /调查/i,
      /排查/i,
      /定位.*问题/i,
      /查找.*bug/i,
      /修复.*错误/i,
      /troubleshoot/i,
      /root.*cause/i,
    ],
    skill: '/investigate',
    instruction: '系统化根因分析，定位问题源头',
    description: '调试调查专家',
    category: 'debug',
  },

  // 架构评审
  {
    patterns: [
      /architect/i,
      /架构.*评审/i,
      /plan.*eng/i,
      /技术.*评审/i,
      /架构.*审查/i,
      /技术.*方案/i,
      /system.*design/i,
      /api.*design/i,
    ],
    skill: '/plan-eng-review',
    instruction: '从工程架构角度评审技术方案',
    description: '架构评审专家',
    category: 'review',
  },

  // CEO 视角评审
  {
    patterns: [
      /ceo.*review/i,
      /ceo.*视角/i,
      /产品.*评审/i,
      /商业.*视角/i,
      /market.*fit/i,
      /产品.*方向/i,
    ],
    skill: '/plan-ceo-review',
    instruction: '从 CEO 视角评审产品计划',
    description: 'CEO 视角评审',
    category: 'product',
  },

  // 设计评审
  {
    patterns: [
      /design.*review/i,
      /设计.*评审/i,
      /ui.*design/i,
      /ux.*review/i,
      /界面.*设计/i,
      /交互.*设计/i,
      /plan.*design/i,
    ],
    skill: '/plan-design-review',
    instruction: '从设计师视角评审设计方案',
    description: '设计评审专家',
    category: 'review',
  },

  // 安全警告
  {
    patterns: [
      /careful/i,
      /danger/i,
      /危险/i,
      /安全.*警告/i,
      /warning/i,
      /风险.*评估/i,
      /security.*check/i,
    ],
    skill: '/careful',
    instruction: '显示危险操作的安全警告',
    description: '安全警告专家',
    category: 'safety',
  },

  // 冻结编辑
  {
    patterns: [
      /freeze/i,
      /锁定.*文件/i,
      /保护.*文件/i,
      /prevent.*edit/i,
      /lock.*file/i,
    ],
    skill: '/freeze',
    instruction: '锁定文件防止意外编辑',
    description: '文件冻结工具',
    category: 'safety',
  },

  // 完整安全模式
  {
    patterns: [
      /guard/i,
      /安全.*模式/i,
      /safe.*mode/i,
      /安全.*保护/i,
    ],
    skill: '/guard',
    instruction: '激活完全安全模式',
    description: '安全守卫模式',
    category: 'safety',
  },

  // 设计咨询
  {
    patterns: [
      /design.*consult/i,
      /设计.*咨询/i,
      /consultation/i,
      /设计.*建议/i,
    ],
    skill: '/design-consultation',
    instruction: '提供设计咨询建议',
    description: '设计咨询专家',
    category: 'review',
  },

  // Codex 审查
  {
    patterns: [
      /codex/i,
      /openai.*codex/i,
      /codex.*review/i,
    ],
    skill: '/codex',
    instruction: '使用 OpenAI Codex 进行代码审查',
    description: 'Codex 代码审查',
    category: 'review',
  },

  // 文档发布
  {
    patterns: [
      /document.*release/i,
      /文档.*发布/i,
      /update.*docs/i,
      /更新.*文档/i,
      /技术.*文档/i,
    ],
    skill: '/document-release',
    instruction: '更新项目技术文档',
    description: '技术文档发布',
    category: 'release',
  },

  // 回顾
  {
    patterns: [
      /retro/i,
      /回顾/i,
      /复盘/i,
      /postmortem/i,
      /sprint.*retro/i,
      /团队.*回顾/i,
    ],
    skill: '/retro',
    instruction: '执行团队回顾会议',
    description: '团队回顾专家',
    category: 'product',
  },
];

/**
 * GStack 技能路由器
 *
 * 核心职责：
 * - 解析用户意图，匹配到对应 GStack Skill
 * - 构建包含 Skill 调用的指令
 * - 提供 Skill 元信息查询
 */
export class SkillRouter {
  private routes: SkillRoute[];
  private skillPath: string;

  constructor() {
    this.routes = SKILL_ROUTES;
    this.skillPath = this.resolveGStackSkillsPath();
  }

  /**
   * 解析 GStack Skills 路径
   */
  private resolveGStackSkillsPath(): string {
    const home = process.env.HOME || process.env.USERPROFILE || '';
    return path.join(home, '.claude', 'skills', 'gstack-openclaw-skills');
  }

  /**
   * 路由意图到 GStack Skill
   * @param intent 用户意图描述
   * @returns 匹配的 SkillRoute 或 null
   */
  route(intent: string): SkillRoute | null {
    for (const route of this.routes) {
      for (const pattern of route.patterns) {
        if (pattern.test(intent)) {
          return route;
        }
      }
    }
    return null;
  }

  /**
   * 检查意图是否匹配任何 Skill
   */
  matchesAnySkill(intent: string): boolean {
    return this.route(intent) !== null;
  }

  /**
   * 获取所有可用 Skill 列表
   */
  getAllSkills(): { skill: string; description: string; category: string }[] {
    return this.routes.map((r) => ({
      skill: r.skill,
      description: r.description,
      category: r.category,
    }));
  }

  /**
   * 按类别获取 Skills
   */
  getSkillsByCategory(category: SkillRoute['category']): SkillRoute[] {
    return this.routes.filter((r) => r.category === category);
  }

  /**
   * 构建 Skill 执行指令
   * @param skill GStack Skill 名称 (如 /review)
   * @param context 用户任务上下文
   * @returns 完整的执行指令
   */
  buildInstruction(skill: string, context: string): string {
    return `使用 ${skill} 技能完成以下任务: ${context}`;
  }

  /**
   * 路由并构建指令 (一次性完成)
   * @param intent 用户意图
   * @param context 任务上下文
   * @returns { matched: true, skill, instruction } | { matched: false }
   */
  routeAndBuild(intent: string, context: string): {
    matched: boolean;
    skill?: string;
    instruction?: string;
    description?: string;
  } {
    const route = this.route(intent);
    if (!route) {
      return { matched: false };
    }
    return {
      matched: true,
      skill: route.skill,
      instruction: this.buildInstruction(route.skill, context),
      description: route.description,
    };
  }

  /**
   * 获取 Skill 的详细描述
   */
  getSkillDescription(skill: string): string | null {
    const route = this.routes.find((r) => r.skill === skill);
    return route ? route.description : null;
  }

  /**
   * 检查 Skill 是否存在
   */
  hasSkill(skill: string): boolean {
    return this.routes.some((r) => r.skill === skill);
  }

  /**
   * 获取 GStack Skills 目录路径
   */
  getSkillsPath(): string {
    return this.skillPath;
  }

  /**
   * 检查 Skills 目录是否存在
   */
  hasSkillsDirectory(): boolean {
    return fs.existsSync(this.skillPath);
  }

  /**
   * 列出已安装的 Skills
   */
  listInstalledSkills(): string[] {
    if (!this.hasSkillsDirectory()) {
      return [];
    }

    try {
      const entries = fs.readdirSync(this.skillPath, { withFileTypes: true });
      return entries
        .filter((e) => e.isDirectory())
        .map((e) => e.name);
    } catch {
      return [];
    }
  }
}

// ============================================
// 单例导出
// ============================================

export const skillRouter = new SkillRouter();
