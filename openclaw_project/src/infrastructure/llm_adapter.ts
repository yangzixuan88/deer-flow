/**
 * @file llm_adapter.ts
 * @description LLM Adapter for GEPA Reflection Analysis
 * Provides real LLM inference for the 6-step evolution process.
 * Uses Anthropic Claude API for reflection and candidate generation.
 */

import * as http from 'http';

// ============================================
// LLM Provider Types
// ============================================

export enum LLMProvider {
  ANTHROPIC = 'anthropic',
  OPENAI = 'openai',
  LOCAL = 'local',
}

export interface LLMConfig {
  provider: LLMProvider;
  apiKey?: string;
  baseUrl?: string;
  model?: string;
  maxTokens?: number;
  temperature?: number;
  embeddingModel?: string;
}

export interface LLMResponse {
  content: string;
  usage: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
  };
  model: string;
  stopReason?: string;
}

export interface ReflectionAnalysis {
  failureReasons: string[];
  improvementSuggestions: string[];
  optimizationHints: string[];
  confidence: number;
}

export interface EmbeddingResult {
  embedding: number[];
  model: string;
  usage: { tokens: number };
}

// ============================================
// Default Configuration
// ============================================

const DEFAULT_CONFIG: LLMConfig = {
  provider: LLMProvider.ANTHROPIC,
  baseUrl: 'https://api.anthropic.com/v1',
  model: 'claude-sonnet-4-20250514',
  maxTokens: 1024,
  temperature: 0.7,
};

// ============================================
// LLM Adapter
// ============================================

export class LLMAdapter {
  private config: LLMConfig;
  private apiKey: string;

  constructor(config: Partial<LLMConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.apiKey = this.config.apiKey || process.env.ANTHROPIC_API_KEY || '';
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<LLMConfig>): void {
    this.config = { ...this.config, ...config };
    if (config.apiKey) {
      this.apiKey = config.apiKey;
    }
  }

  /**
   * Check if API key is configured
   */
  isConfigured(): boolean {
    return !!this.apiKey;
  }

  /**
   * Call LLM with a prompt and return the response
   */
  async complete(prompt: string, system?: string): Promise<LLMResponse> {
    if (!this.isConfigured()) {
      console.warn('[LLM] API key not configured, using mock response');
      return this.mockResponse(prompt);
    }

    switch (this.config.provider) {
      case LLMProvider.ANTHROPIC:
        return this.callAnthropic(prompt, system);
      case LLMProvider.OPENAI:
        return this.callOpenAI(prompt, system);
      default:
        return this.mockResponse(prompt);
    }
  }

  /**
   * Analyze execution trace and provide reflection insights
   * This is the core method used by GEPA's reflectAndGenerate
   */
  async analyzeReflection(
    originalContent: string,
    executionTraces: Array<{
      quality_score: number;
      failure_reason?: string;
      output?: string;
    }>
  ): Promise<ReflectionAnalysis> {
    const prompt = this.buildReflectionPrompt(originalContent, executionTraces);

    const response = await this.complete(prompt, `You are an expert prompt engineer analyzing LLM execution traces.
Your task is to identify failure patterns and suggest concrete improvements.

Respond in JSON format:
{
  "failureReasons": ["reason1", "reason2"],
  "improvementSuggestions": ["suggestion1", "suggestion2"],
  "optimizationHints": ["hint1", "hint2"],
  "confidence": 0.0-1.0
}`);

    try {
      // Try to extract JSON from response
      const jsonMatch = response.content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        return {
          failureReasons: parsed.failureReasons || [],
          improvementSuggestions: parsed.improvementSuggestions || [],
          optimizationHints: parsed.optimizationHints || [],
          confidence: parsed.confidence || 0.5,
        };
      }
    } catch {
      console.warn('[LLM] Failed to parse reflection analysis JSON');
    }

