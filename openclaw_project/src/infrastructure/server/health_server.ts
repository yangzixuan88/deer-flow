/**
 * OpenClaw Health Check & Metrics Server
 * ============================================
 * Phase 14: 生产准备 - 运维工具核心组件
 *
 * 功能:
 * - /health - 健康检查端点
 * - /ready - 就绪检查端点
 * - /metrics - Prometheus 格式指标暴露
 * - 优雅停机处理
 * - 配置热更新
 * ============================================
 */

import http from 'http';
import { Server } from 'http';
import { URL } from 'url';

// ============================================
// 指标类型定义
// ============================================

interface GaugeMetric {
  name: string;
  help: string;
  value: number;
  labels: Record<string, string>;
}

interface CounterMetric {
  name: string;
  help: string;
  value: number;
  labels: Record<string, string>;
}

interface HistogramMetric {
  name: string;
  help: string;
  buckets: { le: number; count: number }[];
  sum: number;
  count: number;
  labels: Record<string, string>;
}

interface MetricsStore {
  gauges: Map<string, GaugeMetric>;
  counters: Map<string, CounterMetric>;
  histograms: Map<string, HistogramMetric>;
  summaries: Map<string, any>;
}

// ============================================
// 全局指标存储
// ============================================

const metricsStore: MetricsStore = {
  gauges: new Map(),
  counters: new Map(),
  histograms: new Map(),
  summaries: new Map(),
};

// ============================================
// 指标注册函数
// ============================================

export function registerGauge(name: string, help: string, value: number, labels: Record<string, string> = {}): void {
  const key = metricKey(name, labels);
  metricsStore.gauges.set(key, { name, help, value, labels });
}

export function registerCounter(name: string, help: string, value: number, labels: Record<string, string> = {}): void {
  const key = metricKey(name, labels);
  metricsStore.counters.set(key, { name, help, value, labels });
}

export function registerHistogram(
  name: string,
  help: string,
  buckets: number[],
  labels: Record<string, string> = {}
): void {
  const key = metricKey(name, labels);
  metricsStore.histograms.set(key, {
    name,
    help,
    buckets: buckets.map(le => ({ le, count: 0 })),
    sum: 0,
    count: 0,
    labels,
  });
}

export function observeHistogram(name: string, value: number, labels: Record<string, string> = {}): void {
  const key = metricKey(name, labels);
  const histogram = metricsStore.histograms.get(key);
  if (histogram) {
    histogram.sum += value;
    histogram.count += 1;
    for (const bucket of histogram.buckets) {
      if (value <= bucket.le) {
        bucket.count++;
      }
    }
  }
}

export function incCounter(name: string, labels: Record<string, string> = {}): void {
  const key = metricKey(name, labels);
  const counter = metricsStore.counters.get(key);
  if (counter) {
    counter.value++;
  }
}

export function setGauge(name: string, value: number, labels: Record<string, string> = {}): void {
  const key = metricKey(name, labels);
  const gauge = metricsStore.gauges.get(key);
  if (gauge) {
    gauge.value = value;
  }
}

function metricKey(name: string, labels: Record<string, string>): string {
  const labelStr = Object.entries(labels).sort().map(([k, v]) => `${k}="${v}"`).join(',');
  return labelStr ? `${name}{${labelStr}}` : name;
}

// ============================================
// Prometheus 格式化输出
// ============================================

function formatPrometheusMetrics(): string {
  const lines: string[] = [];

  // Gauges
  lines.push('# HELP openclaw_info OpenClaw application info');
  lines.push('# TYPE openclaw_info gauge');
  lines.push('openclaw_info{version="2.0",service="openclaw"} 1');
  lines.push('');

  for (const [, gauge] of metricsStore.gauges) {
    lines.push(`# HELP ${gauge.name} ${gauge.help}`);
    lines.push(`# TYPE ${gauge.name} gauge`);
    const labelStr = Object.entries(gauge.labels).map(([k, v]) => `${k}="${v}"`).join(',');
    lines.push(labelStr ? `${gauge.name}{${labelStr}} ${gauge.value}` : `${gauge.name} ${gauge.value}`);
  }

  // Counters
  for (const [, counter] of metricsStore.counters) {
    lines.push(`# HELP ${counter.name} ${counter.help}`);
    lines.push(`# TYPE ${counter.name} counter`);
    const labelStr = Object.entries(counter.labels).map(([k, v]) => `${k}="${v}"`).join(',');
    lines.push(labelStr ? `${counter.name}{${labelStr}} ${counter.value}` : `${counter.name} ${counter.value}`);
  }

  // Histograms
  for (const [, histogram] of metricsStore.histograms) {
    lines.push(`# HELP ${histogram.name} ${histogram.help}`);
    lines.push(`# TYPE ${histogram.name} histogram`);
    const baseLabels = Object.entries(histogram.labels).map(([k, v]) => `${k}="${v}"`).join(',');
    const baseLabelStr = baseLabels ? `{${baseLabels}}` : '';

    for (const bucket of histogram.buckets) {
      lines.push(`${histogram.name}_bucket{le="${bucket.le}"${baseLabels ? ',' + baseLabels : ''}} ${bucket.count}`);
    }
    lines.push(`${histogram.name}_bucket{le="+Inf"${baseLabels ? ',' + baseLabels : ''}} ${histogram.count}`);
    lines.push(`${histogram.name}_sum${baseLabelStr} ${histogram.sum}`);
    lines.push(`${histogram.name}_count${baseLabelStr} ${histogram.count}`);
  }

  return lines.join('\n');
}

