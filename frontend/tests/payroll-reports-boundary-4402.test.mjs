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
    resolve('tests/payroll-reports-boundary-4402.ts'),
    resolve('tests/payroll-reports-4357.tsx'),
  ],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  packages: 'external',
  write: false,
  outdir: 'isolated-payroll-report-4402',
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

const boundary = load('payroll-reports-boundary-4402.js');
const screen = load('payroll-reports-4357.js');
const map = boundary.mapFictionalPayrollReports4402;

function original(overrides = {}) {
  return {
    reference: 'TEST-COMP-A',
    recipient: 'Fictional Contractor Alpha',
    category: 'contractor',
    kind: 'COMPENSATION',
    adjustment_of: null,
    amount: '1250.00',
    recorded_status: 'PAID_RECORDED',
    first_approval_recorded: true,
    comptroller_approval_recorded: true,
    audit_recorded: true,
    independently_verified_paid_date: null,
    independently_verified_paid: false,
    exception: false,
    ...overrides,
  };
}

function fixture() {
  return {
    view: 'fictional_company_payroll_report_only',
    period_start: '2026-11-02',
    period_end: '2026-11-08',
    backend_scope_verified: false,
    external_payment_evidence_verified: false,
    exports_available: false,
    live_payroll_authorized: false,
    rows: [
      original(),
      original({
        reference: 'TEST-COMP-B',
        recipient: 'Fictional Employee Beta',
        category: 'employee',
        amount: '600.00',
        recorded_status: 'APPROVED',
      }),
      original({
        reference: 'TEST-ADJUST-A',
        kind: 'ADJUSTMENT',
        adjustment_of: 'TEST-COMP-A',
        amount: '-50.00',
        recorded_status: 'DRAFT',
        first_approval_recorded: false,
        comptroller_approval_recorded: false,
        audit_recorded: false,
        exception: true,
      }),
    ],
  };
}

function render(data, viewer = 'CEO') {
  return renderToStaticMarkup(
    React.createElement(screen.PayrollReports4357, {
      report: map(data),
      viewer,
    })
  );
}

test('01 fictional report translates and renders', () => {
  const result = map(fixture());
  assert.equal(result.rows.length, 3);
  const html = render(fixture());
  assert.match(html, /Fictional Contractor Alpha/);
  assert.match(html, /Fictional Employee Beta/);
});

test('02 exact obligations do not count draft adjustments', () => {
  const html = render(fixture());
  assert.match(html, /1,850\.00/);
  assert.equal(map(fixture()).rows[2].amount, '-50.00');
  assert.equal(map(fixture()).rows[2].recordedStatus, 'DRAFT');
});

test('03 recorded payment never becomes verified payment', () => {
  const result = map(fixture());
  assert.equal(result.externalPaymentEvidenceVerified, false);
  assert.equal(
    result.rows[0].independentlyVerifiedPaidDate, null
  );
  assert.equal(result.rows[0].independentlyVerifiedPaid, false);
  const data = fixture();
  data.rows[0].independently_verified_paid = true;
  assert.throws(() => map(data));
});

test('04 report period, approval and adjustment failures', () => {
  const invalidPeriod = fixture();
  invalidPeriod.period_start = '2026-11-03';
  assert.throws(() => map(invalidPeriod));

  const missingApproval = fixture();
  missingApproval.rows[0].comptroller_approval_recorded = false;
  assert.throws(() => map(missingApproval));

  const invalidAdjustment = fixture();
  invalidAdjustment.rows[2].adjustment_of = 'TEST-MISSING';
  assert.throws(() => map(invalidAdjustment));

  const duplicate = fixture();
  duplicate.rows.push(original());
  assert.throws(() => map(duplicate));
});

test('05 private data, export and scope restrictions', () => {
  const data = fixture();
  data.rows[0].bank_account = 'SECRET-DO-NOT-EXPOSE';
  data.tax_identifier = 'SECRET-DO-NOT-EXPOSE';

  const result = map(data);
  const html = render(data);

  assert.doesNotMatch(
    JSON.stringify(result), /SECRET-DO-NOT-EXPOSE/
  );
  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.equal(result.exportsAvailable, false);
  assert.equal(result.backendScopeVerified, false);
  assert.equal(result.livePayrollAuthorized, false);
  assert.equal(boundary.payrollReportsBoundaryGrantsAccess4402(), false);

  const exportClaim = fixture();
  exportClaim.exports_available = true;
  assert.throws(() => map(exportClaim));

  assert.throws(() => render(fixture(), 'TECHNICIAN'));
});
