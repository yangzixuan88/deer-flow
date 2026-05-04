/**
 * @file search_protocol.ts
 * @description Implementation of the STORM Three-Round Search Protocol based on the "Super Constitution".
 * Defines the state machine for recursive search and validation.
 */

import { IPostToolUseHook, HookContext } from './hooks';

export type SearchRound = 1 | 2 | 3;

export interface SearchSource {
  title: string;
  url: string;
  content: string;
  date?: string;
  confidence: number;
}

export interface SearchResult {
  query: string;
  round: SearchRound;
  sources: SearchSource[];
  summary: string;
  confidence: number; // 0-1
  missingInfo?: string;
}

export interface SearchProtocolState {
  originalQuery: string;
  currentRound: SearchRound;
  allResults: SearchResult[];
  finalSummary?: string;
  isCompleted: boolean;
}

/**
 * The STORM Three-Round Search Protocol State Machine
 * Reference: Super Constitution §2.2
 */
export class SearchProtocolEngine {
  private state: SearchProtocolState;
  private readonly CONFIDENCE_THRESHOLD = 0.7;

  constructor(query: string) {
    this.state = {
      originalQuery: query,
      currentRound: 1,
      allResults: [],
      isCompleted: false,
    };
  }

  /**
   * Evaluates if the current search results satisfy the requirement.
   * Logic: >= 2 independent sources, confidence >= 0.7, no critical missing info.
   */
  public evaluateQuality(result: SearchResult): boolean {
    if (result.confidence >= this.CONFIDENCE_THRESHOLD && result.sources.length >= 2) {
      return true;
    }
    return false;
  }

  /**
   * Determines the next strategy based on the current state.
   */
  public getNextStrategy(): { round: SearchRound; strategy: string } | null {
    if (this.state.isCompleted) return null;

    const lastResult = this.state.allResults[this.state.allResults.length - 1];
    
    if (this.state.currentRound === 1) {
      return { 
        round: 2, 
        strategy: "Technical Refinement: Focus on GitHub Issues, Official Docs, and StackOverflow." 
      };
    } else if (this.state.currentRound === 2) {
      return { 
        round: 3, 
        strategy: "Gap-Filling: Extract specific snippets using Jina Reader and perform targeted deep research." 
      };
    }
    
    return null;
  }

  public addResult(result: SearchResult): void {
    this.state.allResults.push(result);
    if (this.evaluateQuality(result) || this.state.currentRound === 3) {
      this.state.isCompleted = true;
    } else {
      this.state.currentRound++;
    }
  }

  public getState(): SearchProtocolState {
    return { ...this.state };
  }
}

/**
 * Interface for the Jina Reader Adapter
 * Reference: Super Constitution §2.2 & §5.5
 */
export interface IJinaReaderAdapter {
  /**
   * Fetches URL content and converts to High-Purity Markdown via r.jina.ai
   */
  fetchMarkdown(url: string): Promise<string>;
  
  /**
   * FlashRank Rerank: Reorders content to put Top 3 high-confidence snippets at the top.
   */
  rerank(content: string, query: string): Promise<string>;
}
