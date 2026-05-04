/** @type {import('jest').Config} */
const config = {
  preset: 'ts-jest/presets/default-esm',
  testEnvironment: 'node',
  extensionsToTreatAsEsm: ['.ts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },
  transform: {
    '^.+\\.tsx?$': [
      'ts-jest',
      {
        useESM: true,
        tsconfig: 'tsconfig.jest.json',
      },
    ],
  },
  testMatch: [
    '**/*.test.ts',
    '**/*.spec.ts',
  ],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/frontend/src/core/threads/utils.test.ts',
    '/frontend/src/core/api/stream-mode.test.ts',
    '/src/m11/',  // Ignore old duplicate code (Architecture 1.0)
  ],
  collectCoverageFrom: [
    'src/domain/**/*.ts',
    '!src/**/*.test.ts',
    '!src/**/types.ts',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50,
    },
  },
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
  verbose: true,
  testTimeout: 60000,
};

module.exports = config;
