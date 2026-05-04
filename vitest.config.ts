import { defineConfig } from 'vitest/config'
export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['src/**/*.test.ts'],
    cache: false,
    testTimeout: 30000,
    // 排除使用 @jest/globals 的测试文件（需要用 Jest 运行）
    exclude: [
      'src/domain/ice_engine.test.ts',
      'src/domain/nightly_distiller.test.ts',
      'src/domain/e2e/stress.test.ts',
    ],
  },
})
