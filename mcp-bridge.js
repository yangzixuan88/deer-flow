#!/usr/bin/env node
/**
 * @file mcp-bridge.js
 * @description Zero-Dependency MCP Bridge for OpenClaw Architecture 2.0
 * Purpose: Provides lightweight bridge between MCP protocol and OpenClaw's SQLite asset database.
 * Reference: Decision D-021 & Phase 11 "Mobile Autonomy" & "Omni-Empowerment"
 *
 * Architecture: Node.js primary process + child_process for Python SQLite access
 * Zero external npm dependencies - uses only built-in Node.js modules
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Configuration
const MCP_SERVER_PATH = path.join(__dirname, 'src/infrastructure/server/mcp_server.py');
const ASSET_DB_PATH = path.join(__dirname, 'assets/Asset_Manifest.sqlite');

/**
 * MCP Protocol Response Formatter
 * Ensures all responses follow the MCP JSON-RPC 2.0 specification
 */
class MCPProtocol {
  static successResponse(id, result) {
    return {
      jsonrpc: '2.0',
      id,
      result
    };
  }

  static errorResponse(id, code, message) {
    return {
      jsonrpc: '2.0',
      id,
      error: { code, message }
    };
  }

  static parseRequest(rawRequest) {
    try {
      const request = JSON.parse(rawRequest);
      if (request.jsonrpc !== '2.0') {
        throw new Error('Invalid JSON-RPC version');
      }
      return request;
    } catch (e) {
      return null;
    }
  }
}

/**
 * Python SQLite Bridge
 * Spawns a Python child process to handle SQLite operations
 * This achieves "zero npm dependency" for database access
 */
class PythonSQLiteBridge {
  constructor(dbPath) {
    this.dbPath = dbPath;
    this.pythonProcess = null;
  }

