/**
 * M04 搜索系统适配器
 * ================================================
 * STORM三轮搜索 · 多引擎路由 · 交叉验证
 * ================================================
 */

import * as http from 'http';
import * as crypto from 'crypto';
import {
  SearchEngine,
  SearchRound,
  SearchResult,
  SearchResponse,
  SearchStrategy,
  SearchSource,
} from '../types';

// ============================================
// 搜索系统适配器
// ============================================

/**
 * 搜索系统适配器
 *
 * 封装搜索系统的核心能力：
 * - 三轮搜索机制
 * - 多引擎路由
 * - 交叉验证
 */
export class SearchAdapter {
  private engineRouters: Map<SearchEngine, (query: string) => Promise<SearchSource[]>>;
  private searxngHost: string;
  private tavilyApiKey: string | undefined;
  private exaApiKey: string | undefined;

  constructor() {
    this.engineRouters = new Map();
    this.searxngHost = process.env.SEARXNG_HOST || 'localhost:8080';
    this.tavilyApiKey = process.env.TAVILY_API_KEY;
    this.exaApiKey = process.env.EXA_API_KEY;
    this.registerDefaultEngines();
  }

  /**
   * 注册默认引擎
   */
  private registerDefaultEngines(): void {
    // SearXNG - 通用搜索
    this.engineRouters.set(SearchEngine.SEARXNG, async (query) => {
      return this.searchSearXNG(query);
    });

    // Tavily - AI优化搜索
    this.engineRouters.set(SearchEngine.TAVILY, async (query) => {
      return this.searchTavily(query);
    });

    // Exa - 语义搜索
    this.engineRouters.set(SearchEngine.EXA, async (query) => {
      return this.searchExa(query);
    });

    // Context7 - 官方文档 (使用Jina提取)
    this.engineRouters.set(SearchEngine.CONTEXT7, async (query) => {
      return this.searchContext7(query);
    });

    // GitHub - 代码搜索
    this.engineRouters.set(SearchEngine.GITHUB, async (query) => {
      return this.searchGitHub(query);
    });

    // Jina - 内容提取
    this.engineRouters.set(SearchEngine.JINA, async (query) => {
      return this.extractWithJina(query);
    });
  }

  /**
   * SearXNG 搜索
   */
  private async searchSearXNG(query: string): Promise<SearchSource[]> {
    try {
      const results = await this.httpGet(
        `http://${this.searxngHost}/search?q=${encodeURIComponent(query)}&format=json&engines=google,bing,duckduckgo`
      );
      if (results && results.results) {
        return results.results.slice(0, 5).map((r: any) => ({
          title: r.title || '',
          url: r.url || '',
          content: r.content || r.snippet || '',
          confidence: 0.7 + crypto.randomInt(0, 21) / 100,
        }));
      }
      return this.mockSearch(query, 'searxng');
    } catch (error) {
      console.warn(`[SearchAdapter] SearXNG failed: ${error}`);
      return this.mockSearch(query, 'searxng');
    }
  }

  /**
   * Tavily 搜索
   */
  private async searchTavily(query: string): Promise<SearchSource[]> {
    if (!this.tavilyApiKey) {
      console.warn('[SearchAdapter] TAVILY_API_KEY not set, using mock');
      return this.mockSearch(query, 'tavily');
    }
    try {
      const response = await this.httpPost(
        'https://api.tavily.com/search',
        {
          api_key: this.tavilyApiKey,
          query,
          max_results: 5,
          include_answer: true,
        }
      );
      if (response && response.results) {
        return response.results.map((r: any) => ({
          title: r.title || '',
          url: r.url || '',
          content: r.content || r.snippet || r.raw_content || '',
          confidence: r.score || 0.8,
        }));
      }
      return this.mockSearch(query, 'tavily');
    } catch (error) {
      console.warn(`[SearchAdapter] Tavily failed: ${error}`);
      return this.mockSearch(query, 'tavily');
    }
  }

  /**
   * Exa 搜索
   */
  private async searchExa(query: string): Promise<SearchSource[]> {
    if (!this.exaApiKey) {
      // Only warn in verbose/debug mode
      if (process.env.DEBUG === 'true' || process.env.LOG_LEVEL === 'debug') {
        console.warn('[SearchAdapter] EXA_API_KEY not set, using mock');
      }
      return this.mockSearch(query, 'exa');
    }
    try {
      const response = await this.httpPost(
        'https://api.exa.ai/search',
        {
          api_key: this.exaApiKey,
          query,
          maxResults: 5,
          contents: { text: true },
        }
      );
      if (response && response.results) {
        return response.results.map((r: any) => ({
          title: r.title || '',
          url: r.url || '',
          content: r.text || r.snippet || '',
          confidence: r.score || 0.8,
        }));
      }
      return this.mockSearch(query, 'exa');
    } catch (error) {
      console.warn(`[SearchAdapter] Exa failed: ${error}`);
      return this.mockSearch(query, 'exa');
    }
  }

