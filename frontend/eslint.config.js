// Cấu hình eslint (frontend-standards §5, §7). File core.
// Quy tắc kích thước để mức "warn": cổng `standards` của agent flow đọc các cảnh báo này.
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['dist/*', 'node_modules/*', 'coverage/*', '.expo/*'],
  },
  {
    rules: {
      'max-lines': ['warn', { max: 300, skipBlankLines: true, skipComments: true }],
      'max-lines-per-function': ['warn', { max: 80, skipBlankLines: true, skipComments: true, IIFEs: true }],
      'max-params': ['warn', 4],
      'max-depth': ['warn', 3],
      complexity: ['warn', 10],
      'no-console': 'error',
    },
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    rules: { '@typescript-eslint/no-explicit-any': 'error' },
  },
  {
    files: ['**/*.test.ts', '**/*.test.tsx', '__tests__/**'],
    rules: { 'max-lines': 'off', 'max-lines-per-function': 'off' },
  },
]);
