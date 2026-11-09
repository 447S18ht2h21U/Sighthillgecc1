import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { build } from 'esbuild';

const require = createRequire(import.meta.url);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const compiled = await build({
  entryPoints: [
    resolve('tests/payroll-history-boundary-4393.ts'),
    resolve('tests/payroll-payment-history-4351.tsx'),
  ],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  packages: 'external',
  write: false,
  outdir: 'isolated-history-test-output',
  logLevel: 'silent',
});

function load(index) {
  const module = { exports: {} };
  new Function(
    'require', 'module', 'exports',
    compiled.outputFiles[index].text
  )(require, module, module.exports);
  return module.exports;
}

const boundaryFile = compiled.outputFiles.find(
  file => file.path.endsWith('payroll-history-boundary-4393.js')
);
const componentFile = compiled.outputFiles.find(
  file => file.path.endsWith('payroll-payment-history-4351.js')
);

assert.ok(boundaryFile && componentFile);

function loadFile(file) {
  const module = { exports: {} };
  new Function(
    'require', 'module', 'exports', file.text
  )(require, module, module.exports);
  return module.exports;
}

const boundary = loadFile(boundaryFile);
const component = loadFile(componentFile);
const map = boundary.mapFictionalPaymentHistory4393;

function fixture() {
  return {
    view: 'fictional_payment_history_only',
    backend_scope_verified: false,
    external_payment_evidence_verified: false,
    live_payment_authorized: false,
    payment_actions_authorized: false,
    rows: [
      {
        reference: 'TEST-ORIGINAL',
        recipient: 'Fictional Contractor',
        category: 'contractor',
        kind: 'COMPENSATION',
        adjustment_of: null,
        compensation_date: '2026-11-02',
        period_start: '2026-11-02',
        period_end: '2026-11-08',
        amount: '1250.00',
        recorded_status: 'PAID',
        proposed_payment_date: '2026-11-11',
        issued_date: '2026-11-11',
        settlement_candidate_date: '2026-11-12',
        method: 'ACH',
        payment_reference: 'TEST-ACH',
        actual_paid_date: null,
        actual_paid_date_verified: false,
        exception: false,
        bank_account: 'SECRET-DO-NOT-EXPOSE',
      },
      {
        reference: 'TEST-ADJUST',
        recipient: 'Fictional Contractor',
        category: 'contractor',
        kind: 'ADJUSTMENT',
        adjustment_of: 'TEST-ORIGINAL',
        compensation_date: '2026-11-05',
        period_start: '2026-11-02',
        period_end: '2026-11-08',
        amount: '-50.00',
        recorded_status: 'APPROVED',
        proposed_payment_date: null,
        issued_date: null,
        settlement_candidate_date: null,
        method: null,
        payment_reference: null,
        actual_paid_date: null,
        actual_paid_date_verified: false,
        exception: true,
      },
    ],
  };
}

function render(data) {
  const report = map(data);
  return renderToStaticMarkup(
    React.createElement(component.PayrollPaymentHistory4351, {
      report,
    })
  );
}

test('01 snake_case records render in approved history', () => {
  const html = render(fixture());
  assert.match(html, /Fictional Contractor/);
  assert.match(html, /Recorded as Paid - not independently verified/);
  assert.match(html, /Approved - Not Yet Paid/);
});

test('02 exact amounts and separate adjustments survive', () => {
  const result = map(fixture());
  assert.equal(result.rows[0].amount, '1250.00');
  assert.equal(result.rows[1].amount, '-50.00');
  assert.equal(result.rows[1].adjustmentOf, 'TEST-ORIGINAL');
  assert.equal(result.rows[0].compensationDate, '2026-11-02');
});

test('03 issuance and settlement never become actual payment', () => {
  const result = map(fixture());
  assert.equal(result.rows[0].issuedDate, '2026-11-11');
  assert.equal(
    result.rows[0].settlementCandidateDate, '2026-11-12'
  );
  assert.equal(result.rows[0].actualPaidDate, null);
  assert.equal(result.externalPaymentEvidenceVerified, false);
});

test('04 unsafe dates, scope and adjustments fail closed', () => {
  const clone = () => structuredClone(fixture());

  const date = clone();
  date.rows[0].actual_paid_date = '2026-11-12';
  assert.throws(() => map(date));

  const scope = clone();
  scope.backend_scope_verified = true;
  assert.throws(() => map(scope));

  const issuance = clone();
  issuance.rows[0].method = null;
  assert.throws(() => map(issuance));

  const adjustment = clone();
  adjustment.rows[1].adjustment_of = 'TEST-ADJUST';
  assert.throws(() => map(adjustment));
});

test('05 private fields and live capabilities remain excluded', () => {
  const data = fixture();
  data.company_total = 'SECRET-DO-NOT-EXPOSE';
  const result = map(data);
  const html = render(data);

  assert.doesNotMatch(JSON.stringify(result), /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /<button/i);
  assert.equal(result.livePaymentAuthorized, false);
  assert.equal(boundary.historyBoundaryGrantsLiveAccess4393(), false);
});
