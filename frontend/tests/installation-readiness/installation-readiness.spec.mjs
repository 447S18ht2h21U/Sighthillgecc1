import { test, expect } from '@playwright/test';

const isolatedURL = process.env.VERIDIAN_TEST_BASE_URL;

if (!isolatedURL) {
  throw new Error(
    'SAFETY STOP: Run these browser tests through run-isolated.mjs.'
  );
}

const parsedURL = new URL(isolatedURL);

if (
  parsedURL.protocol !== 'http:' ||
  parsedURL.hostname !== '127.0.0.1' ||
  !parsedURL.port ||
  parsedURL.username ||
  parsedURL.password ||
  parsedURL.pathname !== '/' ||
  parsedURL.search ||
  parsedURL.hash
) {
  throw new Error(
    'SAFETY STOP: Browser tests require an isolated 127.0.0.1 server.'
  );
}

const chromeExecutable = process.env.VERIDIAN_TEST_CHROME;

if (chromeExecutable !== 'C:/Program Files/Google/Chrome/Application/chrome.exe') {
  throw new Error(
    'SAFETY STOP: Browser tests require the approved local Chrome executable.'
  );
}

test.use({
  baseURL: parsedURL.origin,
  browserName: 'chromium',
  launchOptions: { executablePath: chromeExecutable },
});

const A = '11111111-1111-4111-8111-111111111111';
const B = '22222222-2222-4222-8222-222222222222';

async function pending(page, fragment, method = 'GET') {
  await expect.poll(async () => {
    return page.evaluate(({ fragment, method }) =>
      window.veridianTest.pending().filter(
        r => !r.settled && r.path.includes(fragment) && r.method === method
      ).length, { fragment, method });
  }).toBeGreaterThan(0);

  return page.evaluate(({ fragment, method }) => {
    const requests = window.veridianTest.pending();
    const match = requests.find(
      r => !r.settled && r.path.includes(fragment) && r.method === method
    );
    if (!match) throw new Error('Synthetic request not found.');
    return match.index;
  }, { fragment, method });
}

async function resolve(page, index, value) {
  await page.evaluate(({ index, value }) => {
    window.veridianTest.resolve(index, value);
  }, { index, value });
}

async function reject(page, index, message) {
  await page.evaluate(({ index, message }) => {
    window.veridianTest.reject(index, message);
  }, { index, message });
}

async function readiness(page, id, eligible) {
  return page.evaluate(({ id, eligible }) =>
    window.veridianTest.ready(id, eligible), { id, eligible });
}

test.beforeEach(async ({ page }) => {
  await page.goto('/tests/installation-readiness/index.html');
  await expect(page.getByRole('heading', {
    name: 'Schedule an installation',
  }).first()).toBeVisible();
  await expect(page.getByRole('option', {
    name: /TEST-PROJECT-A/,
  })).toHaveCount(1);
});

test('outdated project readiness cannot overwrite current project', async ({ page }) => {
  const project = page.getByRole('combobox', { name: 'Project', exact: true });

  await project.selectOption(A);
  const older = await pending(page, `${A}/installation-eligibility/`);

  await project.selectOption(B);
  const newer = await pending(page, `${B}/installation-eligibility/`);

  await resolve(page, newer, await readiness(page, B, true));

  await expect(page.getByText('READY FOR INSTALLATION', { exact: true })).toBeVisible();
  await resolve(page, older, await readiness(page, A, false));

  await expect(page.getByText('READY FOR INSTALLATION', { exact: true })).toBeVisible();
  await expect(project).toHaveValue(B);
  await expect(page.getByText('NOT READY FOR INSTALLATION')).toHaveCount(0);
});

