/** Cấu hình jest (frontend-standards §6). File core. */
module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  testPathIgnorePatterns: ['/node_modules/', '/dist/'],
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|react-native-svg|react-native-body-highlighter|@tanstack/.*|zustand))',
  ],
  collectCoverageFrom: ['src/**/*.{ts,tsx}', '!src/app/**', '!src/**/*.d.ts', '!src/screens/dev/**'],
};
