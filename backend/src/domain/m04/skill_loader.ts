/**
 * GStack Skill 加载器
 * ================================================
 * 从磁盘加载 GStack Skills 并解析元信息
 * 支持 SKILL.md frontmatter 格式
 * ================================================
 */

import * as fs from 'fs';
import * as path from 'path';

export interface SkillDefinition {
  name: string;
  description: string;
  version?: string;
  author?: string;
  tags?: string[];
  category?: string;
  filePath: string;
  directory: string;
}

export interface SkillFrontmatter {
  name?: string;
  description?: string;
  version?: string;
  author?: string;
  tags?: string[];
  category?: string;
  [key: string]: string | string[] | undefined;
}

// GStack Skills 搜索路径列表
const SKILL_SEARCH_PATHS = [
  // macOS/Linux
  path.join(process.env.HOME || '', '.claude', 'skills', 'gstack-openclaw-skills'),
  path.join(process.env.HOME || '', '.claude', 'skills', 'gstack'),
  // Windows
  path.join(process.env.USERPROFILE || '', '.claude', 'skills', 'gstack-openclaw-skills'),
  path.join(process.env.USERPROFILE || '', '.claude', 'skills', 'gstack'),
  // 本地项目路径 (开发环境)
  path.join(process.env.HOME || '', '.claude', 'projects', 'gstack-openclaw-skills'),
];

/**
 * GStack Skill 加载器
 *
 * 核心职责：
 * - 扫描 GStack Skills 目录
 * - 解析 SKILL.md frontmatter
 * - 缓存已加载的 Skill 定义
 */
export class SkillLoader {
  private skills: Map<string, SkillDefinition>;
  private searchPaths: string[];
  private loaded: boolean;

  constructor() {
    this.skills = new Map();
    this.searchPaths = SKILL_SEARCH_PATHS;
    this.loaded = false;
  }

  /**
   * 加载所有 GStack Skills
   * @returns Map<skill_name, SkillDefinition>
   */
  loadAllSkills(): Map<string, SkillDefinition> {
    if (this.loaded) {
      return this.skills;
    }

    this.skills.clear();

    for (const searchPath of this.searchPaths) {
      this.loadSkillsFromDirectory(searchPath);
    }

    this.loaded = true;
    console.log(`[SkillLoader] Loaded ${this.skills.size} GStack Skills`);
    return this.skills;
  }

