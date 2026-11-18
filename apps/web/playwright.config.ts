import { defineConfig } from '@playwright/test'

/**
 * E2E configuration. Tests run against a full-stack origin (UI + API on the
 * same port):
 *  - local dev:  http://localhost:5173 (vite proxies /api to :8000)
 *  - CI:         the API process serves the built UI on :8000 (SERVE_WEB_DIST)
 * Override with E2E_BASE_URL if your stack runs elsewhere.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    viewport: { width: 1280, height: 860 },
  },
  expect: { timeout: 10_000 },
  workers: 1, // one deterministic session: tests share engine state via the API
  reporter: [['list']],
})
