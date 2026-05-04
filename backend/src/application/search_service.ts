/**
 * @file search_service.ts
 * @description Application service to orchestrate the STORM search protocol.
 * Integrates Domain logic (SearchProtocolEngine) with Infrastructure (JinaReaderAdapter).
 * Reference: Super Constitution Phase 2 & §2.2
 */

import { SearchProtocolEngine, SearchResult } from '../domain/search_protocol';
import { JinaReaderAdapter } from '../infrastructure/jina_adapter';
import { ICEEngine, IntentClarity } from '../domain/ice_engine';
import { SearchAdapter } from '../domain/m04/adapters/search_adapter';

export class SearchService {
  private jina = new JinaReaderAdapter();
  private ice = new ICEEngine();
  private searchAdapter = new SearchAdapter();

  /**
   * Executes the full STORM search workflow with Intent Clarification (ICE).
   */
  public async searchWithClarity(query: string, clarity: IntentClarity): Promise<string> {
    // 1. ICE 意图澄清决策
    const iceResult = this.ice.evaluate(query, clarity);
    if (iceResult.shouldClarify) {
      return `### 🛑 意图待明确 (ICE 0.85 熔断)\n\n为了确保搜索精度，请补充以下细节：\n\n- ${iceResult.questions.join('\n- ')}`;
    }

    // 2. 正常进入 STORM 三轮搜索
    return this.search(query);
  }

  /**
   * Executes the full STORM search workflow.
   * Logic: Intent Dissection -> Parallel Search -> Jina Extraction -> FlashRank Rerank -> Synthesis.
   */
  public async search(query: string): Promise<string> {
    const engine = new SearchProtocolEngine(query);
    console.log(`[SearchService] Starting STORM search for: "${query}"`);

    while (!engine.getState().isCompleted) {
      const strategy = engine.getNextStrategy();
      if (!strategy) break;

      console.log(`[SearchService] Entering Round ${strategy.round}: ${strategy.strategy}`);

      // REAL SEARCH: 使用SearchAdapter执行真实搜索
      const searchResponse = await this.searchAdapter.executeThreeRoundSearch(
        query,
        strategy.round as 1 | 2 | 3
      );

      // 提取当前轮次的结果
      const currentRoundResult = searchResponse.results.find(
        r => r.round === strategy.round
      );

      const realResult: SearchResult = currentRoundResult || {
        query: query,
        round: strategy.round,
        sources: [],
        summary: `STORM Round ${strategy.round} - no results`,
        confidence: 0,
      };

      // Add to engine - state machine will decide if Round 3 or completion is needed
      engine.addResult(realResult);
    }

    const finalState = engine.getState();
    return this.synthesizeFinalAnswer(finalState.allResults);
  }

  /**
   * Final Synthesis with Citation [1][2] as per Super Constitution §2.4.
   */
  private synthesizeFinalAnswer(results: SearchResult[]): string {
    let finalOutput = "### 🛡️ STORM 交叉验证搜索报告\n\n";
    
    results.forEach(res => {
      finalOutput += `**Round ${res.round} 结论**: ${res.summary}\n`;
    });

    finalOutput += "\n**信息来源 [Citations]**:\n";
    results.forEach(res => {
      res.sources.forEach((src, idx) => {
        finalOutput += `[${idx + 1}] ${src.title} - ${src.url}\n`;
      });
    });

    finalOutput += `\n**综合置信度**: ${Math.max(...results.map(r => r.confidence))}\n`;
    finalOutput += `**状态**: 🚀 已按照《超级宪法》三轮协议完成校准\n`;

    return finalOutput;
  }
}