test('failed pre-submit check prevents scheduling and clears loading', async ({ page }) => {
  await page.getByRole('combobox', { name: 'Project', exact: true }).selectOption(A);
  const initial = await pending(page, `${A}/installation-eligibility/`);
  await resolve(page, initial, await readiness(page, A, true));

  await expect(page.getByText('READY FOR INSTALLATION', { exact: true })).toBeVisible();
  await page.getByLabel('Installation date').fill('2026-11-15');
  await page.getByRole('combobox', {
    name: 'Installation Manager',
    exact: true,
  }).selectOption('33333333-3333-4333-8333-333333333333');
  await page.getByRole('button', { name: 'Create schedule' }).click();

  const preSubmit = await pending(page, `${A}/installation-eligibility/`);
  await reject(page, preSubmit, 'Synthetic readiness service unavailable.');

  await expect(page.getByRole('alert')).toContainText(
    'Synthetic readiness service unavailable.'
  );
  await expect(page.getByText('Checking installation requirements')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Create schedule' })).toBeDisabled();

  const posts = await page.evaluate(() =>
    window.veridianTest.pending().filter(r =>
      r.method === 'POST' && r.path === 'installation-schedules/'
    ).length
  );
  expect(posts).toBe(0);
});

test('fresh eligibility blocker prevents schedule submission', async ({ page }) => {
  await page.getByRole('combobox', { name: 'Project', exact: true }).selectOption(A);
  const initial = await pending(page, `${A}/installation-eligibility/`);
  await resolve(page, initial, await readiness(page, A, true));

  await page.getByLabel('Installation date').fill('2026-11-15');
  await page.getByRole('combobox', {
    name: 'Installation Manager',
    exact: true,
  }).selectOption('33333333-3333-4333-8333-333333333333');
  await page.getByRole('button', { name: 'Create schedule' }).click();

  const fresh = await pending(page, `${A}/installation-eligibility/`);
  await resolve(page, fresh, await readiness(page, A, false));

  await expect(page.getByText('NOT READY FOR INSTALLATION')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Scheduling is blocked');
  await expect(page.getByRole('button', { name: 'Create schedule' })).toBeDisabled();

  const posts = await page.evaluate(() =>
    window.veridianTest.pending().filter(r =>
      r.method === 'POST' && r.path === 'installation-schedules/'
    ).length
  );
  expect(posts).toBe(0);
});

test('synthetic request cannot be settled twice', async ({ page }) => {
  await page.getByRole('combobox', { name: 'Project', exact: true }).selectOption(A);
  const index = await pending(page, `${A}/installation-eligibility/`);
  await resolve(page, index, await readiness(page, A, true));

  const error = await page.evaluate(index => {
    try {
      window.veridianTest.resolve(index, {});
      return '';
    } catch (e) {
      return String(e);
    }
  }, index);

  expect(error).toContain('already settled');
});


test('refresh makes one readiness request and reports refreshed', async ({ page }) => {
  const project = page.getByRole('combobox', {
    name: 'Project',
    exact: true,
  });

  await project.selectOption(A);
  const initial = await pending(page, `${A}/installation-eligibility/`);
  await resolve(page, initial, await readiness(page, A, true));

  await expect(page.getByText('READY FOR INSTALLATION', { exact: true })).toBeVisible();

  const before = await page.evaluate(id =>
    window.veridianTest.pending().filter(r =>
      r.method === 'GET' &&
      r.path === `operational-projects/${id}/installation-eligibility/`
    ).length, A);

  expect(before).toBe(1);

  await page.getByRole('button', { name: 'Refresh installation status', exact: true }).click();

  const refreshRequest = await pending(
    page,
    `${A}/installation-eligibility/`
  );

  await resolve(page, refreshRequest, await readiness(page, A, true));

  await expect(page.getByText('Installation information refreshed.')).toBeVisible();
  await expect(page.getByText('READY FOR INSTALLATION', { exact: true })).toBeVisible();

  const after = await page.evaluate(id =>
    window.veridianTest.pending().filter(r =>
      r.method === 'GET' &&
      r.path === `operational-projects/${id}/installation-eligibility/`
    ).length, A);

  expect(after).toBe(2);

  const posts = await page.evaluate(() =>
    window.veridianTest.pending().filter(r =>
      r.method === 'POST' && r.path === 'installation-schedules/'
    ).length
  );

  expect(posts).toBe(0);
});


const SCHEDULE_A = '44444444-4444-4444-8444-444444444444';
const SCHEDULE_B = '55555555-5555-4555-8555-555555555555';

async function statusPosts(page) {
  return page.evaluate(() =>
    window.veridianTest.pending().filter(request =>
      request.method === 'POST' &&
      /^installation-schedules\/[^/]+\/(complete|cancel)\/$/.test(request.path)
    )
  );
}

test('go back cancels completion confirmation without a request', async ({ page }) => {
  const row = page.getByRole('row').filter({ hasText: 'TEST-PROJECT-A' });

  await row.getByRole('button', {
    name: 'Mark operationally complete',
  }).click();

  const confirmation = row.getByRole('group', {
    name: 'Confirm installation status change',
  });

  await expect(confirmation).toContainText('Confirm installation completion');
  await expect(confirmation).toContainText('TEST-PROJECT-A');
  await expect(confirmation).toContainText('Synthetic Customer A');

  expect(await statusPosts(page)).toHaveLength(0);

  await confirmation.getByRole('button', { name: 'Go back' }).click();

  await expect(confirmation).toHaveCount(0);
  expect(await statusPosts(page)).toHaveLength(0);
});

test('keep installation scheduled sends no cancellation request', async ({ page }) => {
  const row = page.getByRole('row').filter({ hasText: 'TEST-PROJECT-B' });

  await row.getByRole('button', { name: 'Cancel', exact: true }).click();

  const confirmation = row.getByRole('group', {
    name: 'Confirm installation status change',
  });

  await expect(confirmation).toContainText('Confirm installation cancellation');
  await expect(confirmation).toContainText('TEST-PROJECT-B');
  await expect(confirmation).toContainText('Synthetic Customer B');

  expect(await statusPosts(page)).toHaveLength(0);

  await confirmation.getByRole('button', {
    name: 'Keep installation scheduled',
  }).click();

  await expect(confirmation).toHaveCount(0);
  expect(await statusPosts(page)).toHaveLength(0);
});

test('explicit completion confirmation targets the selected installation', async ({ page }) => {
  const row = page.getByRole('row').filter({ hasText: 'TEST-PROJECT-A' });

  await row.getByRole('button', {
    name: 'Mark operationally complete',
  }).click();

  expect(await statusPosts(page)).toHaveLength(0);

  const confirmation = row.getByRole('group', {
    name: 'Confirm installation status change',
  });

  await confirmation.getByRole('button', {
    name: 'Confirm completion',
    exact: true,
  }).click();

  const requestIndex = await pending(
    page,
    `installation-schedules/${SCHEDULE_A}/complete/`,
    'POST'
  );

  expect(requestIndex).toBeGreaterThanOrEqual(0);

  const posts = await statusPosts(page);
  expect(posts).toHaveLength(1);
  expect(posts[0].path).toBe(
    `installation-schedules/${SCHEDULE_A}/complete/`
  );
});

test('explicit cancellation confirmation targets the selected installation', async ({ page }) => {
  const row = page.getByRole('row').filter({ hasText: 'TEST-PROJECT-B' });

  await row.getByRole('button', { name: 'Cancel', exact: true }).click();

  expect(await statusPosts(page)).toHaveLength(0);

  const confirmation = row.getByRole('group', {
    name: 'Confirm installation status change',
  });

  await confirmation.getByRole('button', {
    name: 'Confirm cancellation',
    exact: true,
  }).click();

  const requestIndex = await pending(
    page,
    `installation-schedules/${SCHEDULE_B}/cancel/`,
    'POST'
  );

  expect(requestIndex).toBeGreaterThanOrEqual(0);

  const posts = await statusPosts(page);
  expect(posts).toHaveLength(1);
  expect(posts[0].path).toBe(
    `installation-schedules/${SCHEDULE_B}/cancel/`
  );
});


test('refresh removes confirmation when installation was cancelled elsewhere', async ({ page }) => {
  const row = page.getByRole('row').filter({ hasText: 'TEST-PROJECT-A' });

  await row.getByRole('button', {
    name: 'Mark operationally complete',
  }).click();

  const confirmation = row.getByRole('group', {
    name: 'Confirm installation status change',
  });

  await expect(confirmation).toContainText('Confirm installation completion');
  await expect(confirmation).toContainText('TEST-PROJECT-A');

  expect(await statusPosts(page)).toHaveLength(0);

  await page.evaluate(scheduleId => {
    window.veridianTest.setScheduleStatus(scheduleId, 'CANCELLED');
  }, SCHEDULE_A);

  await page.getByRole('button', {
    name: 'Refresh installation status',
    exact: true,
  }).click();

  await expect(page.getByText(
    'Installation information refreshed.'
  )).toBeVisible();

  await expect(confirmation).toHaveCount(0);

  await expect(row.getByRole('cell', {
    name: 'CANCELLED',
    exact: true,
  })).toBeVisible();

  await expect(row.getByRole('button', {
    name: 'Confirm completion',
  })).toHaveCount(0);

  await expect(row.getByRole('button', {
    name: 'Mark operationally complete',
  })).toHaveCount(0);

  expect(await statusPosts(page)).toHaveLength(0);
});
