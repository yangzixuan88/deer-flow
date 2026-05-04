/**
 * Bridge Manager for OpenClaw Architecture 2.0
 * Purpose: Manages cross-engine data transformation between n8n and Dify
 * Aligns with "DeerFlow + n8n + Dify Triple-Wheel" architecture
 */

import { N8NClient } from './n8n_client';
import { DifyClient } from './dify_client';

export enum BridgeType {
  N8N_TO_DIFY = 'n8n_to_dify',
  DIFY_TO_N8N = 'dify_to_n8n',
  BIDIRECTIONAL = 'bidirectional',
}

export interface BridgeConfig {
  type: BridgeType;
  enabled: boolean;
  data_transform?: {
    map_fields?: Record<string, string>;
    transform_functions?: Record<string, string>;
  };
}

export interface BridgeResult {
  success: boolean;
  data?: any;
  error?: string;
  bridge_type: BridgeType;
}

/**
 * Bridge Manager
 *
 * Manages data flow and transformation between n8n and Dify workflows
 */
export class BridgeManager {
  private n8nClient: N8NClient;
  private difyClient: DifyClient;
  private bridges: Map<string, BridgeConfig> = new Map();

  constructor(n8nClient: N8NClient, difyClient: DifyClient) {
    this.n8nClient = n8nClient;
    this.difyClient = difyClient;
    this.initializeDefaultBridges();
  }

  /**
   * Initialize default bridge configurations
   */
  private initializeDefaultBridges(): void {
    this.bridges.set('n8n_dify_default', {
      type: BridgeType.N8N_TO_DIFY,
      enabled: true,
      data_transform: {
        map_fields: {
          'n8n.output': 'dify.input',
          'n8n.context': 'dify.query',
        },
      },
    });
  }

  /**
   * Create a new bridge
   */
  createBridge(bridgeId: string, config: BridgeConfig): void {
    this.bridges.set(bridgeId, config);
  }

  /**
   * Execute bridge transformation
   */
  async executeBridge(
    bridgeId: string,
    inputData: any,
    direction: 'forward' | 'backward' = 'forward'
  ): Promise<BridgeResult> {
    const bridge = this.bridges.get(bridgeId);
    if (!bridge || !bridge.enabled) {
      return {
        success: false,
        error: `Bridge ${bridgeId} not found or disabled`,
        bridge_type: bridge?.type || BridgeType.BIDIRECTIONAL,
      };
    }

    try {
      // Apply data transformation if configured
      let transformedData = inputData;
      if (bridge.data_transform?.map_fields) {
        transformedData = this.transformData(inputData, bridge.data_transform.map_fields);
      }

      return {
        success: true,
        data: transformedData,
        bridge_type: bridge.type,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        bridge_type: bridge.type,
      };
    }
  }

  /**
   * Transform data based on field mapping
   */
  private transformData(data: any, fieldMap: Record<string, string>): any {
    const result: any = {};
    for (const [sourceField, targetField] of Object.entries(fieldMap)) {
      const value = this.getNestedValue(data, sourceField);
      this.setNestedValue(result, targetField, value);
    }
    return result;
  }

  /**
   * Get nested value from object using dot notation
   */
  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  /**
   * Set nested value in object using dot notation
   */
  private setNestedValue(obj: any, path: string, value: any): void {
    const keys = path.split('.');
    const lastKey = keys.pop();
    const target = keys.reduce((current, key) => {
      if (!current[key]) current[key] = {};
      return current[key];
    }, obj);
    if (lastKey) target[lastKey] = value;
  }

  /**
   * Get all registered bridges
   */
  getBridges(): Map<string, BridgeConfig> {
    return new Map(this.bridges);
  }

  /**
   * Bridge data between two nodes (simplified for unified_executor)
   */
  async bridge(
    fromNode: any,
    toNode: any,
    data: any,
    edge: any
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      // Apply basic transformation
      let transformed = data;
      if (edge?.transform?.map_fields) {
        transformed = this.transformData(data, edge.transform.map_fields);
      }
      return { success: true, data: transformed };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
}

/**
 * Create BridgeManager instance
 */
export function createBridgeManager(
  n8nClient: N8NClient,
  difyClient: DifyClient
): BridgeManager {
  return new BridgeManager(n8nClient, difyClient);
}

/**
 * Get global BridgeManager instance (singleton)
 */
let globalBridgeManager: BridgeManager | null = null;

export function getBridgeManager(): BridgeManager | null {
  return globalBridgeManager;
}
