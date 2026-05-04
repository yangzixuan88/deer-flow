/**
 * Dify API Client for OpenClaw Architecture 2.0
 * Purpose: Provides integration with Dify AI platform (cognitive agent layer)
 * Aligns with "DeerFlow + Dify Double-Wheel" architecture
 */

export interface DifyClientConfig {
  baseUrl?: string;
  apiKey?: string;
  timeout?: number;
}

export interface DifyCompletionRequest {
  query: string;
  response_mode?: 'blocking' | 'streaming';
  user?: string;
  conversation_id?: string;
  inputs?: Record<string, any>;
}

export interface DifyCompletionResponse {
  event: string;
  task_id?: string;
  conversation_id?: string;
  message_id?: string;
  answer?: string;
  output_text?: string;
  outputs?: Record<string, any>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  created_at?: number;
  records?: any[];
  status?: 'pending' | 'running' | 'completed' | 'failed';
  error?: string;
}

export interface DifyChatOptions {
  conversation_id?: string;
  inputs?: Record<string, any>;
}

export interface DifyRetrieveOptions {
  top_k?: number;
  score_threshold?: number;
  rerank_model?: {
    provider: string;
    model_name: string;
  };
}

/**
 * Dify API Client
 *
 * Provides integration with Dify chatbots and completion APIs
 */
export class DifyClient {
  private baseUrl: string;
  private apiKey: string;
  private timeout: number;

  constructor(config: DifyClientConfig) {
    this.baseUrl = config?.baseUrl || 'http://localhost/v1';
    this.apiKey = config?.apiKey || '';
    this.timeout = config?.timeout || 60000;
  }

  /**
   * Check if Dify client is configured
   */
  isConfigured(): boolean {
    return !!this.apiKey && !!this.baseUrl;
  }

  /**
   * Send completion request (blocking mode)
   */
  async completion(
    prompt: string,
    user: string,
    options?: { model?: string; temperature?: number }
  ): Promise<DifyCompletionResponse> {
    if (!this.isConfigured()) {
      throw new Error('Dify client not configured. Please provide API key and base URL.');
    }

    const response = await fetch(`${this.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: prompt,
        response_mode: 'blocking',
        user: user,
      }),
    });

    if (!response.ok) {
      throw new Error(`Dify API error: ${response.status} ${response.statusText}`);
    }

    return await response.json() as DifyCompletionResponse;
  }

  /**
   * Send completion request (blocking mode) - structured request form
   */
  async completionRequest(request: DifyCompletionRequest): Promise<DifyCompletionResponse> {
    if (!this.isConfigured()) {
      throw new Error('Dify client not configured. Please provide API key and base URL.');
    }

    const response = await fetch(`${this.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: request.query,
        response_mode: request.response_mode || 'blocking',
        user: request.user || 'anonymous',
        conversation_id: request.conversation_id || '',
        inputs: request.inputs || {},
      }),
    });

    if (!response.ok) {
      throw new Error(`Dify API error: ${response.status} ${response.statusText}`);
    }

    return await response.json() as DifyCompletionResponse;
  }

  /**
   * Get conversation messages
   */
  async getMessages(conversationId: string): Promise<any[]> {
    if (!this.isConfigured()) {
      throw new Error('Dify client not configured');
    }

    const response = await fetch(
      `${this.baseUrl}/conversations/${conversationId}/messages`,
      {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Dify API error: ${response.status}`);
    }

    const data = await response.json() as { data?: any[] };
    return data.data || [];
  }

  /**
   * Chat with Dify app
   */
  async chat(
    appId: string,
    query: string,
    user: string,
    options?: DifyChatOptions
  ): Promise<DifyCompletionResponse> {
    if (!this.isConfigured()) {
      throw new Error('Dify client not configured');
    }

    const response = await fetch(`${this.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        user,
        conversation_id: options?.conversation_id,
        inputs: options?.inputs,
      }),
    });

    if (!response.ok) {
      throw new Error(`Dify API error: ${response.status}`);
    }

    return await response.json() as DifyCompletionResponse;
  }

  /**
   * Retrieve from Dify knowledge base
   */
  async retrieve(params: {
    dataset_ids: string[];
    query: string;
    top_k?: number;
    score_threshold?: number;
  }): Promise<{ records: any[] }> {
    if (!this.isConfigured()) {
      throw new Error('Dify client not configured');
    }

    const response = await fetch(`${this.baseUrl}/retrieval`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        dataset_ids: params.dataset_ids,
        query: params.query,
        top_k: params.top_k || 5,
        score_threshold: params.score_threshold,
      }),
    });

    if (!response.ok) {
      throw new Error(`Dify API error: ${response.status}`);
    }

    const data = await response.json() as { data?: any[] };
    return { records: data.data || [] };
  }

  /**
   * Run Dify workflow
   */
  async runWorkflow(
    workflowId: string,
    inputs: Record<string, any>,
    user?: string,
    response_mode?: string
  ): Promise<DifyCompletionResponse> {
    if (!this.isConfigured()) {
      throw new Error('Dify client not configured');
    }

    const response = await fetch(`${this.baseUrl}/workflows/run`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        workflow_id: workflowId,
        inputs,
        response_mode: response_mode || 'blocking',
        user: user || 'anonymous',
      }),
    });

    if (!response.ok) {
      throw new Error(`Dify API error: ${response.status}`);
    }

    return await response.json() as DifyCompletionResponse;
  }

  /**
   * Get workflow run detail
   */
  async getRunDetail(runId: string): Promise<any> {
    if (!this.isConfigured()) {
      throw new Error('Dify client not configured');
    }

    const response = await fetch(`${this.baseUrl}/workflows/runs/${runId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Dify API error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Trigger Dify webhook
   */
  async triggerWebhook(webhookUrl: string, data: any): Promise<any> {
    if (!this.isConfigured()) {
      throw new Error('Dify client not configured');
    }

    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Dify webhook error: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<boolean> {
    if (!this.isConfigured()) {
      return false;
    }

    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
        },
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

export default DifyClient;
