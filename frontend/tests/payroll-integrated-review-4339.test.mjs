import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import {
  mapAuthorizedPersonalPayroll4332 as map,
} from './payroll-personal-screen-mapper-4332.mjs';

const dir = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(
  resolve(dir, 'payroll-integrated-review-4339.html'), 'utf8'
);
const entry = readFileSync(
  resolve(dir, 'payroll-integrated-review-4339.tsx'), 'utf8'
);
const data = JSON.parse(readFileSync(
  resolve(dir, 'payroll-synthetic-report-4339.json'), 'utf8'
));

test('integrated browser page uses an isolated root', () => {
  assert.match(html, /payroll-integrated-review-root/);
  assert.match(html, /noindex,nofollow/);
});

test('page imports only its isolated React entry', () => {
  assert.match(html, /payroll-integrated-review-4339\.tsx/);
  assert.doesNotMatch(html, /src\/main\.tsx/);
});

test('preview imports the protected integrated tab component', () => {
  assert.match(entry, /PayrollWorkspaceTab4338/);
  assert.match(entry, /payroll-workspace-tab-4338/);
});

test('fixture is synthetic and requires nonoperational flags', () => {
  const result = map(data);
  assert.equal(result.livePayrollAuthorized, false);
  assert.equal(result.paymentActionsAvailable, false);
  assert.equal(result.exportsAvailable, false);
});

test('Python fixture retains correct personal-payroll amounts', () => {
  const result = map(data);
  assert.equal(result.employeeRecords[0].amount, '$600.00');
  assert.equal(result.contractorRecords[0].amount, '$1,250.00');
});

test('the role switcher is clearly only a fictional preview', () => {
  assert.match(entry, /Fictional position/);
  assert.match(entry, /cannot grant permissions/);
  assert.match(entry, /COMPTROLLER/);
  assert.match(entry, /TECHNICIAN/);
});

test('the page performs no payroll requests or actions', () => {
  assert.doesNotMatch(entry, /\bfetch\s*\(/);
  assert.doesNotMatch(entry, /XMLHttpRequest|axios\./);
  assert.doesNotMatch(entry, /approvePayment|issuePayment/);
});

test('preview remains outside operational navigation and APIs', () => {
  const main = readFileSync(
    resolve(dir, '..', 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(dir, '..', '..', 'backend', 'config', 'urls.py'),
    'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceTab4338/);
  assert.doesNotMatch(main, /payroll-integrated-review-4339/);
  assert.doesNotMatch(urls, /payroll-integrated-review-4339/);
});