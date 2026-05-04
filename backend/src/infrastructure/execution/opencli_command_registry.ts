/**
 * OpenCLI 命令注册器
 * ================================================
 * T4: OpenCLI 命令注册 (557 命令 / 89 平台)
 * 平台映射到现有架构
 * ================================================
 */

import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

export interface OpenCLICmdDefinition {
  site: string;           // 平台名: "bilibili", "xiaohongshu"
  name: string;          // 命令名: "video", "search"
  description: string;   // 命令描述
  domain: string;        // 目标域名
  strategy: string;      // 策略: "cookie", "public", "intercept", "header"
  browser: boolean;      // 是否需要浏览器
  args: OpenCLIArg[];
}

export interface OpenCLIArg {
  name: string;
  type: string;
  required: boolean;
  positional?: boolean;
  default?: string;
  help: string;
}

export interface OpenCLIRegistryEntry {
  site: string;
  commands: OpenCLICmdDefinition[];
  totalCommands: number;
}

/**
 * OpenCLI 命令注册器
 */
export class OpenCLICommandRegistry {
  private commands: Map<string, OpenCLICmdDefinition>;
  private sites: Map<string, OpenCLIRegistryEntry>;
  private manifestPath: string;
  private loaded: boolean = false;

  constructor(manifestPath?: string) {
    // 尝试从 npm 包加载
    this.manifestPath = manifestPath ||
      path.join(process.env.OPENCLI_PATH || path.join(process.cwd(), 'node_modules/@jackwener/opencli'), 'cli-manifest.json');

    this.commands = new Map();
    this.sites = new Map();
  }

  /**
   * 加载 CLI manifest
   */
  async loadManifest(): Promise<void> {
    if (this.loaded) return;

    try {
      // 尝试从文件系统读取
      if (fs.existsSync(this.manifestPath)) {
        const content = fs.readFileSync(this.manifestPath, 'utf8');
        const manifest: OpenCLICmdDefinition[] = JSON.parse(content);

        manifest.forEach(cmd => {
          const key = `${cmd.site}:${cmd.name}`;
          this.commands.set(key, cmd);

          if (!this.sites.has(cmd.site)) {
            this.sites.set(cmd.site, {
              site: cmd.site,
              commands: [],
              totalCommands: 0,
            });
          }
          this.sites.get(cmd.site)!.commands.push(cmd);
        });

        // 更新总数
        this.sites.forEach(entry => {
          entry.totalCommands = entry.commands.length;
        });

        this.loaded = true;
        console.log(`[OpenCLI Registry] Loaded ${this.commands.size} commands from ${this.sites.size} platforms`);
      } else {
        console.warn('[OpenCLI Registry] Manifest not found at:', this.manifestPath);
      }
    } catch (error) {
      console.error('[OpenCLI Registry] Failed to load manifest:', error);
    }
  }

  /**
   * 获取所有命令
   */
  getAllCommands(): OpenCLICmdDefinition[] {
    return Array.from(this.commands.values());
  }

  /**
   * 获取所有平台
   */
  getAllSites(): string[] {
    return Array.from(this.sites.keys());
  }

  /**
   * 获取平台信息
   */
  getSite(site: string): OpenCLIRegistryEntry | undefined {
    return this.sites.get(site);
  }

  /**
   * 获取命令
   */
  getCommand(site: string, name: string): OpenCLICmdDefinition | undefined {
    return this.commands.get(`${site}:${name}`);
  }

  /**
   * 检查命令是否存在
   */
  hasCommand(site: string, name: string): boolean {
    return this.commands.has(`${site}:${name}`);
  }

  /**
   * 按策略筛选命令
   */
  getByStrategy(strategy: string): OpenCLICmdDefinition[] {
    return this.getAllCommands().filter(cmd => cmd.strategy === strategy);
  }

