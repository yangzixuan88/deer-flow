/**
 * @file config_loader.ts
 * @description U0: RTCM Config Loader
 * 使用 js-yaml 加载YAML配置文件
 */

import * as fs from 'fs';
import * as path from 'path';
// @ts-ignore - js-yaml 自带类型定义但 tsconfig 扫描不到
import * as yaml from 'js-yaml';
import {
  Role,
  Agent,
  CONFIG_FILES,
  RTCM_CONFIG_ROOT,
} from './types';

export interface RTCMConfigs {
  roles: Role[];
  agents: Agent[];
  roleRegistry: Record<string, unknown>;
  agentRegistry: Record<string, unknown>;
  issueDebateProtocol: Record<string, unknown>;
  projectDossierSchema: Record<string, unknown>;
  promptLoaderSpec: Record<string, unknown>;
  runtimeOrchestratorSpec: Record<string, unknown>;
  feishuRenderingSpec: Record<string, unknown>;
}

export class ConfigLoader {
  private configRoot: string;
  private configs: RTCMConfigs | null = null;

  constructor(configRoot: string = RTCM_CONFIG_ROOT) {
    this.configRoot = configRoot;
  }

  /**
   * 加载所有RTCM配置
   */
  public async loadAll(): Promise<RTCMConfigs> {
    console.log('[ConfigLoader] 加载RTCM配置...');

    const [
      roleRegistry,
      agentRegistry,
      issueDebateProtocol,
      projectDossierSchema,
      promptLoaderSpec,
      runtimeOrchestratorSpec,
      feishuRenderingSpec,
    ] = await Promise.all([
      this.loadYaml<Record<string, unknown>>(CONFIG_FILES.roleRegistry),
      this.loadYaml<Record<string, unknown>>(CONFIG_FILES.agentRegistry),
      this.loadYaml<Record<string, unknown>>(CONFIG_FILES.issueDebateProtocol),
      this.loadYaml<Record<string, unknown>>(CONFIG_FILES.projectDossierSchema),
      this.loadYaml<Record<string, unknown>>(CONFIG_FILES.promptLoaderSpec),
      this.loadYaml<Record<string, unknown>>(CONFIG_FILES.runtimeOrchestratorSpec),
      this.loadYaml<Record<string, unknown>>(CONFIG_FILES.feishuRenderingSpec),
    ]);

    // 提取角色数组
    const roles = this.extractRoles(roleRegistry);
    const agents = this.extractAgents(agentRegistry);

    this.configs = {
      roles,
      agents,
      roleRegistry,
      agentRegistry,
      issueDebateProtocol,
      projectDossierSchema,
      promptLoaderSpec,
      runtimeOrchestratorSpec,
      feishuRenderingSpec,
    };

    console.log(`[ConfigLoader] 加载完成: ${roles.length} 个角色, ${agents.length} 个Agent`);
    return this.configs;
  }

  /**
   * 获取已加载的配置
   */
  public getConfigs(): RTCMConfigs {
    if (!this.configs) {
      throw new Error('[ConfigLoader] 配置尚未加载，请先调用 loadAll()');
    }
    return this.configs;
  }

  /**
   * 加载单个YAML文件并解析
   */
  private async loadYaml<T>(filename: string): Promise<T> {
    const filePath = path.join(this.configRoot, filename);

    if (!fs.existsSync(filePath)) {
      console.warn(`[ConfigLoader] 配置文件不存在: ${filePath}`);
      return {} as T;
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      // 使用 js-yaml 安全加载，支持复杂嵌套结构
      const parsed = yaml.load(content, {
        filename: filePath,
        json: true,  // 允许 JSON 语法
      }) as T;
      return parsed;
    } catch (error) {
      console.error(`[ConfigLoader] 加载配置文件失败 ${filename}:`, error);
      return {} as T;
    }
  }