  /**
   * Execute a Python script to query SQLite
   * SECURITY FIX: SQL and params passed as command-line arguments, not embedded in script
   */
  async query(sql, params = []) {
    // SECURITY: Pass SQL and params as JSON arguments, not embedded in script
    const args = [
      this.dbPath,
      sql,
      JSON.stringify(params)
    ];

    const script = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
sql = sys.argv[2]
params = json.loads(sys.argv[3])

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(sql, params)

    if sql.strip().upper().startswith('SELECT'):
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
    else:
        conn.commit()
        result = {"affected_rows": cursor.rowcount}

    print(json.dumps({"success": True, "data": result}))
    conn.close()
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
    sys.exit(1)
`;

    return this.runPythonWithArgs(script, args);
  }

  /**
   * Run Python script with command-line arguments
   */
  runPythonWithArgs(script, args) {
    return new Promise((resolve, reject) => {
      const pythonArgs = ['-c', script, ...args];
      const python = spawn('python', pythonArgs, {
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';

      python.stdout.on('data', (data) => { stdout += data.toString(); });
      python.stderr.on('data', (data) => { stderr += data.toString(); });

      python.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Python error: ${stderr}`));
        } else {
          try {
            resolve(JSON.parse(stdout));
          } catch (e) {
            reject(new Error(`Failed to parse Python output: ${stdout}`));
          }
        }
      });

      python.on('error', (error) => reject(error));
    });
  }

  /**
   * Spawn Python process and run script
   */
  runPython(script) {
    return new Promise((resolve, reject) => {
      const python = spawn('python', ['-c', script], {
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';

      python.stdout.on('data', (data) => { stdout += data.toString(); });
      python.stderr.on('data', (data) => { stderr += data.toString(); });

      python.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Python error: ${stderr}`));
        } else {
          try {
            resolve(JSON.parse(stdout));
          } catch (e) {
            reject(new Error(`Failed to parse Python output: ${stdout}`));
          }
        }
      });

      python.on('error', (error) => reject(error));
    });
  }
}

/**
 * MCP Bridge Server
 * Main entry point that bridges MCP protocol to OpenClaw assets
 */
class MCPBridgeServer {
  constructor() {
    this.bridge = new PythonSQLiteBridge(ASSET_DB_PATH);
    this.tools = new Map([
      ['get_optimized_prompt', this.getOptimizedPrompt.bind(this)],
      ['list_available_assets', this.listAvailableAssets.bind(this)]
    ]);
  }

  /**
   * Handle incoming MCP request
   */
  async handleRequest(request) {
    const { method, params, id } = request;

    if (method === 'initialize') {
      return MCPProtocol.successResponse(id, {
        capabilities: { tools: { listChanged: true } },
        serverInfo: { name: 'OpenClaw-MCP-Bridge', version: '1.0.0' }
      });
    }

    if (method === 'tools/list') {
      return MCPProtocol.successResponse(id, {
        tools: [
          {
            name: 'get_optimized_prompt',
            description: 'Retrieve an optimized prompt/skill from the OpenClaw Asset Library.',
            inputSchema: {
              type: 'object',
              properties: {
                asset_name: { type: 'string', description: 'The specific name of the skill or knowledge asset.' }
              },
              required: ['asset_name']
            }
          },
          {
            name: 'list_available_assets',
            description: 'List all gold-level assets (Quality > 0.7) in the current environment.',
            inputSchema: {
              type: 'object',
              properties: {
                asset_type: { type: 'string', description: 'Filter by type (DomainKnowledge, Skill, etc.)' }
              }
            }
          }
        ]
      });
    }

    if (method === 'tools/call') {
      const toolName = params.name;
      const toolArgs = params.arguments || {};

      const handler = this.tools.get(toolName);
      if (!handler) {
        return MCPProtocol.errorResponse(id, -32601, `Tool not found: ${toolName}`);
      }

      try {
        const result = await handler(toolArgs);
        return MCPProtocol.successResponse(id, result);
      } catch (e) {
        return MCPProtocol.errorResponse(id, -32603, e.message);
      }
    }

    return MCPProtocol.errorResponse(id, -32601, 'Method not found');
  }

  /**
   * get_optimized_prompt tool implementation
   */
  async getOptimizedPrompt(args) {
    const { asset_name } = args;

    const result = await this.bridge.query(
      'SELECT name, type, quality_score FROM assets WHERE name = ? OR name LIKE ?',
      [asset_name, `%${asset_name}%`]
    );

    if (!result.success) {
      throw new Error(result.error);
    }

    const rows = result.data;
    if (rows.length === 0) {
      return { content: [{ type: 'text', text: `Asset '${asset_name}' not found in manifest.` }], isError: true };
    }

    const row = rows[0];
    return {
      content: [{
        type: 'text',
        text: `Asset: ${row.name}\nType: ${row.type}\nQuality: ${row.quality_score}\n\n[Asset content would be loaded from filesystem in full implementation]`
      }]
    };
  }

  /**
   * list_available_assets tool implementation
   */
  async listAvailableAssets(args) {
    const { asset_type } = args;

    let query = 'SELECT name, type, quality_score, usage_count FROM assets WHERE quality_score >= 0.7';
    let params = [];

    if (asset_type) {
      query += ' AND type = ?';
      params.push(asset_type);
    }

    const result = await this.bridge.query(query, params);

    if (!result.success) {
      throw new Error(result.error);
    }

    const rows = result.data;
    const assetsList = rows.map(r => `- ${r.name} (${r.type}) | Score: ${r.quality_score} | Used: ${r.usage_count}`).join('\n');

    return {
      content: [{
        type: 'text',
        text: `Available Assets (Quality > 0.7):\n${assetsList || 'None'}`
      }]
    };
  }

  /**
   * Start the bridge server
   */
  start() {
    console.error('[MCP-Bridge] OpenClaw MCP Bridge started (Zero-Dependency Mode)');

    // Read JSON-RPC requests from stdin
    process.stdin.setEncoding('utf8');

    process.stdin.on('data', async (chunk) => {
      const lines = chunk.split('\n').filter(line => line.trim());

      for (const line of lines) {
        const request = MCPProtocol.parseRequest(line);
        if (!request) continue;

        try {
          const response = await this.handleRequest(request);
          console.log(JSON.stringify(response));
        } catch (e) {
          const errorResponse = MCPProtocol.errorResponse(
            request.id || null,
            -32603,
            e.message
          );
          console.log(JSON.stringify(errorResponse));
        }
      }
    });

    process.stdin.on('end', () => {
      console.error('[MCP-Bridge] Stdin closed, shutting down');
    });
  }
}

// Main entry point
if (require.main === module) {
  const server = new MCPBridgeServer();
  server.start();
}

module.exports = { MCPBridgeServer, MCPProtocol, PythonSQLiteBridge };