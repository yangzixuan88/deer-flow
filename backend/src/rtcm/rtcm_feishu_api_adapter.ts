/**
 * @file rtcm_feishu_api_adapter.ts
 * @description RTCM 真实飞书 API 适配器 - Epsilon 稳定发布态核心
 * 负责与飞书开放平台 API 的真实接线，包括消息发送、卡片推送、线程管理等
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import * as crypto from 'crypto';

// ============================================================================
// Types
// ============================================================================

export enum FeishuApiEndpoint {
  SEND_MESSAGE = '/open-apis/im/v1/messages',
  UPLOAD_IMAGE = '/open-apis/im/v1/images',
  GET_MESSAGE = '/open-apis/im/v1/messages/{message_id}',
  CREATE_THREAD = '/open-apis/im/v1/chats',
  GET_CHAT = '/open-apis/im/v1/chats/{chat_id}',
  UPDATE_MESSAGE = '/open-apis/im/v1/messages/{message_id}',
  RECALL_MESSAGE = '/open-apis/im/v1/messages/{message_id}/recall',
}

export interface FeishuApiConfig {
  appId: string;
  appSecret: string;
  tenantKey: string;
  baseUrl: string;
}

export interface FeishuApiResponse<T = any> {
  code: number;
  msg: string;
  data?: T;
}

export interface FeishuTokenResponse {
  code: number;
  msg: string;
  data?: {
    access_token: string;
    token_type: string;
    expires_in: number;
    refresh_token?: string;
  };
}

export interface FeishuSendMessageRequest {
  receive_id: string;
  msg_type: 'text' | 'post' | 'interactive' | 'image' | 'media';
  content: string;
  msg_id?: string;
}

export interface FeishuSendMessageResponse {
  message_id: string;
  create_time: string;
  update_time: string;
}

// ============================================================================
// Feishu API Adapter
// ============================================================================

export class FeishuApiAdapter {
  private config: FeishuApiConfig | null = null;
  private tokenCache: { token: string; expiresAt: number } | null = null;
  private tokenFile: string;

  private static readonly DEFAULT_BASE_URL = 'https://open.feishu.cn';
  private static readonly TOKEN_REFRESH_THRESHOLD_MS = 300000; // 提前5分钟刷新

  constructor() {
    this.tokenFile = runtimePath('rtcm', 'feishu', 'token_cache.json');
    this.ensureDir(path.dirname(this.tokenFile));
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Configuration
  // ===========================================================================

  /**
   * 配置飞书 API
   */
  configure(config: Partial<FeishuApiConfig>): void {
    const appId = config.appId || process.env.FEISHU_APP_ID;
    const appSecret = config.appSecret || process.env.FEISHU_APP_SECRET;
    const tenantKey = config.tenantKey || process.env.FEISHU_TENANT_KEY || 'tenant';
    const baseUrl = config.baseUrl || process.env.FEISHU_BASE_URL || FeishuApiAdapter.DEFAULT_BASE_URL;

    if (!appId || !appSecret) {
      throw new Error('FEISHU_APP_ID and FEISHU_APP_SECRET are required');
    }

    this.config = { appId, appSecret, tenantKey, baseUrl };
  }

  /**
   * 检查是否已配置
   */
  isConfigured(): boolean {
    return this.config !== null && this.tokenCache !== null;
  }

  /**
   * 获取配置（不包含敏感信息）
   */
  getConfig(): FeishuApiConfig | null {
    return this.config;
  }

  // ===========================================================================
  // Authentication
  // ===========================================================================

  /**
   * 获取访问令牌
   */
  async getAccessToken(): Promise<string> {
    if (!this.config) {
      throw new Error('Feishu API not configured');
    }

    // 检查缓存的 token 是否有效
    if (this.tokenCache && this.tokenCache.expiresAt > Date.now() + FeishuApiAdapter.TOKEN_REFRESH_THRESHOLD_MS) {
      return this.tokenCache.token;
    }

    // 刷新 token
    const url = `${this.config.baseUrl}/open-apis/auth/v3/tenant_access_token/internal`;
    const body = {
      app_id: this.config.appId,
      app_secret: this.config.appSecret,
    };

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const result = await response.json() as FeishuTokenResponse;

      // 飞书返回格式: { code: 0, msg: "ok", tenant_access_token: "...", expire: 7180 }
      // 注意: token 在顶层，不在 data 里面
      const token = (result as any).tenant_access_token || result.data?.access_token;
      if (result.code !== 0 || !token) {
        throw new Error(`Failed to get access token: ${result.msg}`);
      }

      // 缓存 token
      this.tokenCache = {
        token: token,
        expiresAt: Date.now() + ((result as any).expire || 7200) * 1000,
      };

      // 持久化缓存
      this.saveTokenCache();

      return token;
    } catch (error) {
      throw new Error(`Failed to get access token: ${error}`);
    }
  }

  private saveTokenCache(): void {
    if (this.tokenCache) {
      fs.writeFileSync(this.tokenFile, JSON.stringify(this.tokenCache), 'utf-8');
    }
  }

  private loadTokenCache(): void {
    if (fs.existsSync(this.tokenFile)) {
      try {
        const cache = JSON.parse(fs.readFileSync(this.tokenFile, 'utf-8'));
        if (cache.token && cache.expiresAt > Date.now()) {
          this.tokenCache = cache;
        }
      } catch {
        // 忽略
      }
    }
  }

  // ===========================================================================
  // API Requests
  // ===========================================================================

  /**
   * 发送 API 请求
   */
  private async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    endpoint: string,
    body?: object
  ): Promise<FeishuApiResponse<T>> {
    const token = await this.getAccessToken();
    const url = `${this.config!.baseUrl}${endpoint}`;

    const options: RequestInit = {
      method,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, options);
      const result = await response.json() as FeishuApiResponse<T>;
      return result;
    } catch (error) {
      return {
        code: -1,
        msg: `Network error: ${error}`,
      };
    }
  }

  // ===========================================================================
  // Message APIs
  // ===========================================================================

  /**
   * 发送消息
   */
  async sendMessage(request: FeishuSendMessageRequest): Promise<FeishuSendMessageResponse> {
    // 根据 receive_id 格式判断类型：oc_xxx = chat_id, @open.xxx = open_id, u_xxx = user_id, 否则 union_id
    let receiveIdType = 'union_id';
    if (request.receive_id.startsWith('oc_')) {
      receiveIdType = 'chat_id';
    } else if (request.receive_id.includes('@')) {
      receiveIdType = 'open_id';
    } else if (request.receive_id.startsWith('u_')) {
      receiveIdType = 'user_id';
    }

    const result = await this.request<{ message_id: string; create_time: string; update_time: string }>(
      'POST',
      FeishuApiEndpoint.SEND_MESSAGE + `?receive_id_type=${receiveIdType}`,
      {
        receive_id: request.receive_id,
        msg_type: request.msg_type,
        content: request.content,
      }
    );

    if (result.code !== 0) {
      throw new Error(`Failed to send message: ${result.msg}`);
    }

    return {
      message_id: result.data!.message_id,
      create_time: result.data!.create_time,
      update_time: result.data!.update_time,
    };
  }

  /**
   * 发送文本消息
   */
  async sendTextMessage(receiveId: string, text: string): Promise<FeishuSendMessageResponse> {
    return this.sendMessage({
      receive_id: receiveId,
      msg_type: 'text',
      content: JSON.stringify({ text }),
    });
  }

  /**
   * 发送富文本消息 (post)
   */
  async sendPostMessage(receiveId: string, content: object): Promise<FeishuSendMessageResponse> {
    return this.sendMessage({
      receive_id: receiveId,
      msg_type: 'post',
      content: JSON.stringify(content),
    });
  }

  /**
   * 发送卡片消息
   */
  async sendCardMessage(receiveId: string, cardPayload: object): Promise<FeishuSendMessageResponse> {
    return this.sendMessage({
      receive_id: receiveId,
      msg_type: 'interactive',
      content: JSON.stringify(cardPayload),
    });
  }

  /**
   * 获取消息详情
   */
  async getMessage(messageId: string): Promise<any> {
    const endpoint = FeishuApiEndpoint.GET_MESSAGE.replace('{message_id}', messageId);
    const result = await this.request<any>('GET', endpoint);
    return result.data;
  }

  /**
   * 更新消息
   */
  async updateMessage(messageId: string, content: object): Promise<void> {
    const endpoint = FeishuApiEndpoint.UPDATE_MESSAGE.replace('{message_id}', messageId);
    await this.request('PATCH', endpoint, { content: JSON.stringify(content) });
  }

  /**
   * 撤回消息
   */
  async recallMessage(messageId: string): Promise<void> {
    const endpoint = FeishuApiEndpoint.RECALL_MESSAGE.replace('{message_id}', messageId);
    await this.request('DELETE', endpoint);
  }

  // ===========================================================================
  // Image/Media APIs
  // ===========================================================================

  /**
   * 上传图片
   */
  async uploadImage(imageBuffer: Buffer, imageName: string = 'image.png'): Promise<string> {
    const token = await this.getAccessToken();
    const url = `${this.config!.baseUrl}${FeishuApiEndpoint.UPLOAD_IMAGE}`;

    const formData = new FormData();
    const blob = new Blob([imageBuffer]);
    formData.append('image', blob, imageName);

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    const result = await response.json() as any;
    if (result.code !== 0) {
      throw new Error(`Failed to upload image: ${result.msg}`);
    }

    return result.data.image_key;
  }

  // ===========================================================================
  // Chat/Thread APIs
  // ===========================================================================

  /**
   * 创建群聊/线程
   */
  async createChat(params: {
    name: string;
    description?: string;
    user_ids?: string[];
    bot_ids?: string[];
    chat_mode?: 'group' | 'p2p';
    chat_type?: 'private' | 'public';
  }): Promise<{ chat_id: string }> {
    const result = await this.request<{ chat_id: string }>(
      'POST',
      FeishuApiEndpoint.CREATE_THREAD,
      {
        name: params.name,
        description: params.description || '',
        user_ids: params.user_ids || [],
        bot_ids: params.bot_ids || [],
        chat_mode: params.chat_mode || 'group',
        chat_type: params.chat_type || 'private',
      }
    );

    if (result.code !== 0) {
      throw new Error(`Failed to create chat: ${result.msg}`);
    }

    return { chat_id: result.data!.chat_id };
  }

  /**
   * 获取群聊信息
   */
  async getChat(chatId: string): Promise<any> {
    const endpoint = FeishuApiEndpoint.GET_CHAT.replace('{chat_id}', chatId);
    const result = await this.request<any>('GET', endpoint);
    return result.data;
  }

  // ===========================================================================
  // Utility
  // ===========================================================================

  /**
   * 健康检查
   */
  async healthCheck(): Promise<{ healthy: boolean; latencyMs: number; error?: string }> {
    const start = Date.now();

    try {
      await this.getAccessToken();
      const latencyMs = Date.now() - start;
      return { healthy: true, latencyMs };
    } catch (error) {
      return { healthy: false, latencyMs: Date.now() - start, error: String(error) };
    }
  }
}

// ============================================================================
// Feishu Webhook Adapter (for simple notifications)
// ============================================================================

export class FeishuWebhookAdapter {
  private webhookUrl: string | null = null;

  /**
   * 配置 Webhook URL
   */
  configure(webhookUrl: string): void {
    this.webhookUrl = webhookUrl;
  }

  /**
   * 发送简单 Webhook 消息（不依赖 appId/appSecret）
   */
  async sendWebhookMessage(content: object): Promise<boolean> {
    if (!this.webhookUrl) {
      throw new Error('Feishu webhook URL not configured');
    }

    try {
      const response = await fetch(this.webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(content),
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  }
}

// ============================================================================
// Singletons
// ============================================================================

export const feishuApiAdapter = new FeishuApiAdapter();
export const feishuWebhookAdapter = new FeishuWebhookAdapter();
