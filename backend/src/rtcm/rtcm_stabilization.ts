/**
 * @file rtcm_stabilization.ts
 * @description RTCM Feishu 与 Nightly Export 稳定化 - Gamma 可运营态
 * 本轮不扩功能，只增强稳定性：push retry、dedup、version、failure recovery
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as crypto from 'crypto';
import { runtimePath } from '../runtime_paths';

// ============================================================================
// Part 1: Feishu Push Stabilization
// ============================================================================

// Feishu Push Event
export interface FeishuPushEvent {
  eventId: string;
  eventType: 'session_opened' | 'issue_progress' | 'validation_result' | 'acceptance' | 'reopen' | 'summary';
  payload: object;
  targetProjectId: string;
  createdAt: string;
  status: 'pending' | 'sent' | 'failed' | 'deduplicated';
  retryCount: number;
  lastRetryAt?: string;
  error?: string;
  sentAt?: string;
}

// Feishu Push Manager
export class FeishuPushManager {
  private pushLogDir: string;
  private pendingPushes: Map<string, FeishuPushEvent> = new Map();
  private dedupCache: Map<string, string> = new Map(); // eventSignature -> eventId

  private static readonly MAX_RETRIES = 3;
  private static readonly DEDUP_WINDOW_MS = 60000; // 60秒内的重复被视为重复

  constructor() {
    this.pushLogDir = runtimePath('rtcm', 'feishu', 'push_log');
    this.ensureDir(this.pushLogDir);
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  /**
   * 生成事件签名（用于去重）
   */
  private generateEventSignature(eventType: string, targetProjectId: string, payload: object): string {
    const content = `${eventType}:${targetProjectId}:${JSON.stringify(payload)}`;
    return crypto.createHash('sha256').update(content).digest('hex').slice(0, 16);
  }

  /**
   * 检查是否重复推送
   */
  isDuplicate(eventType: string, targetProjectId: string, payload: object): boolean {
    const signature = this.generateEventSignature(eventType, targetProjectId, payload);

    if (this.dedupCache.has(signature)) {
      const cachedEventId = this.dedupCache.get(signature)!;
      const cachedEvent = this.pendingPushes.get(cachedEventId);

      if (cachedEvent && cachedEvent.status === 'sent') {
        const timeDiff = Date.now() - new Date(cachedEvent.sentAt!).getTime();
        if (timeDiff < FeishuPushManager.DEDUP_WINDOW_MS) {
          return true; // 在窗口期内，且已发送过
        }
      }
    }

    return false;
  }

  /**
   * 记录推送事件
   */
  recordPush(
    eventType: string,
    targetProjectId: string,
    payload: object
  ): FeishuPushEvent {
    const signature = this.generateEventSignature(eventType, targetProjectId, payload);

    const event: FeishuPushEvent = {
      eventId: `feishu-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`,
      eventType: eventType as FeishuPushEvent['eventType'],
      payload,
      targetProjectId,
      createdAt: new Date().toISOString(),
      status: 'pending',
      retryCount: 0,
    };

    this.pendingPushes.set(event.eventId, event);
    this.dedupCache.set(signature, event.eventId);

    // 持久化 payload
    this.savePayload(event);

    return event;
  }

  /**
   * 标记推送成功
   */
  markSent(eventId: string): void {
    const event = this.pendingPushes.get(eventId);
    if (!event) return;

    event.status = 'sent';
    event.sentAt = new Date().toISOString();
    this.saveEventLog(event);
  }

  /**
   * 标记推送失败并记录错误
   */
  markFailed(eventId: string, error: string): void {
    const event = this.pendingPushes.get(eventId);
    if (!event) return;

    event.retryCount++;
    event.lastRetryAt = new Date().toISOString();
    event.error = error;

    if (event.retryCount >= FeishuPushManager.MAX_RETRIES) {
      event.status = 'failed';
    }

    this.saveEventLog(event);
  }

  /**
   * 重试失败的推送
   */
  retryFailed(): FeishuPushEvent[] {
    const toRetry: FeishuPushEvent[] = [];

    for (const [, event] of this.pendingPushes) {
      if (event.status === 'failed' && event.retryCount < FeishuPushManager.MAX_RETRIES) {
        event.status = 'pending';
        event.error = undefined;
        toRetry.push(event);
      }
    }

    return toRetry;
  }

  /**
   * 获取待处理推送
   */
  getPendingPushes(): FeishuPushEvent[] {
    return Array.from(this.pendingPushes.values()).filter(e => e.status === 'pending');
  }

  /**
   * 获取失败推送（需要人工介入）
   */
  getFailedPushes(): FeishuPushEvent[] {
    return Array.from(this.pendingPushes.values()).filter(e => e.status === 'failed');
  }

  /**
   * 持久化 payload 到磁盘
   */
  private savePayload(event: FeishuPushEvent): void {
    const payloadFile = path.join(this.pushLogDir, `${event.eventId}_payload.json`);
    fs.writeFileSync(payloadFile, JSON.stringify(event.payload, null, 2), 'utf-8');
  }

  private saveEventLog(event: FeishuPushEvent): void {
    const logFile = path.join(this.pushLogDir, 'push_events.jsonl');
    fs.appendFileSync(logFile, JSON.stringify(event) + '\n', 'utf-8');
  }
}