  /**
   * 按平台筛选
   */
  getBySite(site: string): OpenCLICmdDefinition[] {
    const entry = this.sites.get(site);
    return entry ? entry.commands : [];
  }

  /**
   * 获取需要浏览器的命令
   */
  getBrowserCommands(): OpenCLICmdDefinition[] {
    return this.getAllCommands().filter(cmd => cmd.browser);
  }

  /**
   * 获取公开可访问的命令 (不需要登录)
   */
  getPublicCommands(): OpenCLICmdDefinition[] {
    return this.getAllCommands().filter(cmd => cmd.strategy === 'public');
  }

  /**
   * 搜索命令
   */
  search(query: string): OpenCLICmdDefinition[] {
    const lower = query.toLowerCase();
    return this.getAllCommands().filter(cmd =>
      cmd.site.toLowerCase().includes(lower) ||
      cmd.name.toLowerCase().includes(lower) ||
      cmd.description.toLowerCase().includes(lower)
    );
  }

  /**
   * 获取统计信息
   */
  getStats(): {
    totalCommands: number;
    totalSites: number;
    browserCommands: number;
    publicCommands: number;
  } {
    return {
      totalCommands: this.commands.size,
      totalSites: this.sites.size,
      browserCommands: this.getBrowserCommands().length,
      publicCommands: this.getPublicCommands().length,
    };
  }

  /**
   * 执行 OpenCLI 命令
   */
  async execute(
    site: string,
    name: string,
    args: Record<string, string> = {}
  ): Promise<{ success: boolean; stdout: string; stderr: string; exitCode: number }> {
    if (!this.hasCommand(site, name)) {
      return {
        success: false,
        stdout: '',
        stderr: `Command not found: ${site} ${name}`,
        exitCode: 1,
      };
    }

    const cmd = this.getCommand(site, name)!;

    // 构建命令
    const cmdArgs = [site, name];

    // 添加位置参数
    if (args.input) {
      cmdArgs.push(args.input);
    }

    // 添加命名参数
    Object.entries(args).forEach(([key, value]) => {
      if (key !== 'input') {
        cmdArgs.push(`--${key}`, value);
      }
    });

    return new Promise((resolve) => {
      const proc = spawn('opencli', cmdArgs, { timeout: 60000 });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        resolve({
          success: code === 0,
          stdout,
          stderr,
          exitCode: code || 0,
        });
      });

      proc.on('error', (error) => {
        resolve({
          success: false,
          stdout: '',
          stderr: error.message,
          exitCode: 1,
        });
      });
    });
  }
}

// ============================================
// 常用平台快捷映射
// ============================================

/**
 * 常用平台快捷方式
 */
export const POPULAR_PLATFORMS = {
  // 短视频/社交
  bilibili: { name: 'Bilibili', category: 'video', emoji: '📺' },
  xiaohongshu: { name: '小红书', category: 'social', emoji: '📕' },
  douyin: { name: '抖音', category: 'video', emoji: '🎵' },
  tiktok: { name: 'TikTok', category: 'video', emoji: '🎬' },
  weixin: { name: '微信', category: 'social', emoji: '💬' },
  weibo: { name: '微博', category: 'social', emoji: '📝' },
  zhihu: { name: '知乎', category: 'qa', emoji: '💭' },

  // 电商
  taobao: { name: '淘宝', category: 'ecommerce', emoji: '🛒' },
  jd: { name: '京东', category: 'ecommerce', emoji: '📦' },
  '1688': { name: '1688', category: 'ecommerce', emoji: '🏭' },

  // 开发
  github: { name: 'GitHub', category: 'dev', emoji: '💻' },
  npm: { name: 'npm', category: 'dev', emoji: '📦' },

  // 搜索
  google: { name: 'Google', category: 'search', emoji: '🔍' },
  baidu: { name: '百度', category: 'search', emoji: '🔍' },
} as const;

// ============================================
// 单例导出
// ============================================

export const opencliCommandRegistry = new OpenCLICommandRegistry();
