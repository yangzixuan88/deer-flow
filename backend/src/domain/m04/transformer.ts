/**
 * 跨引擎数据转换器
 * ================================================
 * Purpose: 在 n8n 和 Dify 节点间转换数据格式
 * 支持 Jinja2/JSON Path/自定义 JS 转换
 * ================================================
 */

import { WorkflowEngine } from './engine_enum';
import { HybridNode, CrossEngineEdge } from './types';

export interface TransformResult {
  success: boolean;
  data?: any;
  error?: string;
}

/**
 * 跨引擎数据转换器
 *
 * 常见转换场景：
 * 1. n8n JSON → Dify inputs（展平/映射）
 * 2. Dify outputs → n8n 字段提取
 * 3. 流式 chunk → 批量数组
 * 4. 二进制 → Base64
 */
export class CrossEngineDataTransformer {
  /**
   * 转换数据格式
   */
  transform(
    sourceData: any,
    sourceEngine: WorkflowEngine,
    targetNode: HybridNode,
    transformConfig?: CrossEngineEdge['transform']
  ): TransformResult {
    try {
      // 无转换配置，直接返回
      if (!transformConfig) {
        return { success: true, data: sourceData };
      }

      const { type, expression } = transformConfig;

      switch (type) {
        case 'passthrough':
          return { success: true, data: sourceData };

        case 'json_path':
          return this.applyJsonPath(sourceData, expression);

        case 'jinja2':
          return this.applyJinja2(sourceData, expression);

        case 'custom_js':
          return this.applyCustomJS(sourceData, expression);

        default:
          return { success: true, data: sourceData };
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Transform failed',
      };
    }
  }

  /**
   * 应用 JSON Path 表达式
   * 例如: "outputs.result.chunks[0].text"
   */
  private applyJsonPath(data: any, path: string): TransformResult {
    try {
      const parts = path.split('.');
      let current: any = data;

      for (const part of parts) {
        // 处理数组索引
        const arrayMatch = part.match(/^(\w+)\[(\d+)\]$/);
        if (arrayMatch) {
          const [, key, indexStr] = arrayMatch;
          const index = parseInt(indexStr, 10);
          current = current?.[key]?.[index];
        } else {
          current = current?.[part];
        }
      }

      return { success: true, data: current };
    } catch (error) {
      return {
        success: false,
        error: `JSON Path failed: ${error instanceof Error ? error.message : path}`,
      };
    }
  }

  /**
   * 应用 Jinja2 风格模板
   * 例如: "Result: {{ outputs.text }} with {{ outputs.count }} items"
   */
  private applyJinja2(data: any, template: string): TransformResult {
    try {
      // 简化 Jinja2 实现：支持 {{ path }} 插值
      const result = template.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (match, path) => {
        const value = this.getValueByPath(data, path);
        return value !== undefined ? String(value) : match;
      });

      return { success: true, data: result };
    } catch (error) {
      return {
        success: false,
        error: `Jinja2 template failed: ${error instanceof Error ? error.message : template}`,
      };
    }
  }

  /**
   * 应用自定义 JavaScript 表达式
   * 例如: "(data) => data.outputs.filter(x => x.confidence > 0.5)"
   */
  private applyCustomJS(data: any, expression: string): TransformResult {
    try {
      // 安全检查：只允许函数调用
      if (!expression.startsWith('(data) =>')) {
        // 尝试作为路径处理
        return this.applyJsonPath(data, expression);
      }

      // eslint-disable-next-line no-new-func
      const fn = new Function('data', `return ${expression.replace('(data) =>', '')}(data);`);
      const result = fn(data);
      return { success: true, data: result };
    } catch (error) {
      return {
        success: false,
        error: `Custom JS failed: ${error instanceof Error ? error.message : expression}`,
      };
    }
  }

  /**
   * 按路径获取值
   */
  private getValueByPath(data: any, path: string): any {
    const parts = path.split('.');
    let current: any = data;

    for (const part of parts) {
      if (current === undefined || current === null) break;
      current = current[part];
    }

    return current;
  }

  // ============================================
  // 预设转换模板
  // ============================================

  /**
   * n8n 输出 → Dify inputs 标准化
   */
  static n8nToDify(sourceData: any, nodeId: string): any {
    // n8n 通常返回 { data: {...}, json: {...} } 结构
    // Dify 通常需要 { inputs: {...} } 结构
    return {
      inputs: sourceData.json || sourceData.data || sourceData,
      metadata: {
        source_node: nodeId,
        transform: 'n8n_to_dify',
      },
    };
  }

  /**
   * Dify outputs → n8n 字段标准化
   */
  static difyToN8(sourceData: any, mapping?: Record<string, string>): any {
    // Dify 返回 { outputs: {...}, text: "...", ... }
    // 提取到 n8n 兼容格式
    const result: any = {
      json: sourceData.outputs || sourceData,
    };

    // 应用字段映射
    if (mapping) {
      for (const [target, source] of Object.entries(mapping)) {
        const value = sourceData.outputs?.[source] ?? sourceData[source];
        if (value !== undefined) {
          result.json[target] = value;
        }
      }
    }

    return result;
  }

  /**
   * 展平嵌套对象
   */
  static flatten(data: any, prefix: string = ''): Record<string, any> {
    const result: Record<string, any> = {};

    if (typeof data !== 'object' || data === null) {
      result[prefix || 'value'] = data;
      return result;
    }

    for (const [key, value] of Object.entries(data)) {
      const newKey = prefix ? `${prefix}.${key}` : key;

      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        Object.assign(result, this.flatten(value, newKey));
      } else {
        result[newKey] = value;
      }
    }

    return result;
  }

  /**
   * 将流式 chunks 合并为字符串
   */
  static mergeStreamChunks(chunks: any[]): string {
    return chunks.map((c) => (typeof c === 'string' ? c : JSON.stringify(c))).join('');
  }

  /**
   * 将字符串拆分为 chunks
   */
  static splitToChunks(data: string, chunkSize: number = 100): string[] {
    const chunks: string[] = [];
    for (let i = 0; i < data.length; i += chunkSize) {
      chunks.push(data.slice(i, i + chunkSize));
    }
    return chunks;
  }
}

// ============================================
// 单例导出
// ============================================

export const crossEngineTransformer = new CrossEngineDataTransformer();
