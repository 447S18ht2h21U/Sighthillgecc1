import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const dir = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(
  resolve(dir, 'payroll-reports-browser-4359.html'), 'utf8'
);
const entry = readFileSync(
  resolve(dir, 'payroll-reports-browser-4359.tsx'), 'utf8'
);
const workspace = readFileSync(
  resolve(dir, 'payroll-workspace-reports-4358.tsx'), 'utf8'
);

test('final browser preview remains isolated and nonindexable', () => {
  assert.match(html, /payroll-integrated-review-root/);
  assert.match(html, /noindex,nofollow/);
});

test('HTML loads only the new test-only React entry', () => {
  assert.match(html, /payroll-reports-browser-4359\.tsx/);
  assert.doesNotMatch(html, /src\/main\.tsx/);
});

test('preview uses the verified six-tab workspace', () => {
  assert.match(entry, /PayrollWorkspaceReports4358/);
  assert.match(entry, /payroll-workspace-reports-4358/);
});

test('all previous fictional payroll reports remain connected', () => {
  for (const prop of [
    'report={fictionalData}',
    'weeklyReport={fictionalWeekly}',
    'approvalReport={fictionalApprovals}',
    'historyReport={fictionalHistory}',
    'contractorReport={fictionalContractors}',
  ]) assert.ok(entry.includes(prop), prop);
});

test('company report uses fictional approved and paid examples', () => {
  assert.match(entry, /companyReport=\{fictionalReports\}/);
  assert.match(entry, /amount: '600\.00'/);
  assert.match(entry, /amount: '1250\.00'/);
  assert.match(entry, /amount: '-50\.00'/);
});

test('verified paid evidence and financial exports remain disabled', () => {
  assert.match(entry, /externalPaymentEvidenceVerified: false/);
  assert.match(entry, /exportsAvailable: false/);
  assert.match(entry, /livePayrollAuthorized: false/);
});

test('Reports component is connected only in its own tab', () => {
  const start = workspace.indexOf("activeTab === 'Reports'");
  assert.ok(start > 0);
  assert.match(workspace.slice(start), /PayrollReports4357/);
  assert.match(
    workspace.slice(start),
    /companyReport && MANAGEMENT\.includes\(role\)/
  );
});

test('no operational APIs, payment actions or exports are enabled', () => {
  assert.doesNotMatch(entry, /\bfetch\s*\(|XMLHttpRequest|axios\./);
  assert.doesNotMatch(entry, /approvePayment|issuePayment/);

  const main = readFileSync(
    resolve(dir, '..', 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(dir, '..', '..', 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceReports4358/);
  assert.doesNotMatch(main, /payroll-reports-browser-4359/);
  assert.doesNotMatch(urls, /payroll_reports_4357/);
});