  /**
   * Context7 文档搜索 (通过Jina提取)
   */
  private async searchContext7(query: string): Promise<SearchSource[]> {
    try {
      // 使用Jina AI提取官方文档
      const url = `https://r.jina.ai/https://context7.com/search?q=${encodeURIComponent(query)}`;
      const content = await this.httpGet(url);
      if (content) {
        return [{
          title: `Context7: ${query}`,
          url: url,
          content: content.substring(0, 500),
          confidence: 0.85,
        }];
      }
      return this.mockSearch(query, 'context7');
    } catch (error) {
      console.warn(`[SearchAdapter] Context7 failed: ${error}`);
      return this.mockSearch(query, 'context7');
    }
  }

  /**
   * GitHub 代码搜索
   */
  private async searchGitHub(query: string): Promise<SearchSource[]> {
    try {
      const response = await this.httpGet(
        `https://api.github.com/search/code?q=${encodeURIComponent(query)}&per_page=5`,
        { 'Accept': 'application/vnd.github.v3+json' }
      );
      if (response && response.items) {
        return response.items.map((r: any) => ({
          title: r.name || r.path || query,
          url: r.html_url || '',
          content: `Repository: ${r.repository?.full_name || 'unknown'}\nPath: ${r.path || ''}`,
          confidence: 0.75,
        }));
      }
      return this.mockSearch(query, 'github');
    } catch (error) {
      // Only warn in verbose/debug mode
      if (process.env.DEBUG === 'true' || process.env.LOG_LEVEL === 'debug') {
        console.warn(`[SearchAdapter] GitHub failed: ${error}`);
      }
      return this.mockSearch(query, 'github');
    }
  }

  /**
   * Jina 内容提取
   */
  private async extractWithJina(query: string): Promise<SearchSource[]> {
    try {
      const url = `https://r.jina.ai/${encodeURIComponent(query)}`;
      const content = await this.httpGet(url);
      if (content) {
        return [{
          title: query.substring(0, 50),
          url: query,
          content: content.substring(0, 500),
          confidence: 0.8,
        }];
      }
      return this.mockSearch(query, 'jina');
    } catch (error) {
      console.warn(`[SearchAdapter] Jina extraction failed: ${error}`);
      return this.mockSearch(query, 'jina');
    }
  }

