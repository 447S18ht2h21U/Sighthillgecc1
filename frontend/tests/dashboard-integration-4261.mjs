import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { chromium } from '@playwright/test';

const port = 5181;
const url = `http://127.0.0.1:${port}/tests/dashboard-integration-4261.html`;

const server = spawn(
  process.execPath,
  ['node_modules/vite/bin/vite.js',
   '--host', '127.0.0.1', '--port', String(port), '--strictPort'],
  { cwd: process.cwd(), stdio: ['ignore', 'pipe', 'pipe'] }
);

let output = '';
server.stdout.on('data', d => { output += d.toString(); });
server.stderr.on('data', d => { output += d.toString(); });

const prerequisiteStatuses = {
  approved_msr: 'VERIFIED',
  contract_signature: 'CHECK_PASSED',
  cancellation_deadline: 'BLOCKED',
  waiting_period: 'NOT_EVALUATED',
  payment_readiness: 'CHECK_PASSED',
  installation_authorization: 'NOT_EVALUATED',
  final_invoice_delivery: 'NOT_EVALUATED',
  receipt_delivery: 'NOT_EVALUATED',
  completed_docusign: 'NOT_EVALUATED',
  project_completion: 'BLOCKED'
};

const evidence = {
  read_only: true,
  evidence_source: 'EXISTING_PREREQUISITE_CHECKS',
  installation_authorized: false,
  project_completion_authorized: false,
  statuses: prerequisiteStatuses
};

function project(id, name, workflow = evidence) {
  return {
    id,
    code: id,
    customer_name: name,
    location: 'Fictional Installation Address',
    state: 'APPROVED',
    guidance: {
      label: 'Review the project',
      detail: 'Informational guidance only.',
      read_only: true
    },
    workflow_evidence: workflow
  };
}

const first = project('MOCK-4261-A', 'Fictional Customer Alpha');
const second = project('MOCK-4261-B', 'Fictional Customer Beta', {
  ...evidence,
  statuses: {
    ...prerequisiteStatuses,
    approved_msr: 'BLOCKED',
    contract_signature: 'BLOCKED'
  }
});
const third = project('MOCK-4261-C', 'Fictional Customer Gamma');

let browser;
try {
  let ready = false;
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null) {
      throw new Error('Test server exited before becoming ready.');
    }
    try {
      const response = await fetch(url);
      if (response.ok) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(ready, `Vite test server unavailable: ${output}`);

  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.GECC_BROWSER_EXECUTABLE
  });

  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 }
  });

  const errors = [];
  page.on('pageerror', error => errors.push(error.message));

  let calls = 0;
  await page.route('**/api/project-dashboard/', async route => {
    calls++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stages: [{
          key: 'completed_customer_record',
          name: 'Approved Customer Record',
          count: 2,
          projects: [first, second]
        }],
        needs_attention: [third]
      })
    });
  });

  await page.goto(url);
  await page.getByRole('heading', {
    name: 'Project Status Dashboard'
  }).waitFor();

  assert.equal(
    await page.getByText('Fictional Customer Gamma').count(), 1
  );
  console.log('PASS: Existing dashboard renders attention projects.');

  await page.locator('.dashboard-stage').first().click();
  await page.getByText('Fictional Customer Alpha').waitFor();
  await page.getByText('Fictional Customer Beta').waitFor();

  assert.equal(
    await page.locator('.dashboard-selected-project-list > li').count(), 2
  );
  console.log('PASS: Milestone stage expands two fictional projects.');

  const firstRow = page.locator('.dashboard-selected-project-list > li')
    .filter({ hasText: 'Fictional Customer Alpha' });

  await firstRow.locator('summary').click();
  await firstRow.getByText(
    'Contract signature evidence: Prerequisite check passed',
    { exact: true }
  ).waitFor();
  await firstRow.getByText(
    'Cancellation deadline: Blocked',
    { exact: true }
  ).waitFor();
  await firstRow.getByText(
    'Project completion authorization: Blocked',
    { exact: true }
  ).waitFor();
  console.log('PASS: Trusted prerequisite labels display within project.');

  const secondRow = page.locator('.dashboard-selected-project-list > li')
    .filter({ hasText: 'Fictional Customer Beta' });

  await secondRow.locator('summary').click();
  await secondRow.getByText(
    'Current approved Master Sales Record: Blocked',
    { exact: true }
  ).waitFor();
  await secondRow.getByText(
    'Final Receipt and customer email: Not evaluated',
    { exact: true }
  ).waitFor();
  console.log('PASS: Distinct project evidence remains separate.');

  const priorCalls = calls;
  await page.getByRole('button', {
    name: 'Refresh dashboard'
  }).click();
  await page.getByRole('heading', {
    name: 'Project Status Dashboard'
  }).waitFor();
  assert.ok(calls > priorCalls, 'Refresh must request dashboard again.');
  console.log('PASS: Dashboard refresh requests updated information.');

  assert.deepEqual(errors, [], 'Unexpected browser JavaScript errors.');
  console.log('=== STEP 4261 BROWSER INTEGRATION PASSED ===');
} finally {
  await browser?.close();
  server.kill();
}