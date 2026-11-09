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
    resolve('tests/payroll-reports-boundary-4402.ts'),
    resolve('tests/payroll-reports-4357.tsx'),
  ],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  packages: 'external',
  write: false,
  outdir: 'isolated-reports-4404',
  logLevel: 'silent',
});

function load(filename) {
  const file = compiled.outputFiles.find(
    item => item.path.endsWith(filename)
  );
  assert.ok(file, 'Missing compiled entry: ' + filename);
  const module = { exports: {} };
  new Function('require', 'module', 'exports', file.text)(
    require, module, module.exports
  );
  return module.exports;
}

const map = load('payroll-reports-boundary-4402.js')
  .mapFictionalPayrollReports4402;
const Reports = load('payroll-reports-4357.js')
  .PayrollReports4357;

const pythonScript = `
import json
import os
import sys

sys.path.insert(0, os.environ["VERIDIAN_BACKEND_CORE"])
from payroll_reports_screen_4403 import (
    format_fictional_payroll_reports_4403
)

def row(ref, name, amount, status="APPROVED"):
    return {
        "reference": ref,
        "recipient": name,
        "category": "contractor",
        "kind": "COMPENSATION",
        "adjustment_of": None,
        "amount": amount,
        "recorded_status": status,
        "first_approval_recorded": True,
        "comptroller_approval_recorded": True,
        "audit_recorded": True,
        "independently_verified_paid_date": None,
        "independently_verified_paid": False,
        "exception": False,
    }

source = {
    "view": "fictional_company_payroll_report_only",
    "period_start": "2026-11-02",
    "period_end": "2026-11-08",
    "backend_scope_verified": False,
    "external_payment_evidence_verified": False,
    "exports_available": False,
    "live_payroll_authorized": False,
    "rows": [
        row("TEST-COMP-A", "Fictional Contractor Alpha",
            "1250.00", "PAID_RECORDED"),
        row("TEST-COMP-B", "Fictional Contractor Beta",
            "600.00"),
        {
            **row("TEST-ADJUST-A", "Fictional Contractor Alpha",
                  "-50.00", "DRAFT"),
            "kind": "ADJUSTMENT",
            "adjustment_of": "TEST-COMP-A",
            "first_approval_recorded": False,
            "comptroller_approval_recorded": False,
            "audit_recorded": False,
            "exception": True,
        },
    ],
    "bank_account": "SECRET-DO-NOT-EXPOSE",
}

print(json.dumps(
    format_fictional_payroll_reports_4403(source),
    separators=(",", ":")
))
`;

const executed = spawnSync(
  process.env.VERIDIAN_PYTHON,
  ['-c', pythonScript],
  {
    encoding: 'utf8',
    env: process.env,
    timeout: 30000,
  }
);

assert.equal(
  executed.status, 0,
  'Python formatting failed: ' + executed.stderr
);

const pythonOutput = JSON.parse(executed.stdout);

function render(payload, viewer = 'CEO') {
  return renderToStaticMarkup(
    React.createElement(Reports, {
      report: map(payload),
      viewer,
    })
  );
}

test('01 actual Python output renders approved React report', () => {
  const html = render(pythonOutput);
  assert.match(html, /Fictional Contractor Alpha/);
  assert.match(html, /Fictional Contractor Beta/);
  assert.match(html, /1,850\.00/);
});

test('02 recorded paid and draft adjustment stay separate', () => {
  const report = map(pythonOutput);
  assert.equal(report.rows.length, 3);
  assert.equal(report.rows[0].recordedStatus, 'PAID_RECORDED');
  assert.equal(report.rows[0].independentlyVerifiedPaid, false);
  assert.equal(report.rows[0].independentlyVerifiedPaidDate, null);
  assert.equal(report.rows[2].kind, 'ADJUSTMENT');
  assert.equal(report.rows[2].adjustmentOf, 'TEST-COMP-A');
  assert.equal(report.rows[2].recordedStatus, 'DRAFT');
  assert.equal(report.rows[2].amount, '-50.00');

  const html = render(pythonOutput);
  assert.match(html, /1,850\.00/);
  assert.match(html, /Not independently verified/i);
});

test('03 scope, privacy, and export controls fail closed', () => {
  const report = map(pythonOutput);
  const html = render(pythonOutput);

  assert.doesNotMatch(JSON.stringify(report), /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.equal(report.backendScopeVerified, false);
  assert.equal(report.exportsAvailable, false);
  assert.equal(report.livePayrollAuthorized, false);

  const elevated = structuredClone(pythonOutput);
  elevated.exports_available = true;
  assert.throws(() => render(elevated));

  const paid = structuredClone(pythonOutput);
  paid.rows[0].independently_verified_paid = true;
  assert.throws(() => render(paid));

  assert.throws(() => render(pythonOutput, 'TECHNICIAN'));
});
