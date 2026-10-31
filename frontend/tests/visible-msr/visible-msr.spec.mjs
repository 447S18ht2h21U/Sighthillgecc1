import { test, expect } from '@playwright/test';

const baseURL = process.env.VERIDIAN_TEST_BASE_URL;

if (
  !baseURL ||
  !/^http:\/\/127\.0\.0\.1:\d+$/.test(baseURL)
) {
  throw new Error('SAFETY STOP: Isolated test URL is required.');
}

test.use({
  baseURL,
  browserName: 'chromium',
  launchOptions: {
    executablePath: process.env.VERIDIAN_TEST_CHROME,
  },
});

async function pending(page) {
  return page.evaluate(() => window.veridianMSRTest.pending());
}

async function settle(page, index, result) {
  await page.evaluate(
    ({ index, result }) => window.veridianMSRTest.resolve(index, result),
    { index, result },
  );
}

async function reject(page, index, message) {
  await page.evaluate(
    ({ index, message }) => window.veridianMSRTest.reject(index, message),
    { index, message },
  );
}

async function openHarness(page) {
  await page.goto('/tests/visible-msr/index.html');
  await expect(
    page.getByRole('region', { name: 'Visible Master Sales Records' }),
  ).toBeVisible();
  await expect.poll(async () => (await pending(page)).length).toBe(1);
}

test('loads authorized synthetic records and displays read-only details', async ({ page }) => {
  await openHarness(page);
  await expect(page.getByText('Loading Master Sales Records...')).toBeVisible();

  await settle(page, 0, 'first');

  await expect(page.getByText('3 records available. Page 1.')).toBeVisible();
  await expect(page.getByRole('heading', {
    name: 'Synthetic Customer Alpha',
  })).toBeVisible();
  await expect(page.getByRole('heading', {
    name: 'Synthetic Customer Beta',
  })).toBeVisible();

  await page.getByRole('button', {
    name: 'View record for Synthetic Customer Alpha, version 2',
  }).click();

  const details = page.getByRole('article', {
    name: 'Read-only Master Sales Record',
  });

  await expect(details).toContainText('Fictional Site Alpha');
  await expect(details).toContainText('Synthetic revision for browser testing');
  await expect(details).toContainText('Read-only record.');
  await page.getByRole('button', { name: 'Close record' }).click();
  await expect(details).toHaveCount(0);
});

test('searches only the current page', async ({ page }) => {
  await openHarness(page);
  await settle(page, 0, 'first');

  await expect(page.getByText('3 records available. Page 1.')).toBeVisible();

  await page.getByRole('searchbox', { name: 'Search this page' })
    .fill('Alpha');

  await expect(page.getByRole('button', {
    name: 'View record for Synthetic Customer Alpha, version 2',
  })).toBeVisible();

  await expect(page.getByRole('button', {
    name: 'View record for Synthetic Customer Beta, version 3',
  })).toHaveCount(0);

  await page.getByRole('searchbox', { name: 'Search this page' })
    .fill('Gamma');

  await expect(page.getByText(
    'No records on this page match your search.',
  )).toBeVisible();
});

test('supports forward and backward pagination', async ({ page }) => {
  await openHarness(page);
  await settle(page, 0, 'first');

  await expect(page.getByText('3 records available. Page 1.')).toBeVisible();

  await page.getByRole('button', { name: 'Next page' }).click();

  await expect.poll(async () => (await pending(page)).length).toBe(2);
  await expect((await pending(page))[1].path).toBe('visible-msrs/?page=2');

  await settle(page, 1, 'second');

  await expect(page.getByText('3 records available. Page 2.')).toBeVisible();
  await expect(page.getByRole('heading', {
    name: 'Synthetic Customer Gamma',
  })).toBeVisible();

  await page.getByRole('button', { name: 'Previous page' }).click();

  await expect.poll(async () => (await pending(page)).length).toBe(3);
  await expect((await pending(page))[2].path).toBe('visible-msrs/?page=1');

  await settle(page, 2, 'first');
  await expect(page.getByText('3 records available. Page 1.')).toBeVisible();
});

test('shows a clear empty-result message', async ({ page }) => {
  await openHarness(page);
  await settle(page, 0, 'empty');

  await expect(page.getByText('0 records available. Page 1.')).toBeVisible();
  await expect(page.getByText(
    'No Master Sales Records are available.',
  )).toBeVisible();
  await expect(page.getByRole('button', {
    name: 'Next page',
  })).toBeDisabled();
});

test('does not display records after an access-denied request', async ({ page }) => {
  await openHarness(page);
  await reject(page, 0, 'HTTP 403: Access denied');

  await expect(page.getByRole('alert')).toContainText(
    'Master Sales Records could not be loaded.',
  );

  await expect(page.getByRole('button', {
    name: /View record for/,
  })).toHaveCount(0);
});

test('refreshes the current page and clears old details while loading', async ({ page }) => {
  await openHarness(page);
  await settle(page, 0, 'first');

  await expect(page.getByText('3 records available. Page 1.')).toBeVisible();

  await page.getByRole('button', {
    name: 'View record for Synthetic Customer Alpha, version 2',
  }).click();

  await expect(page.getByRole('article', {
    name: 'Read-only Master Sales Record',
  })).toBeVisible();

  await page.getByRole('button', { name: 'Refresh records' }).click();

  await expect.poll(async () => (await pending(page)).length).toBe(2);
  await expect(page.getByRole('article', {
    name: 'Read-only Master Sales Record',
  })).toHaveCount(0);

  await expect(page.getByRole('button', {
    name: /View record for/,
  })).toHaveCount(0);

  await settle(page, 1, 'empty');
  await expect(page.getByText('0 records available. Page 1.')).toBeVisible();
});

test('ignores obsolete responses after pagination changes', async ({ page }) => {
  await openHarness(page);
  await settle(page, 0, 'first');

  await expect(page.getByText('3 records available. Page 1.')).toBeVisible();
  await page.getByRole('button', { name: 'Next page' }).click();

  await expect.poll(async () => (await pending(page)).length).toBe(2);

  await page.getByRole('button', { name: 'Refresh records' })
    .waitFor({ state: 'visible' });

  await settle(page, 1, 'second');
  await expect(page.getByText('3 records available. Page 2.')).toBeVisible();
});

test('offers no editing, approval, or signing controls', async ({ page }) => {
  await openHarness(page);
  await settle(page, 0, 'first');

  await expect(page.getByText('3 records available. Page 1.')).toBeVisible();

  await page.getByRole('button', {
    name: 'View record for Synthetic Customer Alpha, version 2',
  }).click();

  for (const label of [
    /save/i,
    /edit/i,
    /approve/i,
    /sign/i,
    /delete/i,
    /issue payment/i,
  ]) {
    await expect(page.getByRole('button', { name: label })).toHaveCount(0);
  }

  const methods = (await pending(page)).map(request => request.method);
  expect(methods).toEqual(['GET']);
});