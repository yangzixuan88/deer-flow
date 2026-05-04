/**
 * @file constitution_loader.ts
 * @description U0: Constitution Loader
 * Loads constitutional rules and state at upgrade center start
 */

import * as fs from 'fs';
import * as path from 'path';
import { runtimePath } from '../runtime_paths';
import {
  ConstitutionState,
  ImmutableZone,
  PendingApproval,
  ObservationCandidate,
} from './types';

const UPGRADE_CENTER_DIR = runtimePath('upgrade-center');
const CONSTITUTION_DIR = path.join(UPGRADE_CENTER_DIR, 'constitution');
const STATE_DIR = path.join(UPGRADE_CENTER_DIR, 'state');

export class ConstitutionLoader {
  /**
   * Load constitution state from disk
   */
  public async load(): Promise<ConstitutionState> {
    console.log('[ConstitutionLoader] Loading constitution state...');

    // Ensure directories exist
    this.ensureDirectories();

    // Load immutable zones
    const immutableZones = this.loadImmutableZones();

    // Load pending approvals
    const pendingApprovals = this.loadPendingApprovals();

    // Load observation pool snapshot
    const observationPool = this.loadObservationPool();

    const state: ConstitutionState = {
      constitution_loaded: true,
      immutable_zones: immutableZones,
      pending_approvals: pendingApprovals,
      observation_pool_snapshot: observationPool,
      last_updated: new Date().toISOString(),
    };

    console.log(`[ConstitutionLoader] Loaded ${immutableZones.length} immutable zones, ${pendingApprovals.length} pending approvals`);
    return state;
  }

  /**
   * Ensure required directories exist
   */
  private ensureDirectories(): void {
    const dirs = [UPGRADE_CENTER_DIR, CONSTITUTION_DIR, STATE_DIR];
    for (const dir of dirs) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
        console.log(`[ConstitutionLoader] Created directory: ${dir}`);
      }
    }
  }

  /**
   * Load immutable zones from constitution file
   */
  private loadImmutableZones(): ImmutableZone[] {
    const filePath = path.join(CONSTITUTION_DIR, 'immutable_zone_candidates.json');

    if (fs.existsSync(filePath)) {
      try {
        const content = fs.readFileSync(filePath, 'utf-8');
        const data = JSON.parse(content);
        return data.immutable_zones || [];
      } catch (error) {
        console.warn(`[ConstitutionLoader] Failed to load immutable zones: ${error}`);
      }
    }

    // Return default immutable zones
    return this.getDefaultImmutableZones();
  }

  /**
   * Load pending approvals from backlog
   */
  private loadPendingApprovals(): PendingApproval[] {
    const filePath = path.join(STATE_DIR, 'approval_backlog.json');

    if (fs.existsSync(filePath)) {
      try {
        const content = fs.readFileSync(filePath, 'utf-8');
        const data = JSON.parse(content);
        return data.pending_approvals?.filter((p: PendingApproval) => p.status === 'pending') || [];
      } catch (error) {
        console.warn(`[ConstitutionLoader] Failed to load pending approvals: ${error}`);
      }
    }

    return [];
  }

  /**
   * Load observation pool snapshot
   */
  private loadObservationPool(): ObservationCandidate[] {
    const filePath = path.join(STATE_DIR, 'observation_pool.json');

    if (fs.existsSync(filePath)) {
      try {
        const content = fs.readFileSync(filePath, 'utf-8');
        const data = JSON.parse(content);
        return data.candidates || [];
      } catch (error) {
        console.warn(`[ConstitutionLoader] Failed to load observation pool: ${error}`);
      }
    }

    return [];
  }

  /**
   * Get default immutable zones if none configured
   */
  private getDefaultImmutableZones(): ImmutableZone[] {
    return [
      {
        zone_id: 'M01_coordinator',
        description: 'M01协调器核心路由逻辑',
        protection_level: 'absolute',
      },
      {
        zone_id: 'M03_hooks',
        description: 'M03钩子系统敏感路径保护',
        protection_level: 'absolute',
      },
      {
        zone_id: 'M04_unified_executor',
        description: 'M04统一执行器核心',
        protection_level: 'high',
      },
      {
        zone_id: 'boulder_json',
        description: '系统心跳配置',
        protection_level: 'high',
      },
    ];
  }

  /**
   * Save constitution state (for updates)
   */
  public async save(state: ConstitutionState): Promise<void> {
    this.ensureDirectories();

    // Save pending approvals
    const backlogPath = path.join(STATE_DIR, 'approval_backlog.json');
    const backlog = { pending_approvals: state.pending_approvals };
    fs.writeFileSync(backlogPath, JSON.stringify(backlog, null, 2), 'utf-8');

    console.log('[ConstitutionLoader] Saved constitution state');
  }
}
