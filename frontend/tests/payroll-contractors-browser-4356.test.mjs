import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const dir = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(
  resolve(dir, 'payroll-contractors-browser-4356.html'), 'utf8'
);
const entry = readFileSync(
  resolve(dir, 'payroll-contractors-browser-4356.tsx'), 'utf8'
);
const workspace = readFileSync(
  resolve(dir, 'payroll-workspace-contractors-4355.tsx'), 'utf8'
);

test('preview uses isolated, nonindexable HTML', () => {
  assert.match(html, /payroll-integrated-review-root/);
  assert.match(html, /noindex,nofollow/);
});

test('HTML references only the 4356 React entry', () => {
  assert.match(html, /payroll-contractors-browser-4356\.tsx/);
  assert.doesNotMatch(html, /src\/main\.tsx/);
});

test('preview uses verified fifth-tab workspace', () => {
  assert.match(entry, /PayrollWorkspaceContractors4355/);
  assert.match(entry, /payroll-workspace-contractors-4355/);
});

test('earlier approved sections keep their fictional reports', () => {
  assert.match(entry, /report=\{fictionalData\}/);
  assert.match(entry, /weeklyReport=\{fictionalWeekly\}/);
  assert.match(entry, /approvalReport=\{fictionalApprovals\}/);
  assert.match(entry, /historyReport=\{fictionalHistory\}/);
});

test('original, return and pending engagements appear', () => {
  for (const id of [
    'TEST-CTR-A-01', 'TEST-CTR-A-R01', 'TEST-CTR-B-01',
  ]) assert.match(entry, new RegExp(id));
  assert.match(entry, /contractorReport=\{fictionalContractors\}/);
});

test('no contractor onboarding or payroll authority is activated', () => {
  assert.match(entry, /backendAccessVerified: false/);
  assert.match(entry, /onboardingAuthorityGranted: false/);
  assert.match(entry, /livePayrollAuthorized: false/);
});

test('contractor review belongs only to fifth tab', () => {
  const start = workspace.indexOf("activeTab === 'Contractor Records'");
  const end = workspace.indexOf("activeTab === 'Reports'");
  assert.ok(start > 0 && end > start);
  assert.match(workspace.slice(start, end), /PayrollContractorRecords4354/);
});

test('no operational page, payments or API calls enabled', () => {
  assert.doesNotMatch(entry, /\bfetch\s*\(|XMLHttpRequest|axios\./);
  const main = readFileSync(
    resolve(dir, '..', 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(dir, '..', '..', 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollWorkspaceContractors4355/);
  assert.doesNotMatch(main, /payroll-contractors-browser-4356/);
  assert.doesNotMatch(urls, /payroll_contractor_records_4354/);
});