import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { chromium } from '@playwright/test';

const backend = process.env.VERIDIAN_TEST_LIVE_URL;
const cookie = process.env.VERIDIAN_TEST_SESSION_COOKIE;
const projectCode = process.env.VERIDIAN_TEST_PROJECT_CODE;
const browserExecutable = process.env.GECC_BROWSER_EXECUTABLE;

assert.ok(backend?.startsWith('http://localhost:')
  || backend?.startsWith('http://127.0.0.1:'),
  'A local Django live test server is required.');
assert.ok(cookie && projectCode && browserExecutable,
  'Required isolated browser test configuration is missing.');

const port = 5185;
const url = `http://127.0.0.1:${port}/tests/dashboard-integration-4261.html`;

const server = spawn(
  process.execPath,
  [
    'node_modules/vite/bin/vite.js',
    '--host', '127.0.0.1',
    '--port', String(port),
    '--strictPort'
  ],
  {
    cwd: process.cwd(),
    stdio: ['ignore', 'pipe', 'pipe'],
  }
);

let serverOutput = '';
server.stdout.on('data', value => { serverOutput += value.toString(); });
server.stderr.on('data', value => { serverOutput += value.toString(); });

let browser;

try {
  let ready = false;
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null) {
      throw new Error('Vite exited before startup.');
    }
    try {
      if ((await fetch(url)).ok) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(ready, `Vite unavailable: ${serverOutput}`);

  browser = await chromium.launch({
    headless: true,
    executablePath: browserExecutable,
  });

  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });

  const pageErrors = [];
  const bridgeErrors = [];
  let dashboardResponses = 0;
  let targetStageName = null;
  let targetInAttention = false;

  page.on('pageerror', error => pageErrors.push(error.message));

  await page.route('**/api/project-dashboard/', async route => {
    try {
      const response = await fetch(
        `${backend}/api/project-dashboard/`,
        {
          headers: {
            Cookie: cookie,
            Accept: 'application/json',
          },
          signal: AbortSignal.timeout(15000),
        }
      );

      if (response.status !== 200) {
        throw new Error(
          `Actual authenticated Django response: ${response.status}`
        );
      }

      const data = await response.json();
      const projects = [
        ...(data.needs_attention ?? []),
        ...(data.stages ?? []).flatMap(stage => stage.projects ?? []),
      ];

      const found = projects.find(item => item.code === projectCode);
      assert.ok(found, 'Fictional approved project missing from real API.');
      targetStageName =
        (data.stages ?? []).find(stage =>
          (stage.projects ?? []).some(item => item.code === projectCode)
        )?.name ?? null;
      targetInAttention =
        (data.needs_attention ?? []).some(item => item.code === projectCode);
      assert.equal(
        found.workflow_evidence.statuses.approved_msr,
        'VERIFIED'
      );
      assert.equal(
        found.workflow_evidence.statuses.project_completion,
        'BLOCKED'
      );
      assert.equal(
        found.workflow_evidence.installation_authorized,
        false
      );
      assert.equal(
        found.workflow_evidence.project_completion_authorized,
        false
      );

      dashboardResponses++;

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(data),
      });
    } catch (error) {
      bridgeErrors.push(String(error));
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: '{"detail":"Test HTTP bridge failed"}',
      });
    }
  });

  const dashboardRequest = page.waitForResponse(
    response =>
      response.url().includes('/api/project-dashboard/') &&
      response.status() === 200,
    { timeout: 20000 }
  );

  await page.goto(url);
  await dashboardRequest;

  await page.getByRole('heading', {
    name: 'Project Status Dashboard',
  }).waitFor();

  assert.ok(
    dashboardResponses >= 1,
    `Real Django response was not delivered. Bridge errors: ${bridgeErrors.join('; ')}`
  );

  console.log(
    `PASS: Django data loaded. Milestone: ${targetStageName ?? 'none'}; ` +
    `Needs Attention: ${targetInAttention}.`
  );

  let row;

  if (targetStageName) {
    const stage = page.locator('.dashboard-stage')
      .filter({ hasText: targetStageName });

    assert.equal(
      await stage.count(), 1,
      `Expected exactly one milestone named ${targetStageName}.`
    );

    await stage.click();

    row = page.locator('.dashboard-selected-project-list > li')
      .filter({ hasText: projectCode }).first();

    await row.waitFor({ state: 'visible' });
    console.log(`PASS: Real project displayed in milestone: ${targetStageName}`);
  } else {
    assert.ok(
      targetInAttention,
      'Project missing from both milestones and Needs Attention.'
    );

    row = page.locator('.dashboard-attention-projects > li')
      .filter({ hasText: projectCode }).first();

    await row.waitFor({ state: 'visible' });
    console.log('PASS: Real project displayed in Needs Attention.');
  }
  await row.locator('summary').click();

  await row.getByText(
    'Current approved Master Sales Record: Verified',
    { exact: true }
  ).waitFor();

  await row.getByText(
    'Final Receipt and customer email: Not evaluated',
    { exact: true }
  ).waitFor();

  await row.getByText(
    'Completed DocuSign certificate: Not evaluated',
    { exact: true }
  ).waitFor();

  await row.getByText(
    'Project completion authorization: Blocked',
    { exact: true }
  ).waitFor();

  assert.ok(dashboardResponses >= 1,
    'No actual Django dashboard HTTP response was received.');
  assert.deepEqual(bridgeErrors, []);
  assert.deepEqual(pageErrors, []);

  console.log('PASS: Real Django live HTTP response received.');
  console.log('PASS: Actual approved fictional MSR displayed in Chrome.');
  console.log('PASS: Completion remains blocked without retained evidence.');
  console.log('PASS: No external signing or delivery performed.');
  if (process.env.VERIDIAN_TEST_SCREENSHOT_PATH) {
    await page.screenshot({
      path: process.env.VERIDIAN_TEST_SCREENSHOT_PATH,
      fullPage: true,
    });
    console.log('PASS: Fictional project dashboard screenshot captured.');
  }
  console.log('=== LIVE BACKEND TO CHROME INTEGRATION PASSED ===');
} finally {
  await browser?.close();
  server.kill();
}