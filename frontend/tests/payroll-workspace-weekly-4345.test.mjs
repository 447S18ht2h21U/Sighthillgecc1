import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { createServer } from 'vite';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(frontend, '..');
const require = createRequire(resolve(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

let vite;
let Workspace;
let weekly;

before(async () => {
  vite = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: {
      noDiscovery: true,
      entries: [],
      include: [],
    },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });

  const mod = await vite.ssrLoadModule(
    '/tests/payroll-workspace-weekly-4345.tsx'
  );
  Workspace = mod.PayrollWorkspaceWeekly4345;
  assert.equal(typeof Workspace, 'function');

  weekly = {
    view: 'fictional_weekly_register_only',
    historicalRoleBindingVerified: false,
    managerAccessAuthorized: false,
    livePayrollAuthorized: false,
    rows: [{
      reference: 'TEST-A',
      recipient: 'Fictional Contractor A',
      category: 'contractor',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '1250.00',
      managerApproval: 'PENDING',
      comptrollerApproval: 'PENDING',
      scheduledDate: null,
      recordedStatus: 'DRAFT',
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: false,
    }, {
      reference: 'TEST-B',
      recipient: 'Fictional Contractor B',
      category: 'contractor',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '875.00',
      managerApproval: 'APPROVED',
      comptrollerApproval: 'PENDING',
      scheduledDate: '2026-11-11',
      recordedStatus: 'DRAFT',
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: true,
    }],
  };
});

after(async () => {
  if (vite) await vite.close();
});

function page(role = 'COMPTROLLER', data = weekly) {
  return renderToStaticMarkup(
    React.createElement(Workspace, { role, weeklyReport: data })
  );
}

test('approved My Payroll tab remains the initial view', () => {
  const html = page();
  assert.match(html, /aria-label="My Payroll"/);
  assert.match(html, /Your individual earnings/);
});

test('executive workspace preserves all six tabs', () => {
  const html = page();
  for (const name of [
    'My Payroll', 'Weekly Payroll', 'Approvals',
    'Payment History', 'Contractor Records', 'Reports',
  ]) {
    assert.ok(html.includes(name), name);
  }
});

test('weekly register is attached to Weekly Payroll branch', () => {
  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-workspace-weekly-4345.tsx'),
    'utf8'
  );
  const start = source.indexOf("activeTab === 'Weekly Payroll'");
  const end = source.indexOf("activeTab === 'Approvals'");
  assert.ok(start > 0 && end > start);
  assert.match(source.slice(start, end), /PayrollWeeklyRegister4344/);
});

test('weekly register data is not exposed on initial tab', () => {
  const html = page();
  assert.doesNotMatch(html, /Fictional Contractor A/);
  assert.doesNotMatch(html, /Review required/);
});

test('personal-only roles do not receive weekly tab', () => {
  for (const role of ['TECHNICIAN', 'SALES_ASSOCIATE']) {
    const html = page(role);
    assert.doesNotMatch(html, />Weekly Payroll</);
    assert.doesNotMatch(html, />Approvals</);
    assert.doesNotMatch(html, />Contractor Records</);
  }
});

test('manager preview does not show contractor records tab', () => {
  const html = page('SALES_MANAGER');
  assert.match(html, />Weekly Payroll</);
  assert.doesNotMatch(html, />Contractor Records</);
});

test('the new register maintains an empty-data fallback', () => {
  const html = page('COMPTROLLER', undefined);
  assert.match(html, /Your individual earnings/);
});

test('weekly register never grants manager authorization', () => {
  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-workspace-weekly-4345.tsx'),
    'utf8'
  );
  assert.match(source, /NOT backend authorization/);
  assert.doesNotMatch(source, /\bfetch\s*\(/);
});

test('existing approval view remains untouched in copy', () => {
  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-workspace-weekly-4345.tsx'),
    'utf8'
  );
  const start = source.indexOf("activeTab === 'Approvals'");
  const end = source.indexOf("activeTab === 'Payment History'");
  assert.match(source.slice(start, end), /<FictionalTable \/>/);
});

test('new workspace is absent from operational navigation', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollWorkspaceWeekly4345/);
  assert.doesNotMatch(urls, /payroll_workspace_weekly_4345/);
});