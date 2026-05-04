/**
 * Dify API Client for OpenClaw Architecture 2.0
 * ================================================
 * Purpose: Provides AI-native workflow execution via Dify
 * Complements n8n for LLM/RAG/Agent capabilities
 * ================================================
 */

import * as http from 'http';
import { URL } from 'url';

// ============================================
// 类型定义
// ============================================

export interface DifyConfig {
  baseUrl: string;
  apiKey: string;
  timeout: number;
  retryAttempts: number;
}

export interface WorkflowRunRequest {
  workflow_id: string;
  inputs: Record<string, any>;
  response_mode?: 'blocking' | 'streaming';
  user?: string;
}

export interface WorkflowRunResponse {
  task_id: string;
  workflow_run_id: string;
  outputs?: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  error?: string;
  elapsed_time?: number;
}

export interface ChatMessageRequest {
  query: string;
  inputs?: Record<string, any>;
  response_mode: 'blocking' | 'streaming';
  user: string;
  conversation_id?: string;
  files?: Array<{ type: string; url: string }>;
}

export interface ChatMessageResponse {
  message_id: string;
  conversation_id: string;
  mode: 'chat' | 'completion';
  answer: string;
  metadata?: Record<string, any>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface DatasetRetrievalRequest {
  dataset_ids: string[];
  query: string;
  top_k?: number;
  score_threshold?: number;
}

export interface CompletionRequest {
  query: string;
  inputs?: Record<string, any>;
  response_mode?: 'blocking' | 'streaming';
  user?: string;
}

export interface DatasetInfo {
  id: string;
  name: string;
  description?: string;
  document_count: number;
  created_at: string;
}

export interface DocumentUploadResponse {
  id: string;
  dataset_id: string;
  document: {
    id: string;
    name: string;
    status: string;
  };
}

// ============================================
// Dify Client 实现
// ============================================

export class DifyClient {
  private config: DifyConfig;

  constructor(config?: Partial<DifyConfig>) {
    const baseUrl = process.env.DIFY_BASE_URL || 'http://localhost/v1';
    const apiKey = process.env.DIFY_API_KEY || '';

    this.config = {
      baseUrl: baseUrl.replace(/\/$/, ''),
      apiKey,
      timeout: config?.timeout ?? parseInt(process.env.DIFY_TIMEOUT_MS || '60000'),
      retryAttempts: config?.retryAttempts ?? 3,
    };
  }

  // SECURITY: SSRF 防护 - 验证 URL 不指向私有/内网地址
  private validateWebhookUrl(url: string): void {
    try {
      const urlObj = new URL(url);
      const hostname = urlObj.hostname.toLowerCase();

      // 检查是否为内网/私有地址
      const isPrivate = (
        hostname === 'localhost' ||
        hostname === '127.0.0.1' ||
        hostname === '::1' ||
        hostname.startsWith('10.') ||
        hostname.startsWith('172.16.') || hostname.startsWith('172.17.') || hostname.startsWith('172.18.') ||
        hostname.startsWith('172.19.') || hostname.startsWith('172.20.') || hostname.startsWith('172.21.') ||
        hostname.startsWith('172.22.') || hostname.startsWith('172.23.') || hostname.startsWith('172.24.') ||
        hostname.startsWith('172.25.') || hostname.startsWith('172.26.') || hostname.startsWith('172.27.') ||
        hostname.startsWith('172.28.') || hostname.startsWith('172.29.') || hostname.startsWith('172.30.') ||
        hostname.startsWith('172.31.') ||
        hostname.startsWith('192.168.') ||
        hostname.startsWith('169.254.') ||
        hostname.endsWith('.internal') ||
        hostname.endsWith('.local') ||
        hostname === '0.0.0.0' ||
        /^[fF][cCdD][0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){0,6}$/.test(hostname) ||
        hostname.startsWith('fe80:') ||
        hostname === '::' ||
        /^\[.*\]$/.test(hostname)
      );

      if (isPrivate) {
        throw new Error(`SSRF protection: webhook URL cannot point to private/internal network: ${hostname}`);
      }
    } catch (e: any) {
      if (e.message.includes('SSRF protection')) {
        throw e;
      }
      throw new Error(`Invalid webhook URL: ${url}`);
    }
  }

  // ============================================
  // HTTP 请求底层
  // ============================================

