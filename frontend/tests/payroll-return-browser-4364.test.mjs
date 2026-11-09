import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const dir = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(dir, '..');

const html = readFileSync(
  resolve(dir, 'payroll-return-browser-4364.html'), 'utf8'
);
const entry = readFileSync(
  resolve(dir, 'payroll-return-browser-4364.tsx'), 'utf8'
);
const wrapper = readFileSync(
  resolve(dir, 'payroll-return-navigation-4363.tsx'), 'utf8'
);

test('new preview has an isolated React root', () => {
  assert.match(html, /payroll-integrated-review-root/);
});

test('new preview loads only its test-only React entry', () => {
  assert.match(html, /payroll-return-browser-4364\.tsx/);
  assert.doesNotMatch(html, /src\/main\.tsx/);
});

test('approved six-tab payroll workspace uses return wrapper', () => {
  assert.match(entry, /PayrollReturnNavigation4363/);
  assert.match(wrapper, /PayrollWorkspaceReports4358/);
});

test('all fictional payroll fixture connections remain intact', () => {
  for (const prop of [
    'report={fictionalData}',
    'weeklyReport={fictionalWeekly}',
    'approvalReport={fictionalApprovals}',
    'historyReport={fictionalHistory}',
    'contractorReport={fictionalContractors}',
    'companyReport={fictionalReports}',
  ]) {
    assert.ok(entry.includes(prop), prop);
  }
});

test('the callback switches to a fictional destination', () => {
  assert.match(entry, /onReturnToProjects/);
  assert.match(entry, /payrollRoot\.hidden = true/);
  assert.match(entry, /destination\.hidden = false/);
  assert.match(html, /id="payroll-projects-destination-4364"/);
});

test('return action is a button, never logout or payment', () => {
  assert.match(wrapper, /type="button"/);
  assert.match(wrapper, /Return to Customers &amp; Projects/);
  assert.doesNotMatch(wrapper, /\bfetch\s*\(|approvePayment|issuePayment/);
});

test('preview return does not navigate to the live application', () => {
  assert.doesNotMatch(entry, /window\.location|location\.href|fetch\(/);
  assert.match(html, /fictional destination/);
});

test('existing operational registration remains unchanged', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(frontend, '..', 'backend', 'config', 'urls.py'),
    'utf8'
  );

  assert.doesNotMatch(main, /PayrollReturnNavigation4363/);
  assert.doesNotMatch(main, /payroll-return-browser-4364/);
  assert.doesNotMatch(urls, /payroll-return-browser-4364/);
  assert.match(main, /setPanel\('projects'\)/);
});