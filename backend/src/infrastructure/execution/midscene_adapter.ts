/**
 * @file midscene_adapter.ts
 * @description Adapter for Midscene.js (Vision-Driven UI Automation).
 * Integrates with OpenHarness hooks.
 */

import { BaseExecutionAdapter } from './base_adapter';
import { HookContext } from '../../domain/hooks';

export class MidsceneAdapter extends BaseExecutionAdapter {
  private readonly toolName = "Midscene.js";

  /**
   * Executes a visual-only UI automation script.
   * Reference: Super Constitution §12.6
   */
  public async executeVisualAction(
    scriptPath: string,
    context: HookContext
  ): Promise<string> {
    // 强制使用 visual-only 模式以降低 Token 消耗 (72% 节省算法相关)
    const command = `npx @midscene/cli run ${scriptPath} --visual-only`;
    
    return this.executeCLI(
      this.toolName,
      "visual-action",
      { scriptPath, visualOnly: true },
      command,
      context
    );
  }

  /**
   * Bridge Mode: Controls desktop browsers or apps.
   */
  public async executeBridgeMode(
    action: string,
    context: HookContext
  ): Promise<string> {
    const command = `npx @midscene/web bridge --action "${action}"`;
    
    return this.executeCLI(
      this.toolName,
      "bridge-action",
      { action, bridgeMode: true },
      command,
      context
    );
  }
}
