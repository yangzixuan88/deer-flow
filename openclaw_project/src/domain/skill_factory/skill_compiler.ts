/**
 * @file skill_compiler.ts
 * @description Implementation of the Skill-to-Markdown Compiler (Action 027).
 * Converts L3 assets (like react_ui_comparison.md) into OpenClaw SKILL.md format.
 * Reference: Super Constitution Phase 8 & Skill-Packing System.
 */

import * as fs from 'fs';
import * as path from 'path';

export interface SkillMetadata {
  name: string;
  description: string;
  category: string;
  quality_score: number;
}

/**
 * Skill-to-Markdown Compiler (Action 027)
 * Logic: Extract Conclusion -> Compile YAML -> Generate SKILL.md.
 */
export class SkillToMarkdownCompiler {
  // Use relative paths from project root for portability
  private readonly PROJECT_ROOT: string;
  private readonly ASSETS_ROOT: string;
  private readonly SKILLS_ROOT: string;

  constructor() {
    // Resolve paths relative to project root (parent of src/domain)
    this.PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
    this.ASSETS_ROOT = path.join(this.PROJECT_ROOT, 'assets');
    this.SKILLS_ROOT = path.join(this.ASSETS_ROOT, 'cold_skills');
  }

  /**
   * Compiles an asset into a reusable OpenClaw Skill.
   */
  public async compileAssetToSkill(assetPath: string, metadata: SkillMetadata): Promise<string> {
    console.log(`[SkillCompiler] Compiling asset: ${assetPath} into skill: ${metadata.name}`);

    const fullAssetPath = path.join(this.ASSETS_ROOT, assetPath);
    if (!fs.existsSync(fullAssetPath)) {
      throw new Error(`Asset not found: ${fullAssetPath}`);
    }

    const content = fs.readFileSync(fullAssetPath, 'utf-8');

    // 1. Extract core knowledge/conclusion (Simplified logic)
    const skillContent = this.extractSkillContent(content, metadata);

    // 2. Generate SKILL.md with YAML frontmatter
    const skillMarkdown = this.generateSkillMarkdown(metadata, skillContent);

    // 3. Create skill directory and write SKILL.md
    const skillDir = path.join(this.SKILLS_ROOT, metadata.name);
    if (!fs.existsSync(skillDir)) {
      fs.mkdirSync(skillDir, { recursive: true });
    }

    const skillFilePath = path.join(skillDir, 'SKILL.md');
    fs.writeFileSync(skillFilePath, skillMarkdown, 'utf-8');

    console.log(`[SkillCompiler] Successfully compiled skill to: ${skillFilePath}`);
    return skillFilePath;
  }

  /**
   * Generates the SKILL.md content following the OpenClaw specification.
   * YAML Frontmatter + Markdown Body.
   */
  private generateSkillMarkdown(metadata: SkillMetadata, content: string): string {
    const yaml = [
      '---',
      `name: ${metadata.name}`,
      `description: "${metadata.description.replace(/"/g, '\\"')}"`,
      'metadata:',
      `  category: ${metadata.category}`,
      `  quality_score: ${metadata.quality_score}`,
      '---',
      '',
      `# ${metadata.name.replace(/-/g, ' ').toUpperCase()}`,
      '',
      content
    ].join('\n');

    return yaml;
  }

  /**
   * Extracts the core "How-to" or conclusion from an asset to form the skill body.
   */
  private extractSkillContent(content: string, metadata: SkillMetadata): string {
    // Logic: In a real system, this would use an LLM or DSPy to distill the "Skill" part.
    // For now, we take the content and wrap it with a "Usage Guide" header.
    return [
      '## Overview',
      `This skill is derived from the "${metadata.name}" asset, providing expert-level guidance on ${metadata.category}.`,
      '',
      '## Reusable Knowledge',
      content,
      '',
      '## Implementation Guide',
      '1. Review the comparative data above.',
      `2. Apply the "${metadata.name}" standard to your current project.`,
      '3. Verify compatibility in the TES sandbox before deployment.'
    ].join('\n');
  }
}