// ============================================
// 系统健康状态
// ============================================

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime_seconds: number;
  version: string;
  timestamp: string;
  checks: {
    memory: { status: 'pass' | 'fail'; used_mb: number };
    tasks: { status: 'pass' | 'fail'; active: number; queued: number };
    components: { name: string; status: 'up' | 'down'; latency_ms?: number }[];
  };
}

let serverStartTime = Date.now();
let isShuttingDown = false;

// ============================================
// HTTP 请求处理
// ============================================

function parseBody<T>(req: http.IncomingMessage): Promise<T | null> {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      if (!body) return resolve(null);
      try {
        resolve(JSON.parse(body));
      } catch {
        resolve(null);
      }
    });
  });
}

async function handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  const url = new URL(req.url || '/', 'http://localhost');
  const pathname = url.pathname;

  // CORS 头
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (pathname === '/health') {
    // Liveness probe - 应用存活
    const status: HealthStatus = {
      status: isShuttingDown ? 'unhealthy' : 'healthy',
      uptime_seconds: Math.floor((Date.now() - serverStartTime) / 1000),
      version: '2.0',
      timestamp: new Date().toISOString(),
      checks: {
        memory: { status: 'pass', used_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024) },
        tasks: { status: 'pass', active: 0, queued: 0 },
        components: [],
      },
    };

    res.writeHead(status.status === 'healthy' ? 200 : 503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(status));
    return;
  }

  if (pathname === '/ready') {
    // Readiness probe - 应用就绪
    // TODO: 检查 Redis、Dapr 等依赖连接
    const ready = !isShuttingDown;
    res.writeHead(ready ? 200 : 503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ready, timestamp: new Date().toISOString() }));
    return;
  }

  if (pathname === '/metrics') {
    // Prometheus metrics
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end(formatPrometheusMetrics());
    return;
  }

  if (pathname === '/shutdown' && req.method === 'POST') {
    // 优雅停机触发 (仅本地)
    if (req.socket.remoteAddress === '127.0.0.1' || req.socket.remoteAddress === '::1') {
      isShuttingDown = true;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ message: 'Shutdown initiated', will_exit_in_seconds: 10 }));

      // 延迟退出，允许负载均衡移除流量
      setTimeout(() => {
        console.log('[HealthServer] Shutting down gracefully...');
        process.exit(0);
      }, 10000);
      return;
    }
    res.writeHead(403);
    res.end(JSON.stringify({ error: 'Forbidden' }));
    return;
  }

  if (pathname === '/reload' && req.method === 'POST') {
    // 配置热更新 (仅本地)
    if (req.socket.remoteAddress === '127.0.0.1' || req.socket.remoteAddress === '::1') {
      try {
        const body = await parseBody<{ config_path?: string }>(req);
        // TODO: 实现实际配置热更新
        console.log('[HealthServer] Configuration reload requested', body);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ message: 'Configuration reload initiated', reloaded_at: new Date().toISOString() }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Reload failed' }));
      }
      return;
    }
    res.writeHead(403);
    res.end(JSON.stringify({ error: 'Forbidden' }));
    return;
  }

  // 404
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
}

// ============================================
// 服务器启动
// ============================================

let server: Server | null = null;

export function startHealthServer(port = 8081): Promise<Server> {
  return new Promise((resolve) => {
    server = http.createServer(handleRequest);

    // 优雅停机信号处理
    const shutdown = (signal: string) => {
      console.log(`[HealthServer] Received ${signal}, initiating graceful shutdown...`);
      isShuttingDown = true;

      // 给现有请求处理时间
      setTimeout(() => {
        console.log('[HealthServer] Force closing after timeout');
        if (server) server.close();
        process.exit(0);
      }, 30000);
    };

    process.on('SIGTERM', () => shutdown('SIGTERM'));
    process.on('SIGINT', () => shutdown('SIGINT'));

    server.listen(port, () => {
      console.log(`[HealthServer] Health & Metrics server running on port ${port}`);
      console.log(`[HealthServer] Endpoints:`);
      console.log(`  - GET  /health  - Liveness probe`);
      console.log(`  - GET  /ready   - Readiness probe`);
      console.log(`  - GET  /metrics - Prometheus metrics`);
      console.log(`  - POST /shutdown - Graceful shutdown (local only)`);
      console.log(`  - POST /reload  - Config hot reload (local only)`);
      resolve(server!);
    });
  });
}

export function stopHealthServer(): Promise<void> {
  return new Promise((resolve) => {
    if (server) {
      server.close(() => {
        console.log('[HealthServer] Server stopped');
        resolve();
      });
    } else {
      resolve();
    }
  });
}

export function isHealthy(): boolean {
  return !isShuttingDown;
}

// ============================================
// 演示：自动注册默认指标
// ============================================

registerGauge('openclaw_memory_usage_bytes', 'Memory usage in bytes', 0, { type: 'heap' });
registerGauge('openclaw_tasks_active', 'Number of active tasks', 0);
registerGauge('openclaw_tasks_queued', 'Number of queued tasks', 0);
registerCounter('openclaw_requests_total', 'Total HTTP requests', 0, { endpoint: 'unknown' });
registerHistogram('openclaw_request_duration_seconds', 'Request duration in seconds', [0.01, 0.05, 0.1, 0.5, 1, 5]);

// 定期更新内存指标
setInterval(() => {
  const mem = process.memoryUsage();
  setGauge('openclaw_memory_usage_bytes', mem.heapUsed, { type: 'heap' });
  setGauge('openclaw_memory_usage_bytes', mem.heapTotal, { type: 'heap_total' });
  setGauge('openclaw_memory_usage_bytes', mem.rss, { type: 'rss' });
}, 10000);

// ============================================
// 启动演示
// ============================================

if (require.main === module) {
  startHealthServer(8081);
}
