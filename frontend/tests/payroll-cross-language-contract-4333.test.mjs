import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';

import {
  mapAuthorizedPersonalPayroll4332,
} from './payroll-personal-screen-mapper-4332.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const python = resolve(root, '.venv', 'Scripts', 'python.exe');
const script = resolve(
  root, 'backend', 'core', 'payroll_contract_fixture_4333.py'
);

function backend(caseName) {
  return spawnSync(python, [script, caseName], {
    cwd: root,
    encoding: 'utf8',
    timeout: 15000,
    env: {
      ...process.env,
      DJANGO_SETTINGS_MODULE: 'core.test_document_db_settings_4243',
      GECC_DEV: '1',
      VERIDIAN_ENVIRONMENT: 'development',
      VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED: 'False',
    },
  });
}

function successful(caseName = 'valid') {
  const result = backend(caseName);
  assert.equal(
    result.status, 0,
    'Synthetic backend formatter should succeed: ' + result.stderr
  );
  return JSON.parse(result.stdout);
}

function mapped(caseName = 'valid') {
  return mapAuthorizedPersonalPayroll4332(successful(caseName));
}

test('Python backend output is accepted by frontend mapper', () => {
  const result = mapped();
  assert.equal(result.view, 'my_payroll_test_only');
  assert.equal(result.employeeRecords.length, 1);
  assert.equal(result.contractorRecords.length, 1);
});

test('Python employee compensation maps to exact cents', () => {
  const result = mapped();
  assert.equal(result.employeeRecords[0].amountCents, 60000);
  assert.equal(result.employeeRecords[0].amount, '$600.00');
});

test('Python contractor compensation maps to exact cents', () => {
  const result = mapped();
  assert.equal(result.contractorRecords[0].amountCents, 125000);
  assert.equal(result.contractorRecords[0].amount, '$1,250.00');
});

test('Approved and paid remain distinct across both languages', () => {
  const result = mapped();
  assert.equal(
    result.employeeRecords[0].statusLabel,
    'Approved - Not Yet Paid'
  );
  assert.equal(result.contractorRecords[0].statusLabel, 'Paid');
  assert.equal(result.contractorRecords[0].actualPaidDate, null);
});

test('The pay period and date evidence remain unchanged', () => {
  const result = mapped();
  assert.equal(result.periodStart, '2026-11-02');
  assert.equal(result.periodEnd, '2026-11-08');
  assert.equal(result.contractorRecords[0].scheduledPaymentDate, null);
  assert.equal(result.contractorRecords[0].actualPaidDateVerified, false);
});

test('Backend and frontend both exclude private identifiers', () => {
  const backendReport = successful('private_fields');
  const result = mapAuthorizedPersonalPayroll4332(backendReport);
  assert.doesNotMatch(
    JSON.stringify(backendReport),
    /SECRET-DO-NOT-EXPOSE/
  );
  assert.doesNotMatch(
    JSON.stringify(result),
    /SECRET-DO-NOT-EXPOSE/
  );
});

test('Invalid Python financial evidence is rejected before mapping', () => {
  for (const scenario of [
    'bad_status',
    'bad_amount',
    'bad_date',
    'bad_view',
  ]) {
    const result = backend(scenario);
    assert.equal(result.status, 3, scenario);
    assert.equal(result.stdout.trim(), '', scenario);
  }
});

test('Neither side grants live financial actions or exposes a route', () => {
  const report = successful();
  assert.equal(report.live_payroll_authorized, false);
  assert.equal(report.payment_actions_authorized, false);

  const result = mapAuthorizedPersonalPayroll4332(report);
  assert.equal(result.livePayrollAuthorized, false);
  assert.equal(result.paymentActionsAvailable, false);
  assert.equal(result.exportsAvailable, false);

  const main = readFileSync(
    resolve(root, 'frontend', 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspacePreview4325/);
  assert.doesNotMatch(routes, /payroll_contract_fixture_4333/);
  assert.doesNotMatch(routes, /payroll_screen_adapter_4331/);
});