import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const dir = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(resolve(dir, 'payroll-weekly-refined-review-4348.html'), 'utf8');
const entry = readFileSync(resolve(dir, 'payroll-weekly-refined-review-4348.tsx'), 'utf8');
const workspace = readFileSync(resolve(dir, 'payroll-workspace-weekly-4347.tsx'), 'utf8');
const register = readFileSync(resolve(dir, 'payroll-weekly-register-4347.tsx'), 'utf8');

test('browser page is isolated and nonindexable', () => {
  assert.match(html, /payroll-integrated-review-root/);
  assert.match(html, /noindex,nofollow/);
});

test('HTML loads only the new preview entry', () => {
  assert.match(html, /payroll-weekly-refined-review-4348\.tsx/);
  assert.doesNotMatch(html, /src\/main\.tsx/);
});

test('browser uses the refined weekly workspace', () => {
  assert.match(entry, /PayrollWorkspaceWeekly4347/);
  assert.match(entry, /payroll-workspace-weekly-4347/);
  assert.match(entry, /weeklyReport=\{fictionalWeekly\}/);
});

test('the refined register appears in Weekly Payroll', () => {
  const start = workspace.indexOf("activeTab === 'Weekly Payroll'");
  const end = workspace.indexOf("activeTab === 'Approvals'");
  assert.ok(start > 0 && end > start);
  assert.match(workspace.slice(start, end), /PayrollWeeklyRegister4347/);
});

test('wide table and horizontal scrolling remain present', () => {
  assert.match(register, /minWidth: 1450/);
  assert.match(register, /overflowX: 'auto'/);
  assert.match(register, /whiteSpace: 'nowrap'/);
});

test('proposed date and approved schedule are distinct', () => {
  assert.match(register, /Proposed:/);
  assert.match(register, /Scheduled:/);
  assert.match(register, /comptrollerApproval === 'APPROVED'/);
});

test('all simulated payroll roles remain selectable', () => {
  assert.match(entry, /COMPTROLLER/);
  assert.match(entry, /SALES_ASSOCIATE/);
  assert.match(entry, /TECHNICIAN/);
  assert.match(entry, /cannot grant permissions/);
});

test('no operational route or payment endpoint is enabled', () => {
  const main = readFileSync(resolve(dir, '..', 'src', 'main.tsx'), 'utf8');
  const urls = readFileSync(resolve(dir, '..', '..', 'backend', 'config', 'urls.py'), 'utf8');
  assert.doesNotMatch(main, /PayrollWorkspaceWeekly4347/);
  assert.doesNotMatch(main, /payroll-weekly-refined-review-4348/);
  assert.doesNotMatch(urls, /payroll_weekly_register_4347/);
  assert.doesNotMatch(entry, /\bfetch\s*\(|XMLHttpRequest|axios\./);
});