  /**
   * 从roleRegistry中提取角色数组
   */
  private extractRoles(roleRegistry: Record<string, unknown>): Role[] {
    const rolesData = roleRegistry['roles'];
    if (!Array.isArray(rolesData)) {
      console.warn('[ConfigLoader] roles字段不是数组');
      return [];
    }

    return rolesData.map((r: Record<string, unknown>) => {
      const personality = r['personality'] as Record<string, unknown> || {};
      const permissions = r['permissions'] as Record<string, unknown> || {};

      return {
        id: (r['id'] as string) || '',
        name: (r['name'] as string) || '',
        title: (r['title'] as string) || '',
        role_type: (r['role_type'] as 'chair' | 'supervisor' | 'member') || 'member',
        identity: (r['identity'] as string) || '',
        mission: (r['mission'] as string) || '',
        core_responsibilities: (r['core_responsibilities'] as string[]) || [],
        non_responsibilities: (r['non_responsibilities'] as string[]) || [],
        personality: {
          temperament: (personality['temperament'] as string) || '',
          tone: (personality['tone'] as string) || '',
          decision_style: (personality['decision_style'] as string) || '',
          conflict_style: (personality['conflict_style'] as string) || '',
        },
        default_bias: (r['default_bias'] as string) || '',
        debate_functions: (r['debate_functions'] as string[]) || [],
        evidence_preferences: (r['evidence_preferences'] as string[]) || [],
        permissions: {
          speak: (permissions['speak'] as boolean) ?? false,
          propose: (permissions['propose'] as boolean) ?? false,
          challenge: (permissions['challenge'] as boolean) ?? false,
          execute: (permissions['execute'] as boolean) ?? false,
          validate: (permissions['validate'] as boolean) ?? false,
          pause: permissions['pause'] as boolean,
          abort: permissions['abort'] as boolean,
          rollback: permissions['rollback'] as boolean,
          escalate: permissions['escalate'] as boolean,
          assign_execution_lease: permissions['assign_execution_lease'] as boolean,
          close_issue: permissions['close_issue'] as boolean,
          close_project: permissions['close_project'] as boolean,
        },
      };
    });
  }

  /**
   * 从agentRegistry中提取Agent数组
   */
  private extractAgents(agentRegistry: Record<string, unknown>): Agent[] {
    const agentsData = (agentRegistry as Record<string, unknown>)['agents'];
    if (!Array.isArray(agentsData)) {
      console.warn('[ConfigLoader] agents字段不是数组');
      return [];
    }

    return agentsData.map((a: Record<string, unknown>) => {
      const modelPolicy = a['model_policy'] as Record<string, unknown> || {};
      const toolAccessProfile = (a['tool_access_profile'] as Record<string, string>) || {};

      return {
        id: (a['id'] as string) || '',
        name: (a['name'] as string) || '',
        group: (a['group'] as string) || '',
        category: (a['category'] as string) || '',
        role_ref: (a['role_ref'] as string) || '',
        model_policy: {
          primary: (modelPolicy['primary'] as string) || '',
          fallback: (modelPolicy['fallback'] as string) || '',
        },
        capabilities: (a['capabilities'] as string[]) || [],
        hooks: (a['hooks'] as string[]) || [],
        max_concurrent: (a['max_concurrent'] as number) || 1,
        priority: (a['priority'] as number) || 0,
        tool_access_profile: toolAccessProfile,
        signals: (a['signals'] as string[]) || [],
      };
    });
  }

  /**
   * 根据role_id获取角色定义
   */
  public getRoleById(roleId: string): Role | undefined {
    const configs = this.getConfigs();
    return configs.roles.find((r) => r.id === roleId);
  }

  /**
   * 根据agent_id获取Agent定义
   */
  public getAgentById(agentId: string): Agent | undefined {
    const configs = this.getConfigs();
    return configs.agents.find((a) => a.id === agentId);
  }
}

// 单例导出
export const configLoader = new ConfigLoader();
