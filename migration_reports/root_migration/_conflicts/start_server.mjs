/**
 * Start MCP API Server
 * Run with: node start_server.mjs
 */
import { startMCPServer } from './src/infrastructure/server/mcp_api_server.ts';

console.log('Starting OpenClaw MCP API Server...');
console.log(`API Key: ${process.env.MCP_API_KEY || 'dev-api-key-change-in-production'}`);
console.log(`Port: ${process.env.MCP_API_PORT || 8082}`);

startMCPServer(Number(process.env.MCP_API_PORT || 8082))
  .then(() => {
    console.log('Server started successfully');
  })
  .catch(e => {
    console.error('Failed to start server:', e);
    process.exit(1);
  });

// Keep process alive
process.stdin.resume();
