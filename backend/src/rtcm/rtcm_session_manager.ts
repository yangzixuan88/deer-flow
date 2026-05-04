/**
 * @file rtcm_session_manager.ts
 * @description RTCM 长运行与多项目运营能力 - Gamma 可运营态核心
 * 支持多项目并存、暂停/恢复、排队、续会、上下文隔离
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import * as crypto from 'crypto';

// ============================================================================
// Types
// ============================================================================

// 项目状态
export enum ProjectStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  WAITING_FOR_USER = 'waiting_for_user',
  ARCHIVED = 'archived',
  FAILED_RECOVERABLE = 'failed_recoverable',
  FAILED_TERMINAL = 'failed_terminal',
}

// 项目索引项
export interface ProjectIndexEntry {
  projectId: string;
  sessionId: string;
  projectName: string;
  status: ProjectStatus;
  createdAt: string;
  updatedAt: string;
  issueCount: number;
  currentIssueId: string | null;
  resumeIndex?: string;
}

// 项目上下文
export interface ProjectContext {
  projectId: string;
  sessionId: string;
  projectName: string;
  status: ProjectStatus;
  currentIssueId: string | null;
  currentStage: string;
  currentRound: number;
  signOffState: {
    completedIssues: string[];
    pendingIssues: string[];
  };
  leaseState: {
    granted: boolean;
    grantedBy: string | null;
    expiresAt: string | null;
  };
  dossierDir: string;
  telemetryDir: string;
  exportDir: string;
}

// Session Index
export interface SessionIndex {
  projects: ProjectIndexEntry[];
  lastUpdated: string;
}

// ============================================================================
// Session Manager
// ============================================================================

export class SessionManager {
  private indexFile: string;
  private managerDir: string;

  constructor() {
    const baseDir = runtimePath('rtcm', 'sessions');
    this.managerDir = baseDir;
    this.indexFile = path.join(baseDir, 'session_index.json');
    this.ensureDir(baseDir);
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Project Management
  // ===========================================================================

  /**
   * 创建新项目
   */
  createProject(projectName: string): ProjectContext {
    const projectId = `proj-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
    const sessionId = `rtcm-${projectId}`;
    const now = new Date().toISOString();

    const projectDir = path.join(this.managerDir, projectId);
    this.ensureDir(projectDir);
    this.ensureDir(path.join(projectDir, 'dossier'));
    this.ensureDir(path.join(projectDir, 'telemetry'));
    this.ensureDir(path.join(projectDir, 'exports'));

    const context: ProjectContext = {
      projectId,
      sessionId,
      projectName,
      status: ProjectStatus.ACTIVE,
      currentIssueId: null,
      currentStage: 'init',
      currentRound: 0,
      signOffState: {
        completedIssues: [],
        pendingIssues: [],
      },
      leaseState: {
        granted: false,
        grantedBy: null,
        expiresAt: null,
      },
      dossierDir: path.join(projectDir, 'dossier'),
      telemetryDir: path.join(projectDir, 'telemetry'),
      exportDir: path.join(projectDir, 'exports'),
    };

    // 保存项目上下文
    fs.writeFileSync(
      path.join(projectDir, 'context.json'),
      JSON.stringify(context, null, 2),
      'utf-8'
    );

    // 更新索引
    this.addToIndex(context);

    return context;
  }

  /**
   * 更新项目状态
   */
  updateProjectStatus(projectId: string, status: ProjectStatus): void {
    const index = this.readIndex();
    const entry = index.projects.find(p => p.projectId === projectId);
    if (!entry) return;

    entry.status = status;
    entry.updatedAt = new Date().toISOString();

    this.writeIndex(index);

    // 更新上下文
    const contextFile = path.join(this.managerDir, projectId, 'context.json');
    if (fs.existsSync(contextFile)) {
      const context = JSON.parse(fs.readFileSync(contextFile, 'utf-8'));
      context.status = status;
      fs.writeFileSync(contextFile, JSON.stringify(context, null, 2), 'utf-8');
    }
  }

  /**
   * 获取项目上下文
   */
  getProjectContext(projectId: string): ProjectContext | null {
    const contextFile = path.join(this.managerDir, projectId, 'context.json');
    if (!fs.existsSync(contextFile)) return null;
    return JSON.parse(fs.readFileSync(contextFile, 'utf-8'));
  }

  /**
   * 获取会话索引
   */
  getSessionIndex(): SessionIndex {
    return this.readIndex();
  }

  /**
   * 列出活跃项目
   */
  listActiveProjects(): ProjectIndexEntry[] {
    const index = this.readIndex();
    return index.projects.filter(p => p.status === ProjectStatus.ACTIVE);
  }

  /**
   * 列出待用户验收项目
   */
  listWaitingProjects(): ProjectIndexEntry[] {
    const index = this.readIndex();
    return index.projects.filter(p => p.status === ProjectStatus.WAITING_FOR_USER);
  }

  /**
   * 列出可续会项目（最近活跃且非 archived）
   */
  listResumableProjects(): ProjectIndexEntry[] {
    const index = this.readIndex();
    return index.projects
      .filter(p => p.status !== ProjectStatus.ARCHIVED && p.status !== ProjectStatus.FAILED_TERMINAL)
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  }

  // ===========================================================================
  // Project Operations
  // ===========================================================================

  /**
   * 暂停项目
   */
  pauseProject(projectId: string): boolean {
    const context = this.getProjectContext(projectId);
    if (!context) return false;

    this.updateProjectStatus(projectId, ProjectStatus.PAUSED);
    return true;
  }

  /**
   * 恢复项目
   */
  resumeProject(projectId: string): ProjectContext | null {
    const context = this.getProjectContext(projectId);
    if (!context) return null;

    if (context.status === ProjectStatus.ARCHIVED || context.status === ProjectStatus.FAILED_TERMINAL) {
      return null; // 不能恢复已归档或不可恢复的项目
    }

    this.updateProjectStatus(projectId, ProjectStatus.ACTIVE);
    context.status = ProjectStatus.ACTIVE;

    return context;
  }

  /**
   * 归档项目
   */
  archiveProject(projectId: string): void {
    this.updateProjectStatus(projectId, ProjectStatus.ARCHIVED);
  }

  // ===========================================================================
  // Context Isolation
  // ===========================================================================

  /**
   * 确保项目间上下文不串线
   */
  isolateProjectContext(projectId: string): ProjectContext | null {
    const context = this.getProjectContext(projectId);
    if (!context) return null;

    // 确保项目目录存在
    const requiredDirs = [context.dossierDir, context.telemetryDir, context.exportDir];
    for (const dir of requiredDirs) {
      this.ensureDir(dir);
    }

    return context;
  }

  /**
   * 验证项目数据完整性（不串项目）
   */
  validateProjectIsolation(projectId: string): {
    isolated: boolean;
    errors: string[];
  } {
    const errors: string[] = [];
    const context = this.getProjectContext(projectId);

    if (!context) {
      errors.push('Project context not found');
      return { isolated: false, errors };
    }

    // 检查项目目录是否正确隔离
    const projectDir = path.join(this.managerDir, projectId);
    if (!fs.existsSync(projectDir)) {
      errors.push('Project directory missing');
    }

    // 检查 dossier/telemetry/export 是否在正确位置
    const expectedDirs = ['dossier', 'telemetry', 'exports'];
    for (const dir of expectedDirs) {
      const fullPath = path.join(projectDir, dir);
      if (!fs.existsSync(fullPath)) {
        errors.push(`Expected directory missing: ${dir}`);
      }
    }

    // 确保没有混入其他项目的文件
    const allProjectDirs = fs.readdirSync(this.managerDir).filter(f => {
      const stat = fs.statSync(path.join(this.managerDir, f));
      return stat.isDirectory() && f.startsWith('proj-');
    });

    for (const dir of allProjectDirs) {
      if (dir !== projectId) {
        // 检查是否有文件错误地放到了其他项目中
        const otherProjectDir = path.join(this.managerDir, dir);
        const otherFiles = fs.existsSync(otherProjectDir) ? fs.readdirSync(otherProjectDir) : [];
        for (const file of otherFiles) {
          if (file === context.projectId) {
            errors.push(`Cross-project contamination detected: ${dir} contains ${projectId} reference`);
          }
        }
      }
    }

    return {
      isolated: errors.length === 0,
      errors,
    };
  }

  // ===========================================================================
  // Index Management
  // ===========================================================================

  private readIndex(): SessionIndex {
    if (!fs.existsSync(this.indexFile)) {
      return { projects: [], lastUpdated: new Date().toISOString() };
    }
    return JSON.parse(fs.readFileSync(this.indexFile, 'utf-8'));
  }

  private writeIndex(index: SessionIndex): void {
    index.lastUpdated = new Date().toISOString();
    fs.writeFileSync(this.indexFile, JSON.stringify(index, null, 2), 'utf-8');
  }

  private addToIndex(context: ProjectContext): void {
    const index = this.readIndex();

    const entry: ProjectIndexEntry = {
      projectId: context.projectId,
      sessionId: context.sessionId,
      projectName: context.projectName,
      status: context.status,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      issueCount: 0,
      currentIssueId: context.currentIssueId,
    };

    index.projects.push(entry);
    this.writeIndex(index);
  }

  private removeFromIndex(projectId: string): void {
    const index = this.readIndex();
    index.projects = index.projects.filter(p => p.projectId !== projectId);
    this.writeIndex(index);
  }

  // ===========================================================================
  // Multi-Project Concurrent Safety
  // ===========================================================================

  private activeProjectLocks: Map<string, boolean> = new Map();

  /**
   * 获取项目锁（防止并发冲突）
   */
  acquireProjectLock(projectId: string): boolean {
    if (this.activeProjectLocks.has(projectId)) {
      return false; // 已被锁定
    }
    this.activeProjectLocks.set(projectId, true);
    return true;
  }

  /**
   * 释放项目锁
   */
  releaseProjectLock(projectId: string): void {
    this.activeProjectLocks.delete(projectId);
  }

  /**
   * 检查是否有项目正在运行
   */
  hasActiveProjects(): boolean {
    const index = this.readIndex();
    return index.projects.some(p => p.status === ProjectStatus.ACTIVE);
  }

  /**
   * 获取当前活跃项目数
   */
  getActiveProjectCount(): number {
    const index = this.readIndex();
    return index.projects.filter(p => p.status === ProjectStatus.ACTIVE).length;
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const sessionManager = new SessionManager();
