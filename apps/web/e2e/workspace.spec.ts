import { expect, test } from '@playwright/test'

/**
 * Real user workflows across the seven tabs. The suite assumes a fresh API
 * process: run order matters for a few assertions (e.g. session dashboard).
 */

test.describe.configure({ mode: 'serial' })

let page = null as null | import('@playwright/test').Page

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage()
  await page.goto('/')
  await page.waitForLoadState('domcontentloaded')
})

test.afterAll(async () => {
  await page?.close()
})

const clickTab = async (tab: string): Promise<void> => {
  if (page === null) throw new Error('page not ready')
  await page.evaluate((n) => {
    const el = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === n)
    if (el) el.click()
  }, tab)
}

test('workspace loads with all seven tabs and Sparky', async () => {
  if (page === null) throw new Error('page not ready')
  for (const name of ['Circuit', '8086 CPU', 'Verify', 'FSM', 'Faults', 'Explain', 'Visuals']) {
    const tabButton = page.locator('.tab-btn', { hasText: name })
    await expect(tabButton.first()).toBeVisible()
  }
  await expect(page.locator('.sparky-bot')).toBeVisible()
})

test('circuit simulates and truth table opens', async () => {
  if (page === null) throw new Error('page not ready')
  await clickTab('Circuit')
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Truth table')
    if (el) el.click()
  })
  await expect(page.locator('.tt-table')).toBeVisible()
  await expect(page.locator('body')).toContainText('EXHAUSTIVE')
  // close the modal like a real user would
  await page.evaluate(() => document.querySelector('.modal-close')?.click())
  await expect(page.locator('.tt-table')).toHaveCount(0)
})

test('8086 runs the example and halts cleanly', async () => {
  if (page === null) throw new Error('page not ready')
  await clickTab('8086 CPU')
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Run'))
    if (el) el.click()
  })
  await expect(page.locator('.trace-table')).toBeVisible()
  await expect(page.locator('body')).toContainText('HLT')
})

test('verify a combinational invariant', async () => {
  if (page === null) throw new Error('page not ready')
  await clickTab('Verify')
  await page.locator('input[aria-label="Property expression"]').fill('!(sum & carry_out)')
  await page.locator('.verify-form button', { hasText: 'Verify' }).click()
  await expect(page.locator('.verdict-chip')).toBeVisible()
})

test('FSM lab simulates and shows the state graph', async () => {
  if (page === null) throw new Error('page not ready')
  await clickTab('FSM')
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Simulate')
    if (el) el.click()
  })
  await expect(page.locator('.fsm-svg')).toBeVisible()
  await expect(page.locator('.counterexample')).toContainText('cycles')
})

test('fault lab runs a detection experiment', async () => {
  if (page === null) throw new Error('page not ready')
  await clickTab('Faults')
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Run detection experiment'))
    if (el) el.click()
  })
  await expect(page.locator('.verdict-chip').first()).toBeVisible()
})

test('Sparky answers a grounded question', async () => {
  if (page === null) throw new Error('page not ready')
  await page.evaluate(() => {
    const fab = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === '💬')
    if (fab) fab.click()
  })
  await page.locator('.sparky-chat-input input').fill('what is a flip-flop?')
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Ask')
    if (btn) btn.click()
  })
  await expect(page.locator('.sparky-msg-sparky').last()).toContainText('flip-flop')
  await expect(page.locator('.sparky-badge-grounded').last()).toBeVisible()
})

test('visuals dashboard renders session charts', async () => {
  if (page === null) throw new Error('page not ready')
  await clickTab('Visuals')
  await expect(page.locator('.stat-tile')).toHaveCount(4)
  await expect(page.locator('.pipeline-stage')).toHaveCount(9)
  await expect(page.locator('.donut-seg').first()).toBeVisible()
})

test('API contract: error envelope shape on invalid input', async ({ request }) => {
  const response = await request.post('/api/8086/run', {
    data: { source: 'FLY AX, 1', max_steps: 10 },
  })
  expect(response.status()).toBe(400)
  const body = await response.json()
  expect(body.detail.code).toBe('ASM_ERROR')
  expect(body.detail.category).toBe('UNKNOWN_MNEMONIC')
  expect(typeof body.detail.message).toBe('string')
})

test('API contract: unknown route is a structured 404', async ({ request }) => {
  const response = await request.get('/api/nonexistent')
  expect(response.status()).toBe(404)
})
