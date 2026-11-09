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
let History;

before(async () => {
  server = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: { noDiscovery: true, entries: [], include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });

  Workspace = (await server.ssrLoadModule(
    '/tests/payroll-workspace-history-4352.tsx'
  )).PayrollWorkspaceHistory4352;

  History = (await server.ssrLoadModule(
    '/tests/payroll-payment-history-4351.tsx'
  )).PayrollPaymentHistory4351;

  assert.equal(typeof Workspace, 'function');
  assert.equal(typeof History, 'function');
});

after(async () => {
  if (server) await server.close();
});

function fixture() {
  return {
    view: 'fictional_payment_history_only',
    backendScopeVerified: false,
    externalPaymentEvidenceVerified: false,
    livePaymentAuthorized: false,
    rows: [{
      reference: 'TEST-PAY-A',
      recipient: 'Fictional Employee A',
      category: 'employee',
      kind: 'COMPENSATION',
      adjustmentOf: null,
      compensationDate: '2026-11-06',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '600.00',
      recordedStatus: 'APPROVED',
      proposedPaymentDate: '2026-11-11',
      issuedDate: null,
      settlementCandidateDate: null,
      method: null,
      paymentReference: null,
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: false,
    }, {
      reference: 'TEST-PAY-B',
      recipient: 'Fictional Contractor B',
      category: 'contractor',
      kind: 'COMPENSATION',
      adjustmentOf: null,
      compensationDate: '2026-11-05',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '1250.00',
      recordedStatus: 'PAID',
      proposedPaymentDate: '2026-11-11',
      issuedDate: '2026-11-11',
      settlementCandidateDate: '2026-11-12',
      method: 'ACH',
      paymentReference: 'TEST-REF-B',
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: true,
    }, {
      reference: 'TEST-ADJ-C',
      recipient: 'Fictional Contractor B',
      category: 'contractor',
      kind: 'ADJUSTMENT',
      adjustmentOf: 'TEST-PAY-B',
      compensationDate: '2026-11-05',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '-50.00',
      recordedStatus: 'DRAFT',
      proposedPaymentDate: null,
      issuedDate: null,
      settlementCandidateDate: null,
      method: null,
      paymentReference: null,
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: true,
    }],
  };
}

function page(role = 'COMPTROLLER', data = fixture()) {
  return renderToStaticMarkup(
    React.createElement(Workspace, { role, historyReport: data })
  );
}

function historyPage(data = fixture()) {
  return renderToStaticMarkup(
    React.createElement(History, { report: data })
  );
}

test('initial tab remains My Payroll', () => {
  assert.match(page(), /aria-label="My Payroll"/);
});

test('all six approved tabs remain present', () => {
  const html = page();
  for (const name of [
    'My Payroll', 'Weekly Payroll', 'Approvals',
    'Payment History', 'Contractor Records', 'Reports',
  ]) assert.ok(html.includes(name), name);
});

test('Payment History renderer is within the correct tab', () => {
  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-workspace-history-4352.tsx'),
    'utf8'
  );
  const start = source.indexOf("activeTab === 'Payment History'");
  const end = source.indexOf("activeTab === 'Contractor Records'");
  assert.ok(start > 0 && end > start);
  assert.match(source.slice(start, end), /PayrollPaymentHistory4351/);
});

test('initial tab does not leak historical recipient records', () => {
  assert.doesNotMatch(page(), /Fictional Employee A/);
  assert.doesNotMatch(page(), /TEST-REF-B/);
});

test('personal roles retain Payment History tab only', () => {
  for (const role of ['TECHNICIAN', 'SALES_ASSOCIATE']) {
    const html = page(role);
    assert.match(html, />Payment History</);
    assert.doesNotMatch(html, />Weekly Payroll</);
    assert.doesNotMatch(html, />Approvals</);
  }
});

test('compensation amounts and adjustment remain separate', () => {
  const html = historyPage();
  assert.match(html, /\$600\.00/);
  assert.match(html, /\$1,250\.00/);
  assert.match(html, /-\$50\.00/);
  assert.match(html, /Separate adjustment to TEST-PAY-B/);
});

test('recorded issuance is not verified actual payment', () => {
  const html = historyPage();
  assert.match(html, /2026-11-11 \(recorded\)/);
  assert.match(html, /2026-11-12 \(unverified\)/);
  assert.match(html, /Not independently established/);
});

test('invented verified payment dates are rejected', () => {
  const data = fixture();
  data.rows[1].actualPaidDate = '2026-11-12';
  assert.throws(() => historyPage(data));
});

test('unauthorized scope and live payment flags are rejected', () => {
  const data = fixture();
  data.backendScopeVerified = true;
  assert.throws(() => historyPage(data));
  const second = fixture();
  second.livePaymentAuthorized = true;
  assert.throws(() => historyPage(second));
});

test('new component is unregistered and action-free', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollWorkspaceHistory4352/);
  assert.doesNotMatch(urls, /payroll_payment_history_4351/);
  assert.doesNotMatch(historyPage(), /<form\b/);
});