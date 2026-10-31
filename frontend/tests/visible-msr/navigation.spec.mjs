import { test, expect } from '@playwright/test';

const baseURL = process.env.VERIDIAN_TEST_BASE_URL;
const chrome = process.env.VERIDIAN_TEST_CHROME;

if (!baseURL || !/^http:\/\/127\.0\.0\.1:\d+$/.test(baseURL)) {
  throw new Error('SAFETY STOP: Isolated localhost URL required.');
}

if (!chrome || !chrome.endsWith('/chrome.exe')) {
  throw new Error('SAFETY STOP: Approved Chrome required.');
}

test.use({
  baseURL,
  browserName: 'chromium',
  launchOptions: { executablePath: chrome },
});

const authorizedRoles = [
  'CEO',
  'COMPTROLLER',
  'SALES_MANAGER',
  'INSTALLATION_MANAGER',
  'SALES_ASSOCIATE',
  'TECHNICIAN',
];

const excludedRoles = [
  'ACCOUNTS_PAYABLE_ASSOCIATE',
  'DATABASE_ADMINISTRATOR',
];

const syntheticMSR = {
  id: '11111111-1111-4111-8111-111111111111',
  number: 2,
  status: 'APPROVED',
  snapshot: {
    customer: 'Synthetic Navigation Customer',
    scope: 'Fictional installation',
  },
  revision_reason: '',
  approved_at: '2026-10-01T12:00:00Z',
};

function responseFor(path, role) {
  if (path === '/api/csrf/') {
    return { csrfToken: 'synthetic-csrf-token' };
  }

  if (path === '/api/activity/') {
    return {};
  }

  if (path === '/api/me/') {
    return {
      id: '99999999-9999-4999-8999-999999999999',
      username: 'synthetic_user',
      role,
      first_name: 'Synthetic',
      last_name: 'User',
    };
  }

  if (path.startsWith('/api/customers/')) {
    return {
      count: 0,
      next: null,
      previous: null,
      results: [],
    };
  }

  if (path === '/api/directory/') {
    return [];
  }

  if (
    path.startsWith('/api/visible-msrs/') ||
    path.startsWith('/api/marketing-msrs/')
  ) {
    return {
      count: 1,
      next: null,
      previous: null,
      results: [syntheticMSR],
    };
  }

  return null;
}

async function openApplication(page, role) {
  const apiCalls = [];

  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname + url.search;

    apiCalls.push({
      path,
      method: request.method(),
    });

    const result = responseFor(path, role);

    if (result === null) {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Synthetic endpoint not available.',
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(result),
    });
  });

  await page.goto('/tests/visible-msr/navigation.html');

  await expect(page.getByRole('button', {
    name: 'Sign out',
  })).toBeVisible();

  return apiCalls;
}

for (const role of authorizedRoles) {
  test(`${role} can open the role-scoped read-only MSR directory`, async ({ page }) => {
    const calls = await openApplication(page, role);

    await page.getByRole('button', {
      name: 'View Master Sales Records',
      exact: true,
    }).click();

    await expect(page.getByRole('region', {
      name: 'Visible Master Sales Records',
    })).toBeVisible();

    await expect(page.getByText(
      '1 record available. Page 1.',
    )).toBeVisible();

    await expect(page.getByRole('heading', {
      name: 'Synthetic Navigation Customer',
    })).toBeVisible();

    expect(calls.some(call =>
      call.path.startsWith('/api/visible-msrs/') &&
      call.method === 'GET'
    )).toBe(true);

    await expect(page.getByText(
      'Your commercial workspace',
    )).toHaveCount(0);

    await expect(page.getByRole('button', {
      name: 'Create project',
      exact: true,
    })).toHaveCount(0);

    await expect(page.getByRole('button', {
      name: 'Add customer',
      exact: true,
    })).toHaveCount(0);
  });
}

for (const role of excludedRoles) {
  test(`${role} has no Visible MSR navigation`, async ({ page }) => {
    const calls = await openApplication(page, role);

    await expect(page.getByRole('button', {
      name: 'View Master Sales Records',
      exact: true,
    })).toHaveCount(0);

    await expect(page.getByRole('region', {
      name: 'Visible Master Sales Records',
    })).toHaveCount(0);

    expect(calls.some(call =>
      call.path.startsWith('/api/visible-msrs/')
    )).toBe(false);
  });
}

test('Marketing keeps its existing MSR directory', async ({ page }) => {
  const calls = await openApplication(page, 'MARKETING');

  await expect(page.getByRole('region', {
    name: 'Marketing Master Sales Records',
  })).toBeVisible();

  await expect(page.getByRole('button', {
    name: 'View Master Sales Records',
    exact: true,
  })).toHaveCount(0);

  await expect(page.getByText(
    '1 record available. Page 1.',
  )).toBeVisible();

  expect(calls.some(call =>
    call.path.startsWith('/api/marketing-msrs/') &&
    call.method === 'GET'
  )).toBe(true);
});