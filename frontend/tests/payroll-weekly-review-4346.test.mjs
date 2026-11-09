import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const dir = dirname(fileURLToPath(import.meta.url));

const html = readFileSync(
  resolve(dir, 'payroll-weekly-review-4346.html'), 'utf8'
);
const entry = readFileSync(
  resolve(dir, 'payroll-weekly-review-4346.tsx'), 'utf8'
);
const workspace = readFileSync(
  resolve(dir, 'payroll-workspace-weekly-4345.tsx'), 'utf8'
);

test('combined review uses a separate browser root', () => {
  assert.match(html, /payroll-integrated-review-root/);
  assert.match(html, /noindex,nofollow/);
});

test('HTML loads only the isolated 4346 entry', () => {
  assert.match(html, /payroll-weekly-review-4346\.tsx/);
  assert.doesNotMatch(html, /src\/main\.tsx/);
});

test('browser uses the verified combined workspace', () => {
  assert.match(entry, /PayrollWorkspaceWeekly4345/);
  assert.match(entry, /payroll-workspace-weekly-4345/);
});

test('personal and weekly records are both supplied', () => {
  assert.match(entry, /report=\{fictionalData\}/);
  assert.match(entry, /weeklyReport=\{fictionalWeekly\}/);
});

test('both weekly payment amounts are fictional', () => {
  assert.match(entry, /Fictional Contractor A/);
  assert.match(entry, /Fictional Contractor B/);
  assert.match(entry, /amount: '1250\.00'/);
  assert.match(entry, /amount: '875\.00'/);
});

test('weekly authorization remains explicitly disabled', () => {
  assert.match(entry, /historicalRoleBindingVerified: false/);
  assert.match(entry, /managerAccessAuthorized: false/);
  assert.match(entry, /livePayrollAuthorized: false/);
});

test('the weekly register is only within its own tab', () => {
  const weeklyStart = workspace.indexOf(
    "activeTab === 'Weekly Payroll'"
  );
  const approvalsStart = workspace.indexOf(
    "activeTab === 'Approvals'"
  );
  assert.ok(weeklyStart > 0 && approvalsStart > weeklyStart);
  assert.match(
    workspace.slice(weeklyStart, approvalsStart),
    /PayrollWeeklyRegister4344/
  );
});

test('no browser financial actions or live registration', () => {
  assert.doesNotMatch(entry, /\bfetch\s*\(|XMLHttpRequest|axios\./);
  assert.doesNotMatch(entry, /approvePayment|issuePayment/);

  const main = readFileSync(
    resolve(dir, '..', 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(dir, '..', '..', 'backend', 'config', 'urls.py'),
    'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceWeekly4345/);
  assert.doesNotMatch(main, /payroll-weekly-review-4346/);
  assert.doesNotMatch(routes, /payroll_weekly_register_4344/);
});