  /**
   * 从指定目录加载 Skills
   */
  private loadSkillsFromDirectory(dirPath: string): void {
    if (!fs.existsSync(dirPath)) {
      return;
    }

    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true });

      for (const entry of entries) {
        if (!entry.isDirectory()) {
          continue;
        }

        const skillDir = path.join(dirPath, entry.name);
        const skillPath = path.join(skillDir, 'SKILL.md');

        if (fs.existsSync(skillPath)) {
          try {
            const skill = this.loadSkill(entry.name, skillPath, skillDir);
            // 避免重复加载
            if (!this.skills.has(skill.name)) {
              this.skills.set(skill.name, skill);
            }
          } catch (err) {
            console.warn(`[SkillLoader] Failed to load skill at ${skillPath}:`, err);
          }
        }
      }
    } catch (err) {
      console.warn(`[SkillLoader] Failed to read directory ${dirPath}:`, err);
    }
  }

  /**
   * 加载单个 Skill
   */
  loadSkill(name: string, skillPath: string, skillDir: string): SkillDefinition {
    const content = fs.readFileSync(skillPath, 'utf-8');

    // 解析 frontmatter
    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);

    let frontmatter: SkillFrontmatter = {};
    if (frontmatterMatch) {
      frontmatter = this.parseFrontmatter(frontmatterMatch[1]);
    }

    return {
      name: frontmatter.name || name,
      description: frontmatter.description || '',
      version: frontmatter.version,
      author: frontmatter.author,
      tags: frontmatter.tags,
      category: frontmatter.category,
      filePath: skillPath,
      directory: skillDir,
    };
  }

  /**
   * 解析 YAML-like frontmatter
   */
  private parseFrontmatter(content: string): SkillFrontmatter {
    const result: SkillFrontmatter = {};
    const lines = content.split('\n');
    let currentKey: string | null = null;
    let currentValue: string | string[] | null = null;

    for (const line of lines) {
      // 空行处理
      if (!line.trim()) {
        continue;
      }

      // Key: Value 格式
      const simpleMatch = line.match(/^(\w+):\s*(.*)$/);
      if (simpleMatch) {
        // 保存上一个 key
        if (currentKey && currentValue !== null) {
          this.assignResult(result, currentKey, currentValue);
        }
        currentKey = simpleMatch[1];
        currentValue = simpleMatch[2].replace(/^["']|["']$/g, '').trim();
        continue;
      }

      // List item: - item
      const listMatch = line.match(/^\s*-\s*(.+)$/);
      if (listMatch) {
        if (!Array.isArray(currentValue)) {
          currentValue = currentValue ? [currentValue] : [];
        }
        (currentValue as string[]).push(listMatch[1].trim());
        continue;
      }

      // Indented continuation
      if (line.match(/^\s{2,}/) && currentValue !== null) {
        if (Array.isArray(currentValue)) {
          // 追加到最后一个元素
          const last = currentValue[currentValue.length - 1];
          currentValue[currentValue.length - 1] = last + ' ' + line.trim();
        } else {
          currentValue = (currentValue as string) + ' ' + line.trim();
        }
      }
    }

    // 保存最后一个 key
    if (currentKey && currentValue !== null) {
      this.assignResult(result, currentKey, currentValue);
    }

    return result;
  }

  /**
   * 赋值到结果对象，处理类型
   */
  private assignResult(
    result: SkillFrontmatter,
    key: string,
    value: string | string[]
  ): void {
    if (key === 'tags' && !Array.isArray(value)) {
      // tags 可能是逗号分隔的字符串
      result[key] = value.split(',').map((t) => t.trim());
    } else {
      result[key] = value;
    }
  }

  /**
   * 获取单个 Skill 定义
   */
  getSkill(name: string): SkillDefinition | null {
    if (!this.loaded) {
      this.loadAllSkills();
    }
    return this.skills.get(name) || null;
  }

  /**
   * 获取所有已加载的 Skills
   */
  getAllSkills(): Map<string, SkillDefinition> {
    if (!this.loaded) {
      this.loadAllSkills();
    }
    return this.skills;
  }

  /**
   * 获取 Skills 列表 (数组形式)
   */
  getSkillsList(): SkillDefinition[] {
    return Array.from(this.getAllSkills().values());
  }

  /**
   * 按类别获取 Skills
   */
  getSkillsByCategory(category: string): SkillDefinition[] {
    return this.getSkillsList().filter((s) => s.category === category);
  }

  /**
   * 搜索 Skills
   */
  searchSkills(query: string): SkillDefinition[] {
    const lowerQuery = query.toLowerCase();
    return this.getSkillsList().filter(
      (s) =>
        s.name.toLowerCase().includes(lowerQuery) ||
        s.description.toLowerCase().includes(lowerQuery) ||
        s.tags?.some((t) => t.toLowerCase().includes(lowerQuery))
    );
  }

  /**
   * 获取 Skills 数量
   */
  getSkillCount(): number {
    if (!this.loaded) {
      this.loadAllSkills();
    }
    return this.skills.size;
  }

  /**
   * 检查是否有 Skills 目录
   */
  hasSkillsDirectory(): boolean {
    return this.searchPaths.some((p) => fs.existsSync(p));
  }

  /**
   * 获取首个有效路径
   */
  getFirstValidPath(): string | null {
    for (const p of this.searchPaths) {
      if (fs.existsSync(p)) {
        return p;
      }
    }
    return null;
  }

  /**
   * 重新加载 (清除缓存)
   */
  reload(): void {
    this.loaded = false;
    this.skills.clear();
    this.loadAllSkills();
  }
}

// ============================================
// 单例导出
// ============================================

export const skillLoader = new SkillLoader();