    // Fallback
    return {
      failureReasons: ['Failed to parse LLM response'],
      improvementSuggestions: ['Review the original prompt structure'],
      optimizationHints: ['Consider adding more specific instructions'],
      confidence: 0.3,
    };
  }

  /**
   * Generate candidate variants based on reflection analysis
   */
  async generateCandidates(
    originalContent: string,
    analysis: ReflectionAnalysis,
    count: number = 4
  ): Promise<string[]> {
    if (!this.isConfigured()) {
      return this.mockCandidates(originalContent, count);
    }

    const prompt = this.buildCandidatePrompt(originalContent, analysis, count);
    const response = await this.complete(prompt);

    // Parse candidates from response (simple line-based parsing)
    const candidates = response.content
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 10 && !line.startsWith('#'));

    return candidates.slice(0, count);
  }

  /**
   * Generate embedding for text using OpenAI-compatible embedding API
   * Falls back to a simple hash-based embedding if not configured
   */
  async embed(text: string): Promise<EmbeddingResult> {
    if (!this.isConfigured()) {
      return this.mockEmbedding(text);
    }

    const embeddingModel = this.config.embeddingModel || 'text-embedding-3-small';

    try {
      const response = await this.callEmbeddingAPI(text, embeddingModel);
      return response;
    } catch (error) {
      console.warn(`[LLM] Embedding generation failed, using mock: ${error}`);
      return this.mockEmbedding(text);
    }
  }

  /**
   * Compress text using LLM summarization
   */
  async compress(text: string, maxLength: number = 2000): Promise<string> {
    // For short text, no compression needed
    if (text.length <= maxLength) {
      return text;
    }

    if (!this.isConfigured()) {
      // Fallback: simple truncation
      return text.substring(0, maxLength) + '\n[...content truncated...]';
    }

    try {
      const prompt = `Compress the following text into approximately ${maxLength} characters while preserving the key information:

${text}

Provide a concise summary that captures the main points:`;

      const response = await this.complete(prompt);
      return response.content;
    } catch (error) {
      console.warn(`[LLM] Compression failed, using truncation: ${error}`);
      return text.substring(0, maxLength) + '\n[...content truncated...]';
    }
  }

  // ========================================
  // Private Methods
  // ========================================

  /**
   * Build reflection analysis prompt
   */
  private buildReflectionPrompt(
    originalContent: string,
    traces: Array<{ quality_score: number; failure_reason?: string; output?: string }>
  ): string {
    const tracesText = traces
      .map((t, i) => `[Trace ${i + 1}]
Quality Score: ${t.quality_score.toFixed(2)}
Failure Reason: ${t.failure_reason || 'N/A'}
Output: ${t.output?.substring(0, 200) || 'N/A'}...`)
      .join('\n\n');

    return `Analyze the following prompt and its execution traces to identify failure patterns:

=== ORIGINAL PROMPT ===
${originalContent}
========================

=== EXECUTION TRACES ===
${tracesText}
========================

Provide a JSON analysis with failureReasons, improvementSuggestions, and optimizationHints.`;
  }

  /**
   * Build candidate generation prompt
   */
  private buildCandidatePrompt(
    originalContent: string,
    analysis: ReflectionAnalysis,
    count: number
  ): string {
    return `Generate ${count} improved variants of the following prompt based on this analysis:

=== ORIGINAL PROMPT ===
${originalContent}
========================

=== FAILURE REASONS ===
${analysis.failureReasons.map(r => `- ${r}`).join('\n')}

=== IMPROVEMENT SUGGESTIONS ===
${analysis.improvementSuggestions.map(s => `- ${s}`).join('\n')}

Generate ${count} distinct improved versions, each on a separate line.
Keep each variant concise (under 500 characters).
Number each variant (1. 2. 3. etc).`;
  }

  /**
   * Call Anthropic Claude API
   */
  private async callAnthropic(prompt: string, system?: string): Promise<LLMResponse> {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify({
        model: this.config.model,
        max_tokens: this.config.maxTokens,
        temperature: this.config.temperature,
        messages: [
          ...(system ? [{ role: 'user', content: system }] : []),
          { role: 'user', content: prompt },
        ],
      });

      const urlObj = new URL(`${this.config.baseUrl}/messages`);
      const options: http.RequestOptions = {
        hostname: urlObj.hostname,
        port: urlObj.port || 443,
        path: urlObj.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': this.apiKey,
          'anthropic-version': '2023-06-01',
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: 30000,
      };

      const req = http.request(options, (res) => {
        let responseBody = '';
        res.on('data', chunk => responseBody += chunk);
        res.on('end', () => {
          try {
            const data = JSON.parse(responseBody);
            if (data.error) {
              reject(new Error(data.error.message || 'Anthropic API error'));
              return;
            }
            resolve({
              content: data.content?.[0]?.text || '',
              usage: {
                inputTokens: data.usage?.input_tokens || 0,
                outputTokens: data.usage?.output_tokens || 0,
                totalTokens: (data.usage?.input_tokens || 0) + (data.usage?.output_tokens || 0),
              },
              model: data.model || this.config.model || 'unknown',
              stopReason: data.stop_reason,
            });
          } catch {
            reject(new Error(`Failed to parse Anthropic response: ${responseBody}`));
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => reject(new Error('Anthropic API timeout')));
      req.write(body);
      req.end();
    });
  }

  /**
   * Call OpenAI API (compatible structure)
   */
  private async callOpenAI(prompt: string, system?: string): Promise<LLMResponse> {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify({
        model: this.config.model || 'gpt-4',
        max_tokens: this.config.maxTokens,
        temperature: this.config.temperature,
        messages: [
          ...(system ? [{ role: 'system', content: system }] : []),
          { role: 'user', content: prompt },
        ],
      });

      const urlObj = new URL(`${this.config.baseUrl || 'https://api.openai.com/v1'}/chat/completions`);
      const options: http.RequestOptions = {
        hostname: urlObj.hostname,
        port: urlObj.port || 443,
        path: urlObj.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: 30000,
      };

      const req = http.request(options, (res) => {
        let responseBody = '';
        res.on('data', chunk => responseBody += chunk);
        res.on('end', () => {
          try {
            const data = JSON.parse(responseBody);
            if (data.error) {
              reject(new Error(data.error.message || 'OpenAI API error'));
              return;
            }
            resolve({
              content: data.choices?.[0]?.message?.content || '',
              usage: {
                inputTokens: data.usage?.prompt_tokens || 0,
                outputTokens: data.usage?.completion_tokens || 0,
                totalTokens: data.usage?.total_tokens || 0,
              },
              model: data.model || this.config.model || 'unknown',
              stopReason: data.choices?.[0]?.finish_reason,
            });
          } catch {
            reject(new Error(`Failed to parse OpenAI response: ${responseBody}`));
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => reject(new Error('OpenAI API timeout')));
      req.write(body);
      req.end();
    });
  }

  /**
   * Mock response when API key is not configured
   */
  private mockResponse(prompt: string): LLMResponse {
    console.log('[LLM] Using mock LLM response');
    return {
      content: `Mock reflection: Consider adding more explicit instructions to the prompt.`,
      usage: { inputTokens: 100, outputTokens: 50, totalTokens: 150 },
      model: 'mock',
      stopReason: 'end_turn',
    };
  }

  /**
   * Mock candidates generation
   */
  private mockCandidates(original: string, count: number): string[] {
    const prefixes = [
      '【更简洁】',
      '【更详细】',
      '【结构化】',
      '【举例说明】',
    ];
    return Array.from({ length: count }, (_, i) => `${prefixes[i] || ''}${original}`);
  }

  /**
   * Call OpenAI-compatible embedding API
   */
  private async callEmbeddingAPI(text: string, model: string): Promise<EmbeddingResult> {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify({
        model,
        input: text,
      });

      const baseUrl = this.config.baseUrl?.replace('/v1', '') || 'https://api.openai.com';
      const urlObj = new URL(`${baseUrl}/v1/embeddings`);
      const options: http.RequestOptions = {
        hostname: urlObj.hostname,
        port: urlObj.port || 443,
        path: urlObj.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: 30000,
      };

      const req = http.request(options, (res) => {
        let responseBody = '';
        res.on('data', chunk => responseBody += chunk);
        res.on('end', () => {
          try {
            const data = JSON.parse(responseBody);
            if (data.error) {
              reject(new Error(data.error.message || 'Embedding API error'));
              return;
            }
            resolve({
              embedding: data.data?.[0]?.embedding || [],
              model: data.model || model,
              usage: { tokens: data.usage?.total_tokens || 0 },
            });
          } catch {
            reject(new Error(`Failed to parse embedding response: ${responseBody}`));
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => reject(new Error('Embedding API timeout')));
      req.write(body);
      req.end();
    });
  }

  /**
   * Mock embedding (fallback when no API key)
   * Uses a simple hash-based approach to generate deterministic embeddings
   */
  private mockEmbedding(text: string): EmbeddingResult {
    const dimensions = 384; // Standard embedding dimension
    const embedding: number[] = [];

    // Simple deterministic hash-based embedding
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      const char = text.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }

    // Seed random with hash for reproducibility
    const seededRandom = (seed: number) => {
      const x = Math.sin(seed) * 10000;
      return x - Math.floor(x);
    };

    for (let i = 0; i < dimensions; i++) {
      const combined = hash + i * 31;
      embedding.push(seededRandom(combined) * 2 - 1);
    }

    // L2 normalize
    const norm = Math.sqrt(embedding.reduce((sum, v) => sum + v * v, 0));
    const normalized = embedding.map(v => v / norm);

    return {
      embedding: normalized,
      model: 'mock-hash',
      usage: { tokens: Math.ceil(text.length / 4) },
    };
  }
}

// ============================================
// Singleton Export
// ============================================

export const llmAdapter = new LLMAdapter();