// ============================================================================
// Part 2: Nightly Export Stabilization
// ============================================================================

// Export Version Info
export interface ExportVersionInfo {
  exportId: string;
  exportType: 'issue_level' | 'project_level';
  version: string; // 语义版本，如 "1.0.0"
  schemaVersion: string; // 数据结构版本
  createdAt: string;
  checksum: string; // SHA-256 checksum
  snapshotId: string;
  projectId: string;
  previousExportId?: string; // 链式追溯
  metadata: {
    roundCount?: number;
    issueCount?: number;
    totalTokens?: number;
    qualityScore?: number;
  };
}

// Export Snapshot
export interface ExportSnapshot {
  snapshotId: string;
  exportId: string;
  createdAt: string;
  data: object;
  checksum: string;
  immutable: true;
}

// Export Failure Recovery
export interface ExportFailureRecord {
  failureId: string;
  exportId: string;
  exportType: string;
  error: string;
  timestamp: string;
  recovered: boolean;
  recoveryAttempts: number;
}

// Nightly Export Manager
export class NightlyExportManager {
  private exportDir: string;
  private versionFile: string;
  private failures: ExportFailureRecord[] = [];

  private static readonly CURRENT_SCHEMA_VERSION = '1.0.0';

  constructor() {
    this.exportDir = runtimePath('rtcm', 'exports', 'nightly');
    this.versionFile = path.join(this.exportDir, 'export_versions.jsonl');
    this.ensureDir(this.exportDir);
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  /**
   * 生成 export checksum
   */
  generateChecksum(data: object): string {
    return crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex');
  }

  /**
   * 创建 Export Version Info
   */
  createExportVersion(
    exportType: 'issue_level' | 'project_level',
    projectId: string,
    data: object,
    previousExportId?: string
  ): ExportVersionInfo {
    const exportId = `exp-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
    const checksum = this.generateChecksum(data);
    const snapshotId = `snap-${exportId}`;

    const versionInfo: ExportVersionInfo = {
      exportId,
      exportType,
      version: '1.0.0',
      schemaVersion: NightlyExportManager.CURRENT_SCHEMA_VERSION,
      createdAt: new Date().toISOString(),
      checksum,
      snapshotId,
      projectId,
      previousExportId,
    };

    // 写入版本文件
    fs.appendFileSync(this.versionFile, JSON.stringify(versionInfo) + '\n', 'utf-8');

    // 创建不可变快照
    this.createSnapshot(snapshotId, exportId, data);

    return versionInfo;
  }

  /**
   * 创建不可变快照
   */
  private createSnapshot(snapshotId: string, exportId: string, data: object): ExportSnapshot {
    const snapshot: ExportSnapshot = {
      snapshotId,
      exportId,
      createdAt: new Date().toISOString(),
      data,
      checksum: this.generateChecksum(data),
      immutable: true,
    };

    const snapshotFile = path.join(this.exportDir, `${snapshotId}.snap.json`);
    fs.writeFileSync(snapshotFile, JSON.stringify(snapshot, null, 2), 'utf-8');

    // 标记为不可变（通过权限）
    try {
      fs.chmodSync(snapshotFile, 0o444); // 只读
    } catch {
      // 权限设置可能失败，忽略
    }

    return snapshot;
  }

  /**
   * 验证 Export 完整性
   */
  verifyExport(exportId: string): { valid: boolean; reason?: string } {
    // 查找版本信息
    if (!fs.existsSync(this.versionFile)) {
      return { valid: false, reason: 'No version file found' };
    }

    const lines = fs.readFileSync(this.versionFile, 'utf-8').split('\n').filter(Boolean);
    const versionInfo = lines.find(line => {
      const info = JSON.parse(line);
      return info.exportId === exportId;
    });

    if (!versionInfo) {
      return { valid: false, reason: 'Export not found in version history' };
    }

    const info: ExportVersionInfo = JSON.parse(versionInfo);

    // 验证快照是否存在
    const snapshotFile = path.join(this.exportDir, `${info.snapshotId}.snap.json`);
    if (!fs.existsSync(snapshotFile)) {
      return { valid: false, reason: 'Snapshot file missing' };
    }

    // 读取快照并验证 checksum
    const snapshot: ExportSnapshot = JSON.parse(fs.readFileSync(snapshotFile, 'utf-8'));
    if (snapshot.checksum !== info.checksum) {
      return { valid: false, reason: 'Checksum mismatch - data may have been tampered' };
    }

    return { valid: true };
  }

  /**
   * 记录 Export 失败
   */
  recordFailure(exportId: string, exportType: string, error: string): ExportFailureRecord {
    const record: ExportFailureRecord = {
      failureId: `fail-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`,
      exportId,
      exportType,
      error,
      timestamp: new Date().toISOString(),
      recovered: false,
      recoveryAttempts: 0,
    };

    this.failures.push(record);
    this.saveFailureRecord(record);

    return record;
  }

  private saveFailureRecord(record: ExportFailureRecord): void {
    const failureFile = path.join(this.exportDir, 'failures.jsonl');
    fs.appendFileSync(failureFile, JSON.stringify(record) + '\n', 'utf-8');
  }

  /**
   * 恢复失败的 export
   */
  recoverFailedExport(exportId: string): { success: boolean; error?: string } {
    try {
      // 验证 export 是否存在
      const verification = this.verifyExport(exportId);
      if (!verification.valid) {
        return { success: false, error: verification.reason };
      }

      // 标记为已恢复
      const failure = this.failures.find(f => f.exportId === exportId);
      if (failure) {
        failure.recovered = true;
        failure.recoveryAttempts++;
      }

      return { success: true };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  }

  /**
   * 获取导出历史
   */
  getExportHistory(projectId?: string): ExportVersionInfo[] {
    if (!fs.existsSync(this.versionFile)) {
      return [];
    }

    const lines = fs.readFileSync(this.versionFile, 'utf-8').split('\n').filter(Boolean);
    const exports = lines.map(line => JSON.parse(line) as ExportVersionInfo);

    if (projectId) {
      return exports.filter(e => e.projectId === projectId);
    }

    return exports;
  }

  /**
   * 确保 Export 不可逆修改保障
   * 一旦快照创建，原始数据不能被修改
   */
  assertImmutable(snapshotId: string): boolean {
    const snapshotFile = path.join(this.exportDir, `${snapshotId}.snap.json`);

    if (!fs.existsSync(snapshotFile)) {
      return false;
    }

    // 检查文件权限（如果支持）
    try {
      const stat = fs.statSync(snapshotFile);
      // 如果文件可写（除了 owner），则认为不安全
      const mode = stat.mode & 0o777;
      if (mode & 0o222) {
        // 文件可写，重新设置为只读
        fs.chmodSync(snapshotFile, 0o444);
        return false; // 曾被修改
      }
    } catch {
      // 权限检查可能失败，忽略
    }

    return true;
  }
}

// ============================================================================
// Singletons
// ============================================================================

export const feishuPushManager = new FeishuPushManager();
export const nightlyExportManager = new NightlyExportManager();
