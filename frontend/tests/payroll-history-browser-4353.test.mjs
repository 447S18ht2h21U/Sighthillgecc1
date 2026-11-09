import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const dir = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(resolve(dir, 'payroll-history-browser-4353.html'), 'utf8');
const entry = readFileSync(resolve(dir, 'payroll-history-browser-4353.tsx'), 'utf8');
const workspace = readFileSync(resolve(dir, 'payroll-workspace-history-4352.tsx'), 'utf8');

test('Payment History preview is isolated and nonindexable', () => {
  assert.match(html, /payroll-integrated-review-root/);
  assert.match(html, /noindex,nofollow/);
});

test('HTML loads only the isolated history entry', () => {
  assert.match(html, /payroll-history-browser-4353\.tsx/);
  assert.doesNotMatch(html, /src\/main\.tsx/);
});

test('preview uses the verified Payment History workspace', () => {
  assert.match(entry, /PayrollWorkspaceHistory4352/);
  assert.match(entry, /payroll-workspace-history-4352/);
});

test('earlier fictional payroll tabs retain their data', () => {
  assert.match(entry, /report=\{fictionalData\}/);
  assert.match(entry, /weeklyReport=\{fictionalWeekly\}/);
  assert.match(entry, /approvalReport=\{fictionalApprovals\}/);
});

test('three fictional historical entries are available', () => {
  assert.match(entry, /TEST-PAY-A/);
  assert.match(entry, /TEST-PAY-B/);
  assert.match(entry, /TEST-ADJ-C/);
  assert.match(entry, /historyReport=\{fictionalHistory\}/);
});

test('historical actual paid dates remain unverified', () => {
  assert.match(entry, /externalPaymentEvidenceVerified: false/);
  assert.match(entry, /livePaymentAuthorized: false/);
  assert.match(entry, /actualPaidDateVerified: false/);
});

test('history renderer is inside Payment History tab only', () => {
  const start = workspace.indexOf("activeTab === 'Payment History'");
  const end = workspace.indexOf("activeTab === 'Contractor Records'");
  assert.ok(start > 0 && end > start);
  assert.match(workspace.slice(start, end), /PayrollPaymentHistory4351/);
});

test('no operational payment routes or actions are enabled', () => {
  assert.doesNotMatch(entry, /\bfetch\s*\(|XMLHttpRequest|axios\./);
  const main = readFileSync(resolve(dir, '..', 'src', 'main.tsx'), 'utf8');
  const urls = readFileSync(
    resolve(dir, '..', '..', 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollWorkspaceHistory4352/);
  assert.doesNotMatch(main, /payroll-history-browser-4353/);
  assert.doesNotMatch(urls, /payroll_payment_history_4351/);
});