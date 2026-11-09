import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { chromium } from '@playwright/test';

const port = 5179;
const base = `http://127.0.0.1:${port}/tests/dashboard-workflow-review-4259I.html`;

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
    env: { ...process.env }
  }
);

let serverOutput = '';
server.stdout.on('data', data => { serverOutput += data.toString(); });
server.stderr.on('data', data => { serverOutput += data.toString(); });

let browser;

async function openScenario(page, scenario) {
  await page.goto(`${base}?scenario=${scenario}`);
  await page.locator('summary').click();
  await page.getByRole('list', {
    name: 'Document workflow checks for FICTIONAL-4259I'
  }).waitFor();
}

async function expectStatus(page, title, status) {
  const label = `${title}: ${status}`;
  assert.equal(
    await page.getByText(label, { exact: true }).count(),
    1,
    `Expected exactly one '${label}'`
  );
}

try {
  let ready = false;

  for (let attempt = 0; attempt < 100; attempt++) {
    if (server.exitCode !== null) {
      throw new Error('Isolated Vite server exited before startup.');
    }

    try {
      const response = await fetch(base);
      if (response.ok) {
        ready = true;
        break;
      }
    } catch {
      // Server is still starting.
    }

    await new Promise(resolve => setTimeout(resolve, 100));
  }

  assert.ok(ready, `Isolated Vite server unavailable: ${serverOutput}`);

  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.GECC_BROWSER_EXECUTABLE
  });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 }
  });

  const errors = [];
  page.on('pageerror', error => errors.push(error.message));

  await openScenario(page, 'valid');
  assert.equal(
    await page.getByRole('listitem').count(),
    10,
    'All ten workflow checks must be visible.'
  );
  await expectStatus(page,
    'Current approved Master Sales Record', 'Verified');
  await expectStatus(page,
    'Contract signature evidence', 'Prerequisite check passed');
  await expectStatus(page,
    'Cancellation deadline', 'Blocked');
  await expectStatus(page,
    'Installation payment prerequisite', 'Prerequisite check passed');
  await expectStatus(page,
    'Final Receipt and customer email', 'Not evaluated');
  await expectStatus(page,
    'Completed DocuSign certificate', 'Not evaluated');
  await expectStatus(page,
    'Project completion authorization', 'Blocked');
  console.log('PASS: Valid prerequisite results displayed correctly.');

  await openScenario(page, 'unsafe');
  for (const title of [
    'Full installation authorization',
    'Final Invoice and delivery',
    'Final Receipt and customer email',
    'Completed DocuSign certificate'
  ]) {
    await expectStatus(page, title, 'Not evaluated');
  }
  await expectStatus(page,
    'Project completion authorization', 'Blocked');
  console.log('PASS: Forged operational completion statuses rejected.');

  await openScenario(page, 'invalid');
  await expectStatus(page,
    'Contract signature evidence', 'Not evaluated');
  await expectStatus(page,
    'Current approved Master Sales Record', 'Not evaluated');
  await expectStatus(page,
    'Project completion authorization', 'Not evaluated');
  console.log('PASS: Unauthorized evidence envelope rejected.');

  await openScenario(page, 'missing');
  await expectStatus(page,
    'Contract signature evidence', 'Not evaluated');
  await expectStatus(page,
    'Project completion authorization', 'Not evaluated');
  console.log('PASS: Missing evidence remains not evaluated.');

  assert.deepEqual(errors, [], 'Unexpected browser JavaScript errors.');
  console.log('=== ISOLATED DASHBOARD BROWSER TEST PASSED ===');
} finally {
  await browser?.close();
  server.kill();
}