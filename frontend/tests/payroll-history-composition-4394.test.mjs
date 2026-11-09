import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { build } from 'esbuild';

const require = createRequire(import.meta.url);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const compiled = await build({
  entryPoints: [resolve('tests/payroll-history-composition-4394.tsx')],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  packages: 'external',
  write: false,
  logLevel: 'silent',
});

const module = { exports: {} };
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(
  require, module, module.exports
);

const Composition = module.exports.PayrollHistoryComposition4394;

function fixture() {
  return {
    view: 'fictional_payment_history_only',
    backend_scope_verified: false,
    external_payment_evidence_verified: false,
    live_payment_authorized: false,
    payment_actions_authorized: false,
    rows: [{
      reference: 'TEST-HISTORY',
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
    }],
  };
}

function render(data) {
  return renderToStaticMarkup(
    React.createElement(Composition, { fictionalHistorySource: data })
  );
}

test('01 Payment History renders through translator', () => {
  const html = render(fixture());
  assert.match(html, /Fictional Contractor/);
  assert.match(html, /Recorded as Paid - not independently verified/);
});

test('02 issuance and settlement remain unverified', () => {
  const html = render(fixture());
  assert.match(html, /2026-11-11/);
  assert.match(html, /2026-11-12/);
  assert.match(html, /unverified/);
});

test('03 unsafe data is rejected before React rendering', () => {
  const data = fixture();
  data.rows[0].actual_paid_date = '2026-11-12';
  assert.throws(() => render(data));

  const elevated = fixture();
  elevated.live_payment_authorized = true;
  assert.throws(() => render(elevated));
});

test('04 payment actions and private fields remain absent', () => {
  const data = fixture();
  data.rows[0].bank_account = 'SECRET-DO-NOT-EXPOSE';
  const html = render(data);

  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /<button/i);
  assert.match(html, /No payment/);
});