  private async request<T>(
    path: string,
    method: string = 'GET',
    body?: any,
    additionalHeaders?: Record<string, string>
  ): Promise<T> {
    const url = new URL(`${this.config.baseUrl}${path}`);

    return new Promise((resolve, reject) => {
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${this.config.apiKey}`,
        'Content-Type': 'application/json',
        ...additionalHeaders,
      };

      const options: http.RequestOptions = {
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? 443 : 80),
        path: url.pathname + url.search,
        method,
        headers,
        timeout: this.config.timeout,
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          try {
            if (data) {
              const parsed = JSON.parse(data);
              resolve(parsed as T);
            } else {
              resolve({} as T);
            }
          } catch {
            resolve(data as unknown as T);
          }
        });
      });

      req.on('error', (error) => {
        console.error(`[DifyClient] Request failed: ${error.message}`);
        reject(error);
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Request timeout'));
      });

      if (body) {
        const bodyStr = typeof body === 'string' ? body : JSON.stringify(body);
        req.write(bodyStr);
      }
      req.end();
    });
  }

  private async retryRequest<T>(
    path: string,
    method: string,
    body?: any,
    headers?: Record<string, string>,
    attempt: number = 1
  ): Promise<T> {
    try {
      return await this.request<T>(path, method, body, headers);
    } catch (error) {
      if (attempt < this.config.retryAttempts) {
        const backoff = Math.pow(2, attempt) * 1000;
        console.warn(`[DifyClient] Retrying in ${backoff}ms (attempt ${attempt + 1})`);
        await new Promise((r) => setTimeout(r, backoff));
        return this.retryRequest<T>(path, method, body, headers, attempt + 1);
      }
      throw error;
    }
  }

  // ============================================
  // 工作流 API
  // ============================================

  /**
   * 阻塞式运行工作流
   */
  async runWorkflow(
    workflowId: string,
    inputs: Record<string, any>,
    user: string = 'openclaw',
    responseMode: 'blocking' | 'streaming' = 'blocking'
  ): Promise<WorkflowRunResponse> {
    return this.retryRequest<WorkflowRunResponse>(
      '/v1/workflows/run',
      'POST',
      {
        workflow_id: workflowId,
        inputs,
        response_mode: responseMode,
        user,
      }
    );
  }

  /**
   * 停止工作流执行
   */
  async stopWorkflow(taskId: string): Promise<{ result: boolean }> {
    return this.retryRequest<{ result: boolean }>(
      `/v1/workflows/run/${taskId}/stop`,
      'POST',
      {}
    );
  }

  /**
   * 获取工作流执行详情
   */
  async getRunDetail(taskId: string): Promise<WorkflowRunResponse> {
    return this.retryRequest<WorkflowRunResponse>(
      `/v1/workflows/run/${taskId}`,
      'GET'
    );
  }

  // ============================================
  // 聊天 API
  // ============================================

  /**
   * 发送聊天消息（阻塞模式）
   */
  async chat(
    appId: string,
    query: string,
    user: string = 'openclaw',
    options?: {
      conversation_id?: string;
      inputs?: Record<string, any>;
    }
  ): Promise<ChatMessageResponse> {
    return this.retryRequest<ChatMessageResponse>(
      '/v1/chat-messages',
      'POST',
      {
        inputs: options?.inputs || {},
        query,
        response_mode: 'blocking',
        user,
        conversation_id: options?.conversation_id,
      }
    );
  }

  /**
   * 获取聊天消息详情
   */
  async getMessage(messageId: string): Promise<ChatMessageResponse> {
    return this.retryRequest<ChatMessageResponse>(
      `/v1/chat-messages/${messageId}`,
      'GET'
    );
  }

  // ============================================
  // 文本补全 API
  // ============================================

  /**
   * 文本补全（阻塞模式）
   */
  async completion(
    prompt: string,
    user: string = 'openclaw',
    options?: {
      inputs?: Record<string, any>;
      model?: string;
      temperature?: number;
    }
  ): Promise<{ output_text: string; usage?: any }> {
    return this.retryRequest(
      '/v1/completion-messages',
      'POST',
      {
        inputs: options?.inputs || {},
        query: prompt,
        response_mode: 'blocking',
        user,
      }
    );
  }

  // ============================================
  // 知识库 API
  // ============================================

  /**
   * 列出所有知识库
   */
  async listDatasets(): Promise<{ data: DatasetInfo[] }> {
    return this.retryRequest<{ data: DatasetInfo[] }>('/v1/datasets', 'GET');
  }

  /**
   * 创建知识库
   */
  async createDataset(
    name: string,
    description?: string
  ): Promise<{ id: string; name: string }> {
    return this.retryRequest('/v1/datasets', 'POST', {
      name,
      description,
    });
  }

  /**
   * 删除知识库
   */
  async deleteDataset(datasetId: string): Promise<{ result: boolean }> {
    return this.retryRequest<{ result: boolean }>(
      `/v1/datasets/${datasetId}`,
      'DELETE'
    );
  }

  /**
   * 获取知识库详情
   */
  async getDataset(datasetId: string): Promise<DatasetInfo> {
    return this.retryRequest<DatasetInfo>(`/v1/datasets/${datasetId}`, 'GET');
  }

  /**
   * 上传文档到知识库（多部分表单）
   */
  async uploadDocument(
    datasetId: string,
    fileContent: Buffer,
    fileName: string,
    indexingTechnique: 'high_quality' | 'economy' = 'high_quality'
  ): Promise<DocumentUploadResponse> {
    const boundary = `----DifyFormBoundary${Date.now()}`;
    const bodyParts: Buffer[] = [];

    // File part
    const header = `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${fileName}"\r\nContent-Type: application/octet-stream\r\n\r\n`;
    bodyParts.push(Buffer.from(header));
    bodyParts.push(fileContent);
    bodyParts.push(Buffer.from('\r\n'));

    // Indexing technique
    const indexingPart = `--${boundary}\r\nContent-Disposition: form-data; name="indexing_technique"\r\n\r\n${indexingTechnique}\r\n`;
    bodyParts.push(Buffer.from(indexingPart));

    // Process rule
    const processRule = `--${boundary}\r\nContent-Disposition: form-data; name="process_rule"\r\n\r\n${JSON.stringify({ mode: 'automatic', rules: {} })}\r\n`;
    bodyParts.push(Buffer.from(processRule));

    // End boundary
    bodyParts.push(Buffer.from(`--${boundary}--\r\n`));

    const body = Buffer.concat(bodyParts);

    return new Promise((resolve, reject) => {
      const url = new URL(`${this.config.baseUrl}/v1/datasets/${datasetId}/documents`);
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${this.config.apiKey}`,
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
      };

      const options: http.RequestOptions = {
        hostname: url.hostname,
        port: url.port || 80,
        path: url.pathname,
        method: 'POST',
        headers,
        timeout: this.config.timeout,
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            reject(new Error(`Failed to parse response: ${data}`));
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Request timeout'));
      });

      req.write(body);
      req.end();
    });
  }

  /**
   * 知识检索
   */
  async retrieve(
    request: DatasetRetrievalRequest
  ): Promise<{ records: any[] }> {
    return this.retryRequest<{ records: any[] }>(
      '/v1/datasets/retrieve',
      'POST',
      request
    );
  }

  // ============================================
  // Webhook 触发
  // ============================================

  /**
   * 通过 Webhook 触发 Dify 工作流
   */
  async triggerWebhook(
    webhookPath: string,
    data: any
  ): Promise<any> {
    const url = `${this.config.baseUrl}/webhook${webhookPath.startsWith('/') ? webhookPath : '/' + webhookPath}`;
    // SECURITY FIX: SSRF 验证 - 确保 webhook URL 不指向内网
    this.validateWebhookUrl(url);

    return new Promise((resolve, reject) => {
      const urlObj = new URL(url);
      const options: http.RequestOptions = {
        hostname: urlObj.hostname,
        port: urlObj.port || 80,
        path: urlObj.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: this.config.timeout,
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          try {
            resolve(data ? JSON.parse(data) : { received: true });
          } catch {
            resolve(data);
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Webhook timeout'));
      });

      req.write(JSON.stringify(data));
      req.end();
    });
  }

  // ============================================
  // 工具方法
  // ============================================

  /**
   * 健康检查
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.request('/v1/info', 'GET');
      return true;
    } catch {
      return false;
    }
  }

  /**
   * 获取客户端配置
   */
  getConfig(): DifyConfig {
    return { ...this.config };
  }
}

// ============================================
// 单例导出
// ============================================

export const difyClient = new DifyClient();
