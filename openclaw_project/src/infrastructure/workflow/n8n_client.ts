import * as http from 'http';

/**
 * N8N Headless API Client for OpenClaw Architecture 2.0
 * Purpose: Provides Agent-Native control over n8n workflows (deterministic execution layer).
 * Aligns with "DeerFlow + n8n Double-Wheel" architecture.
 */
export class N8NClient {
  private host: string;
  private port: number;
  private apiKey: string;
  private webhookBase: string;

  constructor(host: string, port: number, apiKey: string | undefined, webhookUrl: string) {
    // SECURITY FIX: apiKey 必须作为参数传入，不再有默认值
    // 防止硬编码 token 泄露风险
    // 如果未提供，尝试从环境变量获取
    const effectiveApiKey = apiKey || process.env.N8N_API_KEY;
    if (!effectiveApiKey || typeof effectiveApiKey !== 'string') {
      // 降级：允许无 API Key 构造，但客户端将被标记为未配置
      // 这允许测试环境和其他可选场景正常运行
      console.warn('[N8NClient] N8N API key not provided. Client will run in disabled mode.');
      this.host = host;
      this.port = port;
      this.apiKey = '';
      this.webhookBase = webhookUrl;
      return;
    }
    this.host = host;
    this.port = port;
    this.apiKey = effectiveApiKey;
    this.webhookBase = webhookUrl;
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
        hostname.startsWith('169.254.') ||  // AWS metadata
        hostname.endsWith('.internal') ||
        hostname.endsWith('.local') ||
        hostname === '0.0.0.0' ||
        /^[fF][cCdD][0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){0,6}$/.test(hostname) || // IPv6 link-local
        hostname.startsWith('fe80:') ||
        hostname === '::' ||
        /^\[.*\]$/.test(hostname) // IPv6 with brackets
      );

      if (isPrivate) {
        throw new Error(`SSRF protection: webhook URL cannot point to private/internal network: ${hostname}`);
      }
    } catch (e: any) {
      if (e.message.includes('SSRF protection')) {
        throw e;
      }
      // URL 解析失败也被拒绝
      throw new Error(`Invalid webhook URL: ${url}`);
    }
  }

  private async request(path: string, method: string = 'GET', data?: any): Promise<any> {
    return new Promise((resolve, reject) => {
      const options: http.RequestOptions = {
        hostname: this.host,
        port: this.port,
        path: `/api/v1${path}`,
        method,
        headers: {
          'X-N8N-API-KEY': this.apiKey,
          'Content-Type': 'application/json'
        }
      };

      const req = http.request(options, (res) => {
        let body = '';
        res.on('data', (chunk) => body += chunk);
        res.on('end', () => {
          try {
            resolve(body ? JSON.parse(body) : null);
          } catch {
            resolve(body);
          }
        });
      });

      req.on('error', (error) => {
        console.error(`[N8NClient] Request failed: ${error.message}`);
        reject(error);
      });

      if (data) {
        req.write(JSON.stringify(data));
      }
      req.end();
    });
  }

  // List all workflows in the system
  async listWorkflows() {
    try {
      return await this.request('/workflows');
    } catch (error: any) {
      console.error(`[N8NClient] Failed to list workflows: ${error.message}`);
      throw error;
    }
  }

  // Get a specific workflow by ID
  async getWorkflow(id: string) {
    try {
      return await this.request(`/workflows/${id}`);
    } catch (error: any) {
      console.error(`[N8NClient] Failed to get workflow ${id}: ${error.message}`);
      throw error;
    }
  }

  // Create a new workflow (e.g. for Agent-generated automation)
  async createWorkflow(workflow: any) {
    try {
      return await this.request('/workflows', 'POST', workflow);
    } catch (error: any) {
      console.error(`[N8NClient] Failed to create workflow: ${error.message}`);
      throw error;
    }
  }

  // Update an existing workflow
  async updateWorkflow(id: string, updates: any) {
    try {
      return await this.request(`/workflows/${id}`, 'PUT', updates);
    } catch (error: any) {
      console.error(`[N8NClient] Failed to update workflow ${id}: ${error.message}`);
      throw error;
    }
  }

  // Activate a workflow (must be active to receive webhooks)
  async activateWorkflow(id: string) {
    return this.updateWorkflow(id, { active: true });
  }

  // Deactivate a workflow
  async deactivateWorkflow(id: string) {
    return this.updateWorkflow(id, { active: false });
  }

  // Execute a workflow via its Webhook URL
  async executeWebhook(path: string, method: 'GET' | 'POST' = 'POST', data: any = {}) {
    const url = `${this.webhookBase}${path.startsWith('/') ? path.substring(1) : path}`;
    // SECURITY FIX: SSRF 验证 - 确保 webhook URL 不指向内网
    this.validateWebhookUrl(url);
    try {
      return new Promise((resolve, reject) => {
        const urlObj = new URL(url);
        const options: http.RequestOptions = {
          hostname: urlObj.hostname,
          port: urlObj.port || 80,
          path: urlObj.pathname,
          method,
          headers: {
            'Content-Type': 'application/json'
          }
        };

        const req = http.request(options, (res) => {
          let body = '';
          res.on('data', (chunk) => body += chunk);
          res.on('end', () => {
            try {
              resolve(body ? JSON.parse(body) : null);
            } catch {
              resolve(body);
            }
          });
        });

        req.on('error', (error) => {
          console.error(`[N8NClient] Webhook trigger failed (${url}): ${error.message}`);
          reject(error);
        });

        if (data && method === 'POST') {
          req.write(JSON.stringify(data));
        }
        req.end();
      });
    } catch (error: any) {
      console.error(`[N8NClient] Webhook trigger failed (${url}): ${error.message}`);
      throw error;
    }
  }
}