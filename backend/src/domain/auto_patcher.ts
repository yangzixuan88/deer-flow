/**
 * @file auto_patcher.ts
 * @description Implementation of the Auto-Patching Engine.
 * Applies validated EvolutionPatches and SandboxReports to infrastructure configurations.
 * Reference: Phase 7 Evolution & Self-Healing Architecture
 */

import { SandboxReport } from './shadow_tester';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Auto-Patching Engine
 * The "Immunity Response" that actually modifies the system state after a green sandbox test.
 */
export class AutoPatchingEngine {
  private readonly PROJECT_ROOT = process.cwd();
  private readonly DOCKER_COMPOSE_PATH = path.join(this.PROJECT_ROOT, 'src/infrastructure/docker-compose.yml');

  constructor() {}

  /**
   * Applies an upgrade patch based on a successful SandboxReport.
   */
  public async applyUpgrade(report: SandboxReport): Promise<{ success: boolean; message: string }> {
    console.log(`[AutoPatcher] Applying upgrade for ${report.testVersion} based on Sandbox Report...`);

    if (report.recommendation !== 'upgrade') {
      return { success: false, message: "Recommendation is not 'upgrade'. Skipping." };
    }

    try {
      // Logic: Specifically target Dapr versions in docker-compose.yml
      let content = fs.readFileSync(this.DOCKER_COMPOSE_PATH, 'utf-8');
      
      // Replace old version with new version (Regex-based for safety)
      const oldVersionPattern = new RegExp(`image: "daprio/(dapr|daprd):${report.originalVersion}"`, 'g');
      const newVersionString = `image: "daprio/$1:${report.testVersion}"`;

      if (!content.match(oldVersionPattern)) {
        // Fallback: If 'latest' is used, pin it
        content = content.replace(/image: "daprio\/(dapr|daprd):latest"/g, `image: "daprio/$1:${report.testVersion}"`);
      } else {
        content = content.replace(oldVersionPattern, newVersionString);
      }

      fs.writeFileSync(this.DOCKER_COMPOSE_PATH, content, 'utf-8');
      
      console.log(`[AutoPatcher] Successfully patched docker-compose.yml to version ${report.testVersion}`);
      return { success: true, message: `System evolved to ${report.testVersion}` };
    } catch (error: any) {
      console.error(`[AutoPatcher] Patching failed: ${error.message}`);
      return { success: false, message: error.message };
    }
  }

  /**
   * Records the evolution in the Decision Log.
   */
  public async logEvolution(report: SandboxReport): Promise<void> {
    const logEntry = `
### [E-001] 自动化版本演进: Dapr ${report.testVersion}
*   **背景**: Librarian 发现 Dapr v${report.testVersion} 更新。
*   **验证**: Shadow-A/B-Tester 验证通过 (性能提升: ${report.performanceDiff}%)。
*   **结果**: Auto-Patching Engine 已自动更新 docker-compose.yml 并锚定版本。
*   **状态**: 🚀 自治进化成功
`;
    fs.appendFileSync(path.join(this.PROJECT_ROOT, 'Decision_Log.md'), logEntry, 'utf-8');
  }
}
