import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    testTimeout: 120000,
    hookTimeout: 120000,
    globalSetup: "./tests/globalSetup.ts",
    maxThreads: 1,
    minThreads: 1,
    sequence: {
      concurrent: false,
    },
  },
});
