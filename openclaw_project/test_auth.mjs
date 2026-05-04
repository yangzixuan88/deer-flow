/**
 * Test MCP API Server with authentication
 */
import * as http from 'http';

const testRequest = (path, body, authToken = null) => {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const headers = {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(data)
    };
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const options = {
      hostname: 'localhost',
      port: 8082,
      path,
      method: 'POST',
      headers
    };

    const req = http.request(options, (res) => {
      let responseData = '';
      res.on('data', chunk => responseData += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body: responseData }));
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
};

async function main() {
  const API_KEY = 'dev-api-key-change-in-production';

  console.log('Testing MCP API Server with Authentication\n');

  // Test 1: Health without auth (should work)
  console.log('1. Health without auth:');
  try {
    const res = await new Promise((resolve, reject) => {
      http.get('http://localhost:8082/health', (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => resolve({ status: res.statusCode, body: data }));
      }).on('error', reject);
    });
    console.log(`   ✓ Status ${res.status}: ${res.body}\n`);
  } catch (e) {
    console.log(`   ✗ Error: ${e.message}\n`);
  }

  // Test 2: API info without auth (should work)
  console.log('2. API Info without auth:');
  try {
    const res = await new Promise((resolve, reject) => {
      http.get('http://localhost:8082/api/v1', (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => resolve({ status: res.statusCode, body: data }));
      }).on('error', reject);
    });
    console.log(`   ✓ Status ${res.status}: ${res.body.slice(0, 100)}...\n`);
  } catch (e) {
    console.log(`   ✗ Error: ${e.message}\n`);
  }

  // Test 3: Task recognition WITHOUT auth (should fail with 401)
  console.log('3. Task Recognition WITHOUT auth (should fail):');
  const failResult = await testRequest('/api/v1/prompt/recognize', {
    jsonrpc: '2.0', id: 1, params: { userInput: 'test' }
  });
  console.log(`   ${failResult.status === 401 ? '✓' : '✗'} Status ${failResult.status} (expected 401)\n`);

  // Test 4: Task recognition WITH auth (should work)
  console.log('4. Task Recognition WITH auth (should succeed):');
  const successResult = await testRequest('/api/v1/prompt/recognize', {
    jsonrpc: '2.0', id: 1, params: { userInput: 'test' }
  }, API_KEY);
  console.log(`   ${successResult.status === 200 ? '✓' : '✗'} Status ${successResult.status}`);
  if (successResult.status === 200) {
    const parsed = JSON.parse(successResult.body);
    console.log(`   Result: ${successResult.body.slice(0, 100)}...\n`);
  }

  // Test 5: Memory search WITH auth (should work)
  console.log('5. Memory Search WITH auth:');
  const memResult = await testRequest('/api/v1/memory/search', {
    jsonrpc: '2.0', id: 2, params: { query: 'test', layer: 'session' }
  }, API_KEY);
  console.log(`   ${memResult.status === 200 ? '✓' : '✗'} Status ${memResult.status}`);
  console.log(`   Result: ${memResult.body.slice(0, 100)}...\n`);

  console.log('✅ Authentication tests completed');
  process.exit(0);
}

main().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});