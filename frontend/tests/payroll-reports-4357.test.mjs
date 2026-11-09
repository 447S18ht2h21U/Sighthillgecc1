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
let Reports;

before(async () => {
  server = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: { noDiscovery: true, entries: [], include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });

  Reports = (await server.ssrLoadModule(
    '/tests/payroll-reports-4357.tsx'
  )).PayrollReports4357;

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
    rows: [{
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
    }, {
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
    }, {
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
    }],
  };
}

function render(data = fixture(), viewer = 'COMPTROLLER') {
  return renderToStaticMarkup(
    React.createElement(Reports, { report: data, viewer })
  );
}

test('approved obligations total exactly 1850 dollars', () => {
  const html = render();
  assert.match(html, /Approved obligations/);
  assert.match(html, /\$1,850\.00/);
});

test('independently verified paid total is zero', () => {
  const html = render();
  assert.match(
    html,
    /Independently verified paid<\/div><strong[^>]*>\$0\.00/
  );
});

test('recorded paid without evidence stays separately identified', () => {
  const html = render();
  assert.match(html, /Recorded paid, evidence pending/);
  assert.match(html, /\$1,250\.00/);
  assert.match(html, /Recorded as Paid - verification pending/);
});

test('approved obligations are not falsely reduced by recorded paid', () => {
  const html = render();
  assert.match(html, /Not verified as paid/);
  assert.match(html, /\$1,850\.00/);
});

test('draft negative adjustment is separate and excluded from totals', () => {
  const html = render();
  assert.match(html, /-\$50\.00/);
  assert.match(html, /Draft adjustment to TEST-CTR-B/);
  assert.match(html, /Separate draft adjustments/);
});

test('exceptions are visible and counted without enabling actions', () => {
  const html = render();
  assert.match(html, /Exception records/);
  assert.match(html, /Review required/);
  assert.doesNotMatch(html, /<form\b|type="submit"/);
});

test('missing Comptroller approval fails closed', () => {
  const data = fixture();
  data.rows[0].comptrollerApprovalRecorded = false;
  assert.throws(() => render(data));
});

test('unverified payment cannot claim verified paid status or date', () => {
  const data = fixture();
  data.rows[1].independentlyVerifiedPaid = true;
  assert.throws(() => render(data));

  const other = fixture();
  other.rows[1].independentlyVerifiedPaidDate = '2026-11-12';
  assert.throws(() => render(other));
});

test('invalid adjustment linkage fails closed', () => {
  const data = fixture();
  data.rows[2].adjustmentOf = 'TEST-MISSING';
  assert.throws(() => render(data));
});

test('private identity fields never appear in reporting output', () => {
  const data = fixture();
  data.rows[0].bankAccount = 'SECRET-BANK';
  data.rows[0].taxIdentifier = 'SECRET-TAX';
  const html = render(data);
  assert.doesNotMatch(html, /SECRET-BANK|SECRET-TAX/);
});

test('company-wide fictional totals are limited to CEO Comptroller', () => {
  assert.match(render(fixture(), 'CEO'), /Approved obligations/);
  assert.throws(() => render(fixture(), 'SALES_MANAGER'));
  assert.throws(() => render(fixture(), 'TECHNICIAN'));
});

test('no export, operational route or live authority can be activated', () => {
  const data = fixture();
  data.exportsAvailable = true;
  assert.throws(() => render(data));

  const other = fixture();
  other.backendScopeVerified = true;
  assert.throws(() => render(other));

  const html = render();
  assert.match(html, /PDF and Excel exports are disabled/);

  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollReports4357/);
  assert.doesNotMatch(routes, /payroll_reports_4357/);
});