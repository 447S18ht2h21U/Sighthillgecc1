import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { build } from 'esbuild';

const require = createRequire(import.meta.url);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const compiled = await build({
  entryPoints: [
    resolve('tests/payroll-history-composition-4394.tsx')
  ],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  packages: 'external',
  write: false,
  logLevel: 'silent',
});

const loaded = { exports: {} };
new Function(
  'require', 'module', 'exports',
  compiled.outputFiles[0].text
)(require, loaded, loaded.exports);

const Composition = loaded.exports.PayrollHistoryComposition4394;
assert.equal(typeof Composition, 'function');

const pythonSource = `
import json
import os
import sys

sys.path.insert(0, os.environ["VERIDIAN_BACKEND_CORE"])

from payroll_history_screen_4395 import (
    format_fictional_payment_history_4395,
)

source = {
    "view": "fictional_payment_history_only",
    "backend_scope_verified": False,
    "external_payment_evidence_verified": False,
    "live_payment_authorized": False,
    "payment_actions_authorized": False,
    "company_total": "SECRET-DO-NOT-EXPOSE",
    "rows": [
        {
            "reference": "TEST-ORIGINAL",
            "recipient": "Fictional Contractor",
            "category": "contractor",
            "kind": "COMPENSATION",
            "adjustment_of": None,
            "compensation_date": "2026-11-02",
            "period_start": "2026-11-02",
            "period_end": "2026-11-08",
            "amount": "1250.00",
            "recorded_status": "PAID",
            "proposed_payment_date": "2026-11-11",
            "issued_date": "2026-11-11",
            "settlement_candidate_date": "2026-11-12",
            "method": "ACH",
            "payment_reference": "TEST-ACH",
            "actual_paid_date": None,
            "actual_paid_date_verified": False,
            "exception": False,
            "bank_account": "SECRET-DO-NOT-EXPOSE",
        },
        {
            "reference": "TEST-ADJUSTMENT",
            "recipient": "Fictional Contractor",
            "category": "contractor",
            "kind": "ADJUSTMENT",
            "adjustment_of": "TEST-ORIGINAL",
            "compensation_date": "2026-11-05",
            "period_start": "2026-11-02",
            "period_end": "2026-11-08",
            "amount": "-50.00",
            "recorded_status": "APPROVED",
            "proposed_payment_date": None,
            "issued_date": None,
            "settlement_candidate_date": None,
            "method": None,
            "payment_reference": None,
            "actual_paid_date": None,
            "actual_paid_date_verified": False,
            "exception": True,
        },
    ],
}

result = format_fictional_payment_history_4395(source)
print(json.dumps(result, separators=(",", ":")))
`;

const execution = spawnSync(
  process.env.VERIDIAN_PYTHON,
  ['-c', pythonSource],
  {
    encoding: 'utf8',
    env: { ...process.env },
    timeout: 30000,
  },
);

assert.equal(
  execution.status,
  0,
  'Python formatter failed: ' + execution.stderr
);

const pythonOutput = JSON.parse(execution.stdout);

function render(source) {
  return renderToStaticMarkup(
    React.createElement(Composition, {
      fictionalHistorySource: source,
    })
  );
}

test('01 actual Python output renders in React', () => {
  const html = render(pythonOutput);
  assert.match(html, /Fictional Contractor/);
  assert.match(
    html,
    /Recorded as Paid - not independently verified/
  );
  assert.match(html, /Approved - Not Yet Paid/);
});

test('02 amounts and adjustments survive both languages', () => {
  assert.equal(pythonOutput.rows.length, 2);
  assert.equal(pythonOutput.rows[0].amount, '1250.00');
  assert.equal(pythonOutput.rows[1].amount, '-50.00');
  assert.equal(
    pythonOutput.rows[1].adjustment_of,
    'TEST-ORIGINAL'
  );
  assert.match(render(pythonOutput), /Separate adjustment/);
});

test('03 unsafe payment claims fail before rendering', () => {
  const clone = () => structuredClone(pythonOutput);

  const paid = clone();
  paid.rows[0].actual_paid_date = '2026-11-12';
  assert.throws(() => render(paid));

  const scope = clone();
  scope.backend_scope_verified = true;
  assert.throws(() => render(scope));

  const issuance = clone();
  issuance.rows[0].payment_reference = null;
  assert.throws(() => render(issuance));

  const adjustment = clone();
  adjustment.rows[1].adjustment_of = 'TEST-ADJUSTMENT';
  assert.throws(() => render(adjustment));
});

test('04 privacy and payment controls remain disabled', () => {
  const html = render(pythonOutput);

  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /bank_account/);
  assert.doesNotMatch(html, /company_total/);
  assert.doesNotMatch(html, /<button/i);
  assert.match(html, /No payment/);

  assert.equal(pythonOutput.live_payment_authorized, false);
  assert.equal(
    pythonOutput.external_payment_evidence_verified,
    false
  );
  assert.equal(pythonOutput.payment_actions_authorized, false);
});
