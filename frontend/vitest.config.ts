import { defineConfig } from 'vitest/config'

// Test composable & client murni (tanpa DOM), jadi environment default node
// sudah cukup. File uji ditaruh di tests/ agar tak ikut `vue-tsc -b`.
export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
  },
})
