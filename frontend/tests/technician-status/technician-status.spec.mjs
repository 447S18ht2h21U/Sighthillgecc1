import { test, expect } from '@playwright/test';

const base = process.env.VERIDIAN_TEST_BASE_URL;
const chrome = process.env.VERIDIAN_TEST_CHROME;

if (!base) {
  throw new Error('SAFETY STOP: Isolated test address required.');
}

const url = new URL(base);

if (
  url.protocol !== 'http:' ||
  url.hostname !== '127.0.0.1' ||
  !url.port ||
  url.username ||
  url.password ||
  url.pathname !== '/' ||
  url.search ||
  url.hash
) {
  throw new Error('SAFETY STOP: Invalid isolated test address.');
}

if (chrome !== 'C:/Program Files/Google/Chrome/Application/chrome.exe') {
  throw new Error('SAFETY STOP: Approved local Chrome required.');
}

test.use({
  baseURL: url.origin,
  browserName: 'chromium',
  launchOptions: { executablePath: chrome },
});

test.beforeEach(async ({ page }) => {
  await page.goto('/tests/technician-status/index.html');

  const project = page.getByRole('combobox', {
    name: 'Project',
    exact: true,
  });

  await project.selectOption('11111111-1111-4111-8111-111111111111');

  await expect(page.getByRole('heading', {
    name: 'Active assignments (1)',
  })).toBeVisible();

  await expect(page.getByRole('heading', {
    name: 'Previous assignments (1)',
  })).toBeVisible();
});

test('ACTIVE and ENDED assignment banners display saved statuses', async ({ page }) => {
  await expect(page.getByText('Assignment status: ACTIVE')).toHaveCount(1);
  await expect(page.getByText('Assignment status: ENDED')).toHaveCount(1);

  await expect(page.getByText(
    'This Technician is currently assigned to this project.'
  )).toHaveCount(1);

  await expect(page.getByText(
    'This assignment has ended. Its record is kept for history.'
  )).toHaveCount(1);
});

test('historical assignment retains its end date', async ({ page }) => {
  await expect(page.getByText(/Ended:/)).toHaveCount(1);
  await expect(page.locator('li > strong').filter({ hasText: 'Synthetic Technician (synthetic_technician)' })).toHaveCount(2);
});

test('viewing assignment history never issues write requests', async ({ page }) => {
  const requests = await page.evaluate(
    () => window.veridianTechnicianStatusTest.requests()
  );

  expect(requests.length).toBeGreaterThan(0);
  expect(requests.every(request => request.method === 'GET')).toBe(true);
  expect(requests.some(request =>
    request.path.startsWith('technical-assignment-history/?')
  )).toBe(true);
});
