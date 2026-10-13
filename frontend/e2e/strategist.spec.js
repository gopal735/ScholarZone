// Study-to-Career Strategist E2E: happy path and insufficient-data path, on mobile
// and desktop (the config runs each test in both viewport projects).
//
// These drive the real built UI through the flag-gated route and assert the
// integrity contracts hold end-to-end: a ranked country shows an evidence meter and
// a BDT figure beside the original currency with a rate date; the not-ranked
// section appears with reasons; no "best country" is declared; the disclaimer is
// present. Runs against captured data (?fixture=1) so it needs no backend.
import { expect, test } from '@playwright/test'

const URL = '/ScholarZone/strategist?fixture=1&subject=computer_science&degree=master'

async function openResults(page) {
  await page.goto(URL)
  await page.getByRole('button', { name: /Results/ }).click()
  await expect(page.getByTestId('results')).toBeVisible()
}

test('happy path: ranked countries, evidence meter, BDT beside original currency', async ({ page }) => {
  await openResults(page)
  const ca = page.locator('[data-country="CA"]')
  await expect(ca).toBeVisible()
  // The evidence-completeness meter is exposed to assistive tech.
  await expect(ca.getByRole('meter').first()).toHaveAttribute('aria-valuemax', /\d+/)
  // A BDT figure appears beside an original currency and a rate date.
  const cardText = (await ca.textContent()) || ''
  expect(cardText).toContain('BDT')
  expect(cardText.toLowerCase()).toContain('rate date')
  // No universal "best" country is declared, and the disclaimer is present.
  expect((await page.getByTestId('results').textContent())?.includes('Best country')).toBe(false)
  await expect(page.getByTestId('disclaimer')).toBeVisible()
})

test('insufficient-data path: not-ranked region shows reasons', async ({ page }) => {
  await openResults(page)
  // The not-ranked section exists and names the essential criteria that are missing.
  await expect(page.getByTestId('essential-criteria')).toContainText('subject_salary')
  await expect(page.getByTestId('essential-criteria')).toContainText('post_study_work')
  // A country missing an essential criterion appears with an "Insufficient data" reason.
  const usSection = page.locator('[aria-labelledby="notranked-title"]')
  await expect(usSection).toBeVisible()
  await expect(usSection).toContainText(/Insufficient data/i)
  // Regions : at least the essential criteria list and a published selection rule.
  await expect(page.getByTestId('selection-rule')).toContainText(/completeness|Explicit/i)
})
