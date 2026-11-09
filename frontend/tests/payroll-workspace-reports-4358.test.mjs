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

let server;
let Workspace;
let Reports;

before(async () => {
  server = await createServer({
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

  Workspace = (await server.ssrLoadModule(
    '/tests/payroll-workspace-reports-4358.tsx'
  )).PayrollWorkspaceReports4358;

  Reports = (await server.ssrLoadModule(
    '/tests/payroll-reports-4357.tsx'
  )).PayrollReports4357;

  assert.equal(typeof Workspace, 'function');
  assert.equal(typeof Reports, 'function');
});

after(async () => {
  if (server) await server.close();
});

function fixture() {
  return {
    view: 'fictional_company_payroll_report_only',
    periodStart: '2026-11-02',
    periodEnd: '2026-11-08',
    backendScopeVerified: false,
    externalPaymentEvidenceVerified: false,
    exportsAvailable: false,
    livePayrollAuthorized: false,
    rows: [
      {
        reference: 'TEST-EMP-A',
        recipient: 'Fictional Employee A',
        category: 'employee',
        kind: 'COMPENSATION',
        adjustmentOf: null,
        amount: '600.00',
        recordedStatus: 'APPROVED',
        firstApprovalRecorded: true,
        comptrollerApprovalRecorded: true,
        auditRecorded: true,
        independentlyVerifiedPaidDate: null,
        independentlyVerifiedPaid: false,
        exception: false,
      },
      {
        reference: 'TEST-CTR-B',
        recipient: 'Fictional Contractor B',
        category: 'contractor',
        kind: 'COMPENSATION',
        adjustmentOf: null,
        amount: '1250.00',
        recordedStatus: 'PAID_RECORDED',
        firstApprovalRecorded: true,
        comptrollerApprovalRecorded: true,
        auditRecorded: true,
        independentlyVerifiedPaidDate: null,
        independentlyVerifiedPaid: false,
        exception: true,
      },
      {
        reference: 'TEST-ADJ-B',
        recipient: 'Fictional Contractor B',
        category: 'contractor',
        kind: 'ADJUSTMENT',
        adjustmentOf: 'TEST-CTR-B',
        amount: '-50.00',
        recordedStatus: 'DRAFT',
        firstApprovalRecorded: false,
        comptrollerApprovalRecorded: false,
        auditRecorded: false,
        independentlyVerifiedPaidDate: null,
        independentlyVerifiedPaid: false,
        exception: true,
      },
    ],
  };
}

function workspacePage(role = 'COMPTROLLER', companyReport = fixture()) {
  return renderToStaticMarkup(
    React.createElement(Workspace, { role, companyReport })
  );
}

function reportPage(report = fixture(), viewer = 'COMPTROLLER') {
  return renderToStaticMarkup(
    React.createElement(Reports, { report, viewer })
  );
}

test('initial tab remains the approved My Payroll view', () => {
  assert.match(workspacePage(), /aria-label="My Payroll"/);
});

test('all six approved tabs remain in the workspace', () => {
  const html = workspacePage();
  for (const tab of [
    'My Payroll', 'Weekly Payroll', 'Approvals',
    'Payment History', 'Contractor Records', 'Reports',
  ]) {
    assert.ok(html.includes(tab), tab);
  }
});

test('company Reports component is inside Reports branch', () => {
  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-workspace-reports-4358.tsx'),
    'utf8'
  );
  const start = source.indexOf("activeTab === 'Reports'");
  assert.ok(start > 0);
  assert.match(
    source.slice(start),
    /companyReport && MANAGEMENT\.includes\(role\)/
  );
  assert.match(
    source.slice(start),
    /PayrollReports4357/
  );
});

test('fictional company records never leak into initial tab', () => {
  const html = workspacePage();
  assert.doesNotMatch(html, /Fictional Employee A/);
  assert.doesNotMatch(html, /TEST-ADJ-B/);
});

test('personal roles retain Reports tab without company figures', () => {
  for (const role of ['TECHNICIAN', 'SALES_ASSOCIATE']) {
    const html = workspacePage(role);
    assert.match(html, />Reports</);
    assert.doesNotMatch(html, />Weekly Payroll</);
    assert.doesNotMatch(html, />Contractor Records</);
    assert.doesNotMatch(html, /Fictional Employee A/);
  }
});

test('management company totals are fictional and exact', () => {
  const html = reportPage();
  assert.match(html, /Approved obligations/);
  assert.match(html, /\$1,850\.00/);
});

test('recorded paid does not increase verified paid totals', () => {
  const html = reportPage();
  assert.match(html, /Recorded paid, evidence pending/);
  assert.match(html, /Independently verified paid/);
  assert.match(html, /\$0\.00/);
});

test('draft adjustments remain separate from approved totals', () => {
  const html = reportPage();
  assert.match(html, /-\$50\.00/);
  assert.match(html, /Draft adjustment to TEST-CTR-B/);
});

test('unauthorized company report viewer fails closed', () => {
  assert.throws(() => reportPage(fixture(), 'SALES_MANAGER'));
  assert.throws(() => reportPage(fixture(), 'TECHNICIAN'));
});

test('workspace remains test-only with no exports or live routes', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceReports4358/);
  assert.doesNotMatch(urls, /payroll_reports_4357/);
  assert.doesNotMatch(reportPage(), /<form\b/);
  assert.match(reportPage(), /PDF and Excel exports are disabled/);
});