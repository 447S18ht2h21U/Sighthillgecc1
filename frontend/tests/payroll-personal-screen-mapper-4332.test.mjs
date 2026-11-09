import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  mapAuthorizedPersonalPayroll4332 as map,
} from './payroll-personal-screen-mapper-4332.mjs';

function fixture() {
  return {
    view: 'my_payroll_test_only',
    period_start: '2026-11-02',
    period_end: '2026-11-08',
    amount_basis: 'full_obligation_not_prorated',
    manager_or_company_scope_authorized: false,
    payment_actions_authorized: false,
    actual_paid_date_verified: false,
    live_payroll_authorized: false,
    employee_records: [{
      compensation_type: 'employee',
      period_start: '2026-11-02',
      period_end: '2026-11-08',
      kind: 'BASE',
      amount: '600.00',
      status: 'APPROVED',
      status_label: 'Approved - Not Yet Paid',
      payment_evidence_status: 'NOT_ISSUED',
      scheduled_payment_date: null,
      actual_paid_date: null,
      actual_paid_date_verified: false,
    }],
    contractor_records: [{
      compensation_type: 'contractor',
      period_start: '2026-11-02',
      period_end: '2026-11-08',
      kind: 'COMMISSION',
      amount: '1250.00',
      status: 'PAID',
      status_label: 'Paid',
      payment_evidence_status: 'TEST_EVIDENCE',
      scheduled_payment_date: null,
      actual_paid_date: null,
      actual_paid_date_verified: false,
    }],
  };
}

test('authorized employee amount maps exactly', () => {
  const result = map(fixture());
  assert.equal(result.employeeRecords[0].amount, '$600.00');
  assert.equal(result.employeeRecords[0].amountCents, 60000);
});

test('contractor amount maps exactly', () => {
  const result = map(fixture());
  assert.equal(result.contractorRecords[0].amount, '$1,250.00');
  assert.equal(result.contractorRecords[0].amountCents, 125000);
});

test('approved and paid statuses remain distinct', () => {
  const result = map(fixture());
  assert.equal(
    result.employeeRecords[0].statusLabel,
    'Approved - Not Yet Paid'
  );
  assert.equal(result.contractorRecords[0].statusLabel, 'Paid');
});

test('paid status does not invent an actual paid date', () => {
  const record = map(fixture()).contractorRecords[0];
  assert.equal(record.actualPaidDate, null);
  assert.equal(record.actualPaidDateVerified, false);
});

test('sensitive and unexpected fields never reach the screen', () => {
  const report = fixture();
  report.bank_account = 'SECRET-DO-NOT-EXPOSE';
  report.contractor_records[0].tax_identifier =
    'SECRET-DO-NOT-EXPOSE';
  report.employee_records[0].peer_name =
    'SECRET-DO-NOT-EXPOSE';

  const result = map(report);
  assert.doesNotMatch(JSON.stringify(result), /SECRET-DO-NOT-EXPOSE/);
});

test('unknown or draft status fails closed', () => {
  for (const status of ['DRAFT', 'PENDING', 'UNKNOWN', null]) {
    const report = fixture();
    report.employee_records[0].status = status;
    assert.throws(() => map(report), TypeError);
  }
});

test('contradictory status labels fail closed', () => {
  const report = fixture();
  report.employee_records[0].status_label = 'Paid';
  assert.throws(() => map(report), TypeError);
});

test('invalid money and unsafe amounts fail closed', () => {
  for (const amount of [
    '-1.00', '1.234', 'NaN', '1,000.00',
    100, '90071992547410.00',
  ]) {
    const report = fixture();
    report.employee_records[0].amount = amount;
    assert.throws(() => map(report), TypeError);
  }
});

test('bad dates and nonoverlapping periods fail closed', () => {
  for (const end of ['2026-02-30', '11/08/2026', '2026-10-01']) {
    const report = fixture();
    report.employee_records[0].period_end = end;
    assert.throws(() => map(report), TypeError);
  }
});

test('privileged scope claims and wrong views fail closed', () => {
  for (const [key, value] of [
    ['view', 'company_payroll'],
    ['manager_or_company_scope_authorized', true],
    ['payment_actions_authorized', true],
    ['live_payroll_authorized', true],
  ]) {
    const report = fixture();
    report[key] = value;
    assert.throws(() => map(report), TypeError);
  }
});

test('unverified payment dates and claims fail closed', () => {
  const report = fixture();
  report.contractor_records[0].actual_paid_date = '2026-11-12';
  assert.throws(() => map(report), TypeError);

  const second = fixture();
  second.contractor_records[0].actual_paid_date_verified = true;
  assert.throws(() => map(second), TypeError);
});

test('mapping is read-only and provides no operational actions', () => {
  const report = fixture();
  const before = JSON.stringify(report);
  const result = map(report);
  assert.equal(JSON.stringify(report), before);
  assert.equal(result.livePayrollAuthorized, false);
  assert.equal(result.paymentActionsAvailable, false);
  assert.equal(result.exportsAvailable, false);
  assert.ok(Object.isFrozen(result));
  assert.ok(Object.isFrozen(result.contractorRecords));

  const source = readFileSync(
    new URL('./payroll-personal-screen-mapper-4332.mjs', import.meta.url),
    'utf8'
  );
  assert.doesNotMatch(source, /\bfetch\s*\(/);
  assert.doesNotMatch(source, /\bapi\s*\(/);
});