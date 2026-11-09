import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const dir = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(
  resolve(dir, 'payroll-approvals-browser-4350.html'), 'utf8'
);
const entry = readFileSync(
  resolve(dir, 'payroll-approvals-browser-4350.tsx'), 'utf8'
);
const workspace = readFileSync(
  resolve(dir, 'payroll-workspace-approvals-4349.tsx'), 'utf8'
);

test('approvals preview uses isolated nonindexable HTML', () => {
  assert.match(html, /payroll-integrated-review-root/);
  assert.match(html, /noindex,nofollow/);
});

test('HTML loads the test-only Approvals entry', () => {
  assert.match(html, /payroll-approvals-browser-4350\.tsx/);
  assert.doesNotMatch(html, /src\/main\.tsx/);
});

test('preview reuses the isolated Approvals workspace', () => {
  assert.match(entry, /PayrollWorkspaceApprovals4349/);
  assert.match(entry, /payroll-workspace-approvals-4349/);
});

test('personal and weekly reports remain connected in preview', () => {
  assert.match(entry, /report=\{fictionalData\}/);
  assert.match(entry, /weeklyReport=\{fictionalWeekly\}/);
});

test('all three fictional approval stages are provided', () => {
  assert.match(entry, /WAITING_MANAGER/);
  assert.match(entry, /WAITING_COMPTROLLER/);
  assert.match(entry, /stage: 'APPROVED'/);
  assert.match(entry, /approvalReport=\{fictionalApprovals\}/);
});

test('approval authority is explicitly disabled', () => {
  assert.match(entry, /managerAuthorityVerified: false/);
  assert.match(entry, /comptrollerAuthorityVerified: false/);
  assert.match(entry, /liveApprovalAuthorized: false/);
});

test('approval review appears only inside Approvals branch', () => {
  const start = workspace.indexOf("activeTab === 'Approvals'");
  const end = workspace.indexOf("activeTab === 'Payment History'");
  assert.ok(start > 0 && end > start);
  assert.match(workspace.slice(start, end), /PayrollApprovalsReview4349/);
});

test('preview has no operational payment or approval route', () => {
  assert.doesNotMatch(entry, /\bfetch\s*\(|XMLHttpRequest|axios\./);
  assert.doesNotMatch(entry, /approvePayment|issuePayment/);

  const main = readFileSync(
    resolve(dir, '..', 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(dir, '..', '..', 'backend', 'config', 'urls.py'),
    'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceApprovals4349/);
  assert.doesNotMatch(main, /payroll-approvals-browser-4350/);
  assert.doesNotMatch(routes, /payroll_approvals_review_4349/);
});