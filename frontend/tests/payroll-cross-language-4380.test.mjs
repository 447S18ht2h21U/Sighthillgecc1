import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { transform } from 'esbuild';

const dir = dirname(fileURLToPath(import.meta.url));

const source = await readFile(
  resolve(dir, 'payroll-personal-boundary-4373.ts'),
  'utf8',
);

const compiled = await transform(source, {
  loader: 'ts',
  format: 'esm',
  target: 'es2022',
});

const boundary = await import(
  'data:text/javascript;base64,' +
  Buffer.from(compiled.code).toString('base64')
);

const map = boundary.mapAuthorizedPersonalPayroll4373;

const pythonSource = `
import os
import sys
import json

sys.path.insert(0, os.environ["VERIDIAN_BACKEND"])
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from core.payroll_screen_adapter_4331 import (
    format_authorized_personal_screen_candidate,
)

synthetic = {
    "view": "my_compensation",
    "period_start": "2026-11-02",
    "period_end": "2026-11-08",
    "amount_basis": "full_obligation_not_prorated",
    "employee_records": [{
        "period_start": "2026-11-02",
        "period_end": "2026-11-08",
        "compensation_type": "employee",
        "kind": "BASE",
        "amount": "600.00",
        "status": "APPROVED",
        "status_label": "Approved - Not Yet Paid",
        "payment_evidence_status": "NOT_ISSUED",
        "scheduled_payment_date": None,
        "actual_paid_date": None,
        "bank_account": "SECRET-DO-NOT-EXPOSE",
    }],
    "contractor_records": [{
        "period_start": "2026-11-02",
        "period_end": "2026-11-08",
        "compensation_type": "contractor",
        "kind": "COMMISSION",
        "amount": "1250.00",
        "status": "PAID",
        "status_label": "Paid",
        "payment_evidence_status": "TEST_EVIDENCE",
        "scheduled_payment_date": None,
        "actual_paid_date": None,
        "tax_identifier": "SECRET-DO-NOT-EXPOSE",
    }],
    "account_number": "SECRET-DO-NOT-EXPOSE",
}

result = format_authorized_personal_screen_candidate(synthetic)
print(json.dumps(result, separators=(",", ":")))
`;

const run = spawnSync(
  process.env.VERIDIAN_PYTHON,
  ['-c', pythonSource],
  {
    encoding: 'utf8',
    env: {
      ...process.env,
      VERIDIAN_BACKEND: process.env.VERIDIAN_BACKEND,
    },
    timeout: 30000,
  },
);

assert.equal(
  run.status,
  0,
  'Isolated Django formatter failed: ' + run.stderr,
);

const djangoOutput = JSON.parse(run.stdout);

test('01 actual Django output maps to React', () => {
  const result = map(djangoOutput);
  assert.equal(result.view, 'my_payroll_test_only');
  assert.equal(result.employeeRecords.length, 1);
  assert.equal(result.contractorRecords.length, 1);
});

test('02 exact amounts and status meanings survive', () => {
  const result = map(djangoOutput);
  assert.equal(result.employeeRecords[0].amount, '600.00');
  assert.equal(result.contractorRecords[0].amount, '1250.00');
  assert.equal(
    result.employeeRecords[0].statusLabel,
    'Approved - Not Yet Paid',
  );
  assert.equal(result.contractorRecords[0].statusLabel, 'Paid');
});

test('03 private data and unverified dates stay hidden', () => {
  const result = map(djangoOutput);
  const text = JSON.stringify(result);
  assert.equal(text.includes('SECRET-DO-NOT-EXPOSE'), false);
  assert.equal(text.includes('bank_account'), false);
  assert.equal(text.includes('tax_identifier'), false);
  assert.equal(result.employeeRecords[0].actualPaidDate, null);
  assert.equal(result.contractorRecords[0].actualPaidDate, null);
  assert.equal(result.livePayrollAuthorized, false);
  assert.equal(result.paymentActionsAvailable, false);
  assert.equal(result.exportsAvailable, false);
});

test('04 elevated scope and unsafe payment evidence fail closed', () => {
  const clone = () => structuredClone(djangoOutput);

  const elevated = clone();
  elevated.manager_or_company_scope_authorized = true;
  assert.throws(() => map(elevated));

  const payment = clone();
  payment.payment_actions_authorized = true;
  assert.throws(() => map(payment));

  const date = clone();
  date.contractor_records[0].actual_paid_date = '2026-11-12';
  assert.throws(() => map(date));

  const draft = clone();
  draft.employee_records[0].status = 'DRAFT';
  assert.throws(() => map(draft));
});