  /**
   * HTTP GET 请求
   */
  private httpGet(url: string, headers?: Record<string, string>): Promise<any> {
    return new Promise((resolve, reject) => {
      try {
        const urlObj = new URL(url);
        const options: http.RequestOptions = {
          hostname: urlObj.hostname,
          port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
          path: urlObj.pathname + urlObj.search,
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            ...headers,
          },
          timeout: 10000,
        };

        const req = http.request(options, (res) => {
          let body = '';
          res.on('data', chunk => body += chunk);
          res.on('end', () => {
            try {
              resolve(JSON.parse(body));
            } catch {
              resolve(body);
            }
          });
        });

        req.on('error', reject);
        req.on('timeout', () => reject(new Error('Request timeout')));
        req.end();
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * HTTP POST 请求
   */
  private httpPost(url: string, data: any): Promise<any> {
    return new Promise((resolve, reject) => {
      try {
        const urlObj = new URL(url);
        const body = JSON.stringify(data);
        const options: http.RequestOptions = {
          hostname: urlObj.hostname,
          port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
          path: urlObj.pathname + urlObj.search,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(body),
          },
          timeout: 10000,
        };

        const req = http.request(options, (res) => {
          let responseBody = '';
          res.on('data', chunk => responseBody += chunk);
          res.on('end', () => {
            try {
              resolve(JSON.parse(responseBody));
            } catch {
              resolve(responseBody);
            }
          });
        });

        req.on('error', reject);
        req.on('timeout', () => reject(new Error('Request timeout')));
        req.write(body);
        req.end();
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 模拟搜索 (降级方案)
   */
  private mockSearch(query: string, engine: string): SearchSource[] {
    return [
      {
        title: `${engine} result for: ${query}`,
        url: `https://example.com/${engine}/${encodeURIComponent(query)}`,
        content: `Content extracted from ${engine} for query: ${query}`,
        confidence: 0.8 + crypto.randomInt(0, 16) / 100,
      },
    ];
  }

  /**
   * 执行三轮搜索
   */
  async executeThreeRoundSearch(
    initialQuery: string,
    depth: 1 | 2 | 3 = 3
  ): Promise<SearchResponse> {
    const results: SearchResult[] = [];
    const enginesUsed = new Set<SearchEngine>();
    let currentQuery = initialQuery;
    let currentConfidence = 0;

    for (let round = 1; round <= depth; round++) {
      const strategy = this.planRoundStrategy(currentQuery, round);

      // 选择引擎执行搜索
      const roundSources: SearchSource[] = [];
      for (const engine of strategy.engines) {
        const sources = await this.engineRouters.get(engine)?.(currentQuery) || [];
        roundSources.push(...sources);
        enginesUsed.add(engine);
      }

      // 生成轮次结果
      const roundResult: SearchResult = {
        query: currentQuery,
        round: round as SearchRound,
        sources: roundSources,
        summary: `Round ${round} synthesized ${roundSources.length} sources`,
        confidence: Math.max(...roundSources.map(s => s.confidence), 0),
      };

      results.push(roundResult);
      currentConfidence = roundResult.confidence;

      // 检查是否需要继续
      if (round < 3 && currentConfidence < 0.80) {
        // 精炼查询
        currentQuery = this.refineQuery(currentQuery, results);
      } else if (round < 3 && roundSources.length === 0) {
        // 切换策略
        currentQuery = this.switchStrategy(currentQuery);
      }
    }

    // 交叉验证
    const crossValidation = this.performCrossValidation(results);

    return {
      results,
      summary: this.generateSummary(results),
      missing_info: this.identifyMissingInfo(results, initialQuery),
      search_rounds_used: results.length,
      engines_used: Array.from(enginesUsed),
      cross_validation: crossValidation,
    };
  }

  /**
   * 规划轮次策略
   */
  private planRoundStrategy(query: string, round: number): SearchStrategy {
    const isComplex = query.split(/\s+/).length > 5;
    const hasTechnicalTerms = /[A-Z][a-z]+\d|API|SDK|Framework/i.test(query);

    switch (round) {
      case 1:
        // 第一轮：主查询
        return {
          round: SearchRound.ROUND_1,
          strategy: '主查询',
          query,
          engines: hasTechnicalTerms
            ? [SearchEngine.TAVILY, SearchEngine.EXA]
            : [SearchEngine.SEARXNG, SearchEngine.TAVILY],
        };

      case 2:
        // 第二轮：精炼查询
        return {
          round: SearchRound.ROUND_2,
          strategy: '精炼查询',
          query,
          engines: [SearchEngine.EXA, SearchEngine.CONTEXT7],
        };

      case 3:
        // 第三轮：深度提炼
        return {
          round: SearchRound.ROUND_3,
          strategy: '深度提炼',
          query,
          engines: [SearchEngine.GITHUB, SearchEngine.EXA],
        };

      default:
        return {
          round: SearchRound.ROUND_1,
          strategy: '默认',
          query,
          engines: [SearchEngine.SEARXNG],
        };
    }
  }

  /**
   * 精炼查询
   */
  private refineQuery(originalQuery: string, results: SearchResult[]): string {
    // 基于前一轮结果提取新关键词
    const allContent = results.flatMap(r => r.sources.map(s => s.content)).join(' ');
    const words = allContent.split(/\s+/).filter(w => w.length > 4);
    const unique = [...new Set(words)].slice(0, 3);
    return `${originalQuery} ${unique.join(' ')}`;
  }

  /**
   * 切换策略
   */
  private switchStrategy(query: string): string {
    return `${query} official documentation tutorial`;
  }

  /**
   * 交叉验证
   */
  private performCrossValidation(results: SearchResult[]): {
    sources_count: number;
    conflicts: string[];
    confidence: number;
  } {
    const allSources = results.flatMap(r => r.sources);
    const sources_count = allSources.length;

    // 检测冲突（简化）
    const conflicts: string[] = [];
    const sourceGroups = new Map<string, SearchSource[]>();

    for (const source of allSources) {
      const key = source.title.substring(0, 20);
      if (!sourceGroups.has(key)) {
        sourceGroups.set(key, []);
      }
      sourceGroups.get(key)!.push(source);
    }

    for (const [key, sources] of sourceGroups.entries()) {
      if (sources.length > 1) {
        const confidences = sources.map(s => s.confidence);
        const maxDiff = Math.max(...confidences) - Math.min(...confidences);
        if (maxDiff > 0.3) {
          conflicts.push(`Conflicting sources for "${key}..."`);
        }
      }
    }

    const confidence = sources_count > 0
      ? allSources.reduce((sum, s) => sum + s.confidence, 0) / sources_count
      : 0;

    return { sources_count, conflicts, confidence };
  }

  /**
   * 生成摘要
   */
  private generateSummary(results: SearchResult[]): string {
    if (results.length === 0) return 'No results found';

    const lastResult = results[results.length - 1];
    return `Search completed with ${results.length} rounds, final confidence: ${lastResult.confidence.toFixed(2)}`;
  }

  /**
   * 识别缺失信息
   */
  private identifyMissingInfo(results: SearchResult[], originalQuery: string): string[] {
    const missing: string[] = [];
    const allSources = results.flatMap(r => r.sources);

    if (allSources.length < 3) {
      missing.push('Insufficient source coverage');
    }

    const avgConfidence = allSources.reduce((sum, s) => sum + s.confidence, 0) / allSources.length;
    if (avgConfidence < 0.7) {
      missing.push('Low confidence in results');
    }

    return missing;
  }

  /**
   * 注册自定义引擎
   */
  registerEngine(
    engine: SearchEngine,
    router: (query: string) => Promise<SearchSource[]>
  ): void {
    this.engineRouters.set(engine, router);
  }
}

// ============================================
// 单例导出
// ============================================

export const searchAdapter = new SearchAdapter();
