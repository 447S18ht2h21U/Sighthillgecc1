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
let History;

before(async () => {
  vite = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: { noDiscovery: true, entries: [], include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  const mod = await vite.ssrLoadModule(
    '/tests/payroll-payment-history-4351.tsx'
  );
  History = mod.PayrollPaymentHistory4351;
  assert.equal(typeof History, 'function');
});

after(async () => {
  if (vite) await vite.close();
});

function fixture() {
  const base = {
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
  return base;
}

function render(report = fixture()) {
  return renderToStaticMarkup(
    React.createElement(History, { report })
  );
}

test('all fictional history amounts display correctly', () => {
  const html = render();
  assert.match(html, /\$600\.00/);
  assert.match(html, /\$1,250\.00/);
  assert.match(html, /-\$50\.00/);
});

test('earning and period dates remain separate', () => {
  const html = render();
  assert.match(html, /Compensation date/);
  assert.match(html, /Payroll period/);
  assert.match(html, /2026-11-06/);
});

test('proposed schedule does not imply authorization', () => {
  const html = render();
  assert.match(html, /Proposed: 2026-11-11/);
  assert.doesNotMatch(html, /Scheduled: 2026-11-11/);
});

test('approved unpaid remains distinct from recorded paid', () => {
  const html = render();
  assert.match(html, /Approved - Not Yet Paid/);
  assert.match(html, /Recorded as Paid - not independently verified/);
});

test('issuance and settlement candidate are not actual payment', () => {
  const html = render();
  assert.match(html, /2026-11-11 \(recorded\)/);
  assert.match(html, /2026-11-12 \(unverified\)/);
  assert.match(html, /Not independently established/);
});

test('method and reference are displayed as fictional metadata', () => {
  const html = render();
  assert.match(html, /ACH \/ TEST-REF-B/);
  assert.doesNotMatch(html, /bank_account|tax_identifier/);
});

test('adjustment remains separate from original obligation', () => {
  const html = render();
  assert.match(html, /Separate adjustment to TEST-PAY-B/);
  assert.match(html, /-\$50\.00/);
});

test('invented verified paid date fails closed', () => {
  const data = fixture();
  data.rows[1].actualPaidDate = '2026-11-12';
  assert.throws(() => render(data));
});

test('invalid issued evidence and unknown method fail closed', () => {
  const a = fixture();
  a.rows[0].method = 'ACH';
  assert.throws(() => render(a));
  const b = fixture();
  b.rows[1].method = 'WIRE';
  assert.throws(() => render(b));
});

test('negative normal compensation and invalid adjustment fail', () => {
  const a = fixture();
  a.rows[0].amount = '-100.00';
  assert.throws(() => render(a));
  const b = fixture();
  b.rows[2].adjustmentOf = null;
  assert.throws(() => render(b));
});

test('external evidence and live authority claims fail closed', () => {
  const a = fixture();
  a.externalPaymentEvidenceVerified = true;
  assert.throws(() => render(a));
  const b = fixture();
  b.livePaymentAuthorized = true;
  assert.throws(() => render(b));
});

test('isolated history has no operational actions or routes', () => {
  const html = render();
  assert.match(html, /data-test-only="true"/);
  assert.doesNotMatch(html, /<form\b/);
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollPaymentHistory4351/);
  assert.doesNotMatch(routes, /payroll_payment_history_4351/);
});