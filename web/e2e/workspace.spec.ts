import { expect, test } from '@playwright/test'

const viewports = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'laptop', width: 1024, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
  { name: 'narrow-mobile', width: 360, height: 800 },
]

for (const viewport of viewports) {
  test(`${viewport.name}: configure, stream, complete without overflow`, async ({ page }) => {
    await page.setViewportSize(viewport)
    const consoleErrors: string[] = []
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
    await page.goto('/')
    if (viewport.width < 760) await page.getByLabel('Open configuration').click()
    await page.screenshot({ path: `test-results/${viewport.name}-configuration.png`, fullPage: true })
    await page.getByRole('button', { name: 'Resolve' }).click()
    await expect(page.locator('.identity-block').getByText('SPDR S&P 500 ETF Trust')).toBeVisible()
    await page.getByRole('button', { name: /Start analysis/ }).click()
    await expect(page.getByText('running', { exact: true }).first()).toBeVisible()
    await page.screenshot({ path: `test-results/${viewport.name}-running.png`, fullPage: true })
    await expect(page.getByText('completed', { exact: true }).first()).toBeVisible({ timeout: 12_000 })
    await expect(page.getByText('Adjusted price vs benchmark')).toBeVisible()
    await page.screenshot({ path: `test-results/${viewport.name}-completed.png`, fullPage: true })
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(overflow).toBe(false)
    expect(consoleErrors).toEqual([])
  })
}

test('cancel leaves controls usable and stock hides fund panels', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Symbol').fill('SLOW')
  await page.getByRole('button', { name: 'Resolve' }).click()
  await page.getByRole('button', { name: /Start analysis/ }).click()
  await page.getByRole('button', { name: /Cancel analysis/ }).click()
  await expect(page.getByText('cancelled', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: /Start analysis/ })).toBeEnabled()

  await page.getByRole('button', { name: 'stock' }).click()
  await page.getByLabel('Symbol').fill('AAPL')
  await page.getByRole('button', { name: 'Resolve' }).click()
  await expect(page.locator('.identity-block').getByText('Apple Inc.')).toBeVisible()
  await expect(page.getByText('Top holdings')).toHaveCount(0)
})

test('mobile renders explicit missing holdings state', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByLabel('Open configuration').click()
  await page.getByLabel('Symbol').fill('EMPTY')
  await page.getByRole('button', { name: 'Resolve' }).click()
  await page.getByRole('button', { name: /Start analysis/ }).click()
  await expect(page.getByText('completed', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Holdings unavailable from the provider.')).toBeVisible()
  await page.screenshot({ path: 'test-results/mobile-missing-data.png', fullPage: true })
})

test('desktop renders safe provider failure and preserves form', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.getByLabel('Symbol').fill('FAIL')
  await page.getByRole('button', { name: 'Resolve' }).click()
  await page.getByRole('button', { name: /Start analysis/ }).click()
  await expect(page.getByText('Provider is temporarily unavailable')).toBeVisible()
  await expect(page.getByLabel('Symbol')).toHaveValue('FAIL')
  await page.screenshot({ path: 'test-results/desktop-failure.png', fullPage: true })
})
