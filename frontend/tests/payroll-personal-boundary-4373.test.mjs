import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createServer } from 'vite';

const dir = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(dir, '..');
const require = createRequire(resolve(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

let vite;
let map;
let grantsLiveAccess;
let PersonalView;

before(async () => {
  vite = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: { noDiscovery: true, entries: [], include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });

  const boundary = await vite.ssrLoadModule(
    '/tests/payroll-personal-boundary-4373.ts'
  );
  const view = await vite.ssrLoadModule(
    '/tests/payroll-personal-records-4341.tsx'
  );

  map = boundary.mapAuthorizedPersonalPayroll4373;
  grantsLiveAccess = boundary.personalBoundaryGrantsLiveAccess4373;
  PersonalView = view.PayrollPersonalRecords4341;
});

after(async () => {
  if (vite) await vite.close();
});

function row(type = 'employee') {
  return {
    compensation_type: type,
    period_start: '2026-10-05',
    period_end: '2026-10-11',
    kind: 'Approved compensation',
    amount: '125.00',
    status: 'APPROVED',
    status_label: 'Approved - Not Yet Paid',
    payment_evidence_status: 'NOT_ISSUED',
    scheduled_payment_date: null,
    actual_paid_date: null,
    actual_paid_date_verified: false,
  };
}

function payload() {
  return {
    view: 'my_payroll_test_only',
    amount_basis: 'full_obligation_not_prorated',
    period_start: '2026-10-01',
    period_end: '2026-10-31',
    employee_records: [row()],
    contractor_records: [row('contractor')],
    manager_or_company_scope_authorized: false,
    payment_actions_authorized: false,
    actual_paid_date_verified: false,
    live_payroll_authorized: false,
  };
}

test('Python snake-case fields map to React camel-case', () => {
  const result = map(payload());
  assert.equal(result.periodStart, '2026-10-01');
  assert.equal(result.employeeRecords[0].periodStart, '2026-10-05');
  assert.equal(result.contractorRecords[0].compensationType, 'contractor');
});

test('exact cents and status meaning are preserved', () => {
  const result = map(payload());
  assert.equal(result.employeeRecords[0].amount, '125.00');
  assert.equal(
    result.employeeRecords[0].statusLabel,
    'Approved - Not Yet Paid'
  );
});

test('private source keys are removed by allowlist', () => {
  const source = payload();
  source.employee_records[0].social_security_number = 'NEVER DISPLAY';
  source.employee_records[0].record_id = 'PRIVATE-IDENTIFIER';
  source.private_payroll_notes = 'SECRET NOTES';

  const output = JSON.stringify(map(source));
  assert.doesNotMatch(output, /NEVER DISPLAY|PRIVATE-IDENTIFIER|SECRET NOTES/);
  assert.deepEqual(
    Object.keys(map(source).employeeRecords[0]).sort(),
    [
      'actualPaidDate', 'actualPaidDateVerified', 'amount',
      'compensationKind', 'compensationType', 'paymentEvidenceStatus',
      'periodEnd', 'periodStart', 'scheduledPaymentDate',
      'status', 'statusLabel',
    ].sort()
  );
});

test('backend manager or payment authority claims fail closed', () => {
  for (const name of [
    'manager_or_company_scope_authorized',
    'payment_actions_authorized',
    'actual_paid_date_verified',
    'live_payroll_authorized',
  ]) {
    const source = payload();
    source[name] = true;
    assert.throws(() => map(source), name);
  }
});

test('drafts and false paid labels fail closed', () => {
  const source = payload();
  source.employee_records[0].status = 'DRAFT';
  assert.throws(() => map(source));

  source.employee_records[0].status = 'PAID';
  assert.throws(() => map(source));

  source.employee_records[0].status_label = 'Paid';
  assert.equal(map(source).employeeRecords[0].status, 'PAID');
});

test('unverified payment dates are never accepted', () => {
  for (const field of [
    'scheduled_payment_date',
    'actual_paid_date',
    'actual_paid_date_verified',
  ]) {
    const source = payload();
    source.employee_records[0][field] =
      field === 'actual_paid_date_verified' ? true : '2026-10-14';
    assert.throws(() => map(source), field);
  }
});

test('invalid money, dates, and record types are rejected', () => {
  for (const invalid of ['125', '125.1', '-1.00', '1e5', '01.00']) {
    const source = payload();
    source.employee_records[0].amount = invalid;
    assert.throws(() => map(source), invalid);
  }

  const badDate = payload();
  badDate.employee_records[0].period_start = '2026-02-30';
  assert.throws(() => map(badDate));

  const wrongType = payload();
  wrongType.employee_records[0].compensation_type = 'contractor';
  assert.throws(() => map(wrongType));
});

test('empty reports preserve strict disabled capabilities', () => {
  const source = payload();
  source.employee_records = [];
  source.contractor_records = [];
  const result = map(source);

  assert.equal(result.paymentActionsAvailable, false);
  assert.equal(result.exportsAvailable, false);
  assert.equal(result.livePayrollAuthorized, false);
  assert.equal(result.employeeRecords.length, 0);
});

test('mapped payroll renders in approved My Payroll component', () => {
  const result = map(payload());
  const html = renderToStaticMarkup(
    React.createElement(PersonalView, { report: result })
  );

  assert.match(html, /125\.00/);
  assert.match(html, /Approved - Not Yet Paid/);
  assert.match(html, /Not independently established/);
  assert.doesNotMatch(html, /NEVER DISPLAY|SECRET NOTES/);
});

test('translator is pure and never grants live access', () => {
  assert.equal(grantsLiveAccess(), false);

  const source = readFileSync(
    resolve(dir, 'payroll-personal-boundary-4373.ts'), 'utf8'
  );
  assert.doesNotMatch(source, /\bfetch\s*\(|axios\.|XMLHttpRequest/);
  assert.doesNotMatch(source, /approvePayment\(|issuePayment\(/);
});

test('operational routes and approved layout remain separate', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(frontend, '..', 'backend', 'config', 'urls.py'), 'utf8'
  );
  const workspace = readFileSync(
    resolve(dir, 'payroll-workspace-aligned-4366.tsx'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollPersonalBoundary4373|payroll-personal-boundary-4373/);
  assert.doesNotMatch(routes, /payroll-personal-boundary-4373/);
  assert.match(workspace, /marginLeft: 'auto'/);
  assert.match(workspace, /Return to Customers &amp; Projects/